import os
import pydicom
import numpy as np
from rt_utils import RTStructBuilder
from rt_utils.rtstruct import RTStruct
from totalsegmentator.python_api import totalsegmentator
import glob
from scipy.ndimage import binary_fill_holes
from Front_UI import MaskEditor




def segmentation(filetype, input_path):
    """
    DICOM 파일을 입력받아 TotalSegmentator를 이용해 RTSTRUCT를 생성

    Args:
        filetype (str): 입력 파일 타입 ('dicom' 또는 'nifti'). 현재는 'dicom'만 지원.
        input_path (str): DICOM 파일들이 있는 폴더 경로.
    Returns:
        str: 생성된 RTSTRUCT 파일의 경로. 오류 발생 시 None 반환.
    """
    roi_organ = 'total'
    try:
        if filetype == 'dicom':
            # 출력 경로 설정 (입력 폴더 이름 기준)
            folder_name = os.path.basename(os.path.normpath(input_path))
            output_path = os.path.join('dcm_output', folder_name)
            os.makedirs(output_path, exist_ok=True)
            print(f"segmentation 결과 저장할 경로 : {output_path}")

            # TotalSegmentator 실행
            totalsegmentator(input_path, output_path, task=roi_organ, output_type=filetype)

            # 생성된 RTSTRUCT 파일 경로 반환
            rt_path = os.path.join(output_path, 'structures', 'RS.dcm')
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



def visualize_and_modify(dicom_series_path, rtstruct_path):

    print("원본 DICOM 시리즈를 로딩합니다...")
    # 해당 폴더안에 있는 .dcm파일들 경로를 리스트로 반환
    dicom_files = glob.glob(os.path.join(dicom_series_path, '*.dcm'))
    if not dicom_files:
        print(f"오류: '{dicom_series_path}' 폴더에 DICOM 파일이 없습니다.")
        return
    
    #dicom파일 하나씩 읽고
    slices = [pydicom.dcmread(f) for f in dicom_files]
    # z축 기준 정렬
    slices.sort(key=lambda x: float(x.ImagePositionPatient[2]))

    # hu값변환시 사용할 변수들
    center_val = slices[0].WindowCenter
    width_val = slices[0].WindowWidth
    slope = float(slices[0].RescaleSlope)
    intercept = float(slices[0].RescaleIntercept)
    
    # 원본 3D 볼륨 생성 -> mask editor클래스에 넘겨주는 용도
    ct_volume = np.stack([s.pixel_array for s in slices], axis=-1)
    
    # RTSTRUCT 로드 및 마스크 추출 (구버전 방식)
    print("RTSTRUCT 파일을 로딩합니다...")
    try:
        # pydicom으로 RTSTRUCT 파일을 직접 로드
        rtstruct_dicom = pydicom.dcmread(rtstruct_path)
        
        # 로드한 DICOM 슬라이스 목록과 RTSTRUCT를 RTStruct 객체에 전달
        rtstruct = RTStruct(slices, rtstruct_dicom)

        roi_names = rtstruct.get_roi_names()
        #print(f"발견된 ROI: {roi_names}")
        
        masks_dict = {}
        for name in roi_names:
            # 마스크를 3D numpy 배열로 가져옴 (boolean)
            mask_3d = rtstruct.get_roi_mask_by_name(name)
            masks_dict[name] = mask_3d
            
    except Exception as e:
        print(f"RTSTRUCT 로딩 중 오류 발생: {e}")
        return
    
    print("에디터 실행")
    editor = MaskEditor(ct_volume, masks_dict, center_val, width_val,slope, intercept)
    modified_masks = editor.get_modified_masks()

    # 수정된 마스크를 새로운 RTSTRUCT 파일로 저장 
    if modified_masks:
        print("수정된 마스크를 새로운 RTSTRUCT 파일로 저장합니다")
        output_dir = os.path.dirname(rtstruct_path)
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
    # 원본 DICOM 데이터가 있는 폴더
    input_dicom_folder = 'dcm_data1' 
    # 기존에 segmentation된 결과 있으면 rt_file_path에 할당하고 segmentatino은 수행안하도록
    rt_file_path = 'dcm_output/dcm_data1/segmentations.dcm'


    if rt_file_path is None:
        rt_file_path = segmentation('dicom', input_dicom_folder)

    print("기존에 segmentation된 rtstruct파일이 존재합니다.")
    if rt_file_path and os.path.exists(rt_file_path):
        visualize_and_modify(input_dicom_folder, rt_file_path)
    else:
        print("RTSTRUCT 파일이 유효하지 않음.")