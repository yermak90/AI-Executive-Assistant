"""Real structural parsers for the non-WAV accepted formats (PRD §18.2 /
§31 P1-4: "verify actual MP3/M4A/AAC format, duration, and decodability" —
not just trust the magic bytes and skip duration entirely).

Each parser returns a duration in milliseconds on success, or None if the
bytes don't actually decode as that format (caller treats None as
AUDIO_CORRUPT). These are lightweight structural parsers, not full codec
implementations — enough to prove the file is a real, well-formed container
of its claimed type and to estimate its duration; the real STT adapter that
replaces the fake provider does full decoding.
"""

from __future__ import annotations

# --- MP3 (MPEG-1/2 Layer III) ------------------------------------------

# [mpeg_version_index][layer_index] -> bitrate table (kbps), indexed by the
# 4-bit bitrate field. mpeg_version_index: 0=MPEG2.5/2, 1=MPEG1.
# layer_index: 0=Layer III, 1=Layer II, 2=Layer I (as encoded in the header).
_MP3_BITRATES_V1_L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
_MP3_BITRATES_V2_L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]
_MP3_SAMPLERATES_V1 = [44100, 48000, 32000, 0]
_MP3_SAMPLERATES_V2 = [22050, 24000, 16000, 0]
_MP3_SAMPLERATES_V25 = [11025, 12000, 8000, 0]


def mp3_duration_ms(data: bytes) -> int | None:
    offset = 0
    if data[:3] == b"ID3" and len(data) >= 10:
        size = ((data[6] & 0x7F) << 21) | ((data[7] & 0x7F) << 14) | ((data[8] & 0x7F) << 7) | (data[9] & 0x7F)
        offset = 10 + size

    n = len(data)
    while offset + 4 <= n:
        if data[offset] != 0xFF or (data[offset + 1] & 0xE0) != 0xE0:
            offset += 1
            continue

        b1, b2 = data[offset + 1], data[offset + 2]
        version_bits = (b1 >> 3) & 0x3  # 00=MPEG2.5, 01=reserved, 10=MPEG2, 11=MPEG1
        layer_bits = (b1 >> 1) & 0x3  # 01=Layer III, 10=Layer II, 11=Layer I
        bitrate_index = (b2 >> 4) & 0xF
        samplerate_index = (b2 >> 2) & 0x3

        if version_bits == 1 or layer_bits != 0x1 or bitrate_index in (0, 0xF) or samplerate_index == 3:
            offset += 1
            continue

        if version_bits == 0x3:  # MPEG1
            bitrate_kbps = _MP3_BITRATES_V1_L3[bitrate_index]
            samplerate = _MP3_SAMPLERATES_V1[samplerate_index]
        elif version_bits == 0x2:  # MPEG2
            bitrate_kbps = _MP3_BITRATES_V2_L3[bitrate_index]
            samplerate = _MP3_SAMPLERATES_V2[samplerate_index]
        else:  # MPEG2.5
            bitrate_kbps = _MP3_BITRATES_V2_L3[bitrate_index]
            samplerate = _MP3_SAMPLERATES_V25[samplerate_index]

        if not bitrate_kbps or not samplerate:
            offset += 1
            continue

        # A real frame header — trust it for a CBR-equivalent duration
        # estimate over the remaining audio bytes (VBR files are only
        # approximated this way; good enough to bound min/max duration).
        audio_bytes = n - offset
        duration_sec = audio_bytes * 8 / (bitrate_kbps * 1000)
        return int(duration_sec * 1000)

    return None


# --- M4A / MP4 container (ISO-BMFF: moov -> mvhd) -----------------------


def _find_box(data: bytes, start: int, end: int, want: bytes) -> tuple[int, int] | None:
    pos = start
    while pos + 8 <= end:
        size = int.from_bytes(data[pos : pos + 4], "big")
        box_type = data[pos + 4 : pos + 8]
        header_size = 8
        if size == 1:
            if pos + 16 > end:
                return None
            size = int.from_bytes(data[pos + 8 : pos + 16], "big")
            header_size = 16
        elif size == 0:
            size = end - pos

        if size < header_size:
            return None
        if box_type == want:
            return pos + header_size, pos + size
        pos += size
    return None


def mp4_duration_ms(data: bytes) -> int | None:
    n = len(data)
    ftyp = _find_box(data, 0, n, b"ftyp")
    if ftyp is None:
        return None
    moov = _find_box(data, 0, n, b"moov")
    if moov is None:
        return None
    mvhd = _find_box(data, moov[0], moov[1], b"mvhd")
    if mvhd is None:
        return None

    start, end = mvhd
    if start >= end or start + 4 > n:
        return None
    version = data[start]
    try:
        if version == 1:
            timescale = int.from_bytes(data[start + 20 : start + 24], "big")
            duration = int.from_bytes(data[start + 24 : start + 32], "big")
        else:
            timescale = int.from_bytes(data[start + 12 : start + 16], "big")
            duration = int.from_bytes(data[start + 16 : start + 20], "big")
    except IndexError:
        return None

    if not timescale:
        return None
    return int(duration / timescale * 1000)


# --- Raw AAC (ADTS bitstream, no MP4 container) --------------------------

_ADTS_SAMPLERATES = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350]


def adts_aac_duration_ms(data: bytes) -> int | None:
    offset = 0
    n = len(data)
    samplerate: int | None = None
    frames = 0

    while offset + 7 <= n:
        if data[offset] != 0xFF or (data[offset + 1] & 0xF6) != 0xF0:
            offset += 1
            continue

        b2, b3, b4, b5 = data[offset + 2], data[offset + 3], data[offset + 4], data[offset + 5]
        sr_index = (b2 >> 2) & 0xF
        if sr_index >= len(_ADTS_SAMPLERATES):
            offset += 1
            continue
        frame_length = ((b3 & 0x03) << 11) | (b4 << 3) | ((b5 >> 5) & 0x07)
        if frame_length < 7 or offset + frame_length > n:
            break

        samplerate = _ADTS_SAMPLERATES[sr_index]
        frames += 1
        offset += frame_length

    if not frames or not samplerate:
        return None
    return int(frames * 1024 / samplerate * 1000)
