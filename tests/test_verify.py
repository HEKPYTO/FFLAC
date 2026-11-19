import hashlib
import random
from pathlib import Path

import pytest

from floatflac.errors import FloatflacError
from floatflac.verify import sha256_file, verify
from floatflac.wav import iter_raw_chunks, read_wav_info


@pytest.fixture
def source_wav(fixtures):
    return fixtures / "sine-f32-2ch-48k.wav"


def test_verify_ok(codec, sine_flac, source_wav):
    result = verify(codec, sine_flac, source_wav)
    info = read_wav_info(source_wav)
    assert result.verified is True
    assert result.bytes == info.data_size
    assert result.source_sha256 == result.decoded_sha256
    assert result.flac_sha256 == sha256_file(sine_flac)
    assert (
        result.source_sha256
        == hashlib.sha256(
            b"".join(iter_raw_chunks(source_wav, info.data_offset, info.data_size))
        ).hexdigest()
    )


def test_sha256_file(tmp_path):
    path = tmp_path / "bytes.bin"
    path.write_bytes(b"floatflac")
    assert sha256_file(path) == hashlib.sha256(b"floatflac").hexdigest()


def test_verify_detects_one_byte(monkeypatch, codec, sine_flac, source_wav):
    from floatflac import verify as verify_module

    original = verify_module.decode_file

    def corrupt(codec_paths, src, dst, raw=False):
        original(codec_paths, src, dst, raw=raw)
        data = bytearray(Path(dst).read_bytes())
        data[123] ^= 0xFF
        Path(dst).write_bytes(data)

    monkeypatch.setattr(verify_module, "decode_file", corrupt)
    with pytest.raises(FloatflacError) as exc:
        verify(codec, sine_flac, source_wav)
    assert exc.value.code == "verify_failed"
    assert "first differing byte offset 123" in exc.value.message
    assert "\n" not in exc.value.message


def test_verify_length_mismatch(monkeypatch, codec, sine_flac, source_wav):
    from floatflac import verify as verify_module

    original = verify_module.decode_file

    def truncate(codec_paths, src, dst, raw=False):
        original(codec_paths, src, dst, raw=raw)
        data = Path(dst).read_bytes()
        Path(dst).write_bytes(data[:-1])

    monkeypatch.setattr(verify_module, "decode_file", truncate)
    with pytest.raises(FloatflacError) as exc:
        verify(codec, sine_flac, source_wav)
    assert exc.value.code == "verify_failed"
    assert "length mismatch" in exc.value.message
    assert "\n" not in exc.value.message


def test_verify_rejects_integer_flac(codec, fixtures, source_wav):
    with pytest.raises(FloatflacError) as exc:
        verify(codec, fixtures / "int16-2ch-48k.flac", source_wav)
    assert exc.value.code == "not_float_stream"


def test_verify_rejects_integer_wav(codec, sine_flac, fixtures):
    with pytest.raises(FloatflacError) as exc:
        verify(codec, sine_flac, fixtures / "int16-2ch-48k.wav")
    assert exc.value.code == "not_float32_wav"


def test_verify_corrupt_flac_is_probe_failed(codec, source_wav, tmp_path):
    flac = tmp_path / "garbage.flac"
    flac.write_bytes(random.Random(7).randbytes(4096))
    with pytest.raises(FloatflacError) as exc:
        verify(codec, flac, source_wav)
    assert exc.value.code in {"probe_failed", "decode_failed"}
