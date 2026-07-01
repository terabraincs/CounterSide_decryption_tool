@echo off
chcp 65001 >nul
cd /d "%~dp0"
python "script\02_extract_textasset.py" --output xlsx
pause
