import os
import argparse
import logging
from typing import List, Tuple

import pydicom
from pydicom.uid import ExplicitVRLittleEndian
from pydicom.tag import Tag
from pydicom.errors import InvalidDicomError


def setup_logger(level=logging.INFO):
    logging.basicConfig(
        format="%(levelname)s: %(message)s",
        level=level,
    )


def is_compressed_tsuid(ds: pydicom.dataset.Dataset) -> bool:
    try:
        ts = ds.file_meta.TransferSyntaxUID
        return getattr(ts, "is_compressed", False)
    except Exception:
        return False


def verify_dataset(ds: pydicom.dataset.Dataset) -> List[str]:
    """수정 전에 잠재적 문제를 수집"""
    issues = []

    # 1) Transfer Syntax
    try:
        ts = ds.file_meta.TransferSyntaxUID
    except Exception:
        issues.append("file_meta.TransferSyntaxUID 누락/손상")
    else:
        if is_compressed_tsuid(ds):
            issues.append(f"압축 TSUID 사용: {ts.name if hasattr(ts, 'name') else str(ts)}")

    # 2) Image Type (0008,0008) CS 확인 + 값 타입
    if Tag(0x0008, 0x0008) in ds:
        elem = ds[Tag(0x0008, 0x0008)]
        if elem.VR != "CS":
            issues.append(f"(0008,0008) ImageType VR가 {elem.VR} (기대: CS)")
        v = elem.value
        if not (isinstance(v, str) or isinstance(v, (list, tuple))):
            issues.append(f"(0008,0008) ImageType 값 타입 이상: {type(v).__name__}")
    else:
        issues.append("(0008,0008) ImageType 없음")

    # 3) SpecificCharacterSet
    if not ds.get("SpecificCharacterSet"):
        issues.append("SpecificCharacterSet 없음")

    # 4) VR 깨짐/None, SQ인데 None
    for elem in ds.iterall():
        if not isinstance(elem.VR, str) or elem.VR is None:
            issues.append(f"태그 {elem.tag} VR 누락/손상")
            break
    for elem in ds.iterall():
        if elem.VR == "SQ" and elem.value is None:
            issues.append(f"태그 {elem.tag} SQ 값이 None")
            break

    return issues


def fix_dataset(
    ds: pydicom.dataset.Dataset,
    force_charset: str = None,
) -> Tuple[pydicom.dataset.Dataset, List[str]]:
    """발견된 문제만 보수적으로 수정"""
    fixes = []

    # 0) file_meta 보장
    if not hasattr(ds, "file_meta") or ds.file_meta is None:
        ds.file_meta = pydicom.dataset.FileMetaDataset()
        fixes.append("file_meta 생성")

    # 1) 압축이면 해제
    if is_compressed_tsuid(ds):
        try:
            ds.decompress()
            fixes.append("픽셀데이터 decompress")
        except Exception as e:
            fixes.append(f"decompress 실패: {e}")

    # 2) Image Type (0008,0008) 교정(필요 시)
    tag_image_type = Tag(0x0008, 0x0008)
    if tag_image_type in ds:
        elem = ds[tag_image_type]
        if elem.VR != "CS":
            elem.VR = "CS"
            fixes.append("(0008,0008) VR=CS로 교정")
        v = elem.value
        # 값을 str 또는 MultiValue(str)로 통일
        if isinstance(v, bytes):
            elem.value = v.decode("ascii", errors="ignore")
            fixes.append("(0008,0008) bytes→str 변환")
        elif isinstance(v, (list, tuple)):
            elem.value = [
                x.decode("ascii", "ignore") if isinstance(x, (bytes, bytearray)) else str(x)
                for x in v
            ]
            fixes.append("(0008,0008) list/tuple 항목을 str로 변환")
        elif not isinstance(v, str):
            elem.value = str(v)
            fixes.append("(0008,0008) 값을 str로 강제 변환")
    # 없으면 건드리지 않음(진짜로 없는 경우가 존재)

    # 3) 문자셋
    if force_charset:
        ds.SpecificCharacterSet = force_charset
        fixes.append(f"SpecificCharacterSet 강제: {force_charset}")
    else:
        if not ds.get("SpecificCharacterSet"):
            ds.SpecificCharacterSet = "ISO_IR 100"
            fixes.append("SpecificCharacterSet 기본값 ISO_IR 100 설정")

    # 4) VR 누락/깨짐, SQ None 최소 보정
    for elem in list(ds.iterall()):
        if not isinstance(elem.VR, str) or elem.VR is None:
            # 가능한 경우만 보정: 알 수 없으니 UN으로
            elem.VR = "UN"
            fixes.append(f"{elem.tag} VR=UN으로 교정")
    from pydicom.sequence import Sequence
    for elem in list(ds.iterall()):
        if elem.VR == "SQ" and elem.value is None:
            elem.value = Sequence([])
            fixes.append(f"{elem.tag} SQ None→빈 Sequence")

    # 5) 저장 형식 표준화 (메타 포함)
    # SOPInstanceUID 등 원본 UID 보존
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.is_little_endian = True
    ds.is_implicit_VR = False
    # Implementation UID 없으면 부여
    if not getattr(ds.file_meta, "ImplementationClassUID", None):
        ds.file_meta.ImplementationClassUID = pydicom.uid.generate_uid(prefix="1.2.826.0.1.3680043.9.7434.")
        fixes.append("ImplementationClassUID 생성")

    return ds, fixes


