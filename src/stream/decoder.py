import av
import numpy as np
from PyQt6.QtGui import QImage, QPixmap


class VideoDecoder:
    def __init__(self):
        self.codec = None
        self._init_codec()

    def _init_codec(self):
        try:
            self.codec = av.CodecContext.create("h264", "r")
        except Exception:
            self.codec = None

    def decode(self, annexb_data: bytes) -> QPixmap | None:
        if self.codec is None:
            self._init_codec()
            if self.codec is None:
                return None

        try:
            packets = self.codec.parse(annexb_data)
            for packet in packets:
                frames = self.codec.decode(packet)
                for frame in frames:
                    img = frame.to_ndarray(format="rgb24")
                    h, w, ch = img.shape
                    bytes_per_line = ch * w
                    qimage = QImage(
                        img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
                    )
                    return QPixmap.fromImage(qimage)
        except Exception:
            return None

        return None

    def reset(self):
        self._init_codec()
