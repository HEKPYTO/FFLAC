import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from . import __version__
from .bench import bench
from .codec import decode_file, doctor, encode_file, find_codec, require_float_stream
from .errors import FloatflacError
from .probe import probe
from .process import attenuate
from .report import COMPATIBILITY_WARNING, emit_error, emit_json, envelope
from .verify import sha256_file, verify
from .wav import read_wav_info


@dataclass(frozen=True)
class EncodeResult:
    source: str
    target: str
    source_sha256: str
    flac_sha256: str
    decoded_sha256: str
    verified: bool
    channels: int
    sample_rate: int
    bits_per_sample: int
    source_bytes: int
    flac_bytes: int
    ratio: float
    codec_commit: str | None


@dataclass(frozen=True)
class DecodeResult:
    source: str
    target: str
    raw: bool
    decoded_bytes: int
    flac_sha256: str
    codec_commit: str | None


def _require_file(path: Path) -> None:
    if not path.is_file():
        raise FloatflacError(
            "input_not_found", f"{path}: no such input file", "Check the path."
        )


def _refuse_existing(path: Path, force: bool) -> None:
    if path.exists() and not force:
        raise FloatflacError(
            "output_exists",
            f"{path}: output already exists",
            "Pass --force to overwrite.",
        )


def _print_bench(bench_report) -> None:
    print(f"machine: {bench_report.machine}")
    print(
        f"python: {bench_report.python} preset: {bench_report.preset} codec_commit: {bench_report.codec_commit}"
    )
    print(f"{'file':<38} {'ratio':>8} {'enc(x)':>10} {'dec(x)':>10} verified")
    for row in bench_report.rows:
        print(
            f"{row.file:<38} {row.ratio:>8.4f} {row.encode_rtf:>9.1f}x {row.decode_rtf:>9.1f}x {row.verified}"
        )
        if row.skipped:
            print(f"warning: {row.file}: skipped ({row.skipped})")
    totals = bench_report.totals
    print(
        f"{'TOTAL':<38} {totals.ratio:>8.4f} {'':>10} {'':>10} files={totals.files} source_bytes={totals.source_bytes} flac_bytes={totals.flac_bytes}"
    )


def encode(src, dst=None, preset: int = 5, force: bool = False) -> EncodeResult:
    codec = find_codec()
    source = Path(src)
    _require_file(source)
    info = read_wav_info(source)
    target = Path(dst) if dst is not None else source.with_suffix(".flac")
    _refuse_existing(target, force)
    encode_file(codec, source, target, preset)
    result = verify(codec, target, source)
    flac_bytes = target.stat().st_size
    return EncodeResult(
        source=str(source),
        target=str(target),
        source_sha256=result.source_sha256,
        flac_sha256=result.flac_sha256,
        decoded_sha256=result.decoded_sha256,
        verified=True,
        channels=info.channels,
        sample_rate=info.sample_rate,
        bits_per_sample=info.bits_per_sample,
        source_bytes=info.data_size,
        flac_bytes=flac_bytes,
        ratio=round(flac_bytes / info.data_size, 6) if info.data_size else 0.0,
        codec_commit=codec.commit,
    )


