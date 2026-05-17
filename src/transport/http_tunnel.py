import base64
import uuid
from .connection import Connection


class HttpTunnel:

    def __init__(self, get_conn: Connection, post_conn: Connection,
                 session_cookie: str, tunnel_path: str, host: str, port: int):
        self.get_conn = get_conn
        self.post_conn = post_conn
        self.session_cookie = session_cookie
        self.tunnel_path = tunnel_path
        self.host = host
        self.port = port

    @staticmethod
    def establish(host: str, port: int, path: str, use_tls: bool = False,
                  debug_send_cb=None, debug_recv_cb=None, debug_binary_recv_cb=None):
        session_cookie = str(uuid.uuid4()).replace("-", "")[:16]

        # --- GET connection (for receiving data from server) ---
        get_conn = Connection(
            debug_send_cb=debug_send_cb,
            debug_recv_cb=debug_recv_cb,
            debug_binary_recv_cb=debug_binary_recv_cb,
        )
        get_conn.connect(host, port, use_tls)

        default_port = 443 if use_tls else 80
        host_header = host if port == default_port else f"{host}:{port}"

        get_req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            f"x-sessioncookie: {session_cookie}\r\n"
            f"Accept: application/x-rtsp-tunnelled\r\n"
            f"Pragma: no-cache\r\n"
            f"Cache-Control: no-cache\r\n"
            f"\r\n"
        )
        get_conn.send_raw(get_req.encode("utf-8"))

        get_resp = HttpTunnel._read_http_response(get_conn)
        if get_resp["status"] != 200:
            raw = get_resp.get("raw", b"")
            raw_text = raw.decode("utf-8", errors="replace")[:200] if raw else "(no data received)"
            get_conn.disconnect()
            raise ConnectionError(f"GET tunnel failed: HTTP {get_resp['status']}, response: {raw_text}")

        # --- POST connection (for sending commands to server) ---
        post_conn = Connection(debug_send_cb=debug_send_cb)
        post_conn.connect(host, port, use_tls)

        post_req = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            f"x-sessioncookie: {session_cookie}\r\n"
            f"Content-Type: application/x-rtsp-tunnelled\r\n"
            f"Pragma: no-cache\r\n"
            f"Cache-Control: no-cache\r\n"
            f"Content-Length: 32767\r\n"
            f"\r\n"
        )
        post_conn.send_raw(post_req.encode("utf-8"))

        try:
            post_conn.set_timeout(2.0)
            HttpTunnel._read_http_response(post_conn)
        except Exception:
            pass

        return HttpTunnel(get_conn, post_conn, session_cookie, path, host, port)

    def send_rtsp(self, rtsp_message: str):
        encoded = base64.b64encode(rtsp_message.encode("utf-8")).decode("ascii")
        self.post_conn.send_raw(encoded.encode("utf-8"))

    def recv_rtsp_response(self, timeout: float = None) -> bytes | None:
        return self.get_conn.recv_rtsp_message(timeout)

    def recv_interleaved(self, timeout: float = None):
        return self.get_conn.recv_interleaved(timeout)

    def recv_message(self, timeout: float = None):
        return self.get_conn.recv_message(timeout)

    def set_timeout(self, timeout: float):
        self.get_conn.set_timeout(timeout)

    def is_connected(self) -> bool:
        return (self.get_conn is not None and self.get_conn.is_connected()
                and self.post_conn is not None and self.post_conn.is_connected())

    def disconnect(self):
        if self.get_conn:
            self.get_conn.disconnect()
            self.get_conn = None
        if self.post_conn:
            self.post_conn.disconnect()
            self.post_conn = None

    @staticmethod
    def _read_http_response(conn: Connection) -> dict:
        conn.buffer.clear()
        while b"\r\n\r\n" not in conn.buffer:
            if not conn.recv_into_buffer():
                break

        raw = bytes(conn.buffer)
        idx = conn.buffer.find(b"\r\n\r\n")
        if idx < 0:
            return {"status": 0, "headers": {}, "raw": raw}

        header_bytes = bytes(conn.buffer[:idx])
        del conn.buffer[: idx + 4]

        header_text = header_bytes.decode("utf-8", errors="replace")
        lines = header_text.split("\r\n")
        if not lines:
            return {"status": 0, "headers": {}, "raw": raw}

        status_line = lines[0]
        parts = status_line.split(" ")
        status = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0

        headers = {}
        for line in lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip().lower()] = val.strip()

        return {"status": status, "headers": headers, "raw": header_bytes}
