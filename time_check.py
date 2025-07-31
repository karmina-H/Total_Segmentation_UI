from totalsegmentator.python_api import totalsegmentator
import os
import time
from rt_utils.rtstruct import RTStruct
import pydicom
import glob

def segmentation(filetype, input_path, task):
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
        
def get_mask_From_rtstruct(rtstruct_path, d2_slices):
        # RTSTRUCT 로드 및 마스크 추출 (구버전 방식)
        print("RTSTRUCT 파일을 로딩합니다...")
        print(f"로딩중인 파일경로 : {rtstruct_path}")
        try:
            rtstruct_dicom = pydicom.dcmread(rtstruct_path)
            
            # 로드한 DICOM 슬라이스 목록과 RTSTRUCT를 RTStruct 객체에 전달
            rtstruct = RTStruct(d2_slices, rtstruct_dicom)

            roi_names = rtstruct.get_roi_names()
            #rint(f"발견된 ROI: {roi_names}")
            
            temp_masks_dict = {}
            for name in roi_names:
                # 마스크를 3D numpy 배열로 가져옴 (boolean)
                mask_3d = rtstruct.get_roi_mask_by_name(name)
                temp_masks_dict[name] = mask_3d
            
            return temp_masks_dict
                
        except Exception as e:
            print(f"RTSTRUCT 로딩 중 오류 발생: {e}")
            return
        
if __name__ == '__main__':
    task_names = ["total","total_mr","lung_vessels","body","body_mr","vertebrae_mr","cerebral_bleed","hip_implant","pleural_pericard_effusion","head_glands_cavities","head_muscles",
        "headneck_bones_vessels","headneck_muscles","liver_vessels","oculomotor_muscles","lung_nodules","kidney_cysts","breasts","liver_segments","liver_segments_mr",
        "craniofacial_structures","abdominal_muscles"]

    input_path = 'dcm_data1' 

    for task in task_names:
        start_time = time.time()
        segmentation('dicom',input_path,task)
        end_time = time.time()
        execution_time = end_time - start_time
        with open("execution_log.txt", "a") as f:
            f.write(f"{task} segmentation runtime: {execution_time:.4f}(sec) \n")



