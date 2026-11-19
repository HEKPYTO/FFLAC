import math
import struct
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .codec import decode_file, read_stream_info, require_float_stream
from .errors import FloatflacError
from .wav import iter_raw_chunks, read_wav_info, write_float_wav


@dataclass(frozen=True)
class ProcessResult:
    input_peak_dbfs: float | None
    target_dbfs: float
    output_peak_dbfs: float | None
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


def attenuate(codec, src_flac, dst_wav, target_dbfs: float = -1.0) -> ProcessResult:
    if not math.isfinite(target_dbfs) or not -200 <= target_dbfs <= 0:
        raise FloatflacError(
            "usage",
            "target must be between -200 and 0 dBFS",
            "Choose a target between -200 and 0 dBFS.",
        )
    flac = Path(src_flac)
    wav = Path(dst_wav)
    require_float_stream(codec, flac, error_code="process_failed")
    stream = read_stream_info(codec, flac, error_code="process_failed")
    channels = stream.channels
    sample_rate = int(stream.sample_rate)
    with TemporaryDirectory() as tmp:
        raw = Path(tmp) / "decoded.f32"
        decode_file(codec, flac, raw, raw=True)
        peak, samples = _peak(raw, 0, raw.stat().st_size)
        input_peak_dbfs = 20 * math.log10(peak) if peak > 0 else None
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
    output_peak_dbfs = 20 * math.log10(output_peak) if output_peak > 0 else None
    return ProcessResult(
        input_peak_dbfs=input_peak_dbfs,
        target_dbfs=target_dbfs,
        output_peak_dbfs=output_peak_dbfs,
        gain_db=20 * math.log10(gain),
        channels=channels,
        sample_rate=sample_rate,
        samples=samples,
        source=str(flac),
        target=str(wav),
    )
