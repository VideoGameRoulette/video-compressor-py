
import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QComboBox, QLineEdit, QTextEdit,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import QSettings

class VideoCompressor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Compressor")
        self.settings = QSettings("CortinaKitchens", "VideoCompressor")

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.inner_layout = QVBoxLayout()

        # Table to display video info
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

        # Output folder
        self.output_path = QLineEdit()
        self.output_path.setText(self.settings.value("output_path", ""))
        self.browse_output = QPushButton("Output Folder")
        self.browse_output.clicked.connect(self.select_output_folder)

        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(self.browse_output)

        # CRF & resolution dropdowns
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
            "Very Low (Tiny file)": 32
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

        # Build the inner UI
        self.inner_layout.addLayout(file_button_layout)
        self.inner_layout.addWidget(self.table)
        self.inner_layout.addLayout(output_layout)
        self.inner_layout.addLayout(settings_layout)
        self.inner_layout.addWidget(self.start_btn)
        self.inner_layout.addWidget(QLabel("Log:"))
        self.inner_layout.addWidget(self.log_box)

        # Add inner layout to a container widget
        container = QWidget()
        container.setLayout(self.inner_layout)

        # Footer
        footer = QLabel("© 2025 Christopher Couture")
        footer.setStyleSheet("color: gray; font-size: 10px; margin-top: 6px;")
        footer.setAlignment(Qt.AlignCenter)

        # Final layout
        self.main_layout.addWidget(container)
        self.main_layout.addWidget(footer)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Videos (*.mp4 *.avi *.mov *.mkv)")
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
        ffprobe_path = os.path.join(os.path.dirname(sys.executable), "ffprobe.exe")
        try:
            res_cmd = [
                ffprobe_path, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0", filepath
            ]
            duration_cmd = [
                ffprobe_path, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", filepath
            ]

            resolution = subprocess.check_output(res_cmd, stderr=subprocess.DEVNULL).decode().strip()
            duration_sec = float(subprocess.check_output(duration_cmd, stderr=subprocess.DEVNULL).decode().strip())
            minutes = int(duration_sec // 60)
            seconds = int(duration_sec % 60)
            duration = f"{minutes:02}:{seconds:02}"
            return resolution, duration
        except Exception:
            return "?", "?"

    def compress_all(self):
        crf_label = self.crf_combo.currentText()
        crf = self.crf_map[crf_label]
        resolution = self.res_combo.currentText()
        output_folder = self.output_path.text()

        self.settings.setValue("output_path", output_folder)
        self.settings.setValue("crf_label", crf_label)
        self.settings.setValue("resolution", resolution)

        if not os.path.isdir(output_folder):
            QMessageBox.critical(self, "Error", "Please select a valid output folder.")
            return

        ffmpeg_path = os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe")
        scale_map = {
            "1080p": "1920:1080",
            "720p": "1280:720",
            "480p": "854:480"
        }

        self.log_box.clear()
        self.log_box.append("Starting batch compression...\n")

        for row in range(self.table.rowCount()):
            input_file = self.table.item(row, 0).text()
            name, ext = os.path.splitext(os.path.basename(input_file))
            output_file = os.path.join(output_folder, f"{name}_compressed{ext}")

            cmd = [
                ffmpeg_path, "-i", input_file,
                "-vcodec", "libx264", "-crf", str(crf),
                "-preset", "fast", "-acodec", "aac"
            ]

            if resolution != "Original":
                cmd += ["-vf", f"scale={scale_map[resolution]}"]

            cmd.append(output_file)

            self.log_box.append(f"Compressing: {os.path.basename(input_file)}")
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
                for line in process.stdout:
                    self.log_box.append(line.strip())
                process.wait()
                self.log_box.append(f"Finished: {os.path.basename(output_file)}\n")
            except Exception as e:
                self.log_box.append(f"Error compressing {input_file}: {e}\n")

        QMessageBox.information(self, "Done", "All videos have been compressed.")

if __name__ == "__main__":
    from PyQt5.QtCore import Qt
    app = QApplication(sys.argv)
    window = VideoCompressor()
    window.resize(850, 600)
    window.show()
    sys.exit(app.exec_())
