from dataclasses import dataclass
from hashlib import sha256
from itertools import zip_longest
from pathlib import Path
from tempfile import TemporaryDirectory

from .codec import decode_file, require_float_stream
from .errors import FloatflacError
from .wav import iter_raw_chunks, read_wav_info


@dataclass(frozen=True)
class VerifyResult:
    source_sha256: str
    decoded_sha256: str
    flac_sha256: str
    bytes: int
    verified: bool


def sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(codec, flac_path: Path, source_path: Path) -> VerifyResult:
    flac = Path(flac_path)
    source = Path(source_path)
    require_float_stream(codec, flac)
    info = read_wav_info(source)
    with TemporaryDirectory() as tmp:
        decoded = Path(tmp) / "decoded.f32"
        decode_file(codec, flac, decoded, raw=True)
        decoded_size = decoded.stat().st_size
        source_hash = sha256()
        decoded_hash = sha256()
        total = 0
        chunks = zip_longest(
            iter_raw_chunks(source, info.data_offset, info.data_size),
            iter_raw_chunks(decoded, 0, decoded_size),
            fillvalue=b"",
        )
        for source_chunk, decoded_chunk in chunks:
            source_hash.update(source_chunk)
            decoded_hash.update(decoded_chunk)
            if source_chunk != decoded_chunk:
                common = min(len(source_chunk), len(decoded_chunk))
                first_diff = next(
                    (i for i in range(common) if source_chunk[i] != decoded_chunk[i]),
                    common,
                )
                offset = total + first_diff
                if len(source_chunk) != len(decoded_chunk):
                    raise FloatflacError(
                        "verify_failed",
                        f"length mismatch at offset {offset}: source chunk {len(source_chunk)} bytes, decoded chunk {len(decoded_chunk)} bytes",
                        "Do not ship the file; report the offset and check the input.",
                    )
                raise FloatflacError(
                    "verify_failed",
                    f"first differing byte offset {offset}: source {source_chunk[first_diff]:#04x}, decoded {decoded_chunk[first_diff]:#04x}",
                    "Do not ship the file; report the offset and check the input.",
                )
            total += len(source_chunk)
    return VerifyResult(
        source_hash.hexdigest(),
        decoded_hash.hexdigest(),
        sha256_file(flac),
        total,
        True,
    )
