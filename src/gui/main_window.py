from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QSplitter, QLabel, QApplication)
from PyQt6.QtCore import Qt, QObject, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QPixmap

from .video_panel import VideoPanel
from .debug_panel import DebugPanel
from .control_bar import ControlBar
from ..protocol.factory import create_protocol
from ..stream.rtp_parser import RtpParser
from ..stream.decoder import VideoDecoder


DARK_THEME = """
QMainWindow {
    background-color: #1a1b2e;
}
QWidget {
    background-color: #1a1b2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
}
#controlBar {
    background-color: #252640;
    border-bottom: 1px solid #3a3b50;
    border-radius: 8px;
    margin: 8px 12px 4px 12px;
}
#controlLabel {
    color: #8890b0;
    background: transparent;
}
#addrCombo {
    background-color: #1e1f35;
    border: 1px solid #3a3b50;
    border-radius: 6px;
    padding: 6px 12px;
    color: #cdd6f4;
    min-height: 20px;
}
#addrCombo:hover {
    border-color: #5b9cf5;
}
#addrCombo:focus {
    border-color: #5b9cf5;
}
#addrCombo QAbstractItemView {
    background-color: #1e1f35;
    border: 1px solid #3a3b50;
    color: #cdd6f4;
    selection-background-color: #3a3b50;
}
#addButton {
    background-color: #5b9cf5;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: bold;
}
#addButton:hover {
    background-color: #4a8ae5;
}
#addButton:pressed {
    background-color: #3a7ad5;
}
#toolButton {
    background-color: #3a3b50;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
}
#toolButton:hover {
    background-color: #4a4b60;
}
#connectButton {
    background-color: #46d4a3;
    color: #1a1b2e;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    font-weight: bold;
}
#connectButton:hover {
    background-color: #3ac090;
}
#connectButton:pressed {
    background-color: #30a878;
}
#disconnectButton {
    background-color: #f05060;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 6px 20px;
    font-weight: bold;
}
#disconnectButton:hover {
    background-color: #e04050;
}
#disconnectButton:pressed {
    background-color: #d03040;
}
#protocolLabel {
    color: #8890b0;
    background: transparent;
    padding: 4px 12px;
    border: 1px solid #3a3b50;
    border-radius: 10px;
}
#statusDot {
    color: #6c7086;
    background: transparent;
}
#statusText {
    color: #8890b0;
    background: transparent;
}
#panelTitleBar {
    background-color: #252640;
    color: #cdd6f4;
    font-weight: bold;
    padding: 0 12px;
    border-bottom: 1px solid #3a3b50;
}
#panelTitle {
    color: #cdd6f4;
    background: transparent;
}
QPlainTextEdit {
    background-color: #1e1f35;
    border: none;
    color: #cdd6f4;
    padding: 8px;
}
#debugText {
    background-color: #1e1f35;
    font-family: "Consolas", "Courier New", monospace;
}
QCheckBox {
    color: #8890b0;
    background: transparent;
    spacing: 4px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3a3b50;
    border-radius: 3px;
    background-color: #1e1f35;
}
QCheckBox::indicator:checked {
    background-color: #5b9cf5;
    border-color: #5b9cf5;
}
#videoDisplay {
    background-color: #0a0b14;
    color: #6c7086;
    border: none;
}
#videoInfoBar {
    background-color: #1e1f35;
    color: #8890b0;
    border-top: 1px solid #3a3b50;
}
QScrollBar:vertical {
    background-color: #1a1b2e;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #3a3b50;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #4a4b60;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background-color: #1a1b2e;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #3a3b50;
    border-radius: 4px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #4a4b60;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QSplitter::handle {
    background-color: #3a3b50;
    width: 2px;
}
QSplitter::handle:hover {
    background-color: #5b9cf5;
}
QDialog {
    background-color: #1e1f35;
}
QListWidget {
    background-color: #1a1b2e;
    border: 1px solid #3a3b50;
    border-radius: 6px;
    color: #cdd6f4;
}
QListWidget::item {
    padding: 6px 10px;
    border-bottom: 1px solid #252640;
}
QListWidget::item:selected {
    background-color: #3a3b50;
}
QListWidget::item:hover {
    background-color: #2a2b40;
}
QLineEdit {
    background-color: #1a1b2e;
    border: 1px solid #3a3b50;
    border-radius: 6px;
    padding: 6px 12px;
    color: #cdd6f4;
}
QLineEdit:focus {
    border-color: #5b9cf5;
}
QDialogButtonBox QPushButton {
    background-color: #3a3b50;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
}
QDialogButtonBox QPushButton:hover {
    background-color: #4a4b60;
}
QMessageBox {
    background-color: #1e1f35;
    color: #cdd6f4;
}
QMessageBox QPushButton {
    background-color: #3a3b50;
    color: #cdd6f4;
    border: none;
    border-radius: 6px;
    padding: 6px 16px;
}
QToolTip {
    background-color: #252640;
    color: #cdd6f4;
    border: 1px solid #3a3b50;
    padding: 4px;
}
"""


