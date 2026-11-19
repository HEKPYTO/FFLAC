import struct
import subprocess
import sys
from pathlib import Path

import pytest

from floatflac.codec import encode_file, find_codec
from floatflac.errors import FloatflacError

ROOT = Path(__file__).resolve().parents[1]

FLOAT_GUID = bytes.fromhex("0300000000001000800000aa00389b71")


def _chunk(chunk_id: bytes, payload: bytes) -> bytes:
    return (
        chunk_id
        + struct.pack("<I", len(payload))
        + payload
        + (b"\x00" if len(payload) & 1 else b"")
    )


def make_wav(
    path: Path,
    *,
    channels: int = 2,
    rate: int = 48000,
    bits: int = 32,
    tag: int = 3,
    data: bytes | None = None,
    declared_size: int | None = None,
    extra_chunk: bytes = b"",
    prefix: bytes = b"RIFF",
    form: bytes = b"WAVE",
) -> Path:
    payload = bytes(channels * 4 * 2) if data is None else data
    fmt = struct.pack(
        "<HHIIHH", tag, channels, rate, rate * channels * 4, channels * 4, bits
    )
    if tag == 0xFFFE:
        fmt += struct.pack("<H", 22) + struct.pack("<HI", 32, 0) + FLOAT_GUID
    size = len(payload) if declared_size is None else declared_size
    body = (
        form
        + _chunk(b"fmt ", fmt)
        + extra_chunk
        + b"data"
        + struct.pack("<I", size)
        + payload
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(prefix + struct.pack("<I", len(body)) + body)
    return path


def make_fake_codec(
    directory: Path, *, flac_float: bool = True, meta_float: bool = True
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    flac_help = "--sample-type --force-dpa-mode" if flac_float else "--no-float-here"
    meta_help = "--show-sample-type --show-bps" if meta_float else "--no-float-here"
    for name, help_text in (("flac", flac_help), ("metaflac", meta_help)):
        script = directory / name
        script.write_text(
            "#!/bin/sh\n"
            f'if [ "$1" = "--help" ]; then echo "{help_text}"; fi\n'
            'if [ "$1" = "--version" ]; then echo "flac git-05536fce"; fi\n'
            'if [ "$1" = "--show-sample-type" ]; then echo "LPCM floating point (IEEE 754 binary32)"; fi\n'
        )
        script.chmod(0o755)
    return directory


@pytest.fixture(scope="session")
def codec():
    try:
        return find_codec()
    except FloatflacError as exc:
        pytest.skip(f"float-enabled flac codec unavailable: {exc.code}: {exc.message}")


@pytest.fixture(scope="session")
def fixtures(codec):
    directory = ROOT / "tests" / "fixtures"
    if (
        not (directory / "sine-f32-2ch-48k.wav").is_file()
        or not (directory / "hot-f32-2ch-48k.flac").is_file()
    ):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "fixtures.py")],
            check=True,
            capture_output=True,
            text=True,
        )
    return directory


@pytest.fixture(scope="session")
def sine_flac(codec, fixtures, tmp_path_factory):
    path = tmp_path_factory.mktemp("sine-flac") / "sine-f32-2ch-48k.flac"
    encode_file(codec, fixtures / "sine-f32-2ch-48k.wav", path)
    return path


@pytest.fixture
def fake_bin_dir(tmp_path):
    def build(*, flac_float: bool = True, meta_float: bool = True) -> Path:
        return make_fake_codec(
            tmp_path / "bin", flac_float=flac_float, meta_float=meta_float
        )

    return build
