import os
import pydicom
import numpy as np
from rt_utils import RTStructBuilder
from rt_utils.rtstruct import RTStruct
from totalsegmentator.python_api import totalsegmentator
import glob
from scipy.ndimage import binary_fill_holes
from Front_UI_tmep_v import MaskEditor


if __name__ == '__main__':
    task_names = ["total","total_mr","lung_vessels","body","body_mr","vertebrae_mr","cerebral_bleed","hip_implant","pleural_pericard_effusion","head_glands_cavities","head_muscles",
    "headneck_bones_vessels","headneck_muscles","liver_vessels""oculomotor_muscles","lung_nodules","kidney_cysts","breasts","liver_segments","liver_segments_mr",
    "craniofacial_structures","abdominal_muscles"]

    # 원본 DICOM 데이터가 있는 폴더
    input_dicom_folder = 'dcm_data1' 

    print("에디터 실행")
    editor = MaskEditor(task_names)
    modified_masks = editor.get_modified_masks()

    # 에디터 종료 후 수정된 마스크 저장하는 부분

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
        new_rtstruct = RTStructBuilder.create_new(input_dicom_folder)
        
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

