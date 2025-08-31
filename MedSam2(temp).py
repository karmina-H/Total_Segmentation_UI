# -*- coding: utf-8 -*-
# ========================
# MedSAM2 propagation from a single edited slice (DICOM + RTSTRUCT)
# ========================

# ===== Setup (Colab 권장) =====
# !git clone https://github.com/bowang-lab/MedSAM2.git
# %cd MedSAM2
# %pip install -e .
# %pip install -q rt-utils pydicom SimpleITK tqdm

import os, re, json, math
from os.path import join
from glob import glob
import numpy as np
import pandas as pd
from collections import OrderedDict
from tqdm import tqdm

import SimpleITK as sitk
import pydicom
from rt_utils import RTStructBuilder

from PIL import Image
import torch
from sam2.build_sam import build_sam2_video_predictor_npz
from skimage import measure

import matplotlib.pyplot as plt

torch.set_float32_matmul_precision('high')
torch.manual_seed(2024)
np.random.seed(2024)
if not torch.cuda.is_available():
    raise RuntimeError("CUDA GPU가 필요합니다. (MedSAM2는 GPU 추론 권장)")

# ===== USER CONFIG =====
DICOM_DIR = "./dcm_data1"                   # DICOM 폴더
RTSTRUCT_PATH = "/output/modified_RS4.dcm"               # 기존 RT-STRUCT 파일
ROI_NAME = None                                       # 특정 ROI 이름 (None이면 첫 번째 ROI 사용)
EDITED_SLICE_NPY = "/path/to/edited_slice_mask.npy"   # 사용자가 수정한 2D 마스크(.npy, HxW, 0/1)
EDITED_SLICE_INDEX = 42                               # 수정한 슬라이스 z-index (0-based)

# HU 윈도우(없으면 DICOM 메타에서 읽어 시도, 실패 시 아래 기본값 사용)
WINDOW_CENTER = None
WINDOW_WIDTH  = None
DEFAULT_WIN = (-200, 300)   # (lower, upper) CT soft-tissue 권장 예시

# MedSAM2 모델 경로
CHECKPOINT = "./checkpoints/MedSAM2_2411.pt"
MODEL_CFG  = "configs/sam2.1_hiera_t512.yaml"

# 출력 폴더
SAVE_DIR = "./MedSAM2_outputs"
os.makedirs(SAVE_DIR, exist_ok=True)

# ===== 유틸 =====
def getLargestCC(seg):
    labels = measure.label(seg)
    if labels.max() == 0:
        return seg
    largest = labels == np.argmax(np.bincount(labels.flat)[1:]) + 1
    return largest.astype(seg.dtype)

def bbox_from_mask(mask2d):
    """mask2d: (H,W) bool/0-1 -> [x_min, y_min, x_max, y_max] (원본 해상도 좌표)"""
    ys, xs = np.where(mask2d > 0)
    if len(xs) == 0:
        raise ValueError("수정한 슬라이스 마스크가 비어 있습니다.")
    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()
    return np.array([int(x_min), int(y_min), int(x_max), int(y_max)], dtype=int)

def grayscale3d_to_rgb_resized(vol_uint8, image_size=512):
    """(D,H,W)->(D,3,sz,sz), PIL resize, uint8 -> float(0..1) 이후 표준화는 아래에서"""
    D,H,W = vol_uint8.shape
    out = np.zeros((D, 3, image_size, image_size), dtype=np.uint8)
    for i in range(D):
        img = Image.fromarray(vol_uint8[i])
        img = img.convert("RGB").resize((image_size, image_size), resample=Image.BILINEAR)
        out[i] = np.asarray(img).transpose(2,0,1)
    return out

def window_normalize_to_uint8(vol, wc, ww):
    lower = wc - ww/2.0
    upper = wc + ww/2.0
    vol = np.clip(vol, lower, upper)
    vol = (vol - lower) / (upper - lower + 1e-6) * 255.0
    return vol.astype(np.uint8)

def read_dicom_series(dicom_dir):
    reader = sitk.ImageSeriesReader()
    series_ids = reader.GetGDCMSeriesIDs(dicom_dir)
    if not series_ids:
        raise FileNotFoundError("DICOM 시리즈를 찾을 수 없습니다.")
    series_fns = reader.GetGDCMSeriesFileNames(dicom_dir, series_ids[0])
    reader.SetFileNames(series_fns)
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    img = reader.Execute()  # sitk.Image
    vol = sitk.GetArrayFromImage(img)  # (Z,Y,X)
    return img, vol, series_fns

