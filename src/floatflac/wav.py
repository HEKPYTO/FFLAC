import os
import struct
from dataclasses import dataclass
from pathlib import Path

from .errors import FloatflacError

FLOAT_GUID = bytes.fromhex("0300000000001000800000aa00389b71")


@dataclass(frozen=True)
class WavInfo:
    channels: int
    sample_rate: int
    bits_per_sample: int
    format_tag: int
    subformat_tag: int | None
    data_offset: int
    data_size: int
    is_float32: bool


def _invalid(path: Path, detail: str) -> FloatflacError:
    return FloatflacError(
        "invalid_wav", f"{path.name}: {detail}", "Re-export the WAV as 32-bit float."
    )


def read_wav_info(path: Path) -> WavInfo:
    path = Path(path)
    try:
        handle = path.open("rb")
    except OSError as exc:
        raise FloatflacError(
            "input_not_found",
            f"{path}: {exc.strerror or exc}".replace("\n", " "),
            "Check the path.",
        ) from exc
    with handle:
        header = handle.read(12)
        if len(header) < 12:
            raise _invalid(path, "truncated RIFF header")
        if header[:4] in (b"RF64", b"W64 ", b"riff", b"FORM"):
            raise FloatflacError(
                "unsupported_container",
                f"{path.name}: container {header[:4].decode('latin1')} is not supported",
                "Convert to WAV float32.",
            )
        if header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise _invalid(path, "not a RIFF/WAVE file")
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        handle.seek(12)
        fmt = None
        data = None
        while handle.tell() + 8 <= file_size:
            chunk_header = handle.read(8)
            if len(chunk_header) < 8:
                break
            chunk_id, size = struct.unpack("<4sI", chunk_header)
            pos = handle.tell()
            if size > file_size - pos:
                raise _invalid(
                    path,
                    f"chunk {chunk_id.decode('latin1')} declares {size} bytes past end of file",
                )
            if chunk_id == b"fmt " and fmt is None:
                if size < 16:
                    raise _invalid(path, "fmt chunk is too short")
                tag, channels, rate, _byte_rate, _align, bits = struct.unpack(
                    "<HHIIHH", handle.read(16)
                )
                subformat = None
                if tag == 0xFFFE:
                    if size < 40:
                        raise _invalid(path, "extensible fmt chunk is too short")
                    handle.read(2)
                    handle.read(6)
                    subformat = struct.unpack("<H", handle.read(2))[0]
                fmt = (tag, subformat, channels, rate, bits)
            elif chunk_id == b"data" and data is None:
                data = (pos, size)
            handle.seek(pos + size + (size & 1))
        if fmt is None or data is None:
            raise _invalid(path, "missing fmt or data chunk")
        tag, subformat, channels, rate, bits = fmt
        if channels <= 0 or rate <= 0:
            raise _invalid(path, "invalid channels or sample rate")
        is_float32 = (tag == 3 and bits == 32) or (
            tag == 0xFFFE and subformat == 3 and bits == 32
        )
        if not is_float32:
            raise FloatflacError(
                "not_float32_wav",
                f"{path.name}: format tag {tag:#06x} with {bits}-bit samples is not float32",
                "Export a float32 WAV.",
            )
        data_offset, data_size = data
        if data_size % (channels * 4):
            raise _invalid(path, "data size is not a multiple of channels*4")
        return WavInfo(
            channels, rate, bits, tag, subformat, data_offset, data_size, True
        )


def iter_raw_chunks(path: Path, offset: int, size: int, chunk_size: int = 1 << 20):
    with Path(path).open("rb") as handle:
        handle.seek(offset)
        remaining = size
        while remaining > 0:
            chunk = handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def write_float_wav(path, samples, channels, sample_rate):
    if channels <= 0 or sample_rate <= 0:
        raise FloatflacError(
            "invalid_wav",
            "channels and sample_rate must be positive",
            "Provide a positive channel count and sample rate.",
        )
    destination = Path(path)
    temp = destination.with_name(f"{destination.name}.tmp-{os.getpid()}")
    pack = struct.Struct("<f")
    extensible = channels > 2
    fmt = struct.pack(
        "<HHIIHH",
        0xFFFE if extensible else 3,
        channels,
        sample_rate,
        sample_rate * channels * 4,
        channels * 4,
        32,
    )
    if extensible:
        fmt += struct.pack("<HHI", 22, 32, 0) + FLOAT_GUID
    header_size = 44 + len(fmt) - 16
    completed = False
    try:
        with temp.open("wb") as handle:
            handle.write(
                b"RIFF"
                + struct.pack("<I", 0)
                + b"WAVE"
                + b"fmt "
                + struct.pack("<I", len(fmt))
                + fmt
                + b"data"
                + struct.pack("<I", 0)
            )
            count = 0
            buffer = bytearray()
            for value in samples:
                buffer.extend(pack.pack(value))
                count += 1
                if len(buffer) >= 1 << 20:
                    handle.write(buffer)
                    buffer.clear()
            if buffer:
                handle.write(buffer)
            if count % channels:
                raise FloatflacError(
                    "invalid_wav",
                    f"sample count {count} is not a multiple of {channels} channels",
                    "Provide complete sample frames.",
                )
            data_size = count * 4
            riff_size = header_size - 8 + data_size
            if data_size > 0xFFFFFFFF or riff_size > 0xFFFFFFFF:
                raise FloatflacError(
                    "invalid_wav",
                    f"sample count {count} exceeds the RIFF size limit",
                    "Export fewer samples.",
                )
            handle.seek(4)
            handle.write(struct.pack("<I", riff_size))
            handle.seek(header_size - 4)
            handle.write(struct.pack("<I", data_size))
        os.replace(temp, destination)
        completed = True
    finally:
        if not completed:
            temp.unlink(missing_ok=True)
