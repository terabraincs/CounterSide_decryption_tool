#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any, Iterable

PROJECT_DIR_NAME = "counterside_decryption_tool"
ORIGINAL_DIR_NAME = "원본 파일"
STAGE1_DIR_NAME = "1차 복호화"
STAGE2_DIR_NAME = "2차 복호화(TextAsset)"
SCRIPT_DIR_NAME = "script"

STAGE2_FORMAT_DIRS = {
    "json": "JSON",
    "xlsx": "XLSX",
    "lua": "LUA",
    "luac": "LUAC",
}

WRITE_MODES = ("replace", "skip", "append")

LANGUAGE_DEFINITIONS = {
    "KOREA": {"code": "ko", "folder": "ko", "label": "한국어"},
    "KOR": {"code": "ko", "folder": "ko", "label": "한국어"},
    "ENG": {"code": "en", "folder": "en", "label": "영어"},
    "ENGLISH": {"code": "en", "folder": "en", "label": "영어"},
    "JPN": {"code": "ja", "folder": "ja", "label": "일본어"},
    "JAPAN": {"code": "ja", "folder": "ja", "label": "일본어"},
    "TWN": {"code": "zh-Hant", "folder": "zh-Hant", "label": "중국어 번체"},
    "SCN": {"code": "zh-Hans", "folder": "zh-Hans", "label": "중국어 간체"},
    "CHN": {"code": "zh-Hans", "folder": "zh-Hans", "label": "중국어 간체"},
    "THA": {"code": "th", "folder": "th", "label": "태국어"},
    "DEU": {"code": "de", "folder": "de", "label": "독일어"},
    "GERMAN": {"code": "de", "folder": "de", "label": "독일어"},
    "FRA": {"code": "fr", "folder": "fr", "label": "프랑스어"},
    "FRENCH": {"code": "fr", "folder": "fr", "label": "프랑스어"},
    "VTN": {"code": "vi", "folder": "vi", "label": "베트남어"},
    "VIETNAM": {"code": "vi", "folder": "vi", "label": "베트남어"},
    "DEV": {"code": "dev", "folder": "dev", "label": "개발/테스트"},
}

LANGUAGE_PRIORITY = [
    "KOREA", "KOR", "ENG", "ENGLISH", "JPN", "JAPAN", "TWN", "SCN", "CHN",
    "THA", "DEU", "GERMAN", "FRA", "FRENCH", "VTN", "VIETNAM", "DEV",
]

KNOWN_NAME_TOKENS = {
    "LUA", "NKM", "NKC", "STRING", "TABLE", "TEMPLET", "TEMPLATE", "SCRIPT",
    "UNIT", "SKILL", "ITEM", "EQUIP", "SHOP", "MISSION", "DUNGEON", "MAP",
    "WORLD", "WORLDMAP", "DESC", "TOOLTIP", "STORY", "EPISODE", "CUTSCENE",
    "EVENT", "NORMAL", "MOB", "NPC", "BOSS", "BATTLE", "PVP", "PVE", "RAID",
    "DIVE", "SUPPLY", "CHALLENGE", "GUILD", "ATTENDANCE", "CONTRACT",
    "COLLECTION", "SKIN", "VOICE", "SUBTITLE", "MAIL", "SYSTEM", "TUTORIAL",
    "ACADEMY", "UI", "COMMON", "CONST", "DATA", *LANGUAGE_DEFINITIONS.keys(),
}

EXCEL_FORBIDDEN_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
EXCEL_CELL_MAX_CHARS = 32767
EXCEL_TRUNCATED_MARKER = " ... [truncated]"


def project_root_from_script(script_file: str | Path) -> Path:
    return Path(script_file).resolve().parent.parent


