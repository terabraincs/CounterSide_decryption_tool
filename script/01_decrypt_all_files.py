#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path
from typing import Any

from command import (
    STAGE2_DIR_NAME,
    WRITE_MODES,
    clear_directory_contents,
    ensure_base_dirs,
    is_relative_to,
    normalize_write_mode,
    output_path_for_write_mode,
    project_root_from_script,
    relative_posix,
    write_json,
)

DECRYPT_HEADER_SIZE = 212


def get_bundle_masks(stem_lower: str) -> list[int]:
    digest = hashlib.md5(stem_lower.encode("utf-8")).hexdigest()
    return [
        int(digest[0:16], 16),
        int(digest[16:32], 16),
        int(digest[0:8] + digest[16:24], 16),
        int(digest[8:16] + digest[24:32], 16),
    ]


def xor_header_in_place(buf: bytearray, stem_lower: str) -> None:
    masks = get_bundle_masks(stem_lower)
    limit = min(len(buf), DECRYPT_HEADER_SIZE)
    offset = 0
    mask_index = 0
    while offset < limit:
        mask = masks[mask_index]
        remaining = limit - offset
        if remaining >= 8:
            value = struct.unpack_from("<Q", buf, offset)[0]
            struct.pack_into("<Q", buf, offset, value ^ mask)
            offset += 8
        else:
            key_byte = mask & 0xFF
            for i in range(remaining):
                buf[offset + i] ^= key_byte
            offset += remaining
        mask_index = (mask_index + 1) % len(masks)


def header_kind(data: bytes) -> str:
    if data.startswith(b"UnityFS"):
        return "UnityFS"
    if data.startswith(b"UnityWeb"):
        return "UnityWeb"
    if data.startswith(b"UnityRaw"):
        return "UnityRaw"
    if data.startswith(b"\x1bLua"):
        return "LUAC"
    return "unknown"


def iter_input_files(input_path: Path, output_dir: Path) -> tuple[Path, list[Path]]:
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    if input_path.is_file():
        return input_path.parent, [input_path]
    if not input_path.is_dir():
        raise FileNotFoundError(f"입력 파일/폴더를 찾을 수 없습니다: {input_path}")

    files: list[Path] = []
    for path in sorted(input_path.rglob("*")):
        if not path.is_file():
            continue
        if is_relative_to(path, output_dir):
            continue
        files.append(path)
    return input_path, files


def save_stage1_bytes(out: Path, output_dir: Path, data: bytes, write_mode: str, row: dict[str, Any]) -> bool:
    final_path = output_path_for_write_mode(out, write_mode)
    if final_path is None:
        row["status"] = "skipped_existing"
        row["output_file"] = relative_posix(out, output_dir)
        row["message"] = "기존 결과 파일이 있어서 저장하지 않았습니다."
        return False

    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_bytes(data)
    row["output_file"] = relative_posix(final_path, output_dir)
    return True


def check_or_decrypt_file(path: Path, root: Path, output_dir: Path, check_only: bool, write_mode: str) -> dict[str, Any]:
    rel = path.relative_to(root).as_posix()
    row: dict[str, Any] = {
        "relative_path": rel,
        "input_file": str(path),
        "size": path.stat().st_size,
        "original_header": "",
        "xor_header": "",
        "status": "",
        "output_file": "",
        "message": "",
    }

    try:
        raw = path.read_bytes()
        row["original_header"] = header_kind(raw)

        if raw.startswith(b"UnityFS"):
            row["xor_header"] = "not_needed"
            row["status"] = "already_unityfs"
            if not check_only:
                out = output_dir / rel
                save_stage1_bytes(out, output_dir, raw, write_mode, row)
            return row

        buf = bytearray(raw)
        xor_header_in_place(buf, path.stem.lower())
        decoded = bytes(buf)
        row["xor_header"] = header_kind(decoded)

        if decoded.startswith(b"UnityFS"):
            row["status"] = "ok"
            if not check_only:
                out = output_dir / rel
                save_stage1_bytes(out, output_dir, decoded, write_mode, row)
        else:
            row["status"] = "skipped_not_unityfs_after_xor"
            row["message"] = "1차 XOR 후 UnityFS가 아니어서 저장하지 않았습니다."
        return row
    except Exception as exc:
        row["status"] = "error"
        row["message"] = f"{type(exc).__name__}: {exc}"
        return row


