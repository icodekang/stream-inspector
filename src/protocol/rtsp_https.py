import re
import hashlib
from ..transport.http_tunnel import HttpTunnel
from .base import StreamProtocol


class RtspOverHttpsProtocol(StreamProtocol):

    def __init__(self, url: str):
        super().__init__(url)
        if self.port is None:
            self.port = 443
        self.tunnel = None
        self.rtp_channel = 0
        self.rtcp_channel = 1
        self.auth_realm = ""
        self.auth_nonce = ""
        self.auth_qop = None
        self.tunnel_path = self.parsed.path or "/"
        rtsp_port = self.parsed.port if self.parsed.port and self.parsed.port != 443 else 554
        self._rtsp_url = f"rtsp://{self.host}:{rtsp_port}{self.tunnel_path}"
        if self.parsed.query:
            self._rtsp_url += f"?{self.parsed.query}"

    def connect(self) -> bool:
        self._status("connecting")
        try:
            self._debug("->", "[TLS handshake]")
            self.tunnel = HttpTunnel.establish(
                self.host, self.port, self.tunnel_path, use_tls=True,
                debug_send_cb=lambda d: self._debug("->", d.decode("utf-8", errors="replace")),
                debug_recv_cb=lambda d: self._debug("<-", d.decode("utf-8", errors="replace")),
                debug_binary_recv_cb=lambda s: self._debug("<-", f"[RTP interleaved: {s} bytes]"),
            )
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
        self._status("disconnected")

    def _send_request(self, request: str) -> str | None:
        try:
            self.tunnel.send_rtsp(request)
            response = self.tunnel.recv_rtsp_response(timeout=10.0)
            if response:
                return response.decode("utf-8", errors="replace")
        except Exception as e:
            self._debug("<-", f"[Request error: {e}]")
        return None

    def options(self) -> str | None:
        cseq = self._next_cseq()
        request = (
            f"OPTIONS {self._rtsp_url} RTSP/1.0\r\n"
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
            f"DESCRIBE {self._rtsp_url} RTSP/1.0\r\n"
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
            f"PLAY {self._rtsp_url} RTSP/1.0\r\n"
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
            f"TEARDOWN {self._rtsp_url} RTSP/1.0\r\n"
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
                result = self.tunnel.recv_message(timeout=1.0)
                if result is None:
                    continue
                if isinstance(result, tuple):
                    channel, data = result
                    if channel == self.rtp_channel:
                        self._video(data)
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
            uri = self._rtsp_url
            ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()

            if self.auth_qop:
                cnonce = hashlib.md5(str(self._cseq).encode()).hexdigest()[:16]
                response_val = hashlib.md5(
                    f"{ha1}:{self.auth_nonce}:{self._cseq}:{cnonce}:{self.auth_qop}:{ha2}".encode()
                ).hexdigest()
                return (
                    f'Authorization: Digest username="{self.username}", '
                    f'realm="{self.auth_realm}", '
                    f'nonce="{self.auth_nonce}", '
                    f'uri="{uri}", '
                    f'response="{response_val}", '
                    f'cnonce="{cnonce}", '
                    f'nc=00000001, '
                    f'qop={self.auth_qop}'
                )
            else:
                response_val = hashlib.md5(
                    f"{ha1}:{self.auth_nonce}:{ha2}".encode()
                ).hexdigest()
                return (
                    f'Authorization: Digest username="{self.username}", '
                    f'realm="{self.auth_realm}", '
                    f'nonce="{self.auth_nonce}", '
                    f'uri="{uri}", '
                    f'response="{response_val}"'
                )
        return ""

    def _parse_auth_headers(self, resp: str):
        realm_match = re.search(r'realm="([^"]+)"', resp)
        nonce_match = re.search(r'nonce="([^"]+)"', resp)
        qop_match = re.search(r'qop="?([^",\s]+)"?', resp, re.IGNORECASE)
        if realm_match and nonce_match:
            self.auth_realm = realm_match.group(1)
            self.auth_nonce = nonce_match.group(1)
            self.auth_qop = qop_match.group(1) if qop_match else None
