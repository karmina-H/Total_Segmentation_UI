import os
import pydicom
import numpy as np
import matplotlib.pyplot as plt
from rt_utils import RTStructBuilder

def visualize_dicom_with_segmentation(dicom_folder_path, rtstruct_path, organ_roi):
    try:
        # 1. RTStruct 파일과 원본 DICOM 시리즈 폴더를 함께 로드합니다.
        #    이렇게 하면 RTStruct의 좌표가 원본 이미지 격자에 맞게 변환됩니다.
        rtstruct = RTStructBuilder.create_from(
            dicom_series_path=dicom_folder_path,
            rt_struct_path=rtstruct_path
        )

        # 2. 분할된 모든 장기(ROI)의 이름 목록을 가져옵니다.
        roi_names = rtstruct.get_roi_names()
        if not roi_names:
            print("오류: RTSTRUCT 파일에 분할된 영역(ROI) 정보가 없습니다.")
            return
        
        print("사용 가능한 분할 영역 (ROI):", roi_names)

        # 3. 첫 번째 분할 영역을 3D 마스크(boolean 배열)로 불러옵니다.
        #    이 마스크는 원본 DICOM 볼륨과 크기가 동일합니다.
        #    만약 다른 장기를 보고 싶다면 roi_names 목록에서 원하는 이름을 선택하세요.

        if roi_names not in organ_roi:
            print("해당 장기가 segmentation되지 않았습니다")
            return
        
        mask_3d = rtstruct.get_roi_mask_by_name(organ_roi)

        # 4. 원본 DICOM 시리즈를 3D 볼륨으로 만듭니다. (정렬 포함)
        dicom_files = [pydicom.dcmread(os.path.join(dicom_folder_path, f)) 
                       for f in os.listdir(dicom_folder_path) if f.endswith('.dcm')]
        dicom_files.sort(key=lambda x: int(x.InstanceNumber))
        ct_volume = np.stack([d.pixel_array for d in dicom_files])
        
        # 5. 중간 슬라이스의 인덱스를 계산합니다.
        middle_slice_idx = ct_volume.shape[0] // 2

        # 6. 중간 슬라이스의 CT 이미지와 분할 마스크를 가져옵니다.
        ct_slice = ct_volume[80, :, :]
        mask_3d = mask_3d[:, :, ::-1]
        mask_slice = mask_3d[:, :, 80]

        print(ct_slice.shape, mask_slice.shape)

        # 7. 시각화
        fig, ax = plt.subplots(1, 1, figsize=(8, 8))
        
        # 원본 CT 슬라이스를 회색조로 표시
        ax.imshow(ct_slice, cmap=plt.cm.gray, interpolation='none')
        
        # 분할된 영역을 반투명한 색상으로 겹쳐서 표시
        # np.ma.masked_where를 사용하여 마스크가 0인 부분은 투명하게 만듭니다.
        masked_segmentation = np.ma.masked_where(mask_slice == 0, mask_slice)
        ax.imshow(masked_segmentation, cmap='autumn', alpha=0.5, interpolation='none')
        
        ax.set_title(f'Middle Slice ({middle_slice_idx}) with "{organ_roi}" Segmentation')
        ax.axis('off')
        
        plt.show()

    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        print("파일 경로와 설치된 라이브러리를 확인해주세요.")

# --- 여기부터 시작 ---
if __name__ == '__main__':
    # ⚠️ 1. 원본 2D DICOM 파일들이 들어있는 폴더 경로를 지정하세요.
    dicom_folder_path = 'dcm'

    # ⚠️ 2. RTSTRUCT 파일(.dcm)의 전체 경로를 지정하세요.
    rtstruct_path = 'dcm_output/segmentations.dcm'

    organ_roi = "trachea"

    visualize_dicom_with_segmentation(dicom_folder_path, rtstruct_path, organ_roi)