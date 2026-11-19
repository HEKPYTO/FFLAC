import platform
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from .codec import decode_file, encode_file, find_codec
from .errors import FloatflacError
from .verify import verify
from .wav import WavInfo, read_wav_info


@dataclass(frozen=True)
class BenchRow:
    file: str
    channels: int | None
    sample_rate: int | None
    source_bytes: int
    flac_bytes: int
    ratio: float
    encode_rtf: float
    decode_rtf: float
    verified: bool
    skipped: str | None


@dataclass(frozen=True)
class BenchTotals:
    files: int
    source_bytes: int
    flac_bytes: int
    ratio: float


@dataclass(frozen=True)
class BenchReport:
    machine: str
    python: str
    codec_commit: str | None
    preset: int
    rows: list[BenchRow]
    totals: BenchTotals


def bench(directory, preset: int = 5) -> BenchReport:
    root = Path(directory)
    if not root.is_dir():
        raise FloatflacError(
            "input_not_found",
            f"{root}: no such directory",
            "Pass a directory containing float32 .wav files.",
        )
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() == ".wav"
    )
    if not paths:
        raise FloatflacError(
            "input_not_found",
            f"{root}: no .wav files found",
            "Point bench at a directory containing float32 .wav files.",
        )

    infos: list[tuple[Path, WavInfo | None, str | None]] = []
    for path in paths:
        try:
            infos.append((path, read_wav_info(path), None))
        except FloatflacError as exc:
            reason = f"{exc.code}: {exc.message}"
            infos.append((path, None, reason))
    if not any(info is not None for _path, info, _reason in infos):
        raise FloatflacError(
            "input_not_found",
            f"{root}: no float32 WAV files found",
            "Convert the WAV files to 32-bit float before benchmarking.",
        )

    codec = find_codec()
    measured: dict[Path, BenchRow] = {}
    with TemporaryDirectory() as tmp:
        for path, info, reason in infos:
            if info is None:
                measured[path] = BenchRow(
                    file=str(path.relative_to(root)),
                    channels=None,
                    sample_rate=None,
                    source_bytes=0,
                    flac_bytes=0,
                    ratio=0.0,
                    encode_rtf=0.0,
                    decode_rtf=0.0,
                    verified=False,
                    skipped=reason,
                )
                continue
            flac = Path(tmp) / "stream.flac"
            raw = Path(tmp) / "decoded.f32"
            start = perf_counter()
            encode_file(codec, path, flac, preset)
            encode_seconds = perf_counter() - start
            result = verify(codec, flac, path)
            start = perf_counter()
            decode_file(codec, flac, raw, raw=True)
            decode_seconds = perf_counter() - start
            flac_bytes = flac.stat().st_size
            duration = info.data_size / (info.channels * 4 * info.sample_rate)
            measured[path] = BenchRow(
                file=str(path.relative_to(root)),
                channels=info.channels,
                sample_rate=info.sample_rate,
                source_bytes=info.data_size,
                flac_bytes=flac_bytes,
                ratio=round(flac_bytes / info.data_size, 6) if info.data_size else 0.0,
                encode_rtf=round(duration / encode_seconds, 6)
                if encode_seconds
                else 0.0,
                decode_rtf=round(duration / decode_seconds, 6)
                if decode_seconds
                else 0.0,
                verified=result.verified,
                skipped=None,
            )
    rows = [measured[path] for path, _info, _reason in infos]
    totals = BenchTotals(
        files=sum(row.skipped is None for row in rows),
        source_bytes=sum(row.source_bytes for row in rows),
        flac_bytes=sum(row.flac_bytes for row in rows),
        ratio=round(
            sum(row.flac_bytes for row in rows) / sum(row.source_bytes for row in rows),
            6,
        )
        if any(row.source_bytes for row in rows)
        else 0.0,
    )
    return BenchReport(
        platform.platform(),
        platform.python_version(),
        codec.commit,
        preset,
        rows,
        totals,
    )
