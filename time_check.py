from totalsegmentator.python_api import totalsegmentator
import os
import time
from rt_utils.rtstruct import RTStruct
import pydicom
import glob

def segmentation(filetype, input_path, roi_organs):
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
                totalsegmentator(input_path, output_path, roi_subset=roi_organs, output_type=filetype)

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
        
if __name__ == '__main__':
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


    input_path = 'dcm_data1' 

    # for organ in total_segmentator_names:
    #     list_l = [organ]
    #     start_time = time.time()
    #     segmentation('dicom',input_path,list_l)
    #     end_time = time.time()
    #     execution_time = end_time - start_time
    #     with open("organs_inference_execution_ti.txt", "a") as f:
    #         f.write(f"{organ} segmentation runtime: {execution_time:.4f}(sec) \n")
    start_time = time.time()
    segmentation('dicom',input_path,total_segmentator_names)
    end_time = time.time()
    execution_time = end_time - start_time
    with open("organs_inference_execution_ti.txt", "a") as f:
        f.write(f"total segmentation runtime: {execution_time:.4f}(sec) \n")



