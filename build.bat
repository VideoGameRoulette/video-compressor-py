
@echo off
setlocal EnableDelayedExpansion

set VERSION_FILE=version.txt
if not exist %VERSION_FILE% (
    echo 1.0.0 > %VERSION_FILE%
)

set /p VERSION=<%VERSION_FILE%
for /f "tokens=1-3 delims=." %%a in ("%VERSION%") do (
    set MAJOR=%%a
    set MINOR=%%b
    set PATCH=%%c
)

echo.
echo Current version: %VERSION%
echo What type of update is this?
echo 1. Major
echo 2. Minor
echo 3. Patch
set /p choice=Enter choice (1/2/3):

if "%choice%"=="1" (
    set /a MAJOR+=1
    set MINOR=0
    set PATCH=0
) else if "%choice%"=="2" (
    set /a MINOR+=1
    set PATCH=0
) else (
    set /a PATCH+=1
)

set VERSION=%MAJOR%.%MINOR%.%PATCH%
echo %VERSION% > %VERSION_FILE%
set NAME=video_compressor_ffmpeg_v%VERSION%

echo.
echo 🔄 Cleaning previous builds...
rmdir /s /q build
rmdir /s /q dist
if exist %NAME%.spec del %NAME%.spec

echo.
echo 🛠 Injecting version into ffmpeg.py...
powershell -Command "(Get-Content ffmpeg.py) -replace '__version__ = \".*?\"', '__version__ = \"%VERSION%\"' | Set-Content ffmpeg.py"

echo.
echo ✅ Activating virtual environment...
call venv\\Scripts\\activate

echo.
echo 🛠️ Building video_compressor_ffmpeg_v%VERSION% from ffmpeg.py...
pyinstaller ^
--name "video_compressor_ffmpeg_v%VERSION%" ^
--onefile ^
--windowed ^
--add-data "ffmpeg.exe;." ^
--add-data "ffprobe.exe;." ^
ffmpeg.py

echo.
echo 🎉 Done! Check the dist\\video_compressor_ffmpeg_v%VERSION%.exe file.
pause
