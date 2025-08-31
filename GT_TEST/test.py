import os
import pydicom
from pydicom.uid import ExplicitVRLittleEndian
from pydicom.tag import Tag

# ====== 경로 수정 ======
INPUT_DIR  = r"C:\Users\gusdb\Desktop\Total_Segmentation_UI\GT_TEST\DCM"
OUTPUT_DIR = r"C:\Users\gusdb\Desktop\Total_Segmentation_UI\GT_TEST\DCM_uncompressed"
# ======================

os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_dataset(ds: pydicom.dataset.Dataset):
    """잘못된 VR/타입을 가능한 안전하게 교정"""
    # (0008,0008) Image Type 은 CS, 멀티값 문자열이어야 함
    if Tag(0x0008, 0x0008) in ds:
        elem = ds[Tag(0x0008, 0x0008)]
        elem.VR = "CS"
        v = elem.value
        # bytes -> str, 기타 -> str 리스트
        if isinstance(v, bytes):
            elem.value = v.decode("ascii", errors="ignore")
        elif isinstance(v, str):
            pass
        elif isinstance(v, (list, tuple)):
            elem.value = [x.decode("ascii", "ignore") if isinstance(x, (bytes, bytearray)) else str(x) for x in v]
        else:
            elem.value = str(v)

    # VR이 bytes/None 인 요소들을 UN으로 강제
    for elem in list(ds.iterall()):
        if not isinstance(elem.VR, str) or elem.VR is None:
            elem.VR = "UN"
        # SQ인데 값이 None인 경우 비어있는 시퀀스로
        if elem.VR == "SQ" and elem.value is None:
            from pydicom.sequence import Sequence
            elem.value = Sequence([])

    # 문자 집합 지정(없으면 기본 라틴1로)
    if "SpecificCharacterSet" not in ds or not ds.SpecificCharacterSet:
        ds.SpecificCharacterSet = "ISO_IR 100"

for root, _, files in os.walk(INPUT_DIR):
    for fname in files:
        if not fname.lower().endswith(".dcm"):
            continue
        src = os.path.join(root, fname)
        rel = os.path.relpath(src, INPUT_DIR)
        dst = os.path.join(OUTPUT_DIR, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)

        try:
            ds = pydicom.dcmread(src, force=True)  # 깨진 VR도 읽기
            # 압축이면 해제
            if ds.file_meta and getattr(ds.file_meta.TransferSyntaxUID, "is_compressed", False):
                ds.decompress()

            # 데이터 정리
            sanitize_dataset(ds)

            # 무압축 + Explicit VR로 메타 설정
            ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds.is_little_endian = True
            ds.is_implicit_VR = False

            # 저장 (원본처럼 쓰지 말고, pydicom이 안전하게 쓰도록)
            ds.save_as(dst, write_like_original=False)
            print(f"✅ Converted: {dst}")

        except Exception as e:
            print(f"❌ Failed: {src} ({e})")

print("🎉 완료. OUTPUT_DIR을 Slicer DICOM Import로 불러오세요.")
