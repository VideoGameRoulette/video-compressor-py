import os
import sys
import av
import re
from datetime import datetime

import qdarkstyle
from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (
    QAction, QApplication, QComboBox, QFileDialog, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMenuBar, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, QProgressBar
)

def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)

class PyAVCompressor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Compressor (PyAV)")
        self.settings = QSettings("CortinaKitchens", "VideoCompressor")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.init_ui()

    def init_ui(self):
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["File Path", "Resolution", "Duration", "Size", "Progress"])
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

        self.res_combo = QComboBox()
        self.res_combo.addItems(["Original", "1080p", "720p", "480p"])
        self.scale_map = {
            "1080p": (1920, 1080),
            "720p": (1280, 720),
            "480p": (854, 480),
        }

        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Resolution:"))
        settings_layout.addWidget(self.res_combo)

        self.start_btn = QPushButton("Compress All Videos")
        self.start_btn.clicked.connect(self.compress_all)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)

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

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Videos (*.mp4 *.avi *.mov *.mkv)")
        for file in files:
            try:
                container = av.open(file)
                video_stream = next(s for s in container.streams if s.type == "video")
                duration = float(video_stream.duration * video_stream.time_base)
                resolution = f"{video_stream.width}x{video_stream.height}"
                size = f"{os.path.getsize(file) / (1024 * 1024):.1f} MB"
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(file))
                self.table.setItem(row, 1, QTableWidgetItem(resolution))
                self.table.setItem(row, 2, QTableWidgetItem(f"{int(duration // 60):02}:{int(duration % 60):02}"))
                self.table.setItem(row, 3, QTableWidgetItem(size))
                progress = QProgressBar()
                progress.setValue(0)
                self.table.setCellWidget(row, 4, progress)
            except Exception as e:
                self.log_box.append(f"[ERROR] Could not read file: {file} - {e}")

    def clear_table(self):
        self.table.setRowCount(0)

    def select_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.output_path.setText(folder)

    def compress_all(self):
        res_label = self.res_combo.currentText()
        resolution = None if res_label == "Original" else self.scale_map[res_label]
        output_dir = self.output_path.text()

        if not os.path.isdir(output_dir):
            QMessageBox.critical(self, "Error", "Please select a valid output folder.")
            return

        for row in range(self.table.rowCount()):
            input_file = self.table.item(row, 0).text()
            filename = sanitize_filename(os.path.basename(input_file))
            name, ext = os.path.splitext(filename)
            output_file = os.path.normpath(os.path.join(output_dir, f"{name}_compressed{ext}"))

            if len(output_file) > 250:
                name = name[:30]
                output_file = os.path.normpath(os.path.join(output_dir, f"{name}_compressed{ext}"))

            if os.path.abspath(input_file) == os.path.abspath(output_file):
                self.log_box.append("[ERROR] Input and output paths are the same. Skipping.")
                continue

            progress_bar = self.table.cellWidget(row, 4)

            in_container = None
            out_container = None
            try:
                in_container = av.open(input_file)
                out_container = av.open(str(output_file), mode="w")
                in_stream = next(s for s in in_container.streams if s.type == "video")
                out_stream = out_container.add_stream("libx264", rate=in_stream.average_rate)
                out_stream.width = in_stream.width if not resolution else resolution[0]
                out_stream.height = in_stream.height if not resolution else resolution[1]
                out_stream.pix_fmt = "yuv420p"

                total_frames = in_stream.frames or 1
                frame_count = 0

                for packet in in_container.demux(in_stream):
                    if packet.stream.type != 'video':
                        continue
                    for frame in packet.decode():
                        frame_count += 1
                        if resolution:
                            frame = frame.reformat(width=out_stream.width, height=out_stream.height)
                        for out_packet in out_stream.encode(frame):
                            try:
                                out_container.mux(out_packet)
                            except Exception as mux_err:
                                timestamp = frame.pts or "?"
                                self.log_box.append(f"[ERROR] muxing failed at frame {frame_count} (PTS={timestamp}): {mux_err}")
                        percent = int((frame_count / total_frames) * 100)
                        progress_bar.setValue(percent)

                for pkt in out_stream.encode():
                    out_container.mux(pkt)
                progress_bar.setValue(100)
                self.log_box.append(f"✅ Finished: {output_file}")
            except Exception as e:
                self.log_box.append(f"[ERROR] Compressing {input_file}: {e}")
            finally:
                if in_container:
                    in_container.close()
                if out_container:
                    out_container.close()
                    self.log_box.append(f"[LOG] File closed: {output_file}")

def apply_theme(app):
    settings = QSettings("CortinaKitchens", "VideoCompressor")
    pref = settings.value("theme")
    if pref == "dark" or pref is None:
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())
    else:
        app.setStyleSheet("")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app)
    win = PyAVCompressor()
    win.resize(900, 600)
    win.show()
    sys.exit(app.exec_())
