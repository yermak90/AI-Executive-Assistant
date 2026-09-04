"""PRD §31 P1-4: real structural parsers for MP3/M4A/AAC, not just magic-byte
sniffing with duration skipped. Pure unit tests — no DB, no app."""

from app.services.audio_formats import adts_aac_duration_ms, mp3_duration_ms, mp4_duration_ms

# --- MP3 ---------------------------------------------------------------


def _mp3_bytes(trailing_bytes: int) -> bytes:
    # MPEG1 Layer III, no CRC, bitrate index 9 (128 kbps), samplerate index 0 (44100 Hz).
    header = bytes([0xFF, 0xFB, 0x90, 0x00])
    return header + b"\x00" * trailing_bytes


def test_mp3_duration_ms_computes_real_duration_from_frame_header():
    data = _mp3_bytes(128_000 // 8)  # ~1 second of audio at 128 kbps
    duration = mp3_duration_ms(data)
    assert duration is not None
    assert 950 <= duration <= 1050


def test_mp3_duration_ms_rejects_data_with_no_valid_frame():
    assert mp3_duration_ms(b"this is not an mp3 frame at all" * 20) is None


def test_mp3_duration_ms_skips_id3_tag_before_first_frame():
    id3_size = 100
    size_bytes = bytes(
        [(id3_size >> 21) & 0x7F, (id3_size >> 14) & 0x7F, (id3_size >> 7) & 0x7F, id3_size & 0x7F]
    )
    id3 = b"ID3" + b"\x03\x00\x00" + size_bytes + b"\x00" * id3_size
    data = id3 + _mp3_bytes(64_000 // 8)
    duration = mp3_duration_ms(data)
    assert duration is not None


# --- M4A / MP4 -----------------------------------------------------------


def _box(box_type: bytes, body: bytes) -> bytes:
    return (8 + len(body)).to_bytes(4, "big") + box_type + body


def _m4a_bytes(duration_units: int, timescale: int) -> bytes:
    ftyp = _box(b"ftyp", b"isom" + b"\x00\x00\x00\x00" + b"isom")
    mvhd_body = (
        b"\x00\x00\x00\x00"  # version(0) + flags
        + b"\x00\x00\x00\x00"  # creation_time
        + b"\x00\x00\x00\x00"  # modification_time
        + timescale.to_bytes(4, "big")
        + duration_units.to_bytes(4, "big")
        + b"\x00" * 70  # remaining mvhd fields — never read for version 0
    )
    mvhd = _box(b"mvhd", mvhd_body)
    moov = _box(b"moov", mvhd)
    return ftyp + moov


def test_mp4_duration_ms_reads_mvhd_timescale_and_duration():
    data = _m4a_bytes(duration_units=44100 * 3, timescale=44100)
    assert mp4_duration_ms(data) == 3000


def test_mp4_duration_ms_none_without_ftyp():
    moov = _box(b"moov", _box(b"mvhd", b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" + (44100).to_bytes(4, "big") + (44100).to_bytes(4, "big")))
    assert mp4_duration_ms(moov) is None  # ftyp missing entirely
    assert mp4_duration_ms(_box(b"ftyp", b"isom") + moov) == 1000


def test_mp4_duration_ms_none_without_mvhd():
    ftyp = _box(b"ftyp", b"isom")
    moov = _box(b"moov", b"")  # no mvhd inside
    assert mp4_duration_ms(ftyp + moov) is None


# --- Raw AAC (ADTS) -------------------------------------------------------


def _adts_frame(frame_length: int, sr_index: int = 4, channel_config: int = 2) -> bytes:
    profile = 1  # AAC LC
    b0 = 0xFF
    b1 = 0xF1  # syncword low nibble + ID(0) + layer(00) + protection_absent(1)
    b2 = (profile << 6) | (sr_index << 2) | ((channel_config >> 2) & 0x1)
    b3 = ((channel_config & 0x3) << 6) | ((frame_length >> 11) & 0x3)
    b4 = (frame_length >> 3) & 0xFF
    b5 = ((frame_length & 0x7) << 5) | 0x1F
    b6 = 0xFC
    return bytes([b0, b1, b2, b3, b4, b5, b6]) + b"\x00" * (frame_length - 7)


def test_adts_aac_duration_ms_computes_real_duration_from_frame_count():
    frame = _adts_frame(frame_length=200, sr_index=4)  # 44100 Hz
    data = frame * 44  # 44 frames * 1024 samples / 44100 Hz ≈ 1.02s
    duration = adts_aac_duration_ms(data)
    expected = int(44 * 1024 / 44100 * 1000)
    assert duration is not None
    assert abs(duration - expected) < 5


def test_adts_aac_duration_ms_rejects_data_with_no_valid_frame():
    assert adts_aac_duration_ms(b"definitely not an aac stream" * 20) is None