def decode(src, dst=None, raw: bool = False, force: bool = False) -> DecodeResult:
    codec = find_codec()
    source = Path(src)
    _require_file(source)
    require_float_stream(codec, source, error_code="decode_failed")
    target = (
        Path(dst) if dst is not None else source.with_suffix(".f32" if raw else ".wav")
    )
    _refuse_existing(target, force)
    decode_file(codec, source, target, raw=raw)
    return DecodeResult(
        source=str(source),
        target=str(target),
        raw=raw,
        decoded_bytes=target.stat().st_size,
        flac_sha256=sha256_file(source),
        codec_commit=codec.commit,
    )


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise FloatflacError("usage", message, "Run floatflac --help.")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="floatflac")
    subparsers = parser.add_subparsers(dest="command", required=True)
    enc = subparsers.add_parser("encode")
    enc.add_argument("src")
    enc.add_argument("-o", "--dst")
    enc.add_argument("--preset", type=int, choices=range(9), default=5)
    enc.add_argument("--force", action="store_true")
    enc.add_argument("--json", action="store_true", dest="as_json")

    dec = subparsers.add_parser("decode")
    dec.add_argument("src")
    dec.add_argument("-o", "--dst")
    dec.add_argument("--raw", action="store_true")
    dec.add_argument("--force", action="store_true")
    dec.add_argument("--json", action="store_true", dest="as_json")

    ver = subparsers.add_parser("verify")
    ver.add_argument("src")
    ver.add_argument("--source", required=True)
    ver.add_argument("--json", action="store_true", dest="as_json")

    pr = subparsers.add_parser("probe")
    pr.add_argument("src")
    pr.add_argument("--json", action="store_true", dest="as_json")

    doc = subparsers.add_parser("doctor")
    doc.add_argument("--json", action="store_true", dest="as_json")

    v = subparsers.add_parser("version")
    v.add_argument("--json", action="store_true", dest="as_json")

    bn = subparsers.add_parser("bench")
    bn.add_argument("directory")
    bn.add_argument("--json", action="store_true", dest="as_json")
    bn.add_argument("--out")
    bn.add_argument("--force", action="store_true")
    bn.add_argument("--preset", type=int, choices=range(9), default=5)

    at = subparsers.add_parser("attenuate")
    at.add_argument("src")
    at.add_argument("-o", "--dst")
    at.add_argument("--target-dbfs", type=float, default=-1.0)
    at.add_argument("--force", action="store_true")
    at.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = next((token for token in argv if not token.startswith("-")), "floatflac")
    as_json = "--json" in argv
    args = None
    try:
        args = _parser().parse_args(argv)
        command = args.command
        if command == "version":
            if args.as_json:
                emit_json(command, {"version": __version__})
            else:
                print(f"floatflac {__version__}")
            return 0
        if command == "doctor":
            data = doctor()
            if args.as_json:
                emit_json(command, data)
            else:
                print(f"ok: {data['ok']}")
                print(f"flac: {data['flac']}")
                print(f"metaflac: {data['metaflac']}")
                print(f"commit: {data['commit']}")
                print(f"float_support: {data['float_support']}")
                if data["error"]:
                    print(f"error: {data['error']}")
            return 0 if data["ok"] else 1
        if command == "encode":
            result = encode(args.src, args.dst, args.preset, args.force)
            data = asdict(result)
            if args.as_json:
                emit_json(command, data)
            else:
                print(COMPATIBILITY_WARNING)
                print(
                    f"source: {result.source} sha256={result.source_sha256} bytes={result.source_bytes}"
                )
                print(
                    f"target: {result.target} sha256={result.flac_sha256} bytes={result.flac_bytes}"
                )
                print(
                    f"decoded_sha256: {result.decoded_sha256} bytes={result.source_bytes}"
                )
                print(f"verified: {result.verified}")
            return 0
        if command == "decode":
            result = decode(args.src, args.dst, args.raw, args.force)
            if args.as_json:
                emit_json(command, asdict(result))
            else:
                print(f"target: {result.target} bytes={result.decoded_bytes}")
                print(f"flac_sha256: {result.flac_sha256}")
            return 0
        if command == "verify":
            codec = find_codec()
            flac_path = Path(args.src)
            source_path = Path(args.source)
            _require_file(flac_path)
            _require_file(source_path)
            result = verify(codec, flac_path, source_path)
            data = asdict(result)
            data["source"] = str(source_path)
            data["flac"] = str(flac_path)
            if args.as_json:
                emit_json(command, data)
            else:
                print(
                    f"source: {source_path} ({source_path.stat().st_size} bytes) sha256={result.source_sha256}"
                )
                print(
                    f"flac: {flac_path} ({flac_path.stat().st_size} bytes) sha256={result.flac_sha256}"
                )
                print(f"decoded: {result.bytes} bytes sha256={result.decoded_sha256}")
                print(f"verified: {result.verified}")
            return 0
        if command == "probe":
            codec = find_codec()
            flac_path = Path(args.src)
            _require_file(flac_path)
            result = probe(codec, flac_path)
            data = asdict(result)
            data["source"] = str(flac_path)
            data["flac_sha256"] = sha256_file(flac_path)
            data["flac_bytes"] = flac_path.stat().st_size
            if args.as_json:
                emit_json(command, data)
            else:
                print(COMPATIBILITY_WARNING)
                print(
                    f"source: {flac_path} bytes={data['flac_bytes']} sha256={data['flac_sha256']}"
                )
                print(f"sample_type: {result.sample_type}")
                print(
                    f"bps: {result.bps} channels: {result.channels} sample_rate: {result.sample_rate}"
                )
                print(
                    f"channel_mask: {result.channel_mask} mode: {result.mode} (heuristic: {result.mode_is_heuristic})"
                )
                print(
                    f"standard_decoder_compatible: {result.standard_decoder_compatible}"
                )
            return 0
        if command == "bench":
            output = Path(args.out) if args.out else None
            if output is not None:
                _refuse_existing(output, args.force)
            bench_report = bench(args.directory, args.preset)
            payload = json.dumps(
                envelope(command, asdict(bench_report)), separators=(",", ":")
            )
            if output is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(payload + "\n")
            if args.as_json:
                print(payload)
            else:
                _print_bench(bench_report)
            return 0
        if command == "attenuate":
            source = Path(args.src)
            _require_file(source)
            target = (
                Path(args.dst) if args.dst is not None else source.with_suffix(".wav")
            )
            _refuse_existing(target, args.force)
            result = attenuate(find_codec(), source, target, args.target_dbfs)
            if args.as_json:
                emit_json(command, asdict(result))
            else:
                print("processed, not recovered")
                print(f"source: {result.source}")
                print(
                    f"target: {result.target} channels={result.channels} sample_rate={result.sample_rate} samples={result.samples}"
                )
                input_peak = (
                    "silence"
                    if result.input_peak_dbfs is None
                    else f"{result.input_peak_dbfs:.3f}"
                )
                output_peak = (
                    "silence"
                    if result.output_peak_dbfs is None
                    else f"{result.output_peak_dbfs:.3f}"
                )
                print(f"input_peak_dbfs: {input_peak} output_peak_dbfs: {output_peak}")
                print(
                    f"gain_db: {result.gain_db:.3f} target_dbfs: {result.target_dbfs:.3f}"
                )
            return 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except FloatflacError as exc:
        return emit_error(command, exc, getattr(args, "as_json", as_json))
    return 2
