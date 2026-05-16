import struct


class RtpParser:
    NAL_TYPE_FU_A = 28
    NAL_TYPE_STAP_A = 24

    def __init__(self):
        self._fragments = bytearray()
        self._fragmenting = False

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

        sequence = struct.unpack(">H", data[2:4])[0]
        timestamp = struct.unpack(">I", data[4:8])[0]
        ssrc = struct.unpack(">I", data[8:12])[0]

        offset = 12 + (csrc_count * 4)

        if has_extension and offset + 4 <= len(data):
            ext_header = struct.unpack(">H", data[offset:offset + 2])[0]
            ext_length = struct.unpack(">H", data[offset + 2:offset + 4])[0]
            offset += 4 + ext_length * 4

        if offset >= len(data):
            return []

        nal_data = data[offset:]

        if len(nal_data) == 0:
            return []

        frames = []

        nal_type = nal_data[0] & 0x1F

        if nal_type == self.NAL_TYPE_STAP_A:
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
            frame = self._make_annexb(nal_data)
            frames.append(frame)

        return frames

    def _make_annexb(self, nalu: bytes) -> bytes:
        return b"\x00\x00\x00\x01" + nalu

    def reset(self):
        self._fragments.clear()
        self._fragmenting = False
