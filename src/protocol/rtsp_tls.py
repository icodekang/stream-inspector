from .rtsp import RtspProtocol
from ..transport.connection import Connection


class RtspOverTlsProtocol(RtspProtocol):

    def __init__(self, url: str):
        super().__init__(url)
        if self.parsed.port is None:
            self.port = 322

    def connect(self) -> bool:
        self._status("connecting")
        self._debug("->", "[TLS handshake]")
        self.conn = Connection(
            debug_send_cb=lambda d: self._debug("->", d.decode("utf-8", errors="replace")),
            debug_recv_cb=lambda d: self._debug("<-", d.decode("utf-8", errors="replace")),
        )
        self.conn.connect(self.host, self.port, use_tls=True)
        self._debug("<-", "[TLS handshake OK]")
        self._status("connected")
        return True
