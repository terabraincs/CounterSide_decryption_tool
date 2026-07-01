# counterside_decryption_tool

카운터사이드 리소스 파일을 단계별로 처리하는 로컬 복호화/추출 도구입니다.

이 도구는 사용자의 요구사항에 맞춰 ChatGPT/OpenAI 모델의 도움을 받아 전체 또는 부분적으로 개발되었습니다.

## 폴더 구조

```text
counterside_decryption_tool/
├─ 원본 파일/
├─ 1차 복호화/
├─ 2차 복호화(TextAsset)/
│  ├─ README.md
│  ├─ JSON/
│  ├─ LUA/
│  ├─ LUAC/
│  ├─ XLSX/
│  └─ 언어별 구분/
├─ script/
│  ├─ 01_decrypt_all_files.py
│  ├─ 02_extract_textasset.py
│  ├─ 03_sorting_lang.py
│  └─ command.py
├─ README.md
├─ requirements.txt
├─ 00_install_requirements.bat
├─ 01_check_stage1.bat
├─ 02_decrypt_stage1.bat
├─ 03_extract_stage2_json.bat
├─ 03_extract_stage2_xlsx.bat
├─ 03_extract_stage2_lua.bat
├─ 03_extract_stage2_luac.bat
└─ 04_sorting_file_lang.bat
```

스크립트 실행 시 필요한 기본 폴더가 없으면 자동으로 생성됩니다.

## 빠른 사용 순서

1. `원본 파일` 폴더에 처리할 파일을 넣습니다.
2. `00_install_requirements.bat`를 한 번 실행합니다.
3. `01_check_stage1.bat`로 1차 복호화 가능 여부를 검사합니다.
4. `02_decrypt_stage1.bat`로 1차 복호화를 실행합니다.
5. TextAsset을 2차 복호화하고 원하는 형식으로 저장합니다.
   - JSON: `03_extract_stage2_json.bat`
   - XLSX: `03_extract_stage2_xlsx.bat`
   - LUA: `03_extract_stage2_lua.bat`
   - LUAC: `03_extract_stage2_luac.bat`
6. 복호화된 TextAsset을 언어별로 정리하려면 `04_sorting_file_lang.bat`를 실행합니다.

**복호화 파일이 이미 존재하는 상태에서 복호화 bat을 실행할 경우 기존 파일이 삭제됩니다.**

## 배치파일

### `00_install_requirements.bat`

필요한 Python 라이브러리를 설치합니다.

```bat
python -m pip install -r requirements.txt
```

필요한 라이브러리:

```text
UnityPy   Unity AssetBundle/TextAsset 읽기
openpyxl  XLSX 파일 생성
lz4       Unity 계열 압축 처리 보조
```

### `01_check_stage1.bat`

`원본 파일` 폴더의 파일을 검사하고 보고서를 저장합니다.

```text
1차 복호화/check_report.json
```

### `02_decrypt_stage1.bat`

파일명 기반 XOR로 1차 복호화를 시도하고, UnityFS로 확인된 파일을 `1차 복호화` 폴더에 저장합니다.

```text
1차 복호화/decrypt_report.json
```

### `03_extract_stage2_ㅁㅁ.bat`

`1차 복호화` 폴더에서 기본적으로 확장자 없는 파일만 읽고, AssetBundle 안의 TextAsset을 추출한 뒤 배치파일에 따라 파일형식을 변환하거나 원본 그대로 저장합니다.

```text
2차 복호화(TextAsset)/ㅁㅁ/
2차 복호화(TextAsset)/ㅁㅁ/index.json
2차 복호화(TextAsset)/ㅁㅁ/stage2_report.json
2차 복호화(TextAsset)/ㅁㅁ/파일1/
2차 복호화(TextAsset)/ㅁㅁ/파일1/파일.json
...
```

#### `03_extract_stage2_json.bat`
JSON으로 변환 가능한 항목을 저장합니다.
#### `03_extract_stage2_xlsx.bat`
XLSX로 변환 가능한 항목을 보기 좋은 `data` 시트 중심으로 저장합니다.  
**XLSX 변환은 많은 시간이 소요될 수 있습니다.**
#### `03_extract_stage2_lua.bat`
Lua bytecode로 확인된 항목을 가능한 범위에서 Lua 형태로 저장합니다.  
일반 Lua 스크립트는 원본 소스와 동일하게 복원되지 않을 수 있으며, 가능한 경우 문자열/상수/구조 정보를 담은 best-effort 결과로 저장됩니다.

#### `03_extract_stage2_luac.bat`

Lua bytecode로 확인된 항목을 `.luac` 파일로 저장합니다.

### `04_sorting_file_lang.bat`

각 형식 폴더의 index.json을 보고 2차 복호화 파일을 복사하여 언어별로 정리합니다.

```text
2차 복호화(TextAsset)/언어별 구분/
2차 복호화(TextAsset)/언어별 구분/JSON/...
...
```

## 스크립트 직접 실행 옵션

### 1차 복호화

