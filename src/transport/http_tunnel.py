import base64
import uuid


class HttpTunnel:
    def __init__(self, connection):
        self.conn = connection
        self.session_cookie = None
        self.tunnel_path = None
        self.host = None
        self.port = None
        self.use_tls = False
        self._get_chunked = False
        self._body_remain = 0

    def establish(self, host: str, port: int, path: str, use_tls: bool = False):
        self.host = host
        self.port = port
        self.tunnel_path = path
        self.use_tls = use_tls
        self.session_cookie = str(uuid.uuid4()).replace("-", "")[:16]

        self.conn.connect(host, port, use_tls)

        get_req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"x-sessioncookie: {self.session_cookie}\r\n"
            f"Accept: application/x-rtsp-tunnelled\r\n"
            f"Pragma: no-cache\r\n"
            f"Cache-Control: no-cache\r\n"
            f"\r\n"
        )
        self.conn.send_raw(get_req.encode("utf-8"))

        get_resp = self._read_http_headers()
        if get_resp["status"] != 200:
            raise ConnectionError(f"GET tunnel failed: HTTP {get_resp['status']}")

        self._get_chunked = get_resp.get("transfer_encoding") == "chunked"

        post_req = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"x-sessioncookie: {self.session_cookie}\r\n"
            f"Content-Type: application/x-rtsp-tunnelled\r\n"
            f"Content-Length: 0\r\n"
            f"\r\n"
        )
        self.conn.send_raw(post_req.encode("utf-8"))

        post_resp = self._read_http_headers()
        cl = int(post_resp.get("content_length", 0))
        if cl > 0:
            self._read_exact(cl)
        self._get_chunked = post_resp.get("transfer_encoding") == "chunked" or self._get_chunked

        if post_resp["status"] != 200:
            raise ConnectionError(f"POST tunnel failed: HTTP {post_resp['status']}")

    def send_rtsp(self, rtsp_message: str) -> bytes:
        encoded = base64.b64encode(rtsp_message.encode("utf-8")).decode("ascii")
        body = encoded

        post_req = (
            f"POST {self.tunnel_path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"x-sessioncookie: {self.session_cookie}\r\n"
            f"Content-Type: application/x-rtsp-tunnelled\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
            f"{body}"
        )
        self.conn.send_raw(post_req.encode("utf-8"))

        post_resp = self._read_http_headers()
        cl = int(post_resp.get("content_length", 0))
        if cl > 0:
            self._read_exact(cl)

        resp_data = self._read_chunk_data()
        if resp_data:
            try:
                return base64.b64decode(resp_data)
            except Exception:
                return b""
        return b""

    def disconnect(self):
        self.conn.disconnect()

    def set_timeout(self, timeout: float):
        self.conn.set_timeout(timeout)

    def is_connected(self) -> bool:
        return self.conn.is_connected()

    def _read_http_headers(self) -> dict:
        self.conn.buffer.clear()
        while b"\r\n\r\n" not in self.conn.buffer:
            if not self.conn.recv_into_buffer():
                break

        idx = self.conn.buffer.find(b"\r\n\r\n")
        if idx < 0:
            return {"status": 0, "headers": {}}

        header_bytes = bytes(self.conn.buffer[:idx])
        del self.conn.buffer[: idx + 4]

        header_text = header_bytes.decode("utf-8", errors="replace")
        lines = header_text.split("\r\n")
        if not lines:
            return {"status": 0, "headers": {}}

        status_line = lines[0]
        parts = status_line.split(" ")
        status = int(parts[1]) if len(parts) >= 2 else 0

        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip().lower()] = val.strip()

        result = {"status": status, "headers": headers}
        result["content_length"] = headers.get("content-length", "0")
        result["transfer_encoding"] = headers.get("transfer-encoding", "")
        result["content_type"] = headers.get("content-type", "")
        return result

    def _read_exact(self, size: int) -> bytes:
        while len(self.conn.buffer) < size:
            if not self.conn.recv_into_buffer():
                break
        data = bytes(self.conn.buffer[:size])
        del self.conn.buffer[:size]
        return data

    def _read_line(self) -> str:
        while b"\n" not in self.conn.buffer:
            if not self.conn.recv_into_buffer():
                return ""
        idx = self.conn.buffer.find(b"\n")
        line = bytes(self.conn.buffer[: idx + 1])
        del self.conn.buffer[: idx + 1]
        return line.decode("utf-8", errors="replace").rstrip("\r\n")

    def _read_chunk_data(self) -> str:
        if self._get_chunked:
            return self._read_chunked_tunnel()
        else:
            return self._read_raw_tunnel()

    def _read_chunked_tunnel(self) -> str:
        b64_buffer = ""
        max_attempts = 200
        attempt = 0

        while attempt < max_attempts:
            attempt += 1

            line = self._read_line()
            if not line:
                return b64_buffer

            try:
                chunk_size = int(line.strip(), 16)
            except ValueError:
                b64_buffer += line.strip()
                padding = len(b64_buffer) % 4
                if padding:
                    b64_buffer += "=" * (4 - padding)
                try:
                    decoded = base64.b64decode(b64_buffer)
                    if self._is_complete_rtsp(decoded):
                        return b64_buffer
                except Exception:
                    b64_buffer = b64_buffer.rstrip("=")
                continue

            if chunk_size == 0:
                break

            chunk_bytes = self._read_exact(chunk_size)
            chunk_text = chunk_bytes.decode("ascii", errors="replace")

            crlf = self._read_exact(2)

            b64_buffer += chunk_text
            padding = len(b64_buffer) % 4
            if padding:
                b64_buffer += "=" * (4 - padding)
            try:
                decoded = base64.b64decode(b64_buffer)
                if self._is_complete_rtsp(decoded):
                    return b64_buffer
            except Exception:
                pass
            if padding:
                b64_buffer = b64_buffer.rstrip("=")

        return b64_buffer

    def _read_raw_tunnel(self) -> str:
        while len(self.conn.buffer) == 0:
            if not self.conn.recv_into_buffer():
                return ""
        buf = bytes(self.conn.buffer)
        del self.conn.buffer[:]
        text = buf.decode("ascii", errors="ignore")
        return text.strip()

    def _is_complete_rtsp(self, data: bytes) -> bool:
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            return False
        if "\r\n\r\n" not in text:
            return False
        headers_end = text.find("\r\n\r\n")
        headers = text[:headers_end]
        content_length = 0
        for line in headers.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        if content_length > 0:
            body = text[headers_end + 4:]
            return len(body) >= content_length
        return True
