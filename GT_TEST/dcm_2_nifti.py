import os
import pydicom
import numpy as np
import SimpleITK as sitk
from skimage.draw import polygon as fill_polygon

def validate_series_uid(dicom_folder_path, rt_struct_path):
    """RT-STRUCT와 DICOM 시리즈의 SeriesInstanceUID가 일치하는지 확인합니다."""
    try:
        # RT-STRUCT 파일에서 참조하는 Series UID 추출
        rt_dataset = pydicom.dcmread(rt_struct_path)
        rt_series_uid = rt_dataset.ReferencedFrameOfReferenceSequence[0] \
                                .RTReferencedStudySequence[0] \
                                .RTReferencedSeriesSequence[0] \
                                .SeriesInstanceUID
        
        # DICOM 폴더의 이미지 파일에서 Series UID 추출
        dicom_files = [f for f in os.listdir(dicom_folder_path) if f.endswith('.dcm')]
        if not dicom_files:
            print(f"오류: 폴더에 DICOM 파일이 없습니다: {dicom_folder_path}")
            return False
            
        first_image_path = os.path.join(dicom_folder_path, dicom_files[0])
        image_dataset = pydicom.dcmread(first_image_path)
        image_series_uid = image_dataset.SeriesInstanceUID

        if rt_series_uid == image_series_uid:
            print("✅ UID 일치 확인: 올바른 DICOM-RTSTRUCT 쌍입니다.")
            return True
        else:
            print("❌ UID 불일치! 변환을 중단합니다.")
            print(f"  - RT-STRUCT가 참조하는 UID: {rt_series_uid}")
            print(f"  - DICOM 폴더의 UID:         {image_series_uid}")
            return False
    except Exception as e:
        print(f"UID 확인 중 오류 발생: {e}")
        return False

def convert_rtstruct_to_nifti(dicom_folder, rtstruct_file, target_roi_name, output_nifti):
    """RT-STRUCT를 NIfTI 마스크로 변환하는 최종 함수"""
    
    # 1. UID 검증
    print("--- 1. Series UID 검증 시작 ---")
    if not validate_series_uid(dicom_folder, rtstruct_file):
        return
    
    # 2. 원본 DICOM 시리즈 로드
    print("\n--- 2. 원본 DICOM 시리즈 로드 ---")
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(dicom_folder)
    reader.SetFileNames(dicom_names)
    original_image = reader.Execute()
    print("이미지 로드 완료. 크기:", original_image.GetSize())

    # 3. RT-STRUCT 파일 로드 및 ROI 정보 추출
    print("\n--- 3. RT-STRUCT 데이터 추출 ---")
    rt_ds = pydicom.dcmread(rtstruct_file)
    
    roi_number = next(
        (roi.ROINumber for roi in rt_ds.StructureSetROISequence if roi.ROIName == target_roi_name), 
        None
    )
    if roi_number is None:
        print(f"오류: ROI '{target_roi_name}'을(를) 찾을 수 없습니다.")
        return
    print(f"ROI '{target_roi_name}' (번호: {roi_number}) 확인.")
    
    contour_sequence = next(
        (contour.ContourSequence for contour in rt_ds.ROIContourSequence if contour.ReferencedROINumber == roi_number),
        None
    )
    if contour_sequence is None:
        print(f"오류: ROI 번호 {roi_number}에 대한 Contour를 찾을 수 없습니다.")
        return

    # 4. 마스크 생성 (래스터화)
    print("\n--- 4. 마스크 생성 (래스터화) ---")
    image_array = sitk.GetArrayFromImage(original_image)
    mask_array = np.zeros_like(image_array, dtype=np.uint8)

    for contour in contour_sequence:
        contour_data = np.array(contour.ContourData).reshape(-1, 3)
        
        # Contour가 속한 슬라이스의 Z 인덱스 찾기
        # 첫 번째 점의 물리적 좌표를 이미지 인덱스로 변환하여 z 인덱스를 얻음
        physical_point = contour_data[0]
        slice_index_vec = original_image.TransformPhysicalPointToIndex(physical_point)
        slice_z_index = slice_index_vec[2]

        # 3D 물리적 좌표를 2D 픽셀 좌표로 변환
        pixel_coords = []
        for point in contour_data:
            idx = original_image.TransformPhysicalPointToIndex(point)
            pixel_coords.append([idx[1], idx[0]]) # (row, col) 순서로 저장

        if pixel_coords:
            rows, cols = zip(*pixel_coords)
            rr, cc = fill_polygon(rows, cols, shape=mask_array.shape[1:])
            mask_array[slice_z_index, rr, cc] = 1 # 해당 슬라이스에 마스크 채우기

    print("마스크 생성 완료.")

    # 5. NIfTI 파일로 저장
    print("\n--- 5. NIfTI 파일 저장 ---")
    mask_image = sitk.GetImageFromArray(mask_array)
    mask_image.CopyInformation(original_image) # 원본의 좌표계 정보 복사!
    
    sitk.WriteImage(mask_image, output_nifti)
    print(f"\n🎉 변환 성공! 파일이 저장되었습니다:\n{output_nifti}")


# --- ✍️ 사용자 설정 부분 ---
if __name__ == "__main__":
    dicom_folder_path = "C:/Users/gusdb/Desktop/Total_Segmentation_UI/GT_TEST/mask1_origin"
    rtstruct_path = "C:/Users/gusdb/Desktop/Total_Segmentation_UI/GT_TEST/mask1_spleen_mask.dcm"
    roi_name = "spleen"  # RT-STRUCT 파일 안의 정확한 ROI 이름
    output_path = "C:/Users/gusdb/Desktop/Total_Segmentation_UI/GT_TEST/spleen_mask_final.nii.gz"
    
    convert_rtstruct_to_nifti(dicom_folder_path, rtstruct_path, roi_name, output_path)