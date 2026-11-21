# Floatflac

Lossless 32-bit float audio in FLAC. The CLI wraps a float-enabled reference
codec: it encodes float32 WAV, decodes it back, and hashes the raw samples to
prove the round trip. Peaks above 0 dBFS survive.

## Build from source

You need Python 3.11+, uv, CMake, a C compiler, and git.

```sh
git clone https://github.com/HEKPYTO/FFLAC.git
cd FFLAC
scripts/build-codec.sh
uv sync --group dev
uv run floatflac doctor
```

`build-codec.sh` clones a pinned codec source tree into `.build/flac-float`,
builds `flac` and `metaflac`, and checks that both support float samples.
No token or GitHub credentials are needed. Cloning this repository and fetching
the pinned codec source use the network; the test suite never does.

To run the CMake configure step yourself, from the codec source tree:

```sh
cmake -S . -B build \
  -DENABLE_EXPERIMENTAL_FLOAT_SAMPLE_CODING=ON \
  -DWITH_OGG=OFF \
  -DBUILD_TESTING=ON \
  -DBUILD_DOCS=OFF \
  -DINSTALL_MANPAGES=OFF \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build --target flacapp metaflac --parallel 4
```

The CLI looks in `.build/flac-float/build/`, then `PATH`. If your binaries live
elsewhere, point `FLOATFLAC_BIN_DIR` at the directory containing both.
`uv build` produces a wheel with the Python CLI only; the codec stays separate.

## Commands

| Command | What it does |
|---|---|
| `encode SRC.wav [-o DST.flac] [--preset 0..8]` | Validate float32 WAV, encode, decode, and compare every sample byte. |
| `decode SRC.flac [-o DST.wav] [--raw]` | Write float32 WAV, or raw f32le with `--raw`. |
| `probe SRC.flac` | Show sample type, bit depth, channels, rate, frame mode, and compatibility. |
| `verify SRC.flac --source SRC.wav` | Re-decode and hash samples against the source; fail at the first difference. |
| `bench DIR [--out REPORT.json] [--preset 0..8]` | Encode float32 WAVs under DIR; report ratio, real-time factors, and verification. |
| `doctor` | Check codec paths, commit, and float support. |
| `attenuate SRC.flac [-o DST.wav] [--target-dbfs DBFS] [--force]` | Lower peaks to the target dBFS (default -1.0) in a float32 WAV. Processing, not recovery of clipped audio. |
| `version` | Print the package version. |

Prefix each with `uv run floatflac` (or `floatflac` when it is on `PATH`).
Every command also takes `--json` and prints one `floatflac/v1` envelope.
Preset defaults to 5; `encode` writes `SRC.flac`; `decode` writes `SRC.wav` or
`SRC.f32` with `--raw`. Existing outputs need `--force`.

## Verified round trip

Make a deterministic test WAV and prove the round trip:

```sh
uv run python scripts/fixtures.py
uv run floatflac encode tests/fixtures/sine-f32-2ch-48k.wav -o /tmp/roundtrip.flac
uv run floatflac verify /tmp/roundtrip.flac --source tests/fixtures/sine-f32-2ch-48k.wav
```

The verify step printed this on one build:

```text
source: tests/fixtures/sine-f32-2ch-48k.wav (768044 bytes) sha256=dce5432eee0fa1ce47e20812ec48cf4263b386b5667887387f505315f4b8a62d
flac: /tmp/roundtrip.flac (276513 bytes) sha256=6c041773f978e35ecf7beb2a9d5978861bf0ac3542dfe599715d14f24a0f75a4
decoded: 768000 bytes sha256=dce5432eee0fa1ce47e20812ec48cf4263b386b5667887387f505315f4b8a62d
verified: True
```

`source_sha256` and `decoded_sha256` hash raw float bytes, the WAV data chunk
and the decoded f32le stream, not the WAV header. Equal hashes plus
`verified: True` are the bit-exact proof. `flac_sha256` pins the encoded file.
Hash values depend on the input; equality does not.

## Benchmark

```sh
uv run floatflac bench tests/fixtures --out report.json
```

The report has per-file size ratio, encode and decode real-time factors, and a
`verified` flag, plus totals. Files that are not float32 WAV are skipped with a
reason. The benchmark does not run other codecs.

WavPack often produces smaller files. If size alone decides, use WavPack.
This project's case is FLAC ecosystem fit and keeping peaks above 0 dBFS as
floats instead of clipping them. The bench report here measures this codec's
speed and ratios; it does not benchmark WavPack.

## Compatibility

These streams are not RFC 9639 FLAC. They use reserved legacy fields to mark
the float payload, so a stock `flac`, ffmpeg, or other RFC-only decoder refuses
the file instead of playing noise. Decode with a float-enabled build. `encode`
and `probe` print that warning.

## Licence

The Python package is Apache-2.0 (`LICENSE`). The `flac` and `metaflac`
binaries built from the pinned source are GPL-2.0-or-later, and libFLAC is
BSD-3-Clause (`NOTICE`). The wrapper and the codec are separate works.
