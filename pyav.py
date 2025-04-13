import os
import sys
import av
import re
from datetime import datetime

import qdarkstyle
from PyQt5.QtCore import QSettings, Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QDropEvent
from PyQt5.QtWidgets import (
    QAction, QApplication, QComboBox, QFileDialog, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMenuBar, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QHBoxLayout, QWidget, QProgressBar
)


def sanitize_filename(name):
    return re.sub(r'[<>:"/\\|?*]', "_", name)


class CompressionWorker(QObject):
    progress = pyqtSignal(int, int)  # row, percent
    finished = pyqtSignal(int, str)  # row, output_file
    error = pyqtSignal(int, str)     # row, error message

    def __init__(self, row, input_file, output_file, resolution, format_ext):
        super().__init__()
        self.row = row
        self.input_file = input_file
        self.output_file = output_file
        self.resolution = resolution
        self.format_ext = format_ext

    def run(self):
        in_container = out_container = None
        try:
            in_container = av.open(self.input_file)
            out_container = av.open(str(self.output_file), mode="w")
            in_stream = next(s for s in in_container.streams if s.type == "video")

            if not in_stream:
                self.error.emit(self.row, "No video stream found.")
                return

            out_stream = out_container.add_stream("libx264", rate=in_stream.average_rate)
            out_stream.width = in_stream.width if not self.resolution else self.resolution[0]
            out_stream.height = in_stream.height if not self.resolution else self.resolution[1]
            out_stream.pix_fmt = "yuv420p"

            if not out_stream:
                self.error.emit(self.row, "Failed to create output stream.")
                return

            total_frames = in_stream.frames or 1
            frame_count = 0

            for packet in in_container.demux(in_stream):
                if packet.stream.type != "video":
                    continue
                for frame in packet.decode():
                    frame_count += 1
                    if self.resolution:
                        frame = frame.reformat(width=out_stream.width, height=out_stream.height)
                    for out_packet in out_stream.encode(frame):
                        try:
                            out_container.mux(out_packet)
                        except Exception as mux_err:
                            pts = frame.pts or "?"
                            self.error.emit(self.row, f"muxing failed at frame {frame_count} (PTS={pts}): {mux_err}")
                    percent = int((frame_count / total_frames) * 100)
                    self.progress.emit(self.row, percent)

            for pkt in out_stream.encode():
                out_container.mux(pkt)

            self.progress.emit(self.row, 100)
            self.finished.emit(self.row, self.output_file)
        except Exception as e:
            self.error.emit(self.row, str(e))
        finally:
            if in_container:
                in_container.close()
            if out_container:
                out_container.close()


class PyAVCompressor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Compressor (PyAV - Threaded)")
        self.settings = QSettings("CortinaKitchens", "VideoCompressor")
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.dark_mode = self.settings.value("theme", "dark") == "dark"
        apply_theme(QApplication.instance(), self.dark_mode)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.threads = []
        self.show_log = True
        self.init_ui()
        self.setAcceptDrops(True)

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
        self.output_path.textChanged.connect(lambda path: self.settings.setValue("output_path", path))
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

        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "avi", "mov", "mkv"])

        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Resolution:"))
        settings_layout.addWidget(self.res_combo)
        settings_layout.addWidget(QLabel("Format:"))
        settings_layout.addWidget(self.format_combo)

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

        self._create_menu()

    def _create_menu(self):
        menubar = QMenuBar(self)
        self.setMenuBar(menubar)

        settings_menu = menubar.addMenu("Settings")
        theme_action = QAction("Toggle Dark Mode", self)
        theme_action.triggered.connect(self.toggle_theme)
        settings_menu.addAction(theme_action)

        log_toggle_action = QAction("Show/Hide Logs", self)
        log_toggle_action.triggered.connect(self.toggle_log)
        settings_menu.addAction(log_toggle_action)

        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_log(self):
        self.show_log = not self.show_log
        self.log_box.setVisible(self.show_log)

    def toggle_theme(self):
        current = self.settings.value("theme", "dark")
        new_theme = "light" if current == "dark" else "dark"
        apply_theme(QApplication.instance(), new_theme == "dark")

    def show_about(self):
        QMessageBox.about(
            self,
            "About Video Compressor",
            "Video Compressor with PyAV and threaded processing. © 2025 Christopher Couture"
        )

    def dragEnterEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.add_file_rows(files)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Video Files", "", "Videos (*.mp4 *.avi *.mov *.mkv)")
        self.add_file_rows(files)

    def add_file_rows(self, files):
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
        output_dir = self.output_path.text()
        resolution_label = self.res_combo.currentText()
        resolution = None if resolution_label == "Original" else self.scale_map[resolution_label]
        format_ext = self.format_combo.currentText()

        if not os.path.isdir(output_dir):
            QMessageBox.critical(self, "Error", "Please select a valid output folder.")
            return

        self.threads = []  # clear any old threads

        for row in range(self.table.rowCount()):
            input_file = self.table.item(row, 0).text()
            filename = sanitize_filename(os.path.basename(input_file))
            name, _ = os.path.splitext(filename)
            output_file = os.path.normpath(os.path.join(output_dir, f"{name}_compressed.{format_ext}"))

            if len(output_file) > 250:
                name = name[:30]
                output_file = os.path.normpath(os.path.join(output_dir, f"{name}_compressed.{format_ext}"))

            if os.path.abspath(input_file) == os.path.abspath(output_file):
                self.log_box.append("[ERROR] Input and output paths are the same. Skipping.")
                continue

            thread = QThread(self)
            worker = CompressionWorker(row, input_file, output_file, resolution, format_ext)
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.progress.connect(self.update_progress)
            worker.finished.connect(self.handle_finished)
            worker.error.connect(self.handle_error)
            worker.finished.connect(lambda *_: thread.quit())
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)

            self.threads.append((thread, worker))
            thread.start()

    def update_progress(self, row, percent):
        bar = self.table.cellWidget(row, 4)
        if bar:
            bar.setValue(percent)

    def handle_finished(self, row, output_file):
        self.log_box.append(f"✅ Finished: {output_file}")
        self.log_box.append(f"[LOG] File closed: {output_file}")

    def handle_error(self, row, message):
        self.log_box.append(f"[ERROR] Row {row}: {message}")


def apply_theme(app, force_dark=None):
    settings = QSettings("CortinaKitchens", "VideoCompressor")
    if force_dark is None:
        pref = settings.value("theme", "dark")
        force_dark = pref == "dark"
    settings.setValue("theme", "dark" if force_dark else "light")
    app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5() if force_dark else "")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_theme(app)
    win = PyAVCompressor()
    win.resize(1000, 650)
    win.show()
    sys.exit(app.exec_())
