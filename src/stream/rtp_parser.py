import struct


class RtpParser:
    NAL_TYPE_FU_A = 28
    NAL_TYPE_STAP_A = 24
    NAL_TYPE_AP = 48
    NAL_TYPE_FU = 49

    def __init__(self):
        self._fragments = bytearray()
        self._fragmenting = False
        self._is_h265 = False

    def set_codec(self, codec_name: str):
        self._is_h265 = "h265" in codec_name.lower() or "hevc" in codec_name.lower()

    @staticmethod
    def parse_header(data: bytes) -> dict | None:
        if len(data) < 12:
            return None
        first = data[0]
        version = (first >> 6) & 0x03
        if version != 2:
            return None
        padding = (first >> 5) & 0x01
        extension = (first >> 4) & 0x01
        csrc_count = first & 0x0F
        second = data[1]
        marker = (second >> 7) & 0x01
        payload_type = second & 0x7F
        seq = struct.unpack(">H", data[2:4])[0]
        ts = struct.unpack(">I", data[4:8])[0]
        ssrc = struct.unpack(">I", data[8:12])[0]
        offset = 12 + csrc_count * 4
        if extension and offset + 4 <= len(data):
            offset += 4 + struct.unpack(">H", data[offset + 2:offset + 4])[0] * 4
        payload_len = len(data) - offset
        if padding and payload_len > 0:
            payload_len -= data[-1]
        return {
            "version": version, "marker": marker, "payload_type": payload_type,
            "seq": seq, "ts": ts, "ssrc": ssrc, "payload_len": payload_len,
        }

    def parse(self, data: bytes) -> list[bytes]:
        if len(data) < 12:
            return []

        first_byte = data[0]
        version = (first_byte >> 6) & 0x03
        if version != 2:
            return []

        has_padding = (first_byte >> 5) & 0x01
        has_extension = (first_byte >> 4) & 0x01
        csrc_count = first_byte & 0x0F

        offset = 12 + (csrc_count * 4)

        if has_extension and offset + 4 <= len(data):
            ext_length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
            offset += 4 + ext_length * 4

        if offset >= len(data):
            return []

        nal_data = data[offset:]

        if has_padding and len(nal_data) > 0:
            padding_len = nal_data[-1]
            if 0 < padding_len <= len(nal_data):
                nal_data = nal_data[:-padding_len]

        if len(nal_data) == 0:
            return []

        if self._is_h265:
            return self._parse_h265(nal_data)
        else:
            return self._parse_h264(nal_data)

    def _parse_h264(self, nal_data: bytes) -> list[bytes]:
        frames = []
        nal_type = nal_data[0] & 0x1F

        if nal_type == self.NAL_TYPE_STAP_A:
            self._reset_fragments_if_needed()
            pos = 1
            while pos + 2 <= len(nal_data):
                nalu_size = struct.unpack(">H", nal_data[pos:pos + 2])[0]
                pos += 2
                if pos + nalu_size > len(nal_data):
                    break
                nalu = nal_data[pos:pos + nalu_size]
                pos += nalu_size
                frame = self._make_annexb(nalu)
                frames.append(frame)
        elif nal_type == self.NAL_TYPE_FU_A:
            fu_header = nal_data[1]
            start_bit = (fu_header >> 7) & 0x01
            end_bit = (fu_header >> 6) & 0x01
            fu_type = fu_header & 0x1F

            if start_bit:
                self._fragmenting = True
                self._fragments.clear()
                original_nal = (nal_data[0] & 0xE0) | fu_type
                self._fragments.append(original_nal)
                self._fragments.extend(nal_data[2:])
            elif self._fragmenting:
                self._fragments.extend(nal_data[2:])

            if end_bit and self._fragmenting:
                self._fragmenting = False
                frame = self._make_annexb(bytes(self._fragments))
                frames.append(frame)
                self._fragments.clear()
        else:
            self._reset_fragments_if_needed()
            frame = self._make_annexb(nal_data)
            frames.append(frame)

        return frames

    def _parse_h265(self, nal_data: bytes) -> list[bytes]:
        if len(nal_data) < 2:
            return []

        frames = []
        nal_type = (nal_data[0] >> 1) & 0x3F

        if nal_type == self.NAL_TYPE_AP:
            self._reset_fragments_if_needed()
            pos = 2
            while pos + 2 <= len(nal_data):
                nalu_size = struct.unpack(">H", nal_data[pos:pos + 2])[0]
                pos += 2
                if pos + nalu_size > len(nal_data):
                    break
                nalu = nal_data[pos:pos + nalu_size]
                pos += nalu_size
                frame = self._make_annexb(nalu)
                frames.append(frame)
        elif nal_type == self.NAL_TYPE_FU:
            if len(nal_data) < 3:
                return []
            fu_header = nal_data[2]
            start_bit = (fu_header >> 7) & 0x01
            end_bit = (fu_header >> 6) & 0x01
            fu_type = fu_header & 0x3F

            if start_bit:
                self._fragmenting = True
                self._fragments.clear()
                original_nal0 = (nal_data[0] & 0x81) | (fu_type << 1)
                original_nal1 = nal_data[1]
                self._fragments.append(original_nal0)
                self._fragments.append(original_nal1)
                self._fragments.extend(nal_data[3:])
            elif self._fragmenting:
                self._fragments.extend(nal_data[3:])

            if end_bit and self._fragmenting:
                self._fragmenting = False
                frame = self._make_annexb(bytes(self._fragments))
                frames.append(frame)
                self._fragments.clear()
        else:
            self._reset_fragments_if_needed()
            frame = self._make_annexb(nal_data)
            frames.append(frame)

        return frames

    def _reset_fragments_if_needed(self):
        if self._fragmenting:
            self._fragmenting = False
            self._fragments.clear()

    def _make_annexb(self, nalu: bytes) -> bytes:
        return b"\x00\x00\x00\x01" + nalu

    def reset(self):
        self._fragments.clear()
        self._fragmenting = False
