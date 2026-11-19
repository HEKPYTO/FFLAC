import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from .codec import read_stream_info, require_float_stream, run_codec
from .errors import FloatflacError


@dataclass(frozen=True)
class ProbeResult:
    sample_type: str
    bps: int
    sample_rate: float
    channels: int
    channel_mask: int
    mode: str
    mode_is_heuristic: bool
    standard_decoder_compatible: bool
    codec_commit: str | None
    float_support: bool


def _frame_mode(ana_path: Path) -> str:
    packed = False
    fallback = False
    try:
        with ana_path.open("r", errors="replace") as handle:
            for line in handle:
                if "type=PACKED" in line:
                    packed = True
                elif "type=" in line:
                    fallback = True
    except OSError as exc:
        raise FloatflacError(
            "probe_failed",
            f"Cannot read analysis file: {exc}".replace("\n", " "),
            "Check the FLAC file.",
        ) from exc
    if packed and fallback:
        return "mixed"
    return "dpa" if packed else "fallback"


def probe(codec, path: Path) -> ProbeResult:
    flac_path = Path(path)
    require_float_stream(codec, flac_path)
    info = read_stream_info(codec, flac_path)
    with TemporaryDirectory() as tmp:
        copy = Path(tmp) / "stream.flac"
        shutil.copyfile(flac_path, copy)
        run_codec([codec.flac, "-a", "-f", str(copy)], "probe_failed")
        mode = _frame_mode(Path(tmp) / "stream.ana")
    return ProbeResult(
        sample_type=info.sample_type,
        bps=info.bps,
        sample_rate=info.sample_rate,
        channels=info.channels,
        channel_mask=info.channel_mask,
        mode=mode,
        mode_is_heuristic=True,
        standard_decoder_compatible=False,
        codec_commit=codec.commit,
        float_support=True,
    )
