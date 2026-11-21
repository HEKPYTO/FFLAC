# tests

Run the suite from the repo root:

```sh
uv sync --group dev
uv run pytest -q
```

Unit tests need only the Python package. Tests that use the codec take the
`codec` fixture and skip with a clear reason when no float-enabled
`flac`/`metaflac` pair is found. Compatibility checks also skip when a stock
`flac` or `ffmpeg` is not installed. Nothing in the suite downloads anything.

| File | Layer |
|---|---|
| `test_package.py` | Version and import |
| `test_wav.py` | RIFF parser, float32 rules, malformed and hostile input |
| `test_codec.py` | Discovery order, build-tree lookup, stock rejection, argument builder, doctor |
| `test_verify.py` | Byte comparison, hashes, mismatch offset, rejection paths |
| `test_probe.py` | Stream fields, frame mode, compatibility flag, corrupt input |
| `test_cli.py` | Commands, defaults, overwrite gate, JSON envelope, exit codes |
| `test_matrix.py` | 1/2/8 channels x 44.1/48/96 kHz x presets 0/5/8, special values, extra args, JSON |
| `test_bench.py` | Corpus report, skip behavior, `--out` overwrite, totals |
| `test_process.py` | Attenuation gain, shape, float output, typed failures |
| `test_compat.py` | Stock decoders reject float streams; float codec decodes and probe flags them |
| `conftest.py` | WAV builders, fake codec helpers, session codec and fixture providers |

To generate the corpus:

```sh
uv run python scripts/fixtures.py
```

That writes deterministic float32 sine WAVs (1/2/8 channels, 44.1/48/96 kHz),
a hot signal above 0 dBFS, special float values, seeded noise, and an int16
rejection case under `tests/fixtures/`. It also encodes the hot and int16
cases. Codec discovery rules are the same as for the CLI. Regenerate the corpus
after changing the codec build.
