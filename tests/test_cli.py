import json
import shutil

from floatflac.cli import main
from floatflac.report import COMPATIBILITY_WARNING
from floatflac.wav import iter_raw_chunks, read_wav_info

ENVELOPE_KEYS = {"schema", "command", "data", "error"}


def run(capsys, argv):
    code = main(argv)
    captured = capsys.readouterr()
    return code, captured


def one_json(captured):
    lines = captured.out.splitlines()
    assert len(lines) == 1, lines
    envelope = json.loads(lines[0])
    assert set(envelope) == ENVELOPE_KEYS
    assert envelope["schema"] == "floatflac/v1"
    return envelope


def copy_fixture(fixtures, name, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixtures / name, target)
    return target


def test_encode_default_target(codec, fixtures, tmp_path, capsys):
    source = copy_fixture(fixtures, "sine-f32-2ch-48k.wav", tmp_path / "master.wav")
    code, captured = run(capsys, ["encode", str(source), "--json"])
    envelope = one_json(captured)
    assert code == 0
    assert envelope["command"] == "encode" and envelope["error"] is None
    assert envelope["data"]["target"] == str(source.with_suffix(".flac"))
    assert envelope["data"]["verified"] is True
    assert envelope["data"]["source_sha256"] == envelope["data"]["decoded_sha256"]
    assert source.with_suffix(".flac").is_file()


def test_encode_refuses_overwrite(codec, fixtures, tmp_path, capsys):
    source = copy_fixture(fixtures, "sine-f32-2ch-48k.wav", tmp_path / "master.wav")
    target = source.with_suffix(".flac")
    target.write_bytes(b"existing")
    code, captured = run(capsys, ["encode", str(source), "--json"])
    envelope = one_json(captured)
    assert code == 1
    assert envelope["data"] is None
    assert envelope["error"]["code"] == "output_exists"
    assert "\n" not in envelope["error"]["message"]
    assert target.read_bytes() == b"existing"


def test_encode_integer_wav_rejected(codec, fixtures, capsys):
    code, captured = run(
        capsys, ["encode", str(fixtures / "int16-2ch-48k.wav"), "--json"]
    )
    envelope = one_json(captured)
    assert code == 1 and envelope["error"]["code"] == "not_float32_wav"


def test_decode_wav(codec, sine_flac, tmp_path, capsys):
    target = tmp_path / "out.wav"
    code, captured = run(
        capsys, ["decode", str(sine_flac), "-o", str(target), "--json"]
    )
    envelope = one_json(captured)
    assert code == 0 and envelope["data"]["target"] == str(target)
    info = read_wav_info(target)
    assert info.is_float32 and info.bits_per_sample == 32
    assert info.channels == 2 and info.sample_rate == 48000


def test_decode_raw(codec, sine_flac, fixtures, tmp_path, capsys):
    target = tmp_path / "out.f32"
    code, captured = run(
        capsys, ["decode", str(sine_flac), "--raw", "-o", str(target), "--json"]
    )
    assert code == 0 and one_json(captured)["data"]["raw"] is True
    source_wav = fixtures / "sine-f32-2ch-48k.wav"
    info = read_wav_info(source_wav)
    expected = b"".join(iter_raw_chunks(source_wav, info.data_offset, info.data_size))
    assert target.read_bytes() == expected


def test_verify_sine(codec, sine_flac, fixtures, capsys):
    source = fixtures / "sine-f32-2ch-48k.wav"
    code, captured = run(
        capsys, ["verify", str(sine_flac), "--source", str(source), "--json"]
    )
    envelope = one_json(captured)
    assert code == 0
    assert envelope["data"]["verified"] is True
    assert envelope["data"]["source_sha256"] == envelope["data"]["decoded_sha256"]


def test_integer_flac_rejected(codec, fixtures, tmp_path, capsys):
    flac = fixtures / "int16-2ch-48k.flac"
    code, captured = run(
        capsys,
        ["decode", str(flac), "-o", str(tmp_path / "out.f32"), "--raw", "--json"],
    )
    assert code == 1 and one_json(captured)["error"]["code"] == "not_float_stream"
    code, captured = run(capsys, ["probe", str(flac), "--json"])
    assert code == 1 and one_json(captured)["error"]["code"] == "not_float_stream"


