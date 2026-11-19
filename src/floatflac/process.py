import math
import struct
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .codec import decode_file, require_float_stream, run_codec
from .errors import FloatflacError
from .wav import iter_raw_chunks, read_wav_info, write_float_wav


@dataclass(frozen=True)
class ProcessResult:
    input_peak_dbfs: float
    target_dbfs: float
    output_peak_dbfs: float
    gain_db: float
    channels: int
    sample_rate: int
    samples: int
    source: str
    target: str


def _peak(path: Path, offset: int, size: int) -> tuple[float, int]:
    unpack = struct.Struct("<f")
    peak = 0.0
    count = 0
    for chunk in iter_raw_chunks(path, offset, size):
        if len(chunk) % unpack.size:
            raise FloatflacError(
                "process_failed",
                "Decoded raw data is not a multiple of 4 bytes.",
                "Check the FLAC file.",
            )
        for (value,) in unpack.iter_unpack(chunk):
            if not math.isfinite(value):
                raise FloatflacError(
                    "process_failed",
                    "Input contains NaN or Inf.",
                    "Input contains NaN or Inf; clean it before attenuation.",
                )
            peak = max(peak, abs(value))
            count += 1
    return peak, count


def _stream_info(codec, flac: Path) -> tuple[int, int]:
    proc = run_codec(
        [codec.metaflac, "--show-sample-rate", "--show-channels", str(flac)],
        "process_failed",
    )
    fields = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if len(fields) < 2:
        raise FloatflacError(
            "process_failed",
            "metaflac did not return sample rate and channels.",
            "Check the FLAC file.",
        )
    return int(fields[1]), int(float(fields[0]))


def attenuate(codec, src_flac, dst_wav, target_dbfs: float = -1.0) -> ProcessResult:
    if not math.isfinite(target_dbfs) or target_dbfs > 0:
        raise FloatflacError(
            "usage",
            f"target_dbfs must be finite and <= 0, got {target_dbfs}",
            "Choose a target at or below 0 dBFS.",
        )
    flac = Path(src_flac)
    wav = Path(dst_wav)
    require_float_stream(codec, flac, error_code="process_failed")
    channels, sample_rate = _stream_info(codec, flac)
    with TemporaryDirectory() as tmp:
        raw = Path(tmp) / "decoded.f32"
        decode_file(codec, flac, raw, raw=True)
        peak, samples = _peak(raw, 0, raw.stat().st_size)
        target_linear = 10 ** (target_dbfs / 20)
        gain = 1.0 if peak == 0.0 or peak <= target_linear else target_linear / peak
        unpack = struct.Struct("<f")

        def scaled():
            for chunk in iter_raw_chunks(raw, 0, raw.stat().st_size):
                for (value,) in unpack.iter_unpack(chunk):
                    yield value * gain

        write_float_wav(wav, scaled(), channels, sample_rate)
    info = read_wav_info(wav)
    output_peak, _count = _peak(wav, info.data_offset, info.data_size)
    return ProcessResult(
        input_peak_dbfs=20 * math.log10(peak) if peak > 0 else -math.inf,
        target_dbfs=target_dbfs,
        output_peak_dbfs=20 * math.log10(output_peak) if output_peak > 0 else -math.inf,
        gain_db=20 * math.log10(gain),
        channels=channels,
        sample_rate=sample_rate,
        samples=samples,
        source=str(flac),
        target=str(wav),
    )
