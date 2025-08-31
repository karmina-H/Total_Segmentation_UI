import os
import SimpleITK as sitk
import imageio

# 저장 폴더 설정
output_dir = "./GT_TEST/totalsegmentator_spleen"
os.makedirs(output_dir, exist_ok=True)

# NRRD 파일 읽기
img = sitk.ReadImage("./GT_TEST/Totalsegmentator_spleen.nrrd")
arr = sitk.GetArrayFromImage(img)  # (z, y, x)

# PNG로 저장
for i, slice_img in enumerate(arr):
    save_path = os.path.join(output_dir, f"slice_{i:03d}.png")  # 폴더 경로 포함
    imageio.imwrite(save_path, (slice_img.astype("uint8") * 255))

print(f"모든 슬라이스가 '{output_dir}' 폴더에 저장 완료!")
