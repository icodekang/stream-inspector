import re
import hashlib
from ..transport.connection import Connection
from ..transport.http_tunnel import HttpTunnel
from .base import StreamProtocol


class RtspOverHttpsProtocol(StreamProtocol):

    def __init__(self, url: str):
        super().__init__(url)
        if self.port is None:
            self.port = 443
        self.conn = None
        self.tunnel = None
        self.rtp_channel = 0
        self.rtcp_channel = 1
        self.auth_realm = ""
        self.auth_nonce = ""
        self.tunnel_path = self.parsed.path or "/"

    def connect(self) -> bool:
        self._status("connecting")
        self.conn = Connection(
            debug_send_cb=lambda d: self._debug("->", d.decode("utf-8", errors="replace")),
            debug_recv_cb=lambda d: self._debug("<-", d.decode("utf-8", errors="replace")),
            debug_binary_recv_cb=lambda s: self._debug("<-", f"[RTP interleaved: {s} bytes]"),
        )
        self.tunnel = HttpTunnel(self.conn)
        try:
            self._debug("->", "[TLS handshake]")
            self.tunnel.establish(self.host, self.port, self.tunnel_path, use_tls=True)
            self._debug("<-", "[TLS handshake OK]")
        except Exception as e:
            self._debug("<-", f"[Tunnel establish error: {e}]")
            self._status("error")
            return False
        self._status("connected")
        return True

    def disconnect(self):
        self._running = False
        if self.tunnel:
            self.tunnel.disconnect()
            self.tunnel = None
            self.conn = None
        self._status("disconnected")

    def _send_request(self, request: str) -> str | None:
        try:
            response = self.tunnel.send_rtsp(request)
            if response:
                resp_text = response.decode("utf-8", errors="replace")
                self._debug("<-", "[Base64] " + resp_text.strip())
                return resp_text
        except Exception as e:
            self._debug("<-", f"[Request error: {e}]")
        return None

    def options(self) -> str | None:
        cseq = self._next_cseq()
        request = (
            f"OPTIONS {self.url} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
            f"User-Agent: StreamInspector/1.0\r\n"
            f"\r\n"
        )
        self._debug("->", "[Base64] " + request.strip())
        return self._send_request(request)

    def describe(self) -> str | None:
        cseq = self._next_cseq()
        auth_header = self._build_auth_header("DESCRIBE")
        request = (
            f"DESCRIBE {self.url} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
            f"Accept: application/sdp\r\n"
            f"User-Agent: StreamInspector/1.0\r\n"
        )
        if auth_header:
            request += auth_header + "\r\n"
        request += "\r\n"

        self._debug("->", "[Base64] " + request.strip())
        resp_text = self._send_request(request)
        if resp_text:
            if "401 Unauthorized" in resp_text and not auth_header:
                self._parse_auth_headers(resp_text)
                return self.describe()
        return resp_text

    def setup(self, track_url: str, rtp_channel: int = 0, rtcp_channel: int = 1) -> bool:
        self.rtp_channel = rtp_channel
        self.rtcp_channel = rtcp_channel
        cseq = self._next_cseq()
        auth_header = self._build_auth_header("SETUP")

        transport = f"RTP/AVP/TCP;unicast;interleaved={rtp_channel}-{rtcp_channel}"
        request = (
            f"SETUP {track_url} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
            f"Transport: {transport}\r\n"
            f"User-Agent: StreamInspector/1.0\r\n"
        )
        if auth_header:
            request += auth_header + "\r\n"
        request += "\r\n"

        self._debug("->", "[Base64] " + request.strip())
        resp_text = self._send_request(request)
        if resp_text:
            session_match = re.search(r"Session:\s*(\S+)", resp_text, re.IGNORECASE)
            if session_match:
                self._session = session_match.group(1).rstrip(";")
            return "200 OK" in resp_text
        return False

    def play(self) -> bool:
        cseq = self._next_cseq()
        request = (
            f"PLAY {self.url} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
            f"Session: {self._session or ''}\r\n"
            f"User-Agent: StreamInspector/1.0\r\n"
            f"Range: npt=0.000-\r\n"
            f"\r\n"
        )
        self._debug("->", "[Base64] " + request.strip())
        resp_text = self._send_request(request)
        self._running = True
        return resp_text is not None and "200 OK" in resp_text

    def teardown(self):
        if not self.tunnel or not self.tunnel.is_connected():
            return
        cseq = self._next_cseq()
        request = (
            f"TEARDOWN {self.url} RTSP/1.0\r\n"
            f"CSeq: {cseq}\r\n"
            f"Session: {self._session or ''}\r\n"
            f"User-Agent: StreamInspector/1.0\r\n"
            f"\r\n"
        )
        self._debug("->", "[Base64] " + request.strip())
        try:
            self._send_request(request)
        except Exception:
            pass

    def receive_loop(self):
        while self._running:
            try:
                if not self.tunnel or not self.tunnel.is_connected():
                    break
                self.tunnel.set_timeout(1.0)
                result = self.tunnel.conn.recv_message(timeout=1.0)
                if result is None:
                    continue
                if isinstance(result, tuple):
                    channel, data = result
                    if channel == self.rtp_channel:
                        self._video(data)
                else:
                    if isinstance(result, bytes):
                        text = result.decode("utf-8", errors="replace")
                        self._debug("<-", text)
            except Exception:
                import time
                time.sleep(0.1)

    def stop(self):
        self._running = False

    def _build_auth_header(self, method: str) -> str:
        if self.auth_realm and self.auth_nonce and self.username and self.password:
            ha1 = hashlib.md5(
                f"{self.username}:{self.auth_realm}:{self.password}".encode()
            ).hexdigest()
            uri = self.parsed.path or "/"
            if self.parsed.query:
                uri += "?" + self.parsed.query
            ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()
            cnonce = hashlib.md5(str(self._cseq).encode()).hexdigest()[:16]
            response_val = hashlib.md5(
                f"{ha1}:{self.auth_nonce}:{self._cseq}:{cnonce}:auth:{ha2}".encode()
            ).hexdigest()
            return (
                f'Authorization: Digest username="{self.username}", '
                f'realm="{self.auth_realm}", '
                f'nonce="{self.auth_nonce}", '
                f'uri="{uri}", '
                f'response="{response_val}", '
                f'cnonce="{cnonce}", '
                f'nc=00000001, '
                f'qop=auth'
            )
        return ""

    def _parse_auth_headers(self, resp: str):
        realm_match = re.search(r'realm="([^"]+)"', resp)
        nonce_match = re.search(r'nonce="([^"]+)"', resp)
        if realm_match and nonce_match:
            self.auth_realm = realm_match.group(1)
            self.auth_nonce = nonce_match.group(1)
