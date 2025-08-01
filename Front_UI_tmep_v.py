from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import binary_fill_holes
import os
from totalsegmentator.python_api import totalsegmentator
import glob
import pydicom
from rt_utils.rtstruct import RTStruct
from tkinterdnd2 import DND_FILES, TkinterDnD 
import time


'''
좌클릭 -> 추가 mask생성
우클릭 -> ct사진 이동
d + 좌클릭 -> editing중인 roi mask제거
마우스휠 -> 슬라이스넘기기
ctrl + 우클릭 -> ct크기조절
'''

class ScrollableFrame(ttk.Frame):
    """스크롤 가능한 Tkinter 프레임을 만드는 클래스"""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(
                scrollregion=canvas.bbox("all")
            )
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)


class MaskEditor:
    def __init__(self, task_names):
        # hu변환할때 필요한 변수들
        self.center_val = None
        self.width_val = None
        self.slope = None
        self.intercept = None

        self.ct_volume = None # dicom의 넘파이배열버전(x,y,z)
        self.dicom_folder = None # 원본 dicom폴더 경로
        self.d2_slices = None # dicom의 넘파이배열버전(x,y,z) -> dicom_to_np이 함수에서만 사용됨


        self.task_names = task_names

        self.masks_dict = {} # class별로 mask를 boolean형태로(3차원, x,y,z)
        self.isSemented = {} # 해당 task가 이미 분할한건지 boolean
        self.segmented_class_names = [] # 분할완료된 class이름들

        # # --- 상태 변수 ---
        self.current_slice_idx = None
        self.brush_size = 1
        self.drawing = False
        self.erasing = False # 지우기 상태 변수 추가
        self.d_key_pressed = False # 'd' 키 상태 변수 추가
        self.temp_line_mask = None

        # --- 줌 & 팬 상태 변수 ---
        self.zoom_level = 1.0
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.canvas_img_x = 0
        self.canvas_img_y = 0

        # --- 색상 설정 ---
        self.colors = None
        self.root = TkinterDnD.Tk()
        self.root.title("Mask Editor (Tkinter) - Drag & Drop a DICOM folder")
        self.root.geometry("1000x800")

        # --- 상태 변수 (Tkinter용) ---
        self.editing_roi_name = tk.StringVar(value=False)  # Editing ROI 의 string 초기값 할당
        self.segment_check_vars = {name: tk.BooleanVar(value=False) for name in self.task_names}
        self.check_vars = {name: tk.BooleanVar(value=False) for name in self.segmented_class_names} # 체크박스의 선택/해제 상태와 연동되는 set변수
        self.active_rois = {} # 화면에 표시되고 있는 roi 리스트 저장하는 set
        self.segmented = {} # segmentation된 task 저장하는 seg

        # --- UI 레이아웃 생성 ---
        self._setup_ui()

        # --- 드래그 앤 드롭 이벤트 바인딩 ---
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self._on_drop)


        self.root.mainloop()
        self._update_plot()


    def _on_drop(self, event):
        """폴더를 드래그 앤 드롭했을 때 호출되는 이벤트 핸들러"""
        folder_path = event.data.strip('{}')
        print(f"Folder dropped: {folder_path}")

        # 폴더 유효성 확인
        # if not os.path.isdir(folder_path):
        #     self.status_label.config(text=f"Error: Not a valid folder: {folder_path}")
        #     return

        self.dicom_folder = folder_path
        self.status_label.config(text=f"Loading DICOM files from: {self.dicom_folder}")
        self.root.title(f"Mask Editor - {self.dicom_folder}")

        try:
            print("Loading DICOM data...") 
            self.dicom_to_np(self.dicom_folder) # dicom파일을 넘파이배열로 변환하고 정규화
            print("DICOM data loaded.")
        except Exception as e:
            self.status_label.config(text=f"Failed to load DICOM data: {e}")
            return
            
        self.masks_dict = {}
        self.isSemented = {task_name: False for task_name in self.task_names}
        self.segmented_class_names = [] # 초기화

        # --- 상태 변수 ---
        self.current_slice_idx = self.ct_volume.shape[2] // 2
        self.brush_size = 1
        self.drawing = False
        self.erasing = False
        self.d_key_pressed = False
        self.temp_line_mask = np.zeros(self.ct_volume.shape[:2], dtype=bool)

        # --- 줌 & 팬 상태 변수 ---
        self.zoom_level = 1.0
        self.pan_start_x, self.pan_start_y = 0, 0
        self.canvas_img_x, self.canvas_img_y = 0, 0

        # --- 색상 및 UI 변수 재설정 ---
        self.editing_roi_name = tk.StringVar(value=False)
        self.segment_check_vars = {name: tk.BooleanVar(value=False) for name in self.task_names}
        self.check_vars = {name: tk.BooleanVar(value=False) for name in self.segmented_class_names}
        self.active_rois = {}
        self.segmented = {}
        
        # --- UI 업데이트 ---
        self._populate_segmen_rois(self.task_names)
        self._populate_visible_rois_list(self.segmented_class_names)
        self._populate_editing_rois_list(self.segmented_class_names)

        self._update_plot()
        self.status_label.config(text="DICOM data loaded successfully. Ready to edit.")


    def _normalize_to_uint8(self, data, central_val ,width_val):
        window_center = central_val
        window_width = width_val
        min_val = window_center - window_width / 2
        max_val = window_center + window_width / 2
        
        data = np.clip(data, min_val, max_val)
        data = (data - min_val) / (max_val - min_val) * 255
        return data.astype(np.uint8)
    
    def _setup_ui(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_frame, width=300) # roi고르는 창 너비 300pixel
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5) # 세로는 꽉 차게
        left_frame.pack_propagate(False)

        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_rowconfigure(2, weight=1)
        left_frame.grid_columnconfigure(0, weight=1) # 열도 꽉 차게 설정
        
        # 오른쪽 ct나오는 화면
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True) # 남은 공간 모두차지 

         # segmetation task선택부분
        check_container_task = ttk.LabelFrame(left_frame, text="task")
        check_container_task.grid(row=0, column=0, pady=5, sticky="nsew")
        
        ## 'Visible ROIs' 그룹 안에 검색창(Entry)을 만들어주는 부분
        self.visible_search_entry1 = ttk.Entry(check_container_task)
        self.visible_search_entry1.pack(fill=tk.X, padx=5, pady=(5,0))
        self.visible_search_entry1.bind("<KeyRelease>", self._filter_segment_rois) # 키보드 클릭시 마다  _filter_visible_rois함수로 필터링 수행
        # 스크롤 만들어 주는 부분
        self.visible_scroll_frame1 = ScrollableFrame(check_container_task)
        self.visible_scroll_frame1.pack(fill=tk.BOTH, expand=True)
        # 스크롤 안에 roi_names채워넣는 부분
        self._populate_segmen_rois(self.task_names)

        
        # visible roi부분
        check_container_visible = ttk.LabelFrame(left_frame, text="Visible ROIs")
        check_container_visible.grid(row=1, column=0, pady=5, sticky="nsew")
        
        ## 'Visible ROIs' 그룹 안에 검색창(Entry)을 만들어주는 부분
        self.visible_search_entry = ttk.Entry(check_container_visible)
        self.visible_search_entry.pack(fill=tk.X, padx=5, pady=(5,0))
        self.visible_search_entry.bind("<KeyRelease>", self._filter_visible_rois) # 키보드 클릭시 마다  _filter_visible_rois함수로 필터링 수행
        # 스크롤 만들어 주는 부분
        self.visible_scroll_frame = ScrollableFrame(check_container_visible)
        self.visible_scroll_frame.pack(fill=tk.BOTH, expand=True)
        # 스크롤 안에 roi_names채워넣는 부분
        self._populate_visible_rois_list(self.segmented_class_names)

        # editing roi 부분
        radio_container = ttk.LabelFrame(left_frame, text="Editing ROI")
        radio_container.grid(row=2, column=0, pady=5, sticky="nsew")

        self.editing_search_entry = ttk.Entry(radio_container)
        self.editing_search_entry.pack(fill=tk.X, padx=5, pady=(5,0))
        self.editing_search_entry.bind("<KeyRelease>", self._filter_editing_rois)

        self.editing_scroll_frame = ScrollableFrame(radio_container)
        self.editing_scroll_frame.pack(fill=tk.BOTH, expand=True)
        self._populate_editing_rois_list(self.segmented_class_names)

        # 화면 오른쪽에 그릴 빈 canvas만들어줌, 배경은 검은색으로
        self.canvas = tk.Canvas(right_frame, bg='black')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        #  창 맨 아래에 상태 메시지를 표시할 라벨 만들어주기
        self.status_label = ttk.Label(self.root, text="Status..", anchor='w')
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5)
        
        # --- 이벤트 바인딩 ---
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        # self.canvas.bind("<Button-4>", self._on_scroll) -> 이건 리눅스용
        # self.canvas.bind("<Button-5>", self._on_scroll)
        self.root.bind("<KeyPress>", self._on_key_press)
        
        # 'd' 키 이벤트 바인딩
        self.root.bind("<KeyPress-d>", self._on_d_press)
        self.root.bind("<KeyRelease-d>", self._on_d_release)

        self.canvas.bind("<ButtonPress-1>", self._on_press) # 마우스 왼쪽 버튼 누를때
        self.canvas.bind("<ButtonRelease-1>", self._on_release) # 마우스 왼쪽 버튼 뗄시
        self.canvas.bind("<B1-Motion>", self._on_motion) # 마우스 왼쪽버튼 누르면서 움직일떄

        self.canvas.bind("<Control-MouseWheel>", self._on_zoom) # ctrl + 마우스휠 

        self.canvas.bind("<ButtonPress-3>", self._on_pan_start)# 마우스 오른쪽버튼 누를 시
        self.canvas.bind("<B3-Motion>", self._on_pan_move) #마우스 오른쪽버튼 누르고 움직일떄

    def _populate_segmen_rois(self, roi_names_to_display): # filter된거 가지고 ui새로고침 하는 함수
        for widget in self.visible_scroll_frame1.scrollable_frame.winfo_children():
            # 이전에 랜더링된 목록 지우기
            widget.destroy()
        for name in roi_names_to_display:
            # 보여줄 목록 가져와서 기존 true/false랑 연결지어서 pack해서 보여주기
            cb = ttk.Checkbutton(self.visible_scroll_frame1.scrollable_frame, text=name, variable=self.segment_check_vars[name], command=self._on_check_changed_seg)
            cb.pack(anchor='w', padx=5)

    def _filter_segment_rois(self, event=None):
        # 검색창에 입력된거 소문자로 바꾸고 query에 저장
        query = self.visible_search_entry1.get().lower()
        # 문자 포함된거 가지고 roi중에서 필터링후 새로운 filtered_names리스트 만들기
        filtered_names = [name for name in self.task_names if query in name.lower()]
        self._populate_segmen_rois(filtered_names)

    def _filter_visible_rois(self, event=None):
        # 검색창에 입력된거 소문자로 바꾸고 query에 저장
        query = self.visible_search_entry.get().lower()
        # 문자 포함된거 가지고 roi중에서 필터링후 새로운 filtered_names리스트 만들기
        filtered_names = [name for name in self.segmented_class_names if query in name.lower()]
        self._populate_visible_rois_list(filtered_names)

    def _populate_visible_rois_list(self, roi_names_to_display): # filter된거 가지고 ui새로고침 하는 함수
        for widget in self.visible_scroll_frame.scrollable_frame.winfo_children():
            # 이전에 랜더링된 목록 지우기
            widget.destroy()
        for name in roi_names_to_display:
            # 보여줄 목록 가져와서 기존 true/false랑 연결지어서 pack해서 보여주기
            cb = ttk.Checkbutton(self.visible_scroll_frame.scrollable_frame, text=name, variable=self.check_vars[name], command=self._on_check_changed)
            cb.pack(anchor='w', padx=5)
            

    # visible과 동일하게 구현, 근데 참조하는게 달라서 다른 함수로 구현
    def _filter_editing_rois(self, event=None): 
        query = self.editing_search_entry.get().lower()
        filtered_names = [name for name in self.segmented_class_names if query in name.lower()]
        self._populate_editing_rois_list(filtered_names)

    def _populate_editing_rois_list(self, roi_names_to_display):
        for widget in self.editing_scroll_frame.scrollable_frame.winfo_children():
            widget.destroy()
        for name in roi_names_to_display:
            rb = ttk.Radiobutton(self.editing_scroll_frame.scrollable_frame, text=name, variable=self.editing_roi_name, value=name, command=self._update_plot)
            rb.pack(anchor='w', padx=5)
            
    def _canvas_to_image_coords(self, canvas_x, canvas_y): # 화면좌표 -> 원본이미지 픽셀좌표로( 이동이나 확대 고려)
        img_x = (canvas_x - self.canvas_img_x) / self.zoom_level
        img_y = (canvas_y - self.canvas_img_y) / self.zoom_level
        return int(img_x), int(img_y)

    def _on_check_changed(self):
        # 버튼 체크하면 그릴 roi업데이트 하고 다시화면 랜더링
        self.active_rois = {name for name, var in self.check_vars.items() if var.get()}
        self._update_plot()

    def _on_check_changed_seg(self):
        # 버튼 체크하면 그릴 roi업데이트 하고 다시화면 랜더링
        self.segmented = {name for name, var in self.segment_check_vars.items() if var.get()}
        for name in self.segmented:
            if self.isSemented[name] == False:
                print(f"{name} task segmentation진행중 ...")
                temp_path = self.segmentation('dicom', self.dicom_folder, name)
                start_time = time.time()
                new_mask = self.get_mask_From_rtstruct(temp_path)
                if new_mask is None:
                    return
                end_time = time.time()
                print(f"rtstruct loading time = {end_time-start_time}")
                self.isSemented[name] == True
                if new_mask is not None:
                    print("mask가 존재합니다")
                    self.masks_dict.update(new_mask) # 기존 마스크딕셔너리에 새로운 마스크들 추가
                    self.segmented_class_names.extend(list(self.masks_dict.keys())) # class name 최신화

                    self._populate_editing_rois_list(self.segmented_class_names)
                    self.check_vars = {name: tk.BooleanVar(value=False) for name in self.segmented_class_names} # 체크박스의 선택/해제 상태와 연동되는 set변수
                    self.colors = plt.cm.get_cmap('gist_rainbow', len(self.segmented_class_names))
                    self.roi_colors = {name: [int(c*255) for c in self.colors(i)[:3]] for i, name in enumerate(self.segmented_class_names)}

        for widget in self.visible_scroll_frame.scrollable_frame.winfo_children():
            # 이전에 랜더링된 목록 지우기
            widget.destroy()
        for name in self.segmented_class_names:
            # 보여줄 목록 가져와서 기존 true/false랑 연결지어서 pack해서 보여주기
            cb = ttk.Checkbutton(self.visible_scroll_frame.scrollable_frame, text=name, variable=self.check_vars[name], command=self._on_check_changed)
            cb.pack(anchor='w', padx=5)

    def _on_d_press(self, event):
        self.d_key_pressed = True

    def _on_d_release(self, event):
        self.d_key_pressed = False

    def _on_key_press(self, event):
        key = event.keysym
        if key == 'Up':
            self.current_slice_idx = min(self.ct_volume.shape[2] - 1, self.current_slice_idx + 1)
        elif key == 'Down':
            self.current_slice_idx = max(0, self.current_slice_idx - 1)
        elif key in ['plus', 'equal']:
            self.brush_size += 1
        elif key == 'minus':
            self.brush_size = max(1, self.brush_size - 1)
        elif key.lower() == '0':
            self.zoom_level = 1.0
            self.canvas_img_x = 0
            self.canvas_img_y = 0
        elif key == 'Delete':
            roi_name = self.editing_roi_name.get()
            print(f"Clearing mask for '{roi_name}' on slice {self.current_slice_idx}")
            self.masks_dict[roi_name][:, :, self.current_slice_idx] = False
            self.temp_line_mask.fill(False)
        elif key.lower() == '1':
            print("편집된 마스크 저장을 시도합니다. 창을 닫아주세요.")
            self.root.destroy()
            return
        elif key.lower() == '2':
            self.masks_dict = None
            print("저장하지 않고 종료합니다.")
            self.root.destroy()
            return
        self._update_plot()
        
    def _on_scroll(self, event):
        if event.state & 0x4 == 0: # ctrl키 안눌렸을 경우
            # 마우스 휠 동작 감지 -> 마우스 휠로도 슬라이스 넘기게끔
            if event.delta > 0 or event.num == 4:
                self._on_key_press(type('Event', (), {'keysym': 'Up'})())
            elif event.delta < 0 or event.num == 5:
                self._on_key_press(type('Event', (), {'keysym': 'Down'})())

    def _on_zoom(self, event):
        old_zoom = self.zoom_level
        if event.delta > 0: 
            self.zoom_level *= 1.1
        else: 
            self.zoom_level /= 1.1
        self.zoom_level = np.clip(self.zoom_level, 0.1, 10)
        mouse_x, mouse_y = event.x, event.y
        self.canvas_img_x = mouse_x - (mouse_x - self.canvas_img_x) * (self.zoom_level / old_zoom)
        self.canvas_img_y = mouse_y - (mouse_y - self.canvas_img_y) * (self.zoom_level / old_zoom)
        self._update_plot()

    def _on_pan_start(self, event): # 드래그 시작위치
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def _on_pan_move(self, event): # 드래그 끝난위치
        dx = event.x - self.pan_start_x
        dy = event.y - self.pan_start_y
        self.canvas_img_x += dx
        self.canvas_img_y += dy
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        self._update_plot()
        
    def _on_press(self, event):
        # 왼쪽 마우스버튼 눌렸을떄
        if event.num == 1:
            self.temp_line_mask.fill(False)
            # d키 눌리면 지우기모드, 아니면 그리기모드
            if self.d_key_pressed:
                self.erasing = True
            else:
                self.drawing = True
            self._paint(event)

    def _on_release(self, event):
        # 마우스왼쪽버튼 뗄때,drawing모드일때
        if self.drawing:
            current_mask_slice = self.masks_dict[self.editing_roi_name.get()][:, :, self.current_slice_idx] # 현재 슬라이스의 roi마스크 가져오기
            boundary = np.logical_or(current_mask_slice, self.temp_line_mask) # or연산 이용해서 두개 마스크 합쳐줌
            filled_mask = binary_fill_holes(boundary) # fill_holes함수로 구멍 채우기
            self.masks_dict[self.editing_roi_name.get()][:, :, self.current_slice_idx] = filled_mask # 새로만들어진 마스크를 mask_dict에 적용
            self._update_plot() # 화면 udpate
        
        # 그리기, 지우기 상태 모두 초기화
        self.drawing = False
        self.erasing = False
        self.temp_line_mask.fill(False) # 임시 저장한 선 지워주기

    def _on_motion(self, event):
        # 그리기 또는 지우기 상태일 때 _paint 호출
        if self.drawing or self.erasing:
            self._paint(event)

    def _paint(self, event):
        x, y = self._canvas_to_image_coords(event.x, event.y) # 현재 마우스위치의 x,y좌표 가져오기(ct좌표계에서의)
        h, w = self.ct_volume.shape[:2]
        if not (0 <= x < w and 0 <= y < h): return # 영역 밖이면 return

        #브러시모양을 사각형으로 
        shape = (self.brush_size * 2 + 1, self.brush_size * 2 + 1)
        brush = np.ones(shape, dtype=bool)
        
        # 브러시 가장자리 처리
        paint_area_y = slice(max(0, y - self.brush_size), min(h, y + self.brush_size + 1))
        paint_area_x = slice(max(0, x - self.brush_size), min(w, x + self.brush_size + 1))
        
        brush_y_start = self.brush_size - y if y < self.brush_size else 0
        brush_y_end = brush.shape[0] - (y + self.brush_size + 1 - h) if y + self.brush_size + 1 > h else brush.shape[0]
        brush_x_start = self.brush_size - x if x < self.brush_size else 0
        brush_x_end = brush.shape[1] - (x + self.brush_size + 1 - w) if x + self.brush_size + 1 > w else brush.shape[1]
        
        brush_slice = brush[brush_y_start:brush_y_end, brush_x_start:brush_x_end]
        
        current_roi = self.editing_roi_name.get() # 현재 그리거나 지울 roi이름
        if self.drawing:
            self.temp_line_mask[paint_area_y, paint_area_x] |= brush_slice # temp에 brush위치를 true로
        # 지우기 로직 추가
        elif self.erasing:
            mask_slice = self.masks_dict[current_roi][:, :, self.current_slice_idx]
            mask_slice[paint_area_y, paint_area_x] &= ~brush_slice # temp에 brush위치를 false로
            
        self._update_plot()

    def _update_plot(self):
        ct_slice = self.ct_volume_display[:, :, self.current_slice_idx]  # 원본 ct가져오고
        display_img_base = np.stack([ct_slice] * 3, axis=-1) # overlay를 위해서 3채널로 바꿔줌

        for roi_name in self.active_rois:
            # # 체크해놓은 것들중, 이름과 색상을 가져오고
            mask = self.masks_dict[roi_name][:, :, self.current_slice_idx]
            color = self.roi_colors[roi_name]
            # 기존 ct에 오버레이
            display_img_base[mask] = (display_img_base[mask] * 0.5 + np.array(color) * 0.5).astype(np.uint8)

        # drawing중이면 사용자가 그린 색을 현재 editing중인 class 색상으로
        if self.drawing:
            display_img_base[self.temp_line_mask]= self.roi_colors[self.editing_roi_name.get()]
            #display_img_base[self.temp_line_mask] = [255, 255, 0]

        # 최종 오버레이된 이미지를 넘파이배열로 변환하고
        self.pil_img = Image.fromarray(display_img_base)
        w, h = self.pil_img.size
        # 현재 zoom-level에 맞게끔 높이, 너비 구하고
        new_w, new_h = int(w * self.zoom_level), int(h * self.zoom_level)
        # 해당 사이즈로 resize
        resized_img = self.pil_img.resize((new_w, new_h), Image.Resampling.NEAREST)
        # tkinter캔버스에 표시할수있게끔 변환
        self.photo_img = ImageTk.PhotoImage(image=resized_img)

        #기존 내용지우고
        self.canvas.delete("all")
        #새이미지를 랜더링
        self.canvas.create_image(self.canvas_img_x, self.canvas_img_y, image=self.photo_img, anchor='nw')
        
        # 상태바 텍스트 변경
        status_text = (f"Slice: {self.current_slice_idx}/{self.ct_volume.shape[2]-1} | "
                       f"Zoom: {self.zoom_level:.2f}x | "
                       f"Editing: {self.editing_roi_name.get()} | "
                       f"Brush: {self.brush_size}\n"
                       f"Controls: L-Draw, d+L-Erase, R-Pan, Wheel-Slice, Ctrl+Wheel-Zoom\n"
                       f"Keys: +/- (Brush), Del (Clear Slice), 0 (Reset Zoom), 1 (Save), 2 (Quit)")
        self.status_label.config(text=status_text)
    
    def get_modified_masks(self):
        return self.masks_dict
    
    def get_mask_From_rtstruct(self, rtstruct_path):
        # RTSTRUCT 로드 및 마스크 추출 (구버전 방식)
        print("RTSTRUCT 파일을 로딩합니다...")
        print(f"로딩중인 파일경로 : {rtstruct_path}")
        try:
            rtstruct_dicom = pydicom.dcmread(rtstruct_path)
            
            # 로드한 DICOM 슬라이스 목록과 RTSTRUCT를 RTStruct 객체에 전달
            rtstruct = RTStruct(self.d2_slices, rtstruct_dicom)

            roi_names = rtstruct.get_roi_names()
            #print(f"발견된 ROI: {roi_names}")
            
            temp_masks_dict = {}
            for name in roi_names:
                # 마스크를 3D numpy 배열로 가져옴 (boolean)
                mask_3d = rtstruct.get_roi_mask_by_name(name)
                temp_masks_dict[name] = mask_3d
            
            return temp_masks_dict
                
        except Exception as e:
            print(f"RTSTRUCT 로딩 중 오류 발생: {e}")
            return

    
    def dicom_to_np(self, dicom_series_path):
        print("원본 DICOM 시리즈를 로딩합니다...")
        # 해당 폴더안에 있는 .dcm파일들 경로를 리스트로 반환
        dicom_files = glob.glob(os.path.join(dicom_series_path, '*.dcm'))
        if not dicom_files:
            print(f"오류: '{dicom_series_path}' 폴더에 DICOM 파일이 없습니다.")
            return
        
        #dicom파일 하나씩 읽고
        self.d2_slices = [pydicom.dcmread(f) for f in dicom_files]
        # z축 기준 정렬
        self.d2_slices.sort(key=lambda x: float(x.ImagePositionPatient[2]))

        # hu값변환시 사용할 변수들
        self.center_val = self.d2_slices[0].WindowCenter
        self.width_val = self.d2_slices[0].WindowWidth
        self.slope = float(self.d2_slices[0].RescaleSlope)
        self.intercept = float(self.d2_slices[0].RescaleIntercept)
        
        # 원본 3D 볼륨 생성 -> mask editor클래스에 넘겨주는 용도
        self.ct_volume = np.stack([s.pixel_array for s in self.d2_slices], axis=-1)

        # hu값으로 변환하고 값 정규화
        hu_image = self.ct_volume * self.slope + self.intercept
        self.ct_volume_display = self._normalize_to_uint8(hu_image, self.center_val ,self.width_val)


    def segmentation(self, filetype, input_path, task):
        """
        DICOM 파일을 입력받아 TotalSegmentator를 이용해 RTSTRUCT를 생성

        Args:
            filetype (str): 입력 파일 타입 ('dicom' 또는 'nifti'). 현재는 'dicom'만 지원.
            input_path (str): DICOM 파일들이 있는 폴더 경로.
        Returns:
            str: 생성된 RTSTRUCT 파일의 경로. 오류 발생 시 None 반환.
        """
        try:
            if filetype == 'dicom':
                # 출력 경로 설정 (입력 폴더 이름 기준)
                folder_name = os.path.basename(os.path.normpath(input_path))
                output_path = os.path.join('dcm_output', folder_name)
                os.makedirs(output_path, exist_ok=True)
                print(f"segmentation 결과 저장할 경로 : {output_path}")

                # TotalSegmentator 실행
                totalsegmentator(input_path, output_path, task=task, output_type=filetype)

                # 생성된 RTSTRUCT 파일 경로 반환
                rt_path = os.path.join(output_path,'segmentations.dcm')
                #rt_path = output_path
                if os.path.exists(rt_path):
                    print(f"분할 완료! RTSTRUCT 파일: {rt_path}")
                    return rt_path
                else:
                    print("오류: RTSTRUCT 파일이 생성되지 않았습니다.")
                    return None

            elif filetype == 'nifti':
                print("nifti 파일 타입은 아직 구현되지 않았습니다.")
                return None

        except FileNotFoundError:
            print("파일 경로를 다시 확인하세요.")
            return None
        except Exception as e:
            print(f"분할 중 오류 발생: {e}")
            return None 
