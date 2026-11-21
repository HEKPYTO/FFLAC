# Floatflac

Floatflac puts 32-bit float audio in FLAC. The Python CLI wraps a float-enabled
reference codec: it encodes float32 WAV, decodes it, and hashes the raw samples
to prove a bit-exact round trip. Peaks above 0 dBFS stay as floats instead of
clipping. This is an experimental extension, not an RFC 9639 stream. It claims
neither standard FLAC compatibility nor smaller files than every other codec.

## Quickstart

Prerequisites: Python 3.11+, uv, CMake, a C compiler, and git. The codec build
clones a pinned source tree over the network; the test suite never does. Tested
on macOS arm64 and Linux x86_64; Windows is untested.

```sh
git clone https://github.com/HEKPYTO/FFLAC.git
cd FFLAC
scripts/build-codec.sh
uv sync --group dev
uv run floatflac doctor
uv run python scripts/fixtures.py
uv run floatflac encode tests/fixtures/sine-f32-2ch-48k.wav -o /tmp/roundtrip.flac
uv run floatflac verify /tmp/roundtrip.flac --source tests/fixtures/sine-f32-2ch-48k.wav
```

`doctor` prints `ok: True` and `float_support: True`. The final `verify` prints:

```text
source: tests/fixtures/sine-f32-2ch-48k.wav (768044 bytes) sha256=dce5432eee0fa1ce47e20812ec48cf4263b386b5667887387f505315f4b8a62d
flac: /tmp/roundtrip.flac (276513 bytes) sha256=6c041773f978e35ecf7beb2a9d5978861bf0ac3542dfe599715d14f24a0f75a4
decoded: 768000 bytes sha256=dce5432eee0fa1ce47e20812ec48cf4263b386b5667887387f505315f4b8a62d
verified: True
```

`build-codec.sh` writes `.build/flac-float/` (override `FLOATFLAC_SOURCE_DIR`).
The CLI finds `flac` and `metaflac` there, then on `PATH`; `FLOATFLAC_BIN_DIR`
overrides. `uv build` packages the Python CLI only; the codec stays separate.

## Install a prebuilt release

The public install script fetches a release wheel and codec archive without a
token, verifies both against `SHA256SUMS`, and installs under a prefix:

```sh
curl -fsSL https://raw.githubusercontent.com/HEKPYTO/FFLAC/main/scripts/install.sh | sh
```

It installs to `$FLOATFLAC_PREFIX` (default `$HOME/.local`) and writes a launcher
at `<prefix>/bin/floatflac`, by default `$HOME/.local/bin/floatflac`; add that
directory to `PATH`. To choose a version or prefix, save the script and pass its
flags:

```sh
curl -fsSL https://raw.githubusercontent.com/HEKPYTO/FFLAC/main/scripts/install.sh -o install.sh
sh install.sh --version v0.2.0 --prefix /opt/floatflac
export PATH="/opt/floatflac/bin:$PATH"
```

`FLOATFLAC_PREFIX` and `FLOATFLAC_VERSION` supply defaults; the flags override
them. Public releases need no token (one is only an optional fallback for API
rate limits).

## Results

Measured with `uv run floatflac bench tests/fixtures --preset 5 --out report.json`
on Apple M2, macOS 27.0.1, Python 3.13.15, codec commit `05536fce`. Ratio is FLAC
bytes / source WAV data bytes; RTF is audio seconds / wall seconds (higher is
faster). Timings vary by machine. The int16 case is skipped (not float32).

| File | Ratio | Encode RTF | Decode RTF | Verified |
|---|---:|---:|---:|:---:|
| hot-f32-2ch-48k.wav | 0.3721 | 117.1x | 146.4x | yes |
| noise-f32-2ch-48k.wav | 0.8513 | 190.5x | 289.5x | yes |
| sine-f32-1ch-48k.wav | 0.3368 | 237.5x | 288.2x | yes |
| sine-f32-2ch-44k.wav | 0.3649 | 178.2x | 233.6x | yes |
| sine-f32-2ch-48k.wav | 0.3600 | 175.3x | 217.6x | yes |
| sine-f32-2ch-96k.wav | 0.2391 | 110.4x | 155.4x | yes |
| sine-f32-8ch-48k.wav | 0.3425 | 57.2x | 82.0x | yes |
| special-1ch-48k.wav | 0.4352 | 145.8x | 163.2x | yes |
| Total (8 files) | 0.4602 | | | yes |

WavPack often produces smaller files; if size alone decides, use WavPack.
Floatflac's case is FLAC ecosystem fit and keeping peaks above 0 dBFS as floats.
This bench does not run WavPack or any other codec.

## Commands

Prefix each with `uv run floatflac` (or `floatflac` on `PATH`). Every command
takes `--json` for a `floatflac/v1` envelope. Preset defaults to 5. Outputs that
already exist need `--force`.

| Command | Minimal example |
|---|---|
| `doctor` | `floatflac doctor` |
| `version` | `floatflac version` |
| `encode` | `floatflac encode in.wav -o out.flac --preset 5` |
| `decode` | `floatflac decode in.flac -o out.wav` |
| `verify` | `floatflac verify in.flac --source in.wav` |
| `probe` | `floatflac probe in.flac` |
| `bench` | `floatflac bench tests/fixtures --preset 5 --out report.json` |
| `attenuate` | `floatflac attenuate hot.flac -o out.wav --target-dbfs -1.0` |

`encode` and `bench` accept `--preset 0..8`. `decode` accepts `--raw` for f32le
output (default `.wav`); the default decode target is `.wav`, or `.f32` with
`--raw`. `attenuate` lowers peaks to `--target-dbfs` (default -1.0); it processes
audio, it does not recover clipped samples. `encode`, `decode`, `bench`, and
`attenuate` accept `--force`.

## Verification

`encode` and `verify` hash raw f32le samples, not the WAV header or codec stdout.
`source_sha256` is the WAV data chunk; `decoded_sha256` is the decoded float
stream. Equal hashes plus `verified: True` are the bit-exact proof, and a
mismatch reports the first differing byte offset. `flac_sha256` pins the encoded
file; the hash values change with the input, the equality does not.

The suite:

```sh
uv run pytest -q
```

Result: 117 passed. Codec-backed tests skip with a reason when no float-enabled
`flac`/`metaflac` pair is found. Coverage includes 1/2/8 channels, 44.1/48/96
kHz, presets 0/5/8, NaN, ±Inf, subnormal, and -0.0, the `--force-fallback-mode`
and `--seekpoint` extra args, integer WAV rejection, and stock-decoder refusal.

## Compatibility

These streams are not RFC 9639 FLAC. They mark the float payload in reserved
legacy fields, so a stock `flac`, ffmpeg, or other RFC-only decoder refuses the
file rather than playing noise. Decode with a float-enabled build. `encode` and
`probe` print the warning.

## Licence

The Python package is Apache-2.0 (`LICENSE`). The `flac` and `metaflac` binaries
built from the pinned source are GPL-2.0-or-later, and libFLAC is BSD-3-Clause
(`NOTICE`). The wrapper and the codec are separate works.

## More

Module responsibilities in `src/floatflac/README.md`, test layers and fixtures
in `tests/README.md`, build and release scripts in `scripts/README.md`.