```bat
python "script\01_decrypt_all_files.py" "원본 파일" -o "1차 복호화"
```

옵션:

```text
-o, --output       1차 결과 폴더
--check-only       실제 복호화 파일은 저장하지 않고 검사 report만 생성
--write-mode       replace, skip, append 중 선택. 기본값은 replace
--quiet            파일별 진행 로그를 숨김
```

1차 스크립트는 기본적으로 현재 처리 중인 파일과 성공/스킵/오류 상태를 콘솔에 출력합니다.
`--check-only`에서는 `--write-mode replace`여도 기존 1차 결과 파일을 삭제하지 않고 `check_report.json`만 갱신합니다.

### 2차 TextAsset 추출

```bat
python "script\02_extract_textasset.py" "1차 복호화" -o "2차 복호화(TextAsset)" --output json
```

옵션:

```text
-o, --output-dir   2차 결과 폴더
--output json      JSON으로 저장, 기본값
--output xlsx      XLSX로 저장
--output lua       Lua 형태로 저장
--output luac      LUAC bytecode로 저장
--all-files        확장자 있는 파일도 처리 대상에 포함
--xlsx-flat-sheet  XLSX 저장 시 path_value 펼침 시트도 함께 생성
--write-mode       replace, skip, append 중 선택. 기본값은 replace
--quiet            파일별 진행 로그를 숨김
```

기본 모드는 확장자 없는 파일만 2차 처리 대상으로 봅니다. 확장자 있는 파일까지 검사하려면 `--all-files`를 사용합니다.
XLSX는 기본적으로 `data` 시트를 첫 시트로 만들고, `data`가 2칸짜리 목록이면 `key`, `text` 표로 저장합니다. `--xlsx-flat-sheet`를 사용하면 JSON 전체를 `path`, `value_type`, `value` 형태로 펼친 `path_value` 시트도 추가합니다.
2차 스크립트는 기본적으로 현재 처리 중인 파일과 저장/스킵/오류 개수를 콘솔에 출력합니다.
`--write-mode replace`는 실행한 출력 형식 폴더만 비우고 다시 채웁니다. 예를 들어 JSON 실행 시 `JSON/`만 비우며 `XLSX/`, `LUA/`, `LUAC/`, `언어별 구분/`은 건드리지 않습니다.

### 언어별 분류

```bat
python "script\03_sorting_lang.py" "2차 복호화(TextAsset)"
```

옵션:

```text
--write-mode       replace, skip, append 중 선택. 기본값은 replace
--quiet            파일별 진행 로그를 숨김
```

`JSON/index.json`, `XLSX/index.json`, `LUA/index.json`, `LUAC/index.json`에 기록된 `language_code`, `language_token`, `language_folder` 정보를 사용합니다.  
`--write-mode replace`는 `언어별 구분/` 폴더만 비우고 다시 정리합니다.

## 공통 저장 방식:

```text
replace   기존 결과 폴더를 비우고 이번 실행 결과로 다시 채움, 기본값
skip      같은 이름의 결과 파일이 있으면 기존 파일을 유지하고 새로 저장하지 않음
append    같은 이름의 결과 파일이 있으면 _1, _2를 붙여 계속 추가
```

## 언어 코드

| language_code | 의미 |
|---|---|
| `ko` | 한국어 |
| `en` | 영어 |
| `ja` | 일본어 |
| `zh-Hant` | 중국어 번체 |
| `zh-Hans` | 중국어 간체 |
| `th` | 태국어 |
| `de` | 독일어 |
| `fr` | 프랑스어 |
| `vi` | 베트남어 |
| `dev` | 개발/테스트 |
| `unknown` | 언어 판별 불가 |

## 주의사항

- 1차 복호화는 파일명으로 키를 계산하므로 원본 파일명은 바꾸지 않는 것이 좋습니다.
- 2차 처리는 UnityPy로 AssetBundle의 TextAsset을 읽고, TextAsset의 `m_Script` 값을 처리합니다.
- TextAsset 데이터가 Lua bytecode로 확인되지 않으면 `skipped_not_luac`로 report에 기록합니다.
- JSON/XLSX 모드에서는 정적 테이블 또는 문자열 목록처럼 변환 가능한 구조만 파일로 저장하고, 문자열/테이블 구분은 report의 `category` 값에 기록합니다.
- XLSX는 Excel 셀 제한 때문에 한 셀의 문자열이 너무 길면 끝에 `... [truncated]`를 붙이고 잘라 저장합니다.
- LUA/LUAC 모드에서도 Lua bytecode로 확인되지 않는 항목은 저장하지 않고 report에 기록합니다.
- `.lua` 출력은 완전한 원본 소스 복원이 아니라 가능한 범위의 변환 결과입니다.
- 결과가 비어 있거나 적게 나오는 경우 실행한 형식 폴더 안의 `stage2_report.json`에서 `status`, `message`, `payload_decode_method`를 먼저 확인하세요.
- `ab_script_string_table`의 경우 파일이 상당히 크기 때문에 2차 복호화에 상당한 시간이 소요되며 이는 버그가 아닙니다.
