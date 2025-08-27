import dicom2nifti
import os

# DICOM 파일들이 있는 원본 폴더 경로
dicom_folder = "dcm_data1"

# NIfTI 파일을 저장할 경로와 파일명
nifti_folder = "nifti_data1"
nifti_file = os.path.join(nifti_folder, "output.nii.gz")

# NIfTI 파일을 저장할 폴더가 없으면 생성
if not os.path.exists(nifti_folder):
    os.makedirs(nifti_folder)

# DICOM to NIfTI 변환 실행
try:
    dicom2nifti.convert_directory(dicom_folder, nifti_folder)
    print("DICOM 폴더를 NIfTI 파일로 성공적으로 변환했습니다.")
    print(f"저장된 경로: {nifti_folder}")

except Exception as e:
    print(f"오류가 발생했습니다: {e}")