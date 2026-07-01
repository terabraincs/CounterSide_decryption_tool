#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from command import (
    STAGE2_FORMAT_DIRS,
    WRITE_MODES,
    clear_directory_contents,
    copy_file,
    ensure_base_dirs,
    ensure_stage2_dirs,
    normalize_write_mode,
    output_path_for_write_mode,
    project_root_from_script,
    read_json,
    relative_posix,
    sanitize_filename,
    write_json,
)


def load_stage2_records(stage2_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    index_sources: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for output_type, type_dir in sorted(STAGE2_FORMAT_DIRS.items()):
        index_path = stage2_dir / type_dir / "index.json"
        if not index_path.exists():
            continue

        index = read_json(index_path)
        typed_records: list[dict[str, Any]] = []
        for item in index.get("files", []):
            if not isinstance(item, dict):
                continue
            record = dict(item)
            record["output_type"] = str(record.get("output_type") or output_type).lower()
            typed_records.append(record)

        index_sources.append({
            "output_type": output_type,
            "index_path": str(index_path),
            "file_count": len(typed_records),
        })
        records.extend(typed_records)

    if index_sources:
        return index_sources, records

    legacy_index_path = stage2_dir / "index.json"
    if legacy_index_path.exists():
        index = read_json(legacy_index_path)
        legacy_records = [r for r in index.get("files", []) if isinstance(r, dict)]
        return [{
            "output_type": str(index.get("output_type") or "unknown"),
            "index_path": str(legacy_index_path),
            "file_count": len(legacy_records),
            "legacy_top_level_index": True,
        }], legacy_records

    expected = ", ".join(str(stage2_dir / folder / "index.json") for folder in STAGE2_FORMAT_DIRS.values())
    raise FileNotFoundError(f"형식별 index.json을 찾을 수 없습니다: {expected}")


def get_existing_records(stage2_dir: Path, records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        rel = str(record.get("file") or "")
        output_type = str(record.get("output_type") or "").lower()
        if not rel or output_type not in STAGE2_FORMAT_DIRS:
            continue
        if not (stage2_dir / rel).exists():
            continue
        grouped.setdefault(output_type, []).append(record)
    return grouped


def destination_for_record(stage2_dir: Path, output_type: str, records: list[dict[str, Any]], record: dict[str, Any]) -> Path:
    type_dir = STAGE2_FORMAT_DIRS[output_type]
    languages = sorted({str(r.get("language_folder") or "unknown") for r in records})
    use_language_folder = languages != ["unknown"]

    rel = Path(str(record["file"]))
    rel_parts = rel.parts[1:] if rel.parts and rel.parts[0].upper() == type_dir else rel.parts
    if len(rel_parts) >= 4 and rel_parts[0] == "by_source" and rel_parts[2] == "by_asset":
        rel_parts = (rel_parts[1], *rel_parts[3:])
    elif len(rel_parts) >= 5 and rel_parts[0] == "by_source" and rel_parts[3] == "by_asset":
        rel_parts = (rel_parts[1], *rel_parts[4:])
    elif len(rel_parts) >= 2 and rel_parts[0] == "by_source":
        rel_parts = rel_parts[1:]

    if use_language_folder:
        language_folder = sanitize_filename(str(record.get("language_folder") or "unknown"))
        return stage2_dir / "언어별 구분" / type_dir / language_folder / Path(*rel_parts)
    return stage2_dir / "언어별 구분" / type_dir / Path(*rel_parts)


def main() -> int:
    project_root = project_root_from_script(__file__)
    ensure_base_dirs(project_root)

    parser = argparse.ArgumentParser(description="Sort existing stage2 outputs by language")
    parser.add_argument("stage2_dir", nargs="?", default=str(project_root / "2차 복호화(TextAsset)"), help="stage2 folder")
    parser.add_argument("--write-mode", choices=WRITE_MODES, default="replace", help="replace, skip, or append sorted files")
    parser.add_argument("--quiet", action="store_true", help="hide per-file progress logs")
    args = parser.parse_args()

    stage2_dir = Path(args.stage2_dir)
    ensure_stage2_dirs(stage2_dir, create_format_dirs=False)
    write_mode = normalize_write_mode(args.write_mode)
    log_progress = not args.quiet
    lang_root = stage2_dir / "언어별 구분"
    cleared_entries = 0

    if log_progress:
        print("언어별 분류 작업을 시작합니다.", flush=True)
        print(f"입력: {stage2_dir}", flush=True)
        print(f"출력: {lang_root}", flush=True)
        print(f"저장 방식: {write_mode}", flush=True)

    if write_mode == "replace":
        if log_progress:
            print("기존 언어별 구분 폴더를 정리합니다...", flush=True)
        cleared_entries = clear_directory_contents(
            lang_root,
            allowed_parent=stage2_dir,
            protected_paths=[
                stage2_dir,
                *[stage2_dir / folder for folder in STAGE2_FORMAT_DIRS.values()],
            ],
        )
        if log_progress:
            print(f"기존 출력 정리: {cleared_entries}개 항목 삭제", flush=True)

    index_sources, records = load_stage2_records(stage2_dir)
    grouped = get_existing_records(stage2_dir, records)

    if log_progress:
        existing_count = sum(len(items) for items in grouped.values())
        print(f"읽은 index 수: {len(index_sources)}개", flush=True)
        for source in index_sources:
            print(
                f"  - {source.get('output_type')}: {source.get('file_count', 0)}개 / {source.get('index_path')}",
                flush=True,
            )
        print(f"실제로 존재하는 분류 대상 파일 수: {existing_count}개", flush=True)
        print("-" * 60, flush=True)

    report_paths: list[Path] = []
    copied_total = 0
    skipped_existing_total = 0

    grouped_items = sorted(grouped.items())
    for format_index, (output_type, typed_records) in enumerate(grouped_items, 1):
        type_dir = STAGE2_FORMAT_DIRS[output_type]
        languages = sorted({str(r.get("language_folder") or "unknown") for r in typed_records})
        flatten_unknown = languages == ["unknown"]
        copied = 0
        skipped_existing = 0
        copied_records: list[dict[str, Any]] = []
        report_files: list[dict[str, Any]] = []
        source_index = next(
            (dict(source) for source in index_sources if str(source.get("output_type") or "").lower() == output_type),
            None,
        )

        if log_progress:
            language_text = ", ".join(languages)
            print(
                f"[{format_index}/{len(grouped_items)}] {type_dir} 형식 분류 시작: {len(typed_records)}개 / 언어: {language_text}",
                flush=True,
            )

        for record_index, record in enumerate(typed_records, 1):
            src = stage2_dir / str(record["file"])
            dst = destination_for_record(stage2_dir, output_type, typed_records, record)
            if log_progress:
                print(f"  [{record_index}/{len(typed_records)}] 처리 중: {record['file']}", flush=True)
            final_dst = output_path_for_write_mode(dst, write_mode)
            if final_dst is None:
                final_dst = dst
                skipped_existing += 1
                sort_status = "skipped_existing"
            else:
                copy_file(src, final_dst)
                copied += 1
                sort_status = "copied"

            copied_record = dict(record)
            copied_record["sorted_from"] = str(record["file"])
            copied_record["file"] = relative_posix(final_dst, stage2_dir)
            copied_record["sort_status"] = sort_status
            copied_record["unknown_folder_flattened"] = flatten_unknown
            copied_records.append(copied_record)

            if log_progress:
                print(f"    -> {sort_status}: {relative_posix(final_dst, stage2_dir)}", flush=True)

            report_files.append({
                "output_type": output_type,
                "language_code": record.get("language_code", "unknown"),
                "language_folder": record.get("language_folder", "unknown"),
                "source": str(record["file"]),
                "destination": relative_posix(final_dst, stage2_dir),
                "sort_status": sort_status,
                "unknown_folder_flattened": flatten_unknown,
            })

        format_report = {
            "tool": "03_sorting_lang.py",
            "stage2_dir": str(stage2_dir),
            "output_type": output_type,
            "folder": type_dir,
            "source_index": source_index,
            "write_mode": write_mode,
            "quiet": bool(args.quiet),
            "cleared_entries": cleared_entries,
            "file_count": copied + skipped_existing,
            "copied_count": copied,
            "skipped_existing_count": skipped_existing,
            "languages": languages,
            "unknown_only_flattened": flatten_unknown,
            "files": report_files,
        }
        format_index_data = {
            "tool": "03_sorting_lang.py",
            "source_index": source_index,
            "output_type": output_type,
            "write_mode": write_mode,
            "quiet": bool(args.quiet),
            "cleared_entries": cleared_entries,
            "file_count": len(copied_records),
            "files": copied_records,
        }

        format_lang_root = lang_root / type_dir
        report_path = format_lang_root / "language_sort_report.json"
        index_path = format_lang_root / "index.json"
        write_json(report_path, format_report)
        write_json(index_path, format_index_data)
        report_paths.append(report_path)
        copied_total += copied
        skipped_existing_total += skipped_existing

        if log_progress:
            print(f"{type_dir} 형식 완료: 복사 {copied}개, 기존 유지 {skipped_existing}개", flush=True)
            print(f"보고서: {report_path}", flush=True)
            print("-" * 60, flush=True)

    if report_paths:
        print("완료: 형식별 언어 분류 보고서를 저장했습니다.")
        for report_path in report_paths:
            print(f"보고서: {report_path}")
    else:
        print("완료: 분류할 파일이 없습니다.")
    print(f"새로 복사한 파일 수: {copied_total}개")
    if skipped_existing_total:
        print(f"기존 유지 파일 수: {skipped_existing_total}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
