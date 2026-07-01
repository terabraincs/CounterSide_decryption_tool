@echo off
chcp 65001 >nul
cd /d "%~dp0"
python "script\01_decrypt_all_files.py"
pause
