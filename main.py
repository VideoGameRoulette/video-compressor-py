__version__ = "0.0.15"

import os
import subprocess
import sys
from datetime import datetime

import qdarkstyle
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QComboBox,
    QFileDialog,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)


def get_version():
    return __version__


def is_system_dark_mode():
    palette = QApplication.palette()
    return palette.color(palette.Window).value() < 128


def apply_theme(app, force_dark=None):
    settings = QSettings("CortinaKitchens", "VideoCompressor")
    if force_dark is None:
        pref = settings.value("theme")
        if pref == "dark":
            force_dark = True
        elif pref == "light":
            force_dark = False
        else:
            force_dark = is_system_dark_mode()
    settings.setValue("theme", "dark" if force_dark else "light")
    if force_dark:
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    else:
        app.setStyleSheet("")


class VideoCompressor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.version = get_version()
        self.setWindowTitle(f"Video Compressor v{self.version}")
        self.settings = QSettings("CortinaKitchens", "VideoCompressor")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.init_ui()

    def init_ui(self):
        self._create_menu()

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["File Path", "Resolution", "Duration", "Size"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.add_files_button = QPushButton("Add Videos")
        self.clear_files_button = QPushButton("Clear List")
        self.add_files_button.clicked.connect(self.add_files)
        self.clear_files_button.clicked.connect(self.clear_table)

        file_button_layout = QHBoxLayout()
        file_button_layout.addWidget(self.add_files_button)
        file_button_layout.addWidget(self.clear_files_button)

        self.output_path = QLineEdit()
        self.output_path.setText(self.settings.value("output_path", ""))
        self.browse_output = QPushButton("Output Folder")
        self.browse_output.clicked.connect(self.select_output_folder)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.browse_output)

        self.crf_combo = QComboBox()
        self.crf_combo.addItems([
            "High Quality (Large)",
            "Medium Quality",
            "Low Quality (Small)",
            "Very Low (Tiny file)"
        ])
        self.crf_map = {
            "High Quality (Large)": 18,
            "Medium Quality": 23,
            "Low Quality (Small)": 28,
            "Very Low (Tiny file)": 32,
        }

        self.res_combo = QComboBox()
        self.res_combo.addItems(["Original", "1080p", "720p", "480p"])

        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Compression Quality:"))
        settings_layout.addWidget(self.crf_combo)
        settings_layout.addWidget(QLabel("Resolution:"))
        settings_layout.addWidget(self.res_combo)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

        self.start_btn = QPushButton("Compress All Videos")
        self.start_btn.clicked.connect(self.compress_all)

        self.main_layout.addLayout(file_button_layout)
        self.main_layout.addWidget(self.table)
        self.main_layout.addLayout(output_layout)
        self.main_layout.addLayout(settings_layout)
        self.main_layout.addWidget(self.start_btn)
        self.main_layout.addWidget(QLabel("Log:"))
        self.main_layout.addWidget(self.log_box)

        footer = QLabel(f"© {datetime.now().year} Christopher Couture")
        footer.setStyleSheet("color: gray; font-size: 10px; margin-top: 6px;")
        footer.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(footer)

    def _create_menu(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        settings_menu = menubar.addMenu("Settings")
        theme_action = QAction("Toggle Dark Mode", self)
        theme_action.triggered.connect(self.toggle_theme)
        settings_menu.addAction(theme_action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_theme(self):
        current = self.settings.value("theme")
        force_dark = current != "dark"
        apply_theme(QApplication.instance(), force_dark)

    def show_about(self):
        QMessageBox.about(
            self,
            "About Video Compressor",
            f"<b>Video Compressor</b><br>"
            f"Version {self.version}<br><br>"
            "© 2025 Christopher Couture<br>"
            "All rights reserved.",
        )

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files", "", "Videos (*.mp4 *.avi *.mov *.mkv)"
        )
        for file in files:
            res, dur = self.get_video_metadata(file)
            size = f"{os.path.getsize(file) / (1024 * 1024):.1f} MB"
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(file))
            self.table.setItem(row, 1, QTableWidgetItem(res))
            self.table.setItem(row, 2, QTableWidgetItem(dur))
            self.table.setItem(row, 3, QTableWidgetItem(size))

    def clear_table(self):
        self.table.setRowCount(0)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_path.setText(folder)

    def get_video_metadata(self, filepath):
        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)
        ffprobe = os.path.join(base_path, "ffprobe.exe")

        filepath = os.path.abspath(filepath)
        try:
            res_proc = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                 "-of", "csv=s=x:p=0", filepath],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
            )
            dur_proc = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", filepath],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
            )
            resolution = res_proc.stdout.strip() or "?"
            try:
                duration_sec = float(dur_proc.stdout.strip())
                duration = f"{int(duration_sec // 60):02}:{int(duration_sec % 60):02}"
            except ValueError:
                duration = "?"
            return resolution, duration
        except Exception as e:
            self.log_box.append(f"[ERROR] ffprobe failed: {str(e)}")
            return "?", "?"

    def compress_all(self):
        crf = self.crf_map[self.crf_combo.currentText()]
        resolution = self.res_combo.currentText()
        output = self.output_path.text()

        self.settings.setValue("output_path", output)
        self.settings.setValue("crf_label", self.crf_combo.currentText())
        self.settings.setValue("resolution", resolution)

        if not os.path.isdir(output):
            QMessageBox.critical(self, "Error", "Please select a valid output folder.")
            return

        if getattr(sys, "frozen", False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)
        ffmpeg = os.path.join(base_path, "ffmpeg.exe")
        scale_map = {
            "1080p": "1920:1080",
            "720p": "1280:720",
            "480p": "854:480",
        }

        self.log_box.clear()
        self.log_box.append("Starting batch compression...")

        for row in range(self.table.rowCount()):
            input_file = self.table.item(row, 0).text()
            name, ext = os.path.splitext(os.path.basename(input_file))
            output_file = os.path.join(output, f"{name}_compressed{ext}")
            cmd = [
                ffmpeg,
                "-i", input_file,
                "-vcodec", "libx264",
                "-crf", str(crf),
                "-preset", "fast",
                "-acodec", "aac"
            ]
            if resolution != "Original":
                cmd += ["-vf", f"scale={scale_map[resolution]}"]
            cmd.append(output_file)

            self.log_box.append(f"Compressing: {os.path.basename(input_file)}")
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True
                )
                for line in proc.stdout:
                    self.log_box.append(line.strip())
                proc.wait()
                self.log_box.append(f"Finished: {os.path.basename(output_file)}")
            except Exception as e:
                self.log_box.append(f"Error compressing {input_file}: {e}")

        QMessageBox.information(self, "Done", "All videos have been compressed.")


if __name__ == "__main__":
    if "--version" in sys.argv:
        print(f"Video Compressor v{get_version()}")
        sys.exit(0)

    app = QApplication(sys.argv)
    apply_theme(app)
    win = VideoCompressor()
    win.resize(850, 600)
    win.show()
    sys.exit(app.exec_())