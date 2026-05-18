import av
from PyQt6.QtGui import QImage, QPixmap


class VideoDecoder:
    def __init__(self, debug_callback=None):
        self._codec_name = "h264"
        self.codec = None
        self._debug_cb = debug_callback
        self._data_chunks = 0
        self._frame_count = 0
        self._init_codec()

    def set_codec(self, codec_name: str):
        self._codec_name = codec_name
        self.reset()

    def _init_codec(self):
        try:
            self.codec = av.CodecContext.create(self._codec_name, "r")
            if self._debug_cb:
                self._debug_cb("--", f"解码器初始化成功: {self._codec_name}")
        except Exception as e:
            self.codec = None
            if self._debug_cb:
                self._debug_cb("!!", f"解码器初始化失败 ({self._codec_name}): {e}")

    def decode(self, annexb_data: bytes) -> QPixmap | None:
        if not annexb_data:
            return None
        self._data_chunks += 1

        if self.codec is None:
            self._init_codec()
            if self.codec is None:
                return None

        try:
            packets = self.codec.parse(annexb_data)
            for packet in packets:
                frames = self.codec.decode(packet)
                for frame in frames:
                    self._frame_count += 1
                    img = frame.to_ndarray(format="rgb24")
                    h, w, ch = img.shape
                    bytes_per_line = ch * w
                    qimage = QImage(
                        img.data, w, h, bytes_per_line, QImage.Format.Format_RGB888
                    ).copy()
                    return QPixmap.fromImage(qimage)

            if self._frame_count == 0 and self._data_chunks % 100 == 0 and self._debug_cb:
                self._debug_cb(
                    "!!",
                    f"已收到 {self._data_chunks} 个数据包但未产生任何帧 (编码: {self._codec_name})",
                )
        except Exception as e:
            if self._debug_cb:
                self._debug_cb("!!", f"解码异常: {e}")
            return None

        return None

    def reset(self):
        self._data_chunks = 0
        self._frame_count = 0
        self._init_codec()
