import json
import math
import struct

import pytest

from floatflac.cli import main
from floatflac.codec import encode_file
from floatflac.errors import FloatflacError
from floatflac.process import attenuate
from floatflac.wav import iter_raw_chunks, read_wav_info, write_float_wav

TARGET_LINEAR = 10 ** (-1 / 20)


def make_flac(codec, tmp_path, samples, channels=2, rate=48000, name="in"):
    source = tmp_path / f"{name}.wav"
    write_float_wav(source, samples, channels, rate)
    flac = tmp_path / f"{name}.flac"
    encode_file(codec, source, flac, 5)
    return source, flac


def sine(amplitude=0.5, frames=4800, channels=2, rate=48000):
    return [
        amplitude
        * math.sin(2 * math.pi * (440.0 + 110.0 * (index % channels)) * index / rate)
        for index in range(frames * channels)
    ]


def samples_of(path):
    info = read_wav_info(path)
    data = b"".join(iter_raw_chunks(path, info.data_offset, info.data_size))
    return [value for (value,) in struct.iter_unpack("<f", data)]


def test_peak_above_zero_is_attenuated(codec, tmp_path):
    _source, flac = make_flac(codec, tmp_path, sine(2.0), name="hot")
    result = attenuate(codec, flac, tmp_path / "out.wav", -1.0)
    assert result.input_peak_dbfs > 0
    assert result.gain_db < 0
    assert result.output_peak_dbfs <= -1.0 + 1e-3
    assert (
        max(abs(value) for value in samples_of(tmp_path / "out.wav"))
        <= TARGET_LINEAR + 1e-6
    )
    assert result.samples == 4800 * 2
    assert result.channels == 2 and result.sample_rate == 48000


def test_below_target_unchanged(codec, tmp_path):
    source, flac = make_flac(codec, tmp_path, sine(0.1), name="quiet")
    out = tmp_path / "out.wav"
    result = attenuate(codec, flac, out, -1.0)
    assert result.gain_db == 0.0
    assert result.input_peak_dbfs == result.output_peak_dbfs
    source_info = read_wav_info(source)
    out_info = read_wav_info(out)
    assert b"".join(
        iter_raw_chunks(source, source_info.data_offset, source_info.data_size)
    ) == b"".join(iter_raw_chunks(out, out_info.data_offset, out_info.data_size))


def test_relative_shape_preserved(codec, tmp_path):
    source, flac = make_flac(codec, tmp_path, sine(2.0), name="hot")
    result = attenuate(codec, flac, tmp_path / "out.wav", -1.0)
    gain = 10 ** (result.gain_db / 20)
    original = samples_of(source)
    processed = samples_of(tmp_path / "out.wav")
    assert len(original) == len(processed)
    assert all(
        abs(processed[index] - original[index] * gain) <= 1e-6
        for index in range(len(original))
    )


def test_output_is_float32_wav(codec, tmp_path):
    _source, flac = make_flac(codec, tmp_path, sine(1.5), name="hot")
    out = tmp_path / "out.wav"
    attenuate(codec, flac, out, -3.0)
    info = read_wav_info(out)
    assert info.is_float32 is True and info.bits_per_sample == 32
    assert info.format_tag in (3, 0xFFFE)
    assert out.read_bytes()[32:34] == struct.pack("<H", info.channels * 4)


@pytest.mark.parametrize(
    "channels,expected_tag,expected_subformat", [(1, 3, None), (8, 0xFFFE, 3)]
)
def test_output_channel_format(
    codec, tmp_path, channels, expected_tag, expected_subformat
):
    _source, flac = make_flac(
        codec,
        tmp_path,
        sine(1.5, frames=2400, channels=channels),
        channels=channels,
        name="in",
    )
    out = tmp_path / "out.wav"
    attenuate(codec, flac, out, -3.0)
    info = read_wav_info(out)
    assert info.format_tag == expected_tag
    assert info.subformat_tag == expected_subformat
    assert info.is_float32 is True


def test_refuses_overwrite(codec, tmp_path, capsys):
    _source, flac = make_flac(codec, tmp_path, sine(1.5), name="hot")
    out = tmp_path / "out.wav"
    out.write_bytes(b"existing")
    code = main(["attenuate", str(flac), "-o", str(out), "--json"])
    envelope = json.loads(capsys.readouterr().out)
    assert code == 1 and envelope["error"]["code"] == "output_exists"
    assert out.read_bytes() == b"existing"
    assert main(["attenuate", str(flac), "-o", str(out), "--force", "--json"]) == 0


def test_human_output_has_no_lossless_claim(codec, tmp_path, capsys):
    _source, flac = make_flac(codec, tmp_path, sine(2.0), name="hot")
    code = main(["attenuate", str(flac), "-o", str(tmp_path / "out.wav")])
    output = capsys.readouterr().out
    assert code == 0
    assert "processed, not recovered" in output
    assert (
        "input_peak_dbfs" in output
        and "output_peak_dbfs" in output
        and "gain_db" in output
    )


def test_non_finite_peak_fails(codec, tmp_path):
    specials = [float("nan"), float("inf"), float("-inf"), -0.0, 0.25]
    _source, flac = make_flac(
        codec,
        tmp_path,
        [specials[index % len(specials)] for index in range(2000)],
        channels=1,
        name="special",
    )
    with pytest.raises(FloatflacError) as exc:
        attenuate(codec, flac, tmp_path / "out.wav", -1.0)
    assert exc.value.code == "process_failed"
    assert exc.value.fix == "Input contains NaN or Inf; clean it before attenuation."


@pytest.mark.parametrize("target", [1.0, float("nan"), float("inf")])
def test_invalid_target_rejected(codec, tmp_path, target):
    _source, flac = make_flac(codec, tmp_path, sine(0.5), name="in")
    with pytest.raises(FloatflacError):
        attenuate(codec, flac, tmp_path / "out.wav", target)


def test_integer_flac_rejected(codec, fixtures, tmp_path):
    with pytest.raises(FloatflacError) as exc:
        attenuate(codec, fixtures / "int16-2ch-48k.flac", tmp_path / "out.wav")
    assert exc.value.code == "not_float_stream"
