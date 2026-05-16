import os
import socket
import ssl
import struct
import select


class Connection:
    def __init__(self, debug_send_cb=None, debug_recv_cb=None, debug_binary_recv_cb=None):
        self.sock = None
        self.buffer = bytearray()
        self.host = None
        self.port = None
        self.use_tls = False
        self.tls_context = None
        self.on_debug_send = debug_send_cb
        self.on_debug_recv = debug_recv_cb
        self.on_debug_binary_recv = debug_binary_recv_cb

    def connect(self, host: str, port: int, use_tls: bool = False, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.use_tls = use_tls

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)

        self.sock.setblocking(False)
        try:
            self.sock.connect((host, port))
        except (BlockingIOError, InterruptedError):
            pass

        _, writable, exceptional = select.select([], [self.sock], [self.sock], timeout)
        if not writable or exceptional:
            self.sock.close()
            self.sock = None
            raise ConnectionError(f"connect to {host}:{port} timed out")

        error = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        if error != 0:
            self.sock.close()
            self.sock = None
            raise ConnectionError(f"connect to {host}:{port} failed: {os.strerror(error)}")

        self.sock.setblocking(True)
        self.sock.settimeout(timeout)

        if use_tls:
            self.tls_context = ssl.create_default_context()
            self.tls_context.check_hostname = False
            self.tls_context.verify_mode = ssl.CERT_NONE
            try:
                self.sock = self.tls_context.wrap_socket(self.sock, server_hostname=host)
                self.sock.settimeout(timeout)
            except Exception as e:
                self.sock.close()
                self.sock = None
                raise ConnectionError(f"TLS handshake failed: {e}")

    def abort(self):
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    def disconnect(self):
        self.abort()
        self.buffer.clear()

    def send_raw(self, data: bytes):
        sock = self.sock
        if not sock:
            return
        try:
            sock.sendall(data)
        except OSError:
            return
        if self.on_debug_send:
            self.on_debug_send(data)

    def send_rtsp(self, message: str):
        self.send_raw(message.encode("utf-8"))

    def recv_into_buffer(self, size: int = 4096) -> bool:
        sock = self.sock
        if not sock:
            return False
        try:
            chunk = sock.recv(size)
        except (socket.timeout, BlockingIOError, OSError, AttributeError):
            return False
        if not chunk:
            self.buffer.clear()
            return False
        self.buffer.extend(chunk)
        return True

    def recv_rtsp_message(self, timeout: float = None) -> bytes | None:
        import time
        start = time.time()

        while b"\r\n\r\n" not in self.buffer:
            remaining = timeout - (time.time() - start) if timeout else None
            if remaining is not None and remaining <= 0:
                return None
            if not self.recv_into_buffer():
                if timeout and (time.time() - start) >= timeout:
                    return None
                continue

        header_end = self.buffer.find(b"\r\n\r\n")
        headers_bytes = self.buffer[:header_end]
        headers_text = headers_bytes.decode("utf-8", errors="replace")

        content_length = 0
        for line in headers_text.split("\r\n"):
            if line.lower().startswith("content-length:"):
                try:
                    content_length = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        total_needed = header_end + 4 + content_length

        while len(self.buffer) < total_needed:
            remaining = timeout - (time.time() - start) if timeout else None
            if remaining is not None and remaining <= 0:
                return None
            if not self.recv_into_buffer():
                return None

        message = bytes(self.buffer[:total_needed])
        self.buffer = self.buffer[total_needed:]

        if self.on_debug_recv:
            self.on_debug_recv(message)

        return message

    def recv_interleaved(self, timeout: float = None) -> tuple[int, bytes] | None:
        import time
        start = time.time()

        while len(self.buffer) < 4:
            remaining = timeout - (time.time() - start) if timeout else None
            if remaining is not None and remaining <= 0:
                return None
            if not self.recv_into_buffer():
                return None

        magic = self.buffer[0]
        if magic != 0x24:
            return None

        channel = self.buffer[1]
        length = struct.unpack(">H", bytes(self.buffer[2:4]))[0]

        total_needed = 4 + length
        while len(self.buffer) < total_needed:
            remaining = timeout - (time.time() - start) if timeout else None
            if remaining is not None and remaining <= 0:
                return None
            if not self.recv_into_buffer():
                return None

        data = bytes(self.buffer[4:total_needed])
        self.buffer = self.buffer[total_needed:]

        if self.on_debug_binary_recv:
            self.on_debug_binary_recv(length)

        return channel, data

    def recv_message(self, timeout: float = None):
        import time
        start = time.time()

        while len(self.buffer) == 0:
            remaining = timeout - (time.time() - start) if timeout else None
            if remaining is not None and remaining <= 0:
                return None
            if not self.recv_into_buffer():
                return None

        first_byte = self.buffer[0]
        if first_byte == 0x24:
            return self.recv_interleaved(timeout)
        else:
            return self.recv_rtsp_message(timeout)

    def set_timeout(self, timeout: float):
        if self.sock:
            self.sock.settimeout(timeout)

    def is_connected(self) -> bool:
        return self.sock is not None
