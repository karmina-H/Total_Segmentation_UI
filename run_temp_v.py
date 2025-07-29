import os
import pydicom
import numpy as np
from rt_utils import RTStructBuilder
from rt_utils.rtstruct import RTStruct
from totalsegmentator.python_api import totalsegmentator
import glob
from scipy.ndimage import binary_fill_holes
from Front_UI_tmep_v import MaskEditor



# def segmentation(filetype, input_path, task):
#     """
#     DICOM 파일을 입력받아 TotalSegmentator를 이용해 RTSTRUCT를 생성

#     Args:
#         filetype (str): 입력 파일 타입 ('dicom' 또는 'nifti'). 현재는 'dicom'만 지원.
#         input_path (str): DICOM 파일들이 있는 폴더 경로.
#     Returns:
#         str: 생성된 RTSTRUCT 파일의 경로. 오류 발생 시 None 반환.
#     """
#     try:
#         if filetype == 'dicom':
#             # 출력 경로 설정 (입력 폴더 이름 기준)
#             folder_name = os.path.basename(os.path.normpath(input_path))
#             output_path = os.path.join('dcm_output', folder_name)
#             os.makedirs(output_path, exist_ok=True)
#             print(f"segmentation 결과 저장할 경로 : {output_path}")

#             # TotalSegmentator 실행
#             totalsegmentator(input_path, output_path, task=task, output_type=filetype)

#             # 생성된 RTSTRUCT 파일 경로 반환
#             rt_path = os.path.join(output_path, 'structures', 'RS.dcm')
#             if os.path.exists(rt_path):
#                 print(f"분할 완료! RTSTRUCT 파일: {rt_path}")
#                 return rt_path
#             else:
#                 print("오류: RTSTRUCT 파일이 생성되지 않았습니다.")
#                 return None

#         elif filetype == 'nifti':
#             print("nifti 파일 타입은 아직 구현되지 않았습니다.")
#             return None

#     except FileNotFoundError:
#         print("파일 경로를 다시 확인하세요.")
#         return None
#     except Exception as e:
#         print(f"분할 중 오류 발생: {e}")
#         return None



def visualize_and_modify(dicom_series_path, task_names):
    
    # # RTSTRUCT 로드 및 마스크 추출 (구버전 방식)
    # print("RTSTRUCT 파일을 로딩합니다...")
    # try:
    #     # pydicom으로 RTSTRUCT 파일을 직접 로드
    #     rtstruct_dicom = pydicom.dcmread(rtstruct_path)
        
    #     # 로드한 DICOM 슬라이스 목록과 RTSTRUCT를 RTStruct 객체에 전달
    #     rtstruct = RTStruct(slices, rtstruct_dicom)

    #     roi_names = rtstruct.get_roi_names()
    #     #print(f"발견된 ROI: {roi_names}")
        
    #     masks_dict = {}
    #     for name in roi_names:
    #         # 마스크를 3D numpy 배열로 가져옴 (boolean)
    #         mask_3d = rtstruct.get_roi_mask_by_name(name)
    #         masks_dict[name] = mask_3d
            
    # except Exception as e:
    #     print(f"RTSTRUCT 로딩 중 오류 발생: {e}")
    #     return
    
    print("에디터 실행")
    editor = MaskEditor(dicom_series_path, task_names)
    modified_masks = editor.get_modified_masks()

    # 수정된 마스크를 새로운 RTSTRUCT 파일로 저장 
    if modified_masks:
        output_dir = 'output'  
        os.makedirs(output_dir, exist_ok=True) 
        #output_dir = os.path.dirname('output')
        base_name = "modified_RS"
        extension = ".dcm"
        i = 1
        while True:
            new_rt_filename = os.path.join(output_dir, f"{base_name}{i}{extension}")
            if not os.path.exists(new_rt_filename):
                break  # 파일명이 존재하지 않으면 루프를 빠져나오기
            i += 1
        
        print(f"{new_rt_filename} 파일 생성중 ...")
        new_rtstruct = RTStructBuilder.create_new(dicom_series_path)
        
        for name, mask in modified_masks.items():
            filled_mask = binary_fill_holes(mask)
            
            # 수정된 마스크를 ROI로 추가
            new_rtstruct.add_roi(
                mask=filled_mask,
                name=f"{name}_modified"
            )
        
        new_rtstruct.save(new_rt_filename)
        print(f"저장 완료! 새로운 파일: {new_rt_filename}")
    else:
        print("저장하지 않고 종료합니다.")

if __name__ == '__main__':
    task_names = ["total","total_mr","lung_vessels","body","body_mr","vertebrae_mr","cerebral_bleed","hip_implant","pleural_pericard_effusion","head_glands_cavities","head_muscles",
    "headneck_bones_vessels","headneck_muscles","liver_vessels""oculomotor_muscles","lung_nodules","kidney_cysts","breasts","liver_segments","liver_segments_mr",
    "craniofacial_structures","abdominal_muscles"]

    # 원본 DICOM 데이터가 있는 폴더
    input_dicom_folder = 'dcm_data1' 
    # 기존에 segmentation된 결과 있으면 rt_file_path에 할당하고 segmentatino은 수행안하도록

    visualize_and_modify(input_dicom_folder, task_names)