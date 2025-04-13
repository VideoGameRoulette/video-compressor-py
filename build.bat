
@echo off
echo.
echo 🔄 Cleaning previous builds...
rmdir /s /q build
rmdir /s /q dist

echo.
echo ✅ Activating virtual environment...
call venv\Scripts\activate

echo.
echo 🛠️ Building video_compressor_gui.exe with PyInstaller...
pyinstaller ^
--name "video_compressor_gui" ^
--onefile ^
--windowed ^
--add-data "ffmpeg.exe;." ^
--add-data "ffprobe.exe;." ^
video_compressor_gui_ffprobe.py

echo.
echo 🎉 Done! Check the dist\video_compressor_gui.exe file.
pause