def process_file(src_path: str, dst_path: str, dry_run=False, force_charset=None) -> Tuple[bool, List[str], List[str]]:
    """단일 파일 처리: (성공여부, issues, fixes)"""
    issues, fixes = [], []
    try:
        ds = pydicom.dcmread(src_path, force=True)
    except (InvalidDicomError, Exception) as e:
        return False, [f"DICOM 읽기 실패: {e}"], fixes

    issues = verify_dataset(ds)

    if dry_run:
        # 검사만
        return True, issues, fixes

    ds, fixes = fix_dataset(ds, force_charset=force_charset)

    # 출력 디렉터리 보장
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    try:
        ds.save_as(dst_path, write_like_original=False)
    except Exception as e:
        return False, issues, fixes + [f"저장 실패: {e}"]

    return True, issues, fixes


def main():

    setup_logger()

    in_dir = './GT_TEST/DCM'
    out_dir = './GT_TEST/TEMP'
    dry_run = True
    force_charset = None
    #ext = args.ext.lower()

    total = 0
    ok = 0
    failed = 0

    summary_issues = {}
    summary_fixes = {}

    for root, _, files in os.walk(in_dir):
        for fname in files:
            total += 1
            src = os.path.join(root, fname)
            rel = os.path.relpath(src, in_dir)
            dst = os.path.join(out_dir, rel)

            success, issues, fixes = process_file(src, dst, dry_run=dry_run, force_charset=force_charset)

            # 파일별 로그
            if success:
                if dry_run:
                    logging.info(f"[검사 성공] {rel}")
                else:
                    logging.info(f"[처리 성공] {rel}")
                if issues:
                    logging.info("  발견된 문제:")
                    for i in issues:
                        logging.info(f"   - {i}")
                        summary_issues[i] = summary_issues.get(i, 0) + 1
                if fixes:
                    logging.info("  적용된 수정:")
                    for f in fixes:
                        logging.info(f"   + {f}")
                        summary_fixes[f] = summary_fixes.get(f, 0) + 1
                ok += 1
            else:
                logging.error(f"[실패] {rel}")
                for i in issues:
                    logging.error(f"   - {i}")
                    summary_issues[i] = summary_issues.get(i, 0) + 1
                for f in fixes:
                    logging.error(f"   (수정 시도) {f}")
                    summary_fixes[f] = summary_fixes.get(f, 0) + 1
                failed += 1

    # 요약
    logging.info("=" * 60)
    logging.info(f"총 파일: {total}, 성공: {ok}, 실패: {failed}, 모드: {'DRY-RUN' if dry_run else 'WRITE'}")
    if summary_issues:
        logging.info("이슈 요약(발견 빈도 상위):")
        for k, v in sorted(summary_issues.items(), key=lambda x: x[1], reverse=True):
            logging.info(f" - {k}: {v}개")
    if not dry_run and summary_fixes:
        logging.info("수정 요약(적용 빈도 상위):")
        for k, v in sorted(summary_fixes.items(), key=lambda x: x[1], reverse=True):
            logging.info(f" + {k}: {v}개")
    logging.info("=" * 60)


if __name__ == "__main__":
    main()