def main() -> int:
    project_root = project_root_from_script(__file__)
    ensure_base_dirs(project_root)

    parser = argparse.ArgumentParser(description="CounterSide stage1 UnityFS decrypt/check tool")
    parser.add_argument("input", nargs="?", default=str(project_root / "원본 파일"), help="input file or folder")
    parser.add_argument("-o", "--output", default=str(project_root / "1차 복호화"), help="output folder")
    parser.add_argument("--check-only", action="store_true", help="check only; do not write decrypted files")
    parser.add_argument("--write-mode", choices=WRITE_MODES, default="replace", help="replace, skip, or append output files")
    parser.add_argument("--quiet", action="store_true", help="hide per-file progress logs")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_mode = normalize_write_mode(args.write_mode)
    cleared_entries = 0

    if not args.check_only and write_mode == "replace":
        cleared_entries = clear_directory_contents(
            output_dir,
            allowed_parent=output_dir.resolve().parent,
            protected_paths=[
                project_root,
                project_root / "원본 파일",
                project_root / STAGE2_DIR_NAME,
                project_root / "script",
                input_path,
            ],
        )

    root_input, files = iter_input_files(input_path, output_dir)
    show_logs = not args.quiet
    mode_text = "검사" if args.check_only else "복호화"

    if show_logs:
        print(f"1차 {mode_text} 작업을 시작합니다.", flush=True)
        print(f"입력: {input_path}", flush=True)
        print(f"출력: {output_dir}", flush=True)
        print(f"모드: {mode_text}", flush=True)
        print(f"저장 방식: {write_mode}", flush=True)
        if not args.check_only and write_mode == "replace":
            print(f"기존 출력 정리: {cleared_entries}개 항목 삭제", flush=True)
        print(f"스캔한 파일 수: {len(files)}개", flush=True)
        print("-" * 60, flush=True)

    rows: list[dict[str, Any]] = []
    for index, path in enumerate(files, start=1):
        rel = path.relative_to(root_input).as_posix()
        if show_logs:
            print(f"[{index}/{len(files)}] 처리 중: {rel}", flush=True)

        row = check_or_decrypt_file(path, root_input, output_dir, args.check_only, write_mode)
        rows.append(row)

        if show_logs:
            status = row.get("status", "")
            original_header = row.get("original_header", "")
            xor_header = row.get("xor_header", "")
            output_file = row.get("output_file", "")
            message = row.get("message", "")

            details: list[str] = []
            if original_header:
                details.append(f"original={original_header}")
            if xor_header:
                details.append(f"xor={xor_header}")
            if output_file:
                details.append(f"output={output_file}")
            if message:
                details.append(str(message))

            detail_text = f" / {' / '.join(details)}" if details else ""
            print(f"  -> {status}{detail_text}", flush=True)

    if show_logs:
        print("-" * 60, flush=True)

    report = {
        "tool": "01_decrypt_all_files.py",
        "mode": "check" if args.check_only else "decrypt",
        "input": str(input_path),
        "output_dir": str(output_dir),
        "write_mode": write_mode,
        "cleared_entries": cleared_entries,
        "quiet": bool(args.quiet),
        "total_files": len(rows),
        "ok_count": sum(1 for r in rows if r["status"] in {"ok", "already_unityfs"}),
        "skipped_count": sum(1 for r in rows if str(r["status"]).startswith("skipped")),
        "error_count": sum(1 for r in rows if r["status"] == "error"),
        "files": rows,
    }

    report_name = "check_report.json" if args.check_only else "decrypt_report.json"
    report_path = output_dir / report_name
    write_json(report_path, report)
    print(f"완료: {report_path}")
    print(
        f"처리 대상: {report['total_files']}개 / "
        f"성공: {report['ok_count']}개 / "
        f"스킵: {report['skipped_count']}개 / "
        f"오류: {report['error_count']}개"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