def test_probe_envelope(codec, sine_flac, capsys):
    code, captured = run(capsys, ["probe", str(sine_flac), "--json"])
    envelope = one_json(captured)
    assert code == 0
    assert envelope["data"]["bps"] == 32
    assert envelope["data"]["standard_decoder_compatible"] is False
    assert envelope["data"]["mode_is_heuristic"] is True
    assert envelope["data"]["flac_sha256"] and envelope["data"]["flac_bytes"] > 0


def test_corrupt_flac_is_decode_failed(codec, tmp_path, capsys):
    flac = tmp_path / "bad.flac"
    flac.write_bytes(b"not a flac stream")
    code, captured = run(capsys, ["decode", str(flac), "--json"])
    assert code == 1 and one_json(captured)["error"]["code"] == "decode_failed"


def test_missing_input(codec, tmp_path, capsys):
    code, captured = run(capsys, ["encode", str(tmp_path / "missing.wav"), "--json"])
    assert code == 1 and one_json(captured)["error"]["code"] == "input_not_found"


def test_exit_codes(codec, fixtures, capsys):
    assert (
        run(
            capsys, ["encode", str(fixtures / "sine-f32-2ch-48k.wav"), "--preset", "9"]
        )[0]
        == 2
    )


def test_json_envelope_for_every_command(codec, sine_flac, fixtures, tmp_path, capsys):
    commands = [
        [
            "encode",
            str(fixtures / "sine-f32-2ch-48k.wav"),
            "-o",
            str(tmp_path / "copy.flac"),
            "--json",
        ],
        [
            "verify",
            str(sine_flac),
            "--source",
            str(fixtures / "sine-f32-2ch-48k.wav"),
            "--json",
        ],
        ["probe", str(sine_flac), "--json"],
        ["decode", str(sine_flac), "-o", str(tmp_path / "copy.wav"), "--json"],
        ["doctor", "--json"],
        ["version", "--json"],
    ]
    for argv in commands:
        code, captured = run(capsys, argv)
        assert code == 0, argv
        assert set(one_json(captured)) == ENVELOPE_KEYS


def test_human_output_has_warning(codec, sine_flac, fixtures, tmp_path, capsys):
    source = copy_fixture(fixtures, "sine-f32-2ch-48k.wav", tmp_path / "master.wav")
    _, encoded = run(capsys, ["encode", str(source)])
    assert COMPATIBILITY_WARNING in encoded.out
    assert "sha256=" in encoded.out
    _, probed = run(capsys, ["probe", str(sine_flac)])
    assert COMPATIBILITY_WARNING in probed.out
    assert "sha256=" in probed.out
    _, verified = run(
        capsys,
        ["verify", str(sine_flac), "--source", str(fixtures / "sine-f32-2ch-48k.wav")],
    )
    assert "sha256=" in verified.out


def test_paths_with_spaces(codec, fixtures, tmp_path, capsys):
    directory = tmp_path / "folder with spaces"
    source = copy_fixture(
        fixtures, "sine-f32-2ch-48k.wav", directory / "master copy.wav"
    )
    code, _ = run(capsys, ["encode", str(source)])
    assert code == 0
    flac = source.with_suffix(".flac")
    code, _ = run(
        capsys, ["decode", str(flac), "--raw", "-o", str(directory / "decoded raw.f32")]
    )
    assert code == 0
    assert (directory / "decoded raw.f32").stat().st_size > 0


def test_usage_error_with_json_is_envelope(capsys):
    code, captured = run(capsys, ["encode", "--json"])
    envelope = one_json(captured)
    assert code == 2
    assert envelope["command"] == "encode"
    assert envelope["data"] is None
    assert envelope["error"]["code"] == "usage"
    assert captured.err == ""


def test_unknown_command_with_json_is_envelope(capsys):
    code, captured = run(capsys, ["bogus", "--json"])
    envelope = one_json(captured)
    assert code == 2
    assert envelope["command"] == "bogus"
    assert envelope["error"]["code"] == "usage"


def test_unknown_command_human_is_usage(capsys):
    code, captured = run(capsys, ["bogus"])
    assert code == 2
    assert "usage:" in captured.err
    assert "fix: Run floatflac --help." in captured.err
