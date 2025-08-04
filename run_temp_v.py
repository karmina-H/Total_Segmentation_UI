import os
import pydicom
import numpy as np
from rt_utils import RTStructBuilder
from rt_utils.rtstruct import RTStruct
from totalsegmentator.python_api import totalsegmentator
import glob
from scipy.ndimage import binary_fill_holes
from Front_UI_tmep_v import MaskEditor

total_segmentator_names = [
    "spleen", "kidney_right", "kidney_left", "gallbladder", "liver", "stomach", 
    "pancreas", "adrenal_gland_right", "adrenal_gland_left", "lung_upper_lobe_left", 
    "lung_lower_lobe_left", "lung_upper_lobe_right", "lung_middle_lobe_right", 
    "lung_lower_lobe_right", "esophagus", "trachea", "thyroid_gland", 
    "small_bowel", "duodenum", "colon", "urinary_bladder", "prostate", 
    "kidney_cyst_left", "kidney_cyst_right", "sacrum", "vertebrae_S1", 
    "vertebrae_L5", "vertebrae_L4", "vertebrae_L3", "vertebrae_L2", "vertebrae_L1", 
    "vertebrae_T12", "vertebrae_T11", "vertebrae_T10", "vertebrae_T9", 
    "vertebrae_T8", "vertebrae_T7", "vertebrae_T6", "vertebrae_T5", "vertebrae_T4", 
    "vertebrae_T3", "vertebrae_T2", "vertebrae_T1", "vertebrae_C7", "vertebrae_C6", 
    "vertebrae_C5", "vertebrae_C4", "vertebrae_C3", "vertebrae_C2", "vertebrae_C1", 
    "heart", "aorta", "pulmonary_vein", "brachiocephalic_trunk", 
    "subclavian_artery_right", "subclavian_artery_left", "common_carotid_artery_right", 
    "common_carotid_artery_left", "brachiocephalic_vein_left", 
    "brachiocephalic_vein_right", "atrial_appendage_left", "superior_vena_cava", 
    "inferior_vena_cava", "portal_vein_and_splenic_vein", "iliac_artery_left", 
    "iliac_artery_right", "iliac_vena_left", "iliac_vena_right", "humerus_left", 
    "humerus_right", "scapula_left", "scapula_right", "clavicula_left", 
    "clavicula_right", "femur_left", "femur_right", "hip_left", "hip_right", 
    "spinal_cord", "gluteus_maximus_left", "gluteus_maximus_right", 
    "gluteus_medius_left", "gluteus_medius_right", "gluteus_minimus_left", 
    "gluteus_minimus_right", "autochthon_left", "autochthon_right", 
    "iliopsoas_left", "iliopsoas_right", "brain", "skull", "rib_left_1", 
    "rib_left_2", "rib_left_3", "rib_left_4", "rib_left_5", "rib_left_6", 
    "rib_left_7", "rib_left_8", "rib_left_9", "rib_left_10", "rib_left_11", 
    "rib_left_12", "rib_right_1", "rib_right_2", "rib_right_3", "rib_right_4", 
    "rib_right_5", "rib_right_6", "rib_right_7", "rib_right_8", "rib_right_9", 
    "rib_right_10", "rib_right_11", "rib_right_12", "sternum", "costal_cartilages"
]


if __name__ == '__main__':

    organ_names = []

    # 원본 DICOM 데이터가 있는 폴더
    input_dicom_folder = 'dcm_data1' 

    print("에디터 실행")
    editor = MaskEditor(total_segmentator_names)
    # modified_masks = editor.get_modified_masks()

    # # 에디터 종료 후 수정된 마스크 저장하는 부분

    # if modified_masks:
    #     output_dir = 'output'  
    #     os.makedirs(output_dir, exist_ok=True) 
    #     #output_dir = os.path.dirname('output')
    #     base_name = "modified_RS"
    #     extension = ".dcm"
    #     i = 1
    #     while True:
    #         new_rt_filename = os.path.join(output_dir, f"{base_name}{i}{extension}")
    #         if not os.path.exists(new_rt_filename):
    #             break  # 파일명이 존재하지 않으면 루프를 빠져나오기
    #         i += 1
        
    #     print(f"{new_rt_filename} 파일 생성중 ...")
    #     new_rtstruct = RTStructBuilder.create_new(input_dicom_folder)
        
    #     for name, mask in modified_masks.items():
    #         filled_mask = binary_fill_holes(mask)
            
    #         # 수정된 마스크를 ROI로 추가
    #         new_rtstruct.add_roi(
    #             mask=filled_mask,
    #             name=f"{name}_modified"
    #         )
        
    #     new_rtstruct.save(new_rt_filename)
    #     print(f"저장 완료! 새로운 파일: {new_rt_filename}")
    # else:
    #     print("저장하지 않고 종료합니다.")

