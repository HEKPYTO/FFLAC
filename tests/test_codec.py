import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import make_fake_codec

from floatflac.codec import (
    CodecPaths,
    decode_file,
    doctor,
    encode_file,
    find_codec,
    require_float_stream,
    run_codec,
)
from floatflac.errors import FloatflacError

CODEC = CodecPaths(Path("bin/flac"), Path("bin/metaflac"), "05536fc", True)


def test_find_codec_env(monkeypatch, tmp_path, fake_bin_dir):
    directory = fake_bin_dir()
    monkeypatch.setenv("FLOATFLAC_BIN_DIR", str(directory))
    codec = find_codec(tmp_path / "unused-project")
    assert codec.flac == directory / "flac"
    assert codec.metaflac == directory / "metaflac"
    assert codec.float_enabled is True


def test_project_build_found(monkeypatch, tmp_path):
    monkeypatch.delenv("FLOATFLAC_BIN_DIR", raising=False)
    directory = tmp_path / ".build/flac-float/build/src"
    make_fake_codec(directory / "flac")
    make_fake_codec(directory / "metaflac")
    codec = find_codec(tmp_path)
    assert codec.flac == directory / "flac/flac"
    assert codec.metaflac == directory / "metaflac/metaflac"


@pytest.mark.parametrize("flac_float,meta_float", [(False, True), (True, False)])
def test_find_codec_rejects_stock(
    monkeypatch, tmp_path, fake_bin_dir, flac_float, meta_float
):
    directory = fake_bin_dir(flac_float=flac_float, meta_float=meta_float)
    monkeypatch.setenv("FLOATFLAC_BIN_DIR", str(directory))
    with pytest.raises(FloatflacError) as exc:
        find_codec(tmp_path / "unused")
    assert exc.value.code == "codec_not_float_enabled"
    assert "ENABLE_EXPERIMENTAL_FLOAT_SAMPLE_CODING=ON" in exc.value.fix


def test_missing_codec(monkeypatch, tmp_path):
    monkeypatch.delenv("FLOATFLAC_BIN_DIR", raising=False)
    monkeypatch.setattr("floatflac.codec.shutil.which", lambda name: None)
    with pytest.raises(FloatflacError) as exc:
        find_codec(tmp_path)
    assert exc.value.code == "codec_missing"
    assert "scripts/build-codec.sh" in exc.value.fix


def test_encode_args(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("floatflac.codec.subprocess.run", fake_run)
    encode_file(CODEC, Path("dir with space/in.wav"), Path("dir with space/out.flac"))
    assert calls == [
        [
            "bin/flac",
            "-f",
            "-5",
            "--verify",
            "dir with space/in.wav",
            "-o",
            "dir with space/out.flac",
        ]
    ]


def test_no_lossy_flags(monkeypatch):
    calls = []

    def fake_run(args, code):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("floatflac.codec.run_codec", fake_run)
    encode_file(CODEC, Path("in.wav"), Path("out.flac"), preset=5)
    argv = [str(arg) for arg in calls[0]]
    assert not any(str(f).lower().startswith("--force") for f in argv)
    assert "--verify" in argv


def test_decode_raw_args(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("floatflac.codec.subprocess.run", fake_run)
    decode_file(CODEC, Path("in.flac"), Path("out.f32"), raw=True)
    assert calls == [
        [
            "bin/flac",
            "-d",
            "-f",
            "--force-raw-format",
            "--sample-type=float",
            "in.flac",
            "-o",
            "out.f32",
        ]
    ]


def test_decode_wav_args(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("floatflac.codec.subprocess.run", fake_run)
    decode_file(CODEC, Path("in.flac"), Path("out.wav"))
    assert calls[0] == ["bin/flac", "-d", "-f", "in.flac", "-o", "out.wav"]


def test_run_codec_reports_last_stderr_line(monkeypatch):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 1, "stdout detail", "first line\nlast line\n"
        )

    monkeypatch.setattr("floatflac.codec.subprocess.run", fake_run)
    with pytest.raises(FloatflacError) as exc:
        run_codec(["flac"], "decode_failed")
    assert exc.value.code == "decode_failed"
    assert exc.value.message == "last line"
    assert "\n" not in exc.value.message


@pytest.mark.parametrize(
    "output,accepted",
    [
        ("LPCM floating point (IEEE 754 binary32)", True),
        ("LPCM 16-bit", False),
        ("", False),
    ],
)
def test_require_float_stream(monkeypatch, output, accepted):
    monkeypatch.setattr(
        "floatflac.codec.run_codec", lambda args, code: SimpleNamespace(stdout=output)
    )
    if accepted:
        assert require_float_stream(CODEC, Path("in.flac")) == output
    else:
        with pytest.raises(FloatflacError) as exc:
            require_float_stream(CODEC, Path("in.flac"))
        assert exc.value.code == "not_float_stream"


def test_doctor_without_codec(monkeypatch, tmp_path):
    monkeypatch.setenv("FLOATFLAC_BIN_DIR", str(tmp_path / "empty"))
    data = doctor(tmp_path)
    assert data["ok"] is False
    assert data["error_code"] == "codec_missing"
    assert data["python"] and data["platform"]


def test_doctor_with_codec(codec):
    data = doctor()
    assert data["ok"] is True
    assert data["flac"] and data["metaflac"]
    assert data["flac_version"]
    assert data["flac_sample_type"] and data["metaflac_sample_type"]