def ensure_base_dirs(root: Path) -> None:
    for rel in [ORIGINAL_DIR_NAME, STAGE1_DIR_NAME, STAGE2_DIR_NAME, SCRIPT_DIR_NAME]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def ensure_stage2_dirs(stage2_dir: Path, *, create_format_dirs: bool = True) -> None:
    stage2_dir.mkdir(parents=True, exist_ok=True)
    if create_format_dirs:
        for folder in STAGE2_FORMAT_DIRS.values():
            (stage2_dir / folder).mkdir(parents=True, exist_ok=True)
    (stage2_dir / "언어별 구분").mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text + ("\n" if not compact else ""), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative_posix(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def normalize_write_mode(write_mode: str) -> str:
    mode = str(write_mode or "replace").lower()
    if mode not in WRITE_MODES:
        raise ValueError(f"unknown write mode: {write_mode}")
    return mode


def clear_directory_contents(target_dir: Path, *, allowed_parent: Path, protected_paths: Iterable[Path] = ()) -> int:
    target = target_dir.resolve()
    allowed = allowed_parent.resolve()
    protected = [path.resolve() for path in protected_paths]

    if target == allowed or not is_relative_to(target, allowed):
        raise RuntimeError(f"비울 수 없는 폴더입니다: {target}")
    for path in protected:
        if target == path or is_relative_to(path, target):
            raise RuntimeError(f"중요 폴더를 포함하므로 비울 수 없습니다: {target}")

    target.mkdir(parents=True, exist_ok=True)
    removed = 0
    for child in target.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed += 1
    return removed


def output_path_for_write_mode(path: Path, write_mode: str) -> Path | None:
    mode = normalize_write_mode(write_mode)
    if mode == "append":
        return unique_path(path, overwrite=False)
    if mode == "skip" and path.exists():
        return None
    return path


def sanitize_filename(name: Any, max_len: int = 160, fallback: str = "unnamed") -> str:
    text = str(name).replace("/", "_").replace("\\", "_")
    text = re.sub(r"[^0-9A-Za-z가-힣._()\[\] -]+", "_", text)
    text = re.sub(r"_+", "_", text).strip(" ._")
    if not text:
        text = fallback
    return text[:max_len]


def unique_path(path: Path, *, overwrite: bool = False) -> Path:
    if overwrite or not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for i in range(1, 10000):
        candidate = path.with_name(f"{stem}_{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"중복 파일명을 만들 수 없습니다: {path}")


def safe_source_folder_name(path: Path, root: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.name
    return sanitize_filename(rel.replace("/", "__"), max_len=180)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def caesar_letters_only(text: str, shift: int) -> str:
    out: list[str] = []
    for ch in text:
        if "A" <= ch <= "Z":
            out.append(chr((ord(ch) - 65 + shift) % 26 + 65))
        elif "a" <= ch <= "z":
            out.append(chr((ord(ch) - 97 + shift) % 26 + 97))
        else:
            out.append(ch)
    return "".join(out)


def score_decoded_asset_name(candidate: str) -> int:
    upper = candidate.upper()
    tokens = [t for t in re.split(r"[_\-.\s]+", upper) if t]
    token_set = set(tokens)
    score = 0
    if upper.startswith("LUA_"):
        score += 180
    if upper.startswith(("NKM_", "NKC_")):
        score += 120
    for token in token_set:
        if token in KNOWN_NAME_TOKENS:
            score += 18
        if token in LANGUAGE_DEFINITIONS:
            score += 30
    if len(tokens) >= 3:
        score += min(len(tokens), 12)
    letters = [ch for ch in upper if "A" <= ch <= "Z"]
    if letters:
        vowel_ratio = sum(ch in "AEIOU" for ch in letters) / len(letters)
        if 0.20 <= vowel_ratio <= 0.52:
            score += 8
        elif vowel_ratio < 0.10:
            score -= 20
    return score


def best_decode_asset_name(encrypted_name: str) -> tuple[str, int | None, str]:
    candidates = []
    for shift in range(26):
        decoded = caesar_letters_only(encrypted_name, shift)
        candidates.append((score_decoded_asset_name(decoded), decoded, shift))
    score, decoded, shift = max(candidates, key=lambda x: (x[0], -x[2]))
    if score >= 80:
        return decoded, shift, "caesar_letters_best_score"
    return encrypted_name, None, "original"


def detect_language(decoded_asset_name: str) -> dict[str, str]:
    tokens = set(re.split(r"[_\-.\s]+", decoded_asset_name.upper()))
    for token in LANGUAGE_PRIORITY:
        if token in tokens:
            info = LANGUAGE_DEFINITIONS[token]
            return {
                "language_code": info["code"],
                "language_token": token,
                "language_folder": info["folder"],
                "language_label": info["label"],
            }
    return {
        "language_code": "unknown",
        "language_token": "UNKNOWN",
        "language_folder": "unknown",
        "language_label": "미분류",
    }


def clean_excel_value(value: Any) -> Any:
    if isinstance(value, str):
        text = EXCEL_FORBIDDEN_RE.sub("", value)
        if len(text) > EXCEL_CELL_MAX_CHARS:
            keep = EXCEL_CELL_MAX_CHARS - len(EXCEL_TRUNCATED_MARKER)
            return text[:keep] + EXCEL_TRUNCATED_MARKER
        return text
    if isinstance(value, list):
        return [clean_excel_value(v) for v in value]
    if isinstance(value, dict):
        return {clean_excel_value(k): clean_excel_value(v) for k, v in value.items()}
    return value


def format_scalar_for_lua(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return repr(value)
    text = str(value)
    text = text.replace("\\", "\\\\").replace("\r", "\\r").replace("\n", "\\n").replace('"', '\\"')
    return f'"{text}"'


def lua_key_repr(key: Any) -> str:
    if isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
        return key
    return f"[{format_scalar_for_lua(key)}]"


def to_lua_literal(value: Any, indent: int = 0) -> str:
    sp = " " * indent
    sp2 = " " * (indent + 4)
    if isinstance(value, list):
        if not value:
            return "{}"
        lines = ["{"]
        for item in value:
            lines.append(f"{sp2}{to_lua_literal(item, indent + 4)},")
        lines.append(f"{sp}}}")
        return "\n".join(lines)
    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for key, item in value.items():
            lines.append(f"{sp2}{lua_key_repr(key)} = {to_lua_literal(item, indent + 4)},")
        lines.append(f"{sp}}}")
        return "\n".join(lines)
    return format_scalar_for_lua(value)


def iter_flatten_path_value(value: Any, path: str = "") -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield {"path": path or "$", "value_type": "object", "value": "{}"}
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from iter_flatten_path_value(child, child_path)
    elif isinstance(value, list):
        if not value:
            yield {"path": path or "$", "value_type": "array", "value": "[]"}
        for i, child in enumerate(value, start=1):
            child_path = f"{path}[{i}]" if path else f"[{i}]"
            yield from iter_flatten_path_value(child, child_path)
    else:
        if value is None:
            value_type = "nil"
            out = ""
        elif isinstance(value, bool):
            value_type = "boolean"
            out = value
        elif isinstance(value, int):
            value_type = "integer"
            out = value
        elif isinstance(value, float):
            value_type = "number"
            out = value
        else:
            value_type = "string"
            out = value
        yield {"path": path or "$", "value_type": value_type, "value": out}


def flatten_path_value(value: Any, path: str = "") -> list[dict[str, Any]]:
    return list(iter_flatten_path_value(value, path))


def write_stage2_readme(stage2_dir: Path) -> None:
    stage2_dir.mkdir(parents=True, exist_ok=True)
    text = """# 2차 복호화(TextAsset) 결과 안내

이 폴더는 1차 복호화된 Unity AssetBundle에서 TextAsset을 추출하고, TextAsset 내부 데이터를 JSON/LUA/LUAC/XLSX 형태로 저장한 결과를 담습니다.

## 폴더 의미

- `JSON/`: JSON 결과와 JSON 전용 `index.json`, `stage2_report.json`을 저장합니다.
- `LUA/`: Lua 결과와 LUA 전용 `index.json`, `stage2_report.json`을 저장합니다.
- `LUAC/`: LUAC 결과와 LUAC 전용 `index.json`, `stage2_report.json`을 저장합니다.
- `XLSX/`: XLSX 결과와 XLSX 전용 `index.json`, `stage2_report.json`을 저장합니다.
- `언어별 구분/`: `04_sorting_file_lang.bat` 실행 시 형식별 `index.json` 정보를 기준으로 새로 정리한 결과와 형식별 분류 report를 저장합니다.

각 출력 형식의 결과 파일은 해당 형식 폴더의 `원본묶음/` 아래에 저장합니다.  
예를 들어 JSON 결과는 `JSON/Assetbundles_ab_script/파일.json` 형태로 저장합니다.  
구분 정보는 형식별 `index.json`과 `stage2_report.json`의 `category` 값에 기록합니다.  

## 관리 파일

- `JSON/index.json`, `XLSX/index.json`, `LUA/index.json`, `LUAC/index.json`: 형식별 저장 결과와 언어 정보를 기록합니다.
- `JSON/stage2_report.json`, `XLSX/stage2_report.json`, `LUA/stage2_report.json`, `LUAC/stage2_report.json`: 형식별 처리 대상, 성공, 스킵, 오류 사유를 기록합니다.
- `언어별 구분/JSON/index.json`, `언어별 구분/XLSX/index.json`, `언어별 구분/LUA/index.json`, `언어별 구분/LUAC/index.json`: 언어별 분류 후 형식별 결과를 기록합니다.
- `언어별 구분/JSON/language_sort_report.json`, `언어별 구분/XLSX/language_sort_report.json`, `언어별 구분/LUA/language_sort_report.json`, `언어별 구분/LUAC/language_sort_report.json`: 언어별 분류 처리 결과를 형식별로 기록합니다.

## 저장 방식

- `replace`: 실행한 출력 형식 폴더를 비우고 이번 실행 결과로 다시 채웁니다. 기본값입니다.
- `skip`: 같은 이름의 결과 파일이 있으면 기존 파일을 유지하고 새로 저장하지 않습니다.
- `append`: 같은 이름의 결과 파일이 있으면 `_1`, `_2`를 붙여 계속 추가합니다.

## 주의사항

- `.lua` 출력은 완전한 디컴파일러가 아니라 가능한 범위의 복원 결과입니다.
- JSON/XLSX 모드에서는 스크립트성 Lua bytecode나 구조를 알 수 없는 항목을 파일로 저장하지 않고 report에 기록합니다.
- XLSX 모드는 기본적으로 보기용 `data` 시트를 첫 시트로 저장하고, `--xlsx-flat-sheet` 사용 시 `path_value` 펼침 시트를 추가합니다.
- XLSX는 Excel 셀 제한 때문에 한 셀의 문자열이 너무 길면 끝에 `... [truncated]`를 붙이고 잘라 저장합니다.
- LUA/LUAC 모드에서는 Lua bytecode로 확인된 항목을 가능한 한 저장합니다.
- 결과 검수는 각 형식 폴더의 `stage2_report.json`과 원본 데이터를 함께 확인하는 것을 권장합니다.
"""
    (stage2_dir / "README.md").write_text(text, encoding="utf-8", newline="\n")
