import os
import numpy as np
import imageio.v3 as iio
import matplotlib.pyplot as plt

def show_pairs(pred_folder, gt_folder, used_pairs, ncols=2):
    """
    used_pairs: (pred_file, gt_file) 리스트
    pred_folder, gt_folder: 각 폴더 경로
    """
    n = len(used_pairs)
    fig, axes = plt.subplots(n, ncols, figsize=(6 * ncols, 3 * n))
    
    if n == 1:
        axes = np.array([axes])  # 한 장짜리도 일관되게 처리
    
    for i, (pred_file, gt_file) in enumerate(used_pairs):
        pred_path = os.path.join(pred_folder, pred_file)
        gt_path   = os.path.join(gt_folder,   gt_file)
        
        pred_img = iio.imread(pred_path)
        gt_img   = iio.imread(gt_path)
        
        # GT (왼쪽)
        ax1 = axes[i, 0] if n > 1 else axes[0]
        ax1.imshow(gt_img, cmap="gray")
        ax1.set_title(f"GT: {gt_file}")
        ax1.axis("off")
        
        # Pred (오른쪽)
        ax2 = axes[i, 1] if n > 1 else axes[1]
        ax2.imshow(pred_img, cmap="gray")
        ax2.set_title(f"Pred: {pred_file}")
        ax2.axis("off")
    
    plt.tight_layout()
    plt.show()


def list_pngs_sorted(folder):
    files = [f for f in os.listdir(folder) if f.lower().endswith(".png")]
    files.sort()  # 같은 규칙(사전식)으로 정렬
    return files

def select_window_by_tail(sorted_files, k_from_end=12, count=16):
    """
    정렬된 파일 리스트에서 '뒤에서 k_from_end번째(포함)'를 끝점으로
    그 앞 방향으로 count장을 선택 (총 count장).
    예: n=100, k_from_end=12, count=16 -> 인덱스 73~88 선택 (0-based)
    """
    n = len(sorted_files)
    if n == 0:
        return []
    end_idx = max(0, min(n - k_from_end, n - 1))
    start_idx = max(0, end_idx - (count - 1))
    return sorted_files[start_idx:end_idx + 1]

def select_window_by_front(sorted_files, k_from_front=12, count=16):
    """
    정렬된 파일 리스트에서 '앞에서 k_from_front번째(포함)'를 시작점으로
    그 뒤 방향으로 count장을 선택 (총 count장).
    예: n=100, k_from_front=12, count=16 -> 인덱스 11~26 선택 (0-based)
    """
    n = len(sorted_files)
    if n == 0:
        return []
    start_idx = max(0, min(k_from_front - 1, n - 1))  # 앞에서 k번째 → index k-1
    end_idx = min(n - 1, start_idx + count - 1)
    window = sorted_files[start_idx:end_idx + 1]
    return window[::-1]


def read_mask_as_bool(path, threshold=127):
    """
    PNG → bool 마스크로 변환 (0/1 또는 0/255 모두 대응).
    RGB면 첫 채널 사용.
    """
    img = iio.imread(path)
    if img.ndim == 3:
        img = img[..., 0]
    return (img.astype(np.int32) > threshold)

def pixel_accuracy(a, b):
    if a.shape != b.shape:
        raise ValueError(f"Shape mismatch: {a.shape} vs {b.shape}")
    return (a == b).mean()

def dice_iou(a, b):
    inter = np.logical_and(a, b).sum()
    sa, sb = a.sum(), b.sum()
    union = sa + sb - inter
    dice = (2 * inter) / (sa + sb) if (sa + sb) > 0 else 1.0
    iou  = inter / union if union > 0 else 1.0
    return dice, iou

def evaluate_by_order(pred_folder, gt_folder, k_from_end=12, count=16, threshold=127):
    pred_all = list_pngs_sorted(pred_folder)
    gt_all   = list_pngs_sorted(gt_folder)

    pred_sel = select_window_by_tail(pred_all, k_from_end=k_from_end, count=count)
    gt_sel   = select_window_by_front(gt_all,   k_from_front=k_from_end, count=count)

    # 두 폴더에서 뽑힌 개수가 다르면 공통 길이만 사용
    use_n = min(len(pred_sel), len(gt_sel))
    pred_sel = pred_sel[:use_n]
    gt_sel   = gt_sel[:use_n]

    if use_n == 0:
        raise RuntimeError("선택된 범위에 해당하는 이미지가 없습니다. 폴더/파라미터를 확인하세요.")

    accs, dices, ious = [], [], []
    used_pairs = []

    for i in range(use_n):
        p_path = os.path.join(pred_folder, pred_sel[i])
        g_path = os.path.join(gt_folder,   gt_sel[i])

        p_mask = read_mask_as_bool(p_path, threshold)
        g_mask = read_mask_as_bool(g_path, threshold)

        acc = pixel_accuracy(g_mask, p_mask)
        d, j = dice_iou(g_mask, p_mask)

        accs.append(acc); dices.append(d); ious.append(j)
        used_pairs.append((pred_sel[i], gt_sel[i]))

    results = {
        "num_pairs": use_n,
        "pixel_accuracy_mean": float(np.mean(accs)),
        "pixel_accuracy_std":  float(np.std(accs)),
        "dice_mean": float(np.mean(dices)),
        "dice_std":  float(np.std(dices)),
        "iou_mean":  float(np.mean(ious)),
        "iou_std":   float(np.std(ious)),
        "used_pairs": used_pairs,  # (pred_file, gt_file) 순서 매칭
    }
    return results

if __name__ == "__main__":
    pred_folder = r"./GT_TEST/totalsegmentator_spleen"   # 예측 폴더
    gt_folder   = r"./GT_TEST/Mask_Spleen"     # GT 폴더

    k_from_end = 12  # 뒤에서 12번째를 끝점(포함)
    count = 16       # 총 16장 사용

    res = evaluate_by_order(pred_folder, gt_folder, k_from_end, count, threshold=127)

    # 비교 이미지 출력
    show_pairs(pred_folder, gt_folder, res["used_pairs"])


    print("=== 평가 결과 ===")
    print(f"사용한 페어 수: {res['num_pairs']}")
    print(f"Pixel Accuracy: {res['pixel_accuracy_mean']:.4f} ± {res['pixel_accuracy_std']:.4f}")
    print(f"Dice:           {res['dice_mean']:.4f} ± {res['dice_std']:.4f}")
    print(f"IoU:            {res['iou_mean']:.4f} ± {res['iou_std']:.4f}")
    # 어떤 파일이 서로 매칭됐는지 확인하려면:
    # for p, g in res["used_pairs"]:
    #     print(p, "<->", g)
