@echo off
set VERSION=0.0.1
set NAME=video_compressor_pyav_v%VERSION%

REM Clean previous build
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist %NAME%.spec del %NAME%.spec

echo ✅ Activating virtual environment...
call venv\\Scripts\\activate

REM Build executable
pyinstaller ^
--name "%NAME%" ^
--onefile ^
--windowed ^
pyav.py

pause