def read_wc_ww_from_dicom(first_dcm_path):
    try:
        ds = pydicom.dcmread(first_dcm_path, force=True)
        slope = float(getattr(ds, "RescaleSlope", 1.0))
        inter = float(getattr(ds, "RescaleIntercept", 0.0))
        wc = getattr(ds, "WindowCenter", None)
        ww = getattr(ds, "WindowWidth", None)
        # MultiValue인 경우 첫 번째 값 사용
        if isinstance(wc, pydicom.multival.MultiValue): wc = float(wc[0])
        if isinstance(ww, pydicom.multival.MultiValue): ww = float(ww[0])
        return slope, inter, wc, ww
    except Exception:
        return 1.0, 0.0, None, None

# ===== 1) DICOM/RTSTRUCT 로딩 =====
sitk_img, vol_z_y_x, series_files = read_dicom_series(DICOM_DIR)   # vol: (Z,Y,X)
Z, H, W = vol_z_y_x.shape
print(f"DICOM volume shape: {vol_z_y_x.shape}")

# RT-STRUCT에서 초기 마스크 로드
rtstruct = RTStructBuilder.create_from(dicom_series_path=DICOM_DIR, rt_struct_path=RTSTRUCT_PATH)
roi_names = rtstruct.get_roi_names()
if len(roi_names) == 0:
    raise RuntimeError("RT-STRUCT에 ROI가 없습니다.")
roi_to_use = ROI_NAME if ROI_NAME in roi_names else (ROI_NAME if ROI_NAME else roi_names[0])
if ROI_NAME and ROI_NAME not in roi_names:
    print(f"[경고] '{ROI_NAME}' ROI를 찾지 못했습니다. 첫 번째 ROI('{roi_to_use}') 사용합니다.")
initial_mask_zyx = rtstruct.get_roi_mask_by_name(roi_to_use).astype(np.uint8)  # (Z,Y,X), {0,1}
if initial_mask_zyx.shape != vol_z_y_x.shape:
    raise RuntimeError(f"RT-STRUCT 마스크 shape {initial_mask_zyx.shape} != DICOM volume shape {vol_z_y_x.shape}")

# ===== 2) 수정한 단일 슬라이스 반영 =====
edited_mask_2d = np.load(EDITED_SLICE_NPY)  # (H,W)
if edited_mask_2d.shape != (H, W):
    raise ValueError(f"수정 마스크 shape {edited_mask_2d.shape}가 DICOM 슬라이스 {(H,W)}와 다릅니다.")
edited_mask_2d = (edited_mask_2d > 0).astype(np.uint8)

if not (0 <= EDITED_SLICE_INDEX < Z):
    raise IndexError("EDITED_SLICE_INDEX가 범위를 벗어났습니다.")

# 수정한 슬라이스로 교체
initial_mask_zyx[EDITED_SLICE_INDEX] = edited_mask_2d

# ===== 3) 윈도우/정규화 =====
slope, inter, wc_meta, ww_meta = read_wc_ww_from_dicom(series_files[0])

vol_hu = vol_z_y_x.astype(np.float32) * slope + inter
if WINDOW_CENTER is not None and WINDOW_WIDTH is not None:
    wc_use, ww_use = float(WINDOW_CENTER), float(WINDOW_WIDTH)
elif wc_meta is not None and ww_meta is not None:
    wc_use, ww_use = float(wc_meta), float(ww_meta)
else:
    wc_use = (DEFAULT_WIN[0] + DEFAULT_WIN[1]) / 2.0
    ww_use = float(DEFAULT_WIN[1] - DEFAULT_WIN[0])

vol_uint8 = window_normalize_to_uint8(vol_hu, wc_use, ww_use)  # (Z,H,W) uint8 in [0,255]

# ===== 4) SAM2 입력 준비 (RGB, 512 리사이즈 + 표준화) =====
video_height, video_width = H, W
rgb_512 = grayscale3d_to_rgb_resized(vol_uint8, image_size=512)  # (Z,3,512,512) uint8
img_resized = torch.from_numpy(rgb_512.astype(np.float32) / 255.0).cuda()  # (Z,3,512,512)

