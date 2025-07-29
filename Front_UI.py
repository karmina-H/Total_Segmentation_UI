from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import binary_fill_holes

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
    """

    Tkinter를 통해 인터랙티브하게 마스크를 편집하는 클래스.

    """
    def __init__(self, ct_volume, masks_dict, central_val, width_val, slope, intercept):
        # hu변환할때 필요한 변수들
        self.central_val = central_val
        self.width_val = width_val
        # ct 사진변수(row)
        self.ct_volume = ct_volume
        # hu값으로 변환하고 값 정규화
        hu_image = ct_volume * slope + intercept
        self.ct_volume_display = self._normalize_to_uint8(hu_image, central_val ,width_val)

        # roi각각의 마스크를 저장하는 딕셔너리
        self.masks_dict = masks_dict.copy()
        # roi 이름 저장한 리스트 
        self.roi_names = sorted(list(masks_dict.keys()))

        # --- 상태 변수 ---
        self.current_slice_idx = ct_volume.shape[2] // 2
        self.brush_size = 1
        self.drawing = False
        self.erasing = False # 지우기 상태 변수 추가
        self.d_key_pressed = False # 'd' 키 상태 변수 추가
        self.temp_line_mask = np.zeros(ct_volume.shape[:2], dtype=bool) # 사용자가 마우스 좌클릭을 떼기 전까지 그리는 선을 임시로 저장하는 2D numpy 배열

        # --- 줌 & 팬 상태 변수 ---
        self.zoom_level = 1.0
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.canvas_img_x = 0
        self.canvas_img_y = 0


        # --- 색상 설정 ---
        # roi_names 개수만큼 균등간격으로 색상 추출
        self.colors = plt.cm.get_cmap('gist_rainbow', len(self.roi_names))
        # 각 roi이름에 색상할당하고 딕셔너리로 저장
        self.roi_colors = {name: [int(c*255) for c in self.colors(i)[:3]] for i, name in enumerate(self.roi_names)}

        # --- Tkinter UI 설정 ---
        self.root = tk.Tk()
        self.root.title("Mask Editor (Tkinter)")
        self.root.geometry("1000x800") # 초기 창 크기

        # --- 상태 변수 (Tkinter용) ---
        self.editing_roi_name = tk.StringVar(value=self.roi_names[0])  # Editing ROI 의 string 초기값 할당
        self.check_vars = {name: tk.BooleanVar(value=(name == self.roi_names[0])) for name in self.roi_names} # 체크박스의 선택/해제 상태와 연동되는 set변수
        self.active_rois = {self.roi_names[0]} # 화면에 표시되고 있는 roi 리스트 저장하는 set

        print(f"active_rois: {self.active_rois}")

        # --- UI 레이아웃 생성 ---
        self._setup_ui()
        self._update_plot()
        self.root.mainloop()

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
        check_container1 = ttk.LabelFrame(left_frame, text="task")
        check_container1.grid(row=0, column=0, pady=5, sticky="nsew")
        #check_container1.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ## 'Visible ROIs' 그룹 안에 검색창(Entry)을 만들어주는 부분
        self.visible_search_entry1 = ttk.Entry(check_container1)
        self.visible_search_entry1.pack(fill=tk.X, padx=5, pady=(5,0))
        self.visible_search_entry1.bind("<KeyRelease>", self._filter_visible_rois) # 키보드 클릭시 마다  _filter_visible_rois함수로 필터링 수행
        # 스크롤 만들어 주는 부분
        self.visible_scroll_frame1 = ScrollableFrame(check_container1)
        self.visible_scroll_frame1.pack(fill=tk.BOTH, expand=True)
        # 스크롤 안에 roi_names채워넣는 부분
        self._populate_visible_rois_list2(self.roi_names)

        
        # visible roi부분
        check_container = ttk.LabelFrame(left_frame, text="Visible ROIs")
        check_container.grid(row=1, column=0, pady=5, sticky="nsew")
        #check_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        ## 'Visible ROIs' 그룹 안에 검색창(Entry)을 만들어주는 부분
        self.visible_search_entry = ttk.Entry(check_container)
        self.visible_search_entry.pack(fill=tk.X, padx=5, pady=(5,0))
        self.visible_search_entry.bind("<KeyRelease>", self._filter_visible_rois) # 키보드 클릭시 마다  _filter_visible_rois함수로 필터링 수행
        # 스크롤 만들어 주는 부분
        self.visible_scroll_frame = ScrollableFrame(check_container)
        self.visible_scroll_frame.pack(fill=tk.BOTH, expand=True)
        # 스크롤 안에 roi_names채워넣는 부분
        self._populate_visible_rois_list(self.roi_names)

        # editing roi 부분
        radio_container = ttk.LabelFrame(left_frame, text="Editing ROI")
        radio_container.grid(row=2, column=0, pady=5, sticky="nsew")
        #radio_container.pack(fill=tk.BOTH, expand=True, pady=5)

        self.editing_search_entry = ttk.Entry(radio_container)
        self.editing_search_entry.pack(fill=tk.X, padx=5, pady=(5,0))
        self.editing_search_entry.bind("<KeyRelease>", self._filter_editing_rois)

        self.editing_scroll_frame = ScrollableFrame(radio_container)
        self.editing_scroll_frame.pack(fill=tk.BOTH, expand=True)
        self._populate_editing_rois_list(self.roi_names)

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

    def _filter_visible_rois(self, event=None):
        # 검색창에 입력된거 소문자로 바꾸고 query에 저장
        query = self.visible_search_entry.get().lower()
        # 문자 포함된거 가지고 roi중에서 필터링후 새로운 filtered_names리스트 만들기
        filtered_names = [name for name in self.roi_names if query in name.lower()]
        self._populate_visible_rois_list(filtered_names)

    def _populate_visible_rois_list(self, roi_names_to_display): # filter된거 가지고 ui새로고침 하는 함수
        for widget in self.visible_scroll_frame.scrollable_frame.winfo_children():
            # 이전에 랜더링된 목록 지우기
            widget.destroy()
        for name in roi_names_to_display:
            # 보여줄 목록 가져와서 기존 true/false랑 연결지어서 pack해서 보여주기
            cb = ttk.Checkbutton(self.visible_scroll_frame.scrollable_frame, text=name, variable=self.check_vars[name], command=self._on_check_changed)
            cb.pack(anchor='w', padx=5)

    def _populate_visible_rois_list2(self, roi_names_to_display): # filter된거 가지고 ui새로고침 하는 함수
        for widget in self.visible_scroll_frame1.scrollable_frame.winfo_children():
            # 이전에 랜더링된 목록 지우기
            widget.destroy()
        for name in roi_names_to_display:
            # 보여줄 목록 가져와서 기존 true/false랑 연결지어서 pack해서 보여주기
            cb = ttk.Checkbutton(self.visible_scroll_frame1.scrollable_frame, text=name, variable=self.check_vars[name], command=self._on_check_changed)
            cb.pack(anchor='w', padx=5)


    # visible과 동일하게 구현, 근데 참조하는게 달라서 다른 함수로 구현
    def _filter_editing_rois(self, event=None): 
        query = self.editing_search_entry.get().lower()
        filtered_names = [name for name in self.roi_names if query in name.lower()]
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
            # 체크해놓은 것들중, 이름과 색상을 가져오고
            mask = self.masks_dict[roi_name][:, :, self.current_slice_idx]
            color = self.roi_colors[roi_name]
            # 기존 ct에 오버레이
            display_img_base[mask] = (display_img_base[mask] * 0.5 + np.array(color) * 0.5).astype(np.uint8)

        # drawing중이면 사용자가 그린 색을 노란색으로
        if self.drawing:
            display_img_base[self.temp_line_mask] = [255, 255, 0]

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