import requests
import os
import json
import nibabel as nib
import numpy as np
from io import BytesIO

SERVER_URL = "http://127.0.0.1:8000"
IMAGE_ID = "case1"
MODEL_NAME = "deepedit"
OUTPUT_DIR = "./final_output"
IMAGE_PATH = rf"C:\Users\gusdb\dcm_data1\{IMAGE_ID}.nii.gz"

params_data = {
    "points": [
        [30, 50, 50, 6],  # liver
        [10, 10, 10, 0]   # background
    ]
}

# URL: /infer/deepedit?image=case1
infer_url = f"{SERVER_URL}/infer/{MODEL_NAME}?image={IMAGE_ID}&output=image"

# 파일 전송: params + 파일
#여기서 file만 서버에 넘겨주면 전체 라벨을 auto segmentation
# 근데 지금 문제가 라벨을 지정해줘도 전체를 auto segmentation하는 문제가 발생함.
files = {
    'params': (None, json.dumps(params_data), 'application/json'),
    'file': (os.path.basename(IMAGE_PATH), open(IMAGE_PATH, 'rb'), 'application/octet-stream'),
}

print("⏳ 요청 전송 중...")
response = requests.post(infer_url, files=files)

if response.status_code != 200:
    # server error처리
    print("❌ 오류:", response.status_code)
    print(response.text)
else:
    print("✅ 성공! 마스크를 저장 중...")

    output_path = os.path.join(OUTPUT_DIR, f"mask_{IMAGE_ID}_liver.nii.gz")
    with open(output_path, "wb") as f:
        f.write(response.content)

    speicific_label = 0

    if speicific_label:
        #특정라벨만 저장할때
        mask_img = nib.load(output_path)
        mask_data = mask_img.get_fdata()

        # 원하는 label만 남기고, 나머지는 0으로
        target_label = 6
        filtered_data = np.where(mask_data == target_label, target_label, 0).astype(np.uint8)

        # 새로운 NIfTI 이미지 생성
        filtered_img = nib.Nifti1Image(filtered_data, affine=mask_img.affine, header=mask_img.header)

        # 저장할 경로
        filtered_output_path = os.path.join(OUTPUT_DIR, f"mask_{IMAGE_ID}_label{target_label}.nii.gz")
        nib.save(filtered_img, filtered_output_path)

        print(f"라벨 {target_label}만 남긴 마스크 저장 완료: {filtered_output_path}")
    else:
        # 모든라벨 그대로 저장할때
        output_path = os.path.join(OUTPUT_DIR, f"mask_{IMAGE_ID}_liver.nii.gz")
        with open(output_path, "wb") as f:
            f.write(response.content)

        mask_img = nib.load(output_path)
        print(f"라벨 모든라벨 마스크 저장 완료: {output_path}")
