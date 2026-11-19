import math
import shutil
import subprocess
from pathlib import Path

import pytest

from floatflac.codec import decode_file, encode_file
from floatflac.probe import probe
from floatflac.wav import write_float_wav

FIXTURE = (
    Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "hot-f32-2ch-48k.flac"
)
STOCK_FLAC = shutil.which("flac")
FFMPEG = shutil.which("ffmpeg")

pytestmark = pytest.mark.skipif(
    STOCK_FLAC is None, reason="stock flac is not installed"
)


def _stream(codec, tmp_path):
    if FIXTURE.is_file():
        return FIXTURE
    source = tmp_path / "short-f32.wav"
    samples = [
        0.5 * math.sin(2 * math.pi * 440 * index / 48000) for index in range(4800)
    ]
    write_float_wav(source, samples, 1, 48000)
    target = tmp_path / "short-f32.flac"
    encode_file(codec, source, target)
    return target


def test_stock_flac_rejects(codec, tmp_path):
    stream = _stream(codec, tmp_path)
    result = subprocess.run(
        [STOCK_FLAC, "-t", str(stream)], check=False, capture_output=True, text=True
    )
    assert result.returncode != 0


@pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is not installed")
def test_ffmpeg_rejects(codec, tmp_path):
    stream = _stream(codec, tmp_path)
    result = subprocess.run(
        [FFMPEG, "-hide_banner", "-v", "error", "-i", str(stream), "-f", "null", "-"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_float_codec_decodes(codec, tmp_path):
    stream = _stream(codec, tmp_path)
    target = tmp_path / "decoded.wav"
    decode_file(codec, stream, target)
    assert target.is_file() and target.stat().st_size > 0


def test_probe_reports_incompatible(codec, tmp_path):
    stream = _stream(codec, tmp_path)
    assert probe(codec, stream).standard_decoder_compatible is False
