import json
import math
import struct
import subprocess
from pathlib import Path

import pytest

from floatflac.cli import main
from floatflac.codec import CodecPaths, encode_file
from floatflac.verify import verify
from floatflac.wav import read_wav_info, write_float_wav


def signal(channels: int, rate: int, frames: int | None = None) -> list[float]:
    count = round(rate * 0.25) if frames is None else frames
    return [
        0.5
        * math.sin(2 * math.pi * (440.0 + 110.0 * (index % channels)) * index / rate)
        for index in range(count * channels)
    ]


@pytest.mark.parametrize("channels", [1, 2, 8])
@pytest.mark.parametrize("rate", [44100, 48000, 96000])
@pytest.mark.parametrize("preset", [0, 5, 8])
def test_matrix_channels_rates_presets(codec, tmp_path, channels, rate, preset):
    source = tmp_path / "in.wav"
    write_float_wav(source, iter(signal(channels, rate)), channels, rate)
    flac = tmp_path / "out.flac"
    encode_file(codec, source, flac, preset)
    result = verify(codec, flac, source)
    assert result.verified is True
    assert result.source_sha256 == result.decoded_sha256
    assert result.bytes == read_wav_info(source).data_size


def test_special_values_bit_exact(codec, tmp_path):
    specials = [
        float("nan"),
        float("inf"),
        float("-inf"),
        struct.unpack("<f", b"\x01\x00\x00\x00")[0],
        -0.0,
        0.25,
        -0.125,
    ]
    samples = [specials[index % len(specials)] for index in range(4000)]
    source = tmp_path / "special.wav"
    write_float_wav(source, samples, 1, 48000)
    flac = tmp_path / "special.flac"
    encode_file(codec, source, flac, 5)
    result = verify(codec, flac, source)
    assert result.verified is True
    assert result.source_sha256 == result.decoded_sha256


@pytest.mark.parametrize("extra", [("--force-fallback-mode",), ("--seekpoint=100s",)])
def test_extra_args_bit_exact(codec, tmp_path, extra):
    source = tmp_path / "in.wav"
    write_float_wav(source, signal(2, 48000), 2, 48000)
    flac = tmp_path / "out.flac"
    encode_file(codec, source, flac, 5, extra)
    result = verify(codec, flac, source)
    assert result.verified is True
    assert result.source_sha256 == result.decoded_sha256


def test_extra_args_land_before_source(monkeypatch):
    calls = []

    def fake_run(args, _code):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("floatflac.codec.run_codec", fake_run)
    codec = CodecPaths(Path("bin/flac"), Path("bin/metaflac"), "05536fc", True)
    encode_file(codec, Path("in.wav"), Path("out.flac"), 8, ("--seekpoint=100s",))
    argv = [str(arg) for arg in calls[0]]
    assert argv.index("--seekpoint=100s") < argv.index("in.wav")


def test_verify_json(codec, fixtures, tmp_path, capsys):
    source = fixtures / "sine-f32-2ch-48k.wav"
    flac = tmp_path / "sine.flac"
    encode_file(codec, source, flac, 5)
    code = main(["verify", str(flac), "--source", str(source), "--json"])
    envelope = json.loads(capsys.readouterr().out)
    data = envelope["data"]
    assert code == 0
    assert set(envelope) == {"schema", "command", "data", "error"}
    assert data["verified"] is True
    assert data["source_sha256"] == data["decoded_sha256"] and data["flac_sha256"]
    assert data["bytes"] == source.stat().st_size - 44
