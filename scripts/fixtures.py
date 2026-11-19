#!/usr/bin/env python3
import math
import random
import struct
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from floatflac.codec import encode_file, find_codec
from floatflac.wav import write_float_wav

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _sine(
    frames: int,
    channels: int,
    rate: int,
    freqs: list[float] | float,
    amplitude: float = 0.5,
) -> list[float]:
    if isinstance(freqs, (int, float)):
        freqs = [float(freqs)]
    samples = []
    for index in range(frames):
        time = index / rate
        for channel in range(channels):
            samples.append(
                amplitude * math.sin(2 * math.pi * freqs[channel % len(freqs)] * time)
            )
    return samples


def _write_int16_wav(path: Path) -> None:
    rate = 48000
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        data = bytearray()
        for index in range(rate):
            time = index / rate
            data.extend(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * 440 * time)))
            )
            data.extend(
                struct.pack("<h", int(12000 * math.sin(2 * math.pi * 660 * time)))
            )
        handle.writeframes(data)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    cases = [
        ("sine-f32-1ch-48k.wav", _sine(48000 * 2, 1, 48000, 440.0), 1, 48000),
        ("sine-f32-2ch-48k.wav", _sine(48000 * 2, 2, 48000, [440.0, 660.0]), 2, 48000),
        (
            "sine-f32-8ch-48k.wav",
            _sine(
                48000,
                8,
                48000,
                [220.0, 330.0, 440.0, 550.0, 660.0, 770.0, 880.0, 990.0],
            ),
            8,
            48000,
        ),
        ("sine-f32-2ch-44k.wav", _sine(44100 * 2, 2, 44100, [440.0, 660.0]), 2, 44100),
        ("sine-f32-2ch-96k.wav", _sine(96000 * 2, 2, 96000, [440.0, 660.0]), 2, 96000),
        ("hot-f32-2ch-48k.wav", _sine(48000, 2, 48000, [440.0, 660.0], 2.0), 2, 48000),
    ]
    for name, samples, channels, rate in cases:
        write_float_wav(FIXTURES / name, samples, channels, rate)

    special = [
        float("nan"),
        float("inf"),
        float("-inf"),
        struct.unpack("<f", b"\x01\x00\x00\x00")[0],
        -0.0,
        0.25,
        -0.125,
        1.0,
    ]
    write_float_wav(
        FIXTURES / "special-1ch-48k.wav",
        [special[i % len(special)] for i in range(48000)],
        1,
        48000,
    )

    generator = random.Random(20240101)
    write_float_wav(
        FIXTURES / "noise-f32-2ch-48k.wav",
        [generator.uniform(-0.8, 0.8) for _ in range(48000 * 5 * 2)],
        2,
        48000,
    )
    _write_int16_wav(FIXTURES / "int16-2ch-48k.wav")

    codec = find_codec()
    encode_file(
        codec, FIXTURES / "hot-f32-2ch-48k.wav", FIXTURES / "hot-f32-2ch-48k.flac"
    )
    encode_file(codec, FIXTURES / "int16-2ch-48k.wav", FIXTURES / "int16-2ch-48k.flac")


if __name__ == "__main__":
    main()
