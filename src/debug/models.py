from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Direction(Enum):
    SEND = "->"
    RECV = "<-"


class MessageType(Enum):
    RTSP_REQUEST = "RTSP REQ"
    RTSP_RESPONSE = "RTSP RES"
    HTTP_REQUEST = "HTTP REQ"
    HTTP_RESPONSE = "HTTP RES"
    SDP = "SDP"
    ERROR = "ERROR"
    INFO = "INFO"


@dataclass
class DebugEntry:
    timestamp: datetime
    direction: Direction
    message_type: MessageType
    content: str
