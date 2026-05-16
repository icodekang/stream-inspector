from .base import StreamProtocol
from .rtsp import RtspProtocol
from .rtsp_http import RtspOverHttpProtocol
from .rtsp_https import RtspOverHttpsProtocol


PROTOCOL_MAP = {
    "rtsp": RtspProtocol,
    "rtsph": RtspOverHttpProtocol,
    "rtsps": RtspOverHttpsProtocol,
}


def create_protocol(url: str) -> StreamProtocol | None:
    if "://" not in url:
        return None
    scheme = url.split("://")[0].lower()
    protocol_class = PROTOCOL_MAP.get(scheme)
    if protocol_class is None:
        return None
    return protocol_class(url)


def get_supported_schemes() -> list[str]:
    return list(PROTOCOL_MAP.keys())


def get_protocol_name(scheme: str) -> str:
    names = {
        "rtsp": "RTSP",
        "rtsph": "RTSP over HTTP",
        "rtsps": "RTSP over HTTPS",
    }
    return names.get(scheme, scheme.upper())
