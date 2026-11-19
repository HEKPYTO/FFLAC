import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import FloatflacError

PINNED_COMMIT = "05536fce4e43d06d5b71e75912007893ca0b8ca0"
BUILD_FIX = "Run scripts/build-codec.sh (cmake -S . -B build -DENABLE_EXPERIMENTAL_FLOAT_SAMPLE_CODING=ON -DWITH_OGG=OFF -DBUILD_TESTING=ON -DBUILD_DOCS=OFF -DINSTALL_MANPAGES=OFF -DCMAKE_BUILD_TYPE=Release)."
MISSING_FIX = "Run scripts/build-codec.sh or set FLOATFLAC_BIN_DIR to a directory containing flac and metaflac."


@dataclass(frozen=True)
class CodecPaths:
    flac: Path
    metaflac: Path
    commit: str | None
    float_enabled: bool


def _project_root(project_root=None) -> Path:
    return (
        Path(project_root)
        if project_root is not None
        else Path(__file__).resolve().parents[2]
    )


def _candidate_pairs(project_root=None) -> list[tuple[Path, Path]]:
    root = _project_root(project_root)
    env_dir = os.environ.get("FLOATFLAC_BIN_DIR")
    if env_dir:
        directory = Path(env_dir)
        return [(directory / "flac", directory / "metaflac")]
    pairs = []
    build = (
        root / ".build/flac-float/build/src/flac/flac",
        root / ".build/flac-float/build/src/metaflac/metaflac",
    )
    if build[0].is_file() and build[1].is_file():
        pairs.append(build)
    flac = shutil.which("flac")
    metaflac = shutil.which("metaflac")
    if flac and metaflac:
        pairs.append((Path(flac), Path(metaflac)))
    return pairs


def _help_text(binary: Path) -> str:
    try:
        proc = subprocess.run(
            [str(binary), "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout + proc.stderr


def find_codec(project_root=None) -> CodecPaths:
    pairs = _candidate_pairs(project_root)
    if not pairs:
        raise FloatflacError(
            "codec_missing", "No flac/metaflac pair was found.", MISSING_FIX
        )
    flac, metaflac = pairs[0]
    if not flac.is_file() or not metaflac.is_file():
        raise FloatflacError(
            "codec_missing", f"Missing codec binary in {flac.parent}.", MISSING_FIX
        )
    if "--sample-type" not in _help_text(
        flac
    ) or "--show-sample-type" not in _help_text(metaflac):
        raise FloatflacError(
            "codec_not_float_enabled",
            f"Codec in {flac.parent} lacks float sample support.",
            BUILD_FIX,
        )
    commit = None
    try:
        proc = subprocess.run(
            [str(flac), "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        match = re.search(r"git-([0-9a-f]{7,40})", proc.stdout + proc.stderr)
        if match:
            commit = match.group(1)
    except (OSError, subprocess.SubprocessError):
        pass
    return CodecPaths(flac, metaflac, commit, True)


def run_codec(args, error_code: str, timeout: int = 600):
    command = [str(arg) for arg in args]
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        raise FloatflacError(
            error_code,
            f"Codec timed out after {timeout}s.",
            "Check the codec and the input file.",
        ) from exc
    except OSError as exc:
        raise FloatflacError(
            error_code, f"Cannot run codec: {exc}".replace("\n", " "), MISSING_FIX
        ) from exc
    if proc.returncode:
        lines = [line.strip() for line in proc.stderr.splitlines() if line.strip()]
        if not lines:
            lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        detail = lines[-1] if lines else f"codec returned {proc.returncode}"
        raise FloatflacError(
            error_code,
            " ".join(str(detail).split()),
            "Read the codec message and check the input file.",
        )
    return proc


def require_float_stream(
    codec: CodecPaths, path: Path, error_code: str = "probe_failed"
) -> str:
    proc = run_codec([codec.metaflac, "--show-sample-type", str(path)], error_code)
    sample_type = " ".join(proc.stdout.split())
    if "floating point" not in sample_type.lower():
        raise FloatflacError(
            "not_float_stream",
            f"{Path(path).name}: not a float FLAC stream",
            "Decode and probe only float-FLAC streams.",
        )
    return sample_type


def encode_file(
    codec: CodecPaths, src: Path, dst: Path, preset: int = 5, extra_args=()
):
    return run_codec(
        [
            codec.flac,
            "-f",
            f"-{preset}",
            *extra_args,
            "--verify",
            str(src),
            "-o",
            str(dst),
        ],
        "encode_failed",
    )


def decode_file(codec: CodecPaths, src: Path, dst: Path, raw: bool = False):
    args = [codec.flac, "-d", "-f"]
    if raw:
        args.extend(["--force-raw-format", "--sample-type=float"])
    args.extend([str(src), "-o", str(dst)])
    return run_codec(args, "decode_failed")


def doctor(project_root=None) -> dict:
    result = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "flac": None,
        "metaflac": None,
        "commit": None,
        "flac_version": None,
        "flac_sample_type": False,
        "metaflac_sample_type": False,
        "float_support": False,
        "ok": False,
        "error": None,
        "error_code": None,
    }
    try:
        pairs = _candidate_pairs(project_root)
        if pairs:
            result["flac"] = str(pairs[0][0])
            result["metaflac"] = str(pairs[0][1])
        codec = find_codec(project_root)
        result.update(
            flac=str(codec.flac),
            metaflac=str(codec.metaflac),
            commit=codec.commit,
            float_support=codec.float_enabled,
            ok=True,
        )
    except (FloatflacError, OSError, subprocess.SubprocessError, ValueError) as exc:
        code = exc.code if isinstance(exc, FloatflacError) else "codec_missing"
        result["error"] = code
        result["error_code"] = code
    if result["flac"]:
        help_text = _help_text(Path(result["flac"]))
        result["flac_sample_type"] = "--sample-type" in help_text
        try:
            version = subprocess.run(
                [result["flac"], "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            lines = version.stdout.splitlines()
            result["flac_version"] = lines[0].strip() if lines else None
        except (OSError, subprocess.SubprocessError):
            result["flac_version"] = None
    if result["metaflac"]:
        result["metaflac_sample_type"] = "--show-sample-type" in _help_text(
            Path(result["metaflac"])
        )
    return result
