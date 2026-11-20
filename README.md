# Floatflac

Lossless 32-bit float audio in the FLAC ecosystem.

`floatflac` wraps the reference implementation of a native IEEE 754
single-precision extension to FLAC. It encodes float32 WAV, decodes it back,
and proves the round trip is bit-exact. Float peaks above 0 dBFS survive.

## Install

One command installs the CLI and a prebuilt codec into `~/.local`:

```sh
curl -fsSL https://raw.githubusercontent.com/HEKPYTO/FFLAC/main/scripts/install.sh | sh
```

Pass `--prefix DIR` to install elsewhere
(`curl -fsSL .../install.sh | sh -s -- --prefix /opt/floatflac`), or set
`FLOATFLAC_VERSION` to pin a different release tag. The installer downloads
the wheel, the codec archive for your platform, and `SHA256SUMS`, then
verifies both downloads before extracting or installing anything. Add
`$HOME/.local/bin` (or `<prefix>/bin`) to `PATH`.
While the repository is private, set `GITHUB_TOKEN` (or `GH_TOKEN`) to a token with repo read access; the same command works unauthenticated once the repository is public.

Release binaries are unsigned; macOS binaries are not notarized, so your OS
may warn on first run. No Homebrew formula is provided. For a local build,
see below.

## Install from source

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), CMake, a C
compiler, and git for the codec build.

```sh
scripts/build-codec.sh
uv sync
uv run floatflac version
uv run floatflac doctor
```

`build-codec.sh` clones the pinned codec commit into `.build/flac-float/` and
compiles `flac` and `metaflac` with float sample coding enabled. To use an
existing checkout, set `FLOATFLAC_SOURCE_DIR`; the checkout must be at the
pinned commit. To use prebuilt binaries, set `FLOATFLAC_BIN_DIR` to a
directory containing both `flac` and `metaflac`.

Build a wheel with `uv build` and install `dist/*.whl`. The wheel contains the
Python CLI only; the codec binaries are separate.

## Commands

| Command | What it does |
|---|---|
| `floatflac encode SRC.wav [-o DST.flac]` | Validate float32 WAV, encode, verify bit-exactness |
| `floatflac decode SRC.flac [-o DST.wav]` | Decode to float32 WAV; `--raw` writes f32le |
| `floatflac verify SRC.flac --source SRC.wav` | Compare decoded samples to the source, fail at the first difference |
| `floatflac probe SRC.flac` | Sample type, channels, rate, frame mode, compatibility |
| `floatflac bench DIR` | Ratio, encode/decode real-time factor, bit-exactness |
| `floatflac attenuate SRC.flac [-o DST.wav]` | Lower peaks to a target dBFS |
| `floatflac doctor` | Check the codec, its commit, and float support |
| `floatflac version` | Print the version |

Defaults: preset 5; `encode` writes `SRC.flac`; `decode` writes `SRC.wav` or
`SRC.f32`; `attenuate` writes `SRC.wav`. Existing outputs require `--force`.
Every command accepts `--json` and prints one `floatflac/v1` envelope.

`attenuate` is processing. It does not recover audio that was already clipped
in an integer source.

## Compatibility

This is **not RFC 9639 FLAC**. The stream uses reserved legacy fields to
signal incompatibility, so a standard `flac` decoder or ffmpeg refuses it
instead of playing noise. A `floatflac` build is required to decode. The
command prints this warning on `encode` and `probe`.

## Verification

`encode` verifies by default: it decodes the new stream to raw f32le and
compares every byte with the source WAV samples. On success it reports the
SHA-256 of the source samples, the decoded samples, and the FLAC file. A
mismatch fails with the first differing offset. `verify` performs the same
check without writing a new stream.

## Benchmark

```sh
uv run floatflac bench tests/fixtures --out report.json
```

The report records machine, codec commit, preset, per-file ratio, encode and
decode real-time factors, and the verified flag.

## Limitations

- The Linux codec archive is built on Ubuntu 24.04 x86_64 and needs glibc
  2.39 or newer. The macOS archive targets Apple silicon.
- Float32 only. No 64-bit float, Ogg/FLAC, or AIFF.
- Linux x86_64 and macOS arm64 are the supported release targets. Release
  binaries are unsigned and macOS binaries are not notarized. Windows is
  untested.
- WavPack produces smaller files on several tiers; this project wins on FLAC
  ecosystem fit, encode speed, and peak preservation.
- Integer delivery formats are out of scope. Use a separate converter after
  attenuation.

## Licence

The floatflac Python package is licensed under the Apache License, Version
2.0; see `LICENSE`. The `flac` and `metaflac` binaries built by
`scripts/build-codec.sh` are GPL-2.0-or-later, and libFLAC is BSD-3-Clause;
see `NOTICE`. The build script fetches the pinned source, so this source
release does not distribute those binaries. The wrapper and the binaries are
separate works; no combined-work licence is asserted.
