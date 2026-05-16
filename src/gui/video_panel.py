from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage


class VideoPanel(QWidget):
    frame_received = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._current_frame = None
        self._resolution = ""
        self._codec = ""

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QLabel("视频预览")
        title_bar.setObjectName("panelTitleBar")
        title_bar.setFixedHeight(32)

        self.video_label = QLabel()
        self.video_label.setObjectName("videoDisplay")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setText("等待连接...")
        self.video_label.setMinimumSize(320, 240)

        self.info_bar = QLabel("分辨率: --  |  编码: --")
        self.info_bar.setObjectName("videoInfoBar")
        self.info_bar.setFixedHeight(24)
        self.info_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_bar)
        layout.addWidget(self.video_label, 1)
        layout.addWidget(self.info_bar)

    def show_frame(self, pixmap: QPixmap):
        scaled = pixmap.scaled(
            self.video_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(scaled)
        self._current_frame = pixmap

        if not self._resolution:
            self._resolution = f"{pixmap.width()}x{pixmap.height()}"
            self._update_info()

    def set_codec(self, codec: str):
        self._codec = codec
        self._update_info()

    def set_resolution(self, w: int, h: int):
        self._resolution = f"{w}x{h}"
        self._update_info()

    def _update_info(self):
        self.info_bar.setText(f"分辨率: {self._resolution}  |  编码: {self._codec}")

    def set_waiting(self):
        self.video_label.setPixmap(QPixmap())
        self.video_label.setText("等待连接...")
        self._resolution = ""
        self._codec = ""
        self._update_info()

    def set_connecting(self):
        self.video_label.setPixmap(QPixmap())
        self.video_label.setText("正在连接...")

    def set_error(self, message: str):
        self.video_label.setPixmap(QPixmap())
        self.video_label.setText(f"连接失败\n{message}")
