from datetime import datetime
from .models import DebugEntry, Direction, MessageType


class DebugLogger:
    def __init__(self):
        self.callback = None

    def set_callback(self, callback):
        self.callback = callback

    def log_send(self, data: bytes):
        entry = DebugEntry(
            timestamp=datetime.now(),
            direction=Direction.SEND,
            message_type=MessageType.INFO,
            content=data.decode("utf-8", errors="replace")
        )
        self._emit(entry)

    def log_recv(self, data: bytes):
        content = data.decode("utf-8", errors="replace")
        entry = DebugEntry(
            timestamp=datetime.now(),
            direction=Direction.RECV,
            message_type=MessageType.INFO,
            content=content
        )
        self._emit(entry)

    def log_binary_send(self, size: int):
        entry = DebugEntry(
            timestamp=datetime.now(),
            direction=Direction.SEND,
            message_type=MessageType.INFO,
            content=f"[RTP interleaved data: {size} bytes]"
        )
        self._emit(entry)

    def log_binary_recv(self, size: int):
        entry = DebugEntry(
            timestamp=datetime.now(),
            direction=Direction.RECV,
            message_type=MessageType.INFO,
            content=f"[RTP interleaved data: {size} bytes]"
        )
        self._emit(entry)

    def log_error(self, message: str):
        entry = DebugEntry(
            timestamp=datetime.now(),
            direction=Direction.RECV,
            message_type=MessageType.ERROR,
            content=message
        )
        self._emit(entry)

    def log_info(self, message: str):
        entry = DebugEntry(
            timestamp=datetime.now(),
            direction=Direction.SEND,
            message_type=MessageType.INFO,
            content=message
        )
        self._emit(entry)

    def _emit(self, entry: DebugEntry):
        if self.callback:
            self.callback(entry)
