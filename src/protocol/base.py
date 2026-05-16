from abc import ABC, abstractmethod
from urllib.parse import urlparse


class StreamProtocol(ABC):

    def __init__(self, url: str):
        self.url = url
        self.parsed = urlparse(url)
        self.host = self.parsed.hostname or ""
        self.port = self.parsed.port
        self.username = self.parsed.username
        self.password = self.parsed.password
        self._cseq = 1
        self._session = None
        self._running = False

        self.debug_callback = None
        self.video_callback = None
        self.status_callback = None
        self.stream_info_callback = None

    def _debug(self, direction: str, message: str):
        if self.debug_callback:
            self.debug_callback(direction, message)

    def _video(self, data: bytes):
        if self.video_callback:
            self.video_callback(data)

    def _status(self, status: str):
        if self.status_callback:
            self.status_callback(status)

    def _stream_info(self, info: dict):
        if self.stream_info_callback:
            self.stream_info_callback(info)

    def _next_cseq(self) -> int:
        cseq = self._cseq
        self._cseq += 1
        return cseq

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def describe(self) -> str | None:
        pass

    @abstractmethod
    def setup(self, track_url: str, rtp_channel: int, rtcp_channel: int) -> bool:
        pass

    @abstractmethod
    def play(self) -> bool:
        pass

    @abstractmethod
    def teardown(self):
        pass

    @abstractmethod
    def receive_loop(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    def _parse_sdp(self, sdp: str) -> list[dict]:
        tracks = []
        current_track = None
        for line in sdp.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("m="):
                if current_track:
                    tracks.append(current_track)
                parts = line[2:].split(" ")
                media_type = parts[0]
                current_track = {
                    "media": media_type,
                    "port": parts[1] if len(parts) > 1 else "",
                    "proto": parts[2] if len(parts) > 2 else "",
                    "fmt": parts[3] if len(parts) > 3 else "",
                    "control": "",
                    "rtpmap": "",
                    "fmtp": "",
                }
            elif line.startswith("a=control:") and current_track:
                current_track["control"] = line.split(":", 1)[1].strip()
            elif line.startswith("a=rtpmap:") and current_track:
                current_track["rtpmap"] = line.split(":", 1)[1].strip()
            elif line.startswith("a=fmtp:") and current_track:
                current_track["fmtp"] = line.split(":", 1)[1].strip()
        if current_track:
            tracks.append(current_track)
        return tracks