class ProtocolWorker(QObject):
    debug_message = pyqtSignal(str, str)
    video_data = pyqtSignal(bytes)
    status_changed = pyqtSignal(str)
    stream_info = pyqtSignal(dict)
    codec_changed = pyqtSignal(str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.protocol = None
        self._aborted = False

    @pyqtSlot()
    def run(self):
        self._aborted = False
        try:
            self.protocol = create_protocol(self.url)
            if self.protocol is None:
                self.error_occurred.emit(f"无法创建协议: {self.url}")
                return

            self.protocol.debug_callback = lambda d, m: self.debug_message.emit(d, m)
            self.protocol.video_callback = lambda d: self.video_data.emit(d)
            self.protocol.status_callback = lambda s: self.status_changed.emit(s)

            if not self.protocol.connect():
                self.error_occurred.emit("连接失败")
                return

            self.status_changed.emit("connected")

            self.protocol.options()

            sdp = self.protocol.describe()
            if not sdp:
                self.error_occurred.emit("DESCRIBE 失败")
                return

            tracks = self.protocol._parse_sdp(sdp)
            video_track = next((t for t in tracks if t["media"] == "video"), None)
            if video_track is None:
                self.error_occurred.emit("未找到视频轨道")
                return

            track_control = video_track.get("control", "")
            if track_control.startswith("rtsp://"):
                track_url = track_control
            else:
                track_url = self.url.rstrip("/") + "/" + track_control.lstrip("/")

            self.stream_info.emit({
                "codec": video_track.get("rtpmap", "H.264"),
                "control": track_control,
            })

            rtpmap = video_track.get("rtpmap", "")
            self.codec_changed.emit(self._parse_codec_name(rtpmap))

            if not self.protocol.setup(track_url):
                self.error_occurred.emit("SETUP 失败")
                return

            if not self.protocol.play():
                self.error_occurred.emit("PLAY 失败")
                return

            self.protocol.receive_loop()

        except Exception as e:
            if not self._aborted:
                self.error_occurred.emit(str(e))
        finally:
            if self.protocol:
                try:
                    self.protocol.teardown()
                except Exception:
                    pass
            if self.protocol:
                try:
                    self.protocol.disconnect()
                except Exception:
                    pass
            self.protocol = None
            self.finished.emit()

    @pyqtSlot()
    def stop(self):
        self._aborted = True
        if self.protocol:
            try:
                self.protocol.stop()
            except Exception:
                pass

    @staticmethod
    def _parse_codec_name(rtpmap: str) -> str:
        parts = rtpmap.split()
        if len(parts) >= 2:
            codec_part = parts[1].split("/")[0].lower()
            if codec_part in ("h265", "h.265", "hevc"):
                return "hevc"
        return "h264"


class DecodeWorker(QObject):
    frame_ready = pyqtSignal(QPixmap)

    def __init__(self):
        super().__init__()
        self.parser = RtpParser()
        self.decoder = VideoDecoder()
        self._running = False

    @pyqtSlot(str)
    def set_codec(self, codec_name: str):
        self.parser.set_codec(codec_name)
        self.decoder.set_codec(codec_name)

    @pyqtSlot(bytes)
    def process_data(self, data: bytes):
        if not self._running:
            return
        try:
            frames = self.parser.parse(data)
            for frame in frames:
                pixmap = self.decoder.decode(frame)
                if pixmap:
                    self.frame_ready.emit(pixmap)
        except Exception:
            pass

    @pyqtSlot()
    def start_decoding(self):
        self._running = True
        self.parser.reset()
        self.decoder.reset()

    @pyqtSlot()
    def stop_decoding(self):
        self._running = False
        self.parser.reset()
        self.decoder.reset()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stream Inspector")
        self.setMinimumSize(1100, 680)
        self.resize(1350, 820)

        self._protocol_thread = None
        self._protocol_worker = None
        self._decode_thread = None
        self._decode_worker = None

        self._setup_ui()
        self._apply_theme()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.control_bar = ControlBar()
        self.control_bar.connect_clicked.connect(self._on_connect)
        self.control_bar.disconnect_clicked.connect(self._on_disconnect)
        main_layout.addWidget(self.control_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        self.video_panel = VideoPanel()
        self.debug_panel = DebugPanel()

        splitter.addWidget(self.video_panel)
        splitter.addWidget(self.debug_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 750])

        main_layout.addWidget(splitter, 1)

    def _apply_theme(self):
        self.setStyleSheet(DARK_THEME)

    def _on_connect(self, url: str):
        if self._protocol_thread and self._protocol_thread.isRunning():
            return

        self.debug_panel.clear()
        self.debug_panel.append_info(f"开始连接: {url}")
        self.video_panel.set_connecting()

        self.control_bar.set_connecting()

        self._protocol_worker = ProtocolWorker(url)
        self._protocol_thread = QThread()
        self._protocol_worker.moveToThread(self._protocol_thread)

        self._protocol_thread.started.connect(self._protocol_worker.run)

        self._protocol_worker.debug_message.connect(self._on_debug_message)
        self._protocol_worker.status_changed.connect(self._on_status_changed)
        self._protocol_worker.error_occurred.connect(self._on_error)
        self._protocol_worker.stream_info.connect(self._on_stream_info)
        self._protocol_worker.finished.connect(self._on_protocol_finished)

        self._decode_worker = DecodeWorker()
        self._decode_thread = QThread()
        self._decode_worker.moveToThread(self._decode_thread)

        self._protocol_worker.video_data.connect(self._decode_worker.process_data)
        self._protocol_worker.codec_changed.connect(self._decode_worker.set_codec)
        self._decode_worker.frame_ready.connect(self._on_frame_ready)

        self._protocol_thread.start()
        self._decode_thread.start()
        self._decode_worker.start_decoding()

    def _on_disconnect(self):
        self.debug_panel.append_info("断开连接...")

        if self._decode_worker:
            self._decode_worker.stop_decoding()

        if self._protocol_worker:
            self._protocol_worker.stop()

    def _on_debug_message(self, direction: str, message: str):
        self.debug_panel.append_debug(direction, message)

    def _on_status_changed(self, status: str):
        if status == "connected":
            self.control_bar.set_connected()
        elif status == "disconnected":
            self.control_bar.set_disconnected()

    def _on_error(self, message: str):
        self.debug_panel.append_error(message)

    def _on_stream_info(self, info: dict):
        codec = info.get("codec", "H.264")
        self.video_panel.set_codec(codec)

    def _on_frame_ready(self, pixmap: QPixmap):
        self.video_panel.show_frame(pixmap)

    def _on_protocol_finished(self):
        if self._protocol_thread and self._protocol_thread.isRunning():
            self._protocol_thread.quit()
            self._protocol_thread.wait(3000)

        if self._decode_thread and self._decode_thread.isRunning():
            self._decode_thread.quit()
            self._decode_thread.wait(3000)

        self._protocol_worker = None
        self._protocol_thread = None
        self._decode_worker = None
        self._decode_thread = None

        self.control_bar.set_disconnected()
        self.video_panel.set_waiting()
        self.debug_panel.append_info("已断开连接")
