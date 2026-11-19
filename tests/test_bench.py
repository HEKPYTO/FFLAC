import json
import math
from pathlib import Path

import pytest
from conftest import make_wav

from floatflac.bench import bench
from floatflac.cli import main
from floatflac.codec import encode_file
from floatflac.errors import FloatflacError
from floatflac.wav import write_float_wav


def write_sine(
    path: Path, channels: int = 2, rate: int = 48000, seconds: float = 0.5
) -> None:
    frames = round(rate * seconds)
    samples = [
        0.5 * math.sin(2 * math.pi * 440 * index / rate)
        for index in range(frames * channels)
    ]
    write_float_wav(path, samples, channels, rate)


def test_bench_empty_dir(tmp_path):
    with pytest.raises(FloatflacError) as exc:
        bench(tmp_path)
    assert exc.value.code == "input_not_found"
    assert ".wav" in exc.value.fix


def test_bench_one_file(codec, tmp_path):
    write_sine(tmp_path / "sine.wav", seconds=2.0)
    report = bench(tmp_path)
    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.verified is True and row.skipped is None
    assert row.ratio > 0 and row.encode_rtf > 1.0 and row.decode_rtf > 0
    assert report.totals.files == 1
    assert report.totals.source_bytes == row.source_bytes
    assert report.totals.flac_bytes == row.flac_bytes
    assert report.preset == 5 and report.machine and report.python


def test_bench_json_recurses_and_has_totals(codec, tmp_path, capsys):
    nested = tmp_path / "nested"
    nested.mkdir()
    write_sine(tmp_path / "first.wav", channels=1)
    write_sine(nested / "second.wav", channels=8)
    code = main(["bench", str(tmp_path), "--json"])
    envelope = json.loads(capsys.readouterr().out)
    assert code == 0
    assert set(envelope) == {"schema", "command", "data", "error"}
    assert len(envelope["data"]["rows"]) == 2
    assert envelope["data"]["totals"]["files"] == 2
    assert envelope["data"]["totals"]["ratio"] > 0


def test_bench_skips_non_float(codec, tmp_path, monkeypatch):
    write_sine(tmp_path / "float.wav")
    make_wav(tmp_path / "int.wav", tag=1, bits=16)
    calls = []
    original = encode_file

    def counting(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr("floatflac.bench.encode_file", counting)
    report = bench(tmp_path)
    assert len(calls) == 1
    skipped = [row for row in report.rows if row.skipped]
    assert len(skipped) == 1
    assert "not_float32_wav" in skipped[0].skipped
    assert skipped[0].verified is False
    assert report.totals.files == 1


def test_bench_out_file_parses(codec, tmp_path, capsys):
    write_sine(tmp_path / "sine.wav")
    out = tmp_path / "nested" / "report.json"
    code = main(["bench", str(tmp_path), "--out", str(out)])
    assert code == 0
    assert "TOTAL" in capsys.readouterr().out
    envelope = json.loads(out.read_text())
    assert envelope["command"] == "bench"
    assert envelope["data"]["totals"]["files"] == 1


def test_bench_out_refuses_overwrite(codec, tmp_path, capsys):
    write_sine(tmp_path / "sine.wav")
    out = tmp_path / "report.json"
    out.write_text("original")
    code = main(["bench", str(tmp_path), "--out", str(out), "--json"])
    envelope = json.loads(capsys.readouterr().out)
    assert code == 1
    assert envelope["error"]["code"] == "output_exists"
    assert out.read_text() == "original"


def test_bench_out_force_overwrites(codec, tmp_path, capsys):
    write_sine(tmp_path / "sine.wav")
    out = tmp_path / "report.json"
    out.write_text("original")
    code = main(["bench", str(tmp_path), "--out", str(out), "--force", "--json"])
    assert code == 0
    envelope = json.loads(out.read_text())
    assert envelope["data"]["totals"]["files"] == 1
    assert json.loads(capsys.readouterr().out)["command"] == "bench"


def test_bench_out_matches_stdout(codec, tmp_path, capsys):
    write_sine(tmp_path / "sine.wav", seconds=2.0)
    out = tmp_path / "report.json"
    code = main(["bench", str(tmp_path), "--out", str(out), "--json"])
    captured = capsys.readouterr()
    assert code == 0
    assert out.read_text() == captured.out