# ImageNet mean/std
img_mean=(0.485, 0.456, 0.406)
img_std=(0.229, 0.224, 0.225)
img_mean = torch.tensor(img_mean, dtype=torch.float32)[:, None, None].cuda()
img_std  = torch.tensor(img_std,  dtype=torch.float32)[:, None, None].cuda()
img_resized = (img_resized - img_mean) / img_std

# ===== 5) 수정 슬라이스에서 bbox 시드 생성 =====
bbox = bbox_from_mask(initial_mask_zyx[EDITED_SLICE_INDEX])  # [x_min, y_min, x_max, y_max]

# ===== 6) MedSAM2 추론 및 전파 =====
segs_3D = np.zeros((Z, H, W), dtype=np.uint8)
predictor = build_sam2_video_predictor_npz(MODEL_CFG, CHECKPOINT)

with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
    state = predictor.init_state(img_resized, video_height, video_width)

    # seed from edited slice
    _, out_obj_ids, out_mask_logits = predictor.add_new_points_or_box(
        inference_state=state,
        frame_idx=EDITED_SLICE_INDEX,
        obj_id=1,
        box=bbox,  # 원본 해상도 좌표
    )

    # forward propagate
    for out_frame_idx, out_obj_ids, out_mask_logits in predictor.propagate_in_video(state):
        segs_3D[out_frame_idx, (out_mask_logits[0] > 0.0).detach().cpu().numpy()[0]] = 1

    predictor.reset_state(state)

    # re-seed & backward propagate
    _, out_obj_ids, out_mask_logits = predictor.add_new_points_or_box(
        inference_state=state,
        frame_idx=EDITED_SLICE_INDEX,
        obj_id=1,
        box=bbox,
    )
    for out_frame_idx, out_obj_ids, out_mask_logits in predictor.propagate_in_video(state, reverse=True):
        segs_3D[out_frame_idx, (out_mask_logits[0] > 0.0).detach().cpu().numpy()[0]] = 1

# 후처리(선택): LCC
if segs_3D.max() > 0:
    segs_3D = getLargestCC(segs_3D).astype(np.uint8)

# ===== 7) 저장: NIfTI & RTSTRUCT =====
# NIfTI 저장 (DICOM 기하정보 복사)
sitk_img_uint8 = sitk.Cast(sitk.GetImageFromArray(vol_uint8), sitk.sitkUInt8)
sitk_img_uint8.CopyInformation(sitk_img)  # origin/direction/spacing

sitk_mask_u8 = sitk.GetImageFromArray(segs_3D.astype(np.uint8))
sitk_mask_u8.CopyInformation(sitk_img)

nii_img_path  = join(SAVE_DIR, "volume_win_uint8.nii.gz")
nii_mask_path = join(SAVE_DIR, "seg_propagated_mask.nii.gz")
sitk.WriteImage(sitk_img_uint8, nii_img_path)
sitk.WriteImage(sitk_mask_u8, nii_mask_path)
print(f"[저장] {nii_img_path}")
print(f"[저장] {nii_mask_path}")

# 새로운 RT-STRUCT 작성 (원본 시리즈 기준)
new_rt = RTStructBuilder.create_new(dicom_series_path=DICOM_DIR)
new_rt.add_roi(
    mask=segs_3D.astype(bool),   # (Z,Y,X) bool
    name=f"MedSAM2_propagated_from_{roi_to_use}",
    color=[255, 0, 0]
)
rt_out = join(SAVE_DIR, "rtstruct_MedSAM2_propagated.dcm")
new_rt.save(rt_out)
print(f"[저장] {rt_out}")

# ===== 8) (선택) 시각화: 편집 슬라이스 전/후 비교 =====
fig, axes = plt.subplots(1,3, figsize=(12,4))
axes[0].imshow(vol_uint8[EDITED_SLICE_INDEX], cmap='gray'); axes[0].set_title("CT (edited slice)"); axes[0].axis('off')
axes[1].imshow(vol_uint8[EDITED_SLICE_INDEX], cmap='gray'); axes[1].imshow(initial_mask_zyx[EDITED_SLICE_INDEX], alpha=0.4); axes[1].set_title("Initial (edited applied)"); axes[1].axis('off')
axes[2].imshow(vol_uint8[EDITED_SLICE_INDEX], cmap='gray'); axes[2].imshow(segs_3D[EDITED_SLICE_INDEX], alpha=0.4); axes[2].set_title("MedSAM2 propagated"); axes[2].axis('off')
plt.tight_layout()
plt.show()
