import random

import pytest

from floatflac.errors import FloatflacError
from floatflac.probe import probe
from floatflac.report import COMPATIBILITY_WARNING, compatibility_warning


def test_probe_float(codec, sine_flac):
    result = probe(codec, sine_flac)
    assert "floating point" in result.sample_type.lower()
    assert result.bps == 32
    assert result.channels == 2
    assert result.sample_rate == 48000.0
    assert result.mode in {"dpa", "mixed", "fallback"}
    assert result.mode_is_heuristic is True
    assert result.standard_decoder_compatible is False
    assert result.codec_commit == codec.commit
    assert result.float_support is True


def test_integer_flac_rejected(codec, fixtures):
    with pytest.raises(FloatflacError) as exc:
        probe(codec, fixtures / "int16-2ch-48k.flac")
    assert exc.value.code == "not_float_stream"


def test_compatibility_warning():
    warning = compatibility_warning()
    assert warning == COMPATIBILITY_WARNING
    assert "Standard FLAC decoders will refuse it." in warning
    assert "floatflac" in warning


def test_corrupt_flac_is_probe_failed(codec, tmp_path):
    flac = tmp_path / "garbage.flac"
    flac.write_bytes(random.Random(7).randbytes(4096))
    with pytest.raises(FloatflacError) as exc:
        probe(codec, flac)
    assert exc.value.code == "probe_failed"
