import random
import struct

import pytest
from conftest import make_wav

from floatflac.errors import FloatflacError
from floatflac.wav import iter_raw_chunks, read_wav_info


def test_wav_float32(tmp_path):
    path = make_wav(tmp_path / "sine.wav", channels=2, rate=48000, data=bytes(16 * 8))
    info = read_wav_info(path)
    assert (info.channels, info.sample_rate, info.bits_per_sample) == (2, 48000, 32)
    assert info.format_tag == 3 and info.subformat_tag is None
    assert info.data_offset == 12 + 8 + 16 + 8
    assert info.data_size == 128 and info.is_float32 is True


def test_wav_integer_rejected(tmp_path):
    path = make_wav(tmp_path / "int.wav", tag=1, bits=16)
    with pytest.raises(FloatflacError) as exc:
        read_wav_info(path)
    assert exc.value.code == "not_float32_wav"


def test_wav_extensible_float(tmp_path):
    path = make_wav(tmp_path / "ext.wav", tag=0xFFFE)
    info = read_wav_info(path)
    assert info.is_float32 is True and info.subformat_tag == 3
    assert info.format_tag == 0xFFFE


def test_wav_extensible_integer_rejected(tmp_path):
    path = make_wav(tmp_path / "ext-int.wav", tag=0xFFFE, bits=16)
    with pytest.raises(FloatflacError) as exc:
        read_wav_info(path)
    assert exc.value.code == "not_float32_wav"


@pytest.mark.parametrize("prefix", [b"RF64", b"W64 ", b"FORM"])
def test_rf64_rejected(tmp_path, prefix):
    path = make_wav(tmp_path / "big.wav", prefix=prefix)
    with pytest.raises(FloatflacError) as exc:
        read_wav_info(path)
    assert exc.value.code == "unsupported_container"


def test_truncated_chunk(tmp_path):
    path = make_wav(tmp_path / "trunc.wav")
    data = bytearray(path.read_bytes())
    data[20:24] = struct.pack("<I", 0xFFFF)
    path.write_bytes(data)
    with pytest.raises(FloatflacError) as exc:
        read_wav_info(path)
    assert exc.value.code == "invalid_wav"


def test_data_size_multiple(tmp_path):
    path = make_wav(tmp_path / "odd.wav", channels=2, data=bytes(17))
    with pytest.raises(FloatflacError) as exc:
        read_wav_info(path)
    assert exc.value.code == "invalid_wav"


def test_chunk_size_overflow(tmp_path):
    path = make_wav(tmp_path / "huge.wav", declared_size=0xFFFFFFFF)
    with pytest.raises(FloatflacError) as exc:
        read_wav_info(path)
    assert exc.value.code == "invalid_wav"
    assert path.stat().st_size < 1000


def test_odd_chunk_padding(tmp_path):
    extra = b"JUNK" + struct.pack("<I", 3) + b"abc\x00"
    path = make_wav(tmp_path / "padded.wav", extra_chunk=extra)
    info = read_wav_info(path)
    assert info.data_size == 16
    assert info.data_offset == 12 + 8 + 16 + len(extra) + 8


def test_missing_channels_and_rate(tmp_path):
    for channels, rate in ((0, 48000), (2, 0)):
        path = make_wav(
            tmp_path / f"bad-{channels}-{rate}.wav", channels=channels, rate=rate
        )
        with pytest.raises(FloatflacError) as exc:
            read_wav_info(path)
        assert exc.value.code == "invalid_wav"


def test_missing_input(tmp_path):
    with pytest.raises(FloatflacError) as exc:
        read_wav_info(tmp_path / "absent.wav")
    assert exc.value.code == "input_not_found"


def test_fuzz_random_bytes(tmp_path):
    generator = random.Random(1234)
    for index in range(1000):
        path = tmp_path / f"fuzz-{index}.bin"
        path.write_bytes(generator.randbytes(generator.randrange(0, 4096)))
        try:
            read_wav_info(path)
        except FloatflacError as exc:
            assert exc.code in {
                "invalid_wav",
                "unsupported_container",
                "not_float32_wav",
            }
            assert "\n" not in exc.message


def test_iter_raw_chunks(tmp_path):
    payload = bytes(range(256)) * 500
    path = tmp_path / "raw.bin"
    path.write_bytes(b"prefix" + payload + b"suffix")
    chunks = list(iter_raw_chunks(path, 6, len(payload), chunk_size=1000))
    assert b"".join(chunks) == payload
    assert all(len(chunk) <= 1000 for chunk in chunks)
