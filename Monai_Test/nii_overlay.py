import SimpleITK as sitk
import numpy as np
import matplotlib.pyplot as plt

# temp로 생성된 파일을 오버레이하는 부분
# 원본 dicom을 nifti파일로 변환 후 오버레이함.
# deepedit에도 nifti가 필요하기에 맨처음 dicom을 nifti로 변환후 계속 그거 사용

# 이미지 파일 경로
image_path = 'nifti_data1/case1.nii.gz'
mask_path = 'final_output/mask_case1_auto.nii.gz'


# 1. 원본 이미지와 마스크 로드
image_itk = sitk.ReadImage(image_path)
mask_itk = sitk.ReadImage(mask_path)

# 2. ITK 이미지 배열로 변환
image_array = sitk.GetArrayFromImage(image_itk)
mask_array = sitk.GetArrayFromImage(mask_itk)

# 3. 총 슬라이스 개수
total_slices = image_array.shape[0]

# 4. 슬라이스 20개 선택: 고르게 나누기
slice_indices = np.linspace(0, total_slices - 1, 20, dtype=int)

# 5. 시각화
plt.figure(figsize=(15, 12))

for i, slice_idx in enumerate(slice_indices):
    plt.subplot(4, 5, i + 1)

    # 원본 CT
    plt.imshow(image_array[slice_idx, :, :], cmap='gray', alpha=1.0)

    # 마스크 slice
    mask_slice = mask_array[slice_idx, :, :]

    # RGBA 배열 생성 (기본은 투명)
    overlay = np.zeros((*mask_slice.shape, 4), dtype=np.float32)

    # 값이 6인 부분만 빨간색 (R=1, G=0, B=0, A=0.4)
    overlay[mask_slice == 1] = [1, 0, 0, 0.4]
    overlay[mask_slice == 2] = [0, 1, 0, 0.4]
    overlay[mask_slice == 3] = [0, 0, 1, 0.4]
    overlay[mask_slice == 6] = [1, 1, 0, 0.4]
    overlay[mask_slice == 7] = [1, 0, 1, 0.4]
    overlay[mask_slice == 8] = [0, 1, 1, 0.4]
    overlay[mask_slice == 9] = [0.5, 1, 0.5, 0.4]

    plt.imshow(overlay)  # RGBA라 바로 색상 입혀짐

    plt.title(f"Slice {slice_idx}")
    plt.axis('off')

plt.tight_layout()
plt.savefig('total.png', dpi=300)
plt.show()
