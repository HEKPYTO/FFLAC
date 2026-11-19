# tests

| File | Layer |
|---|---|
| `test_package.py` | Version and package import |
| `test_wav.py` | RIFF parser, float32 validation, hostile input |
| `test_codec.py` | Discovery order, stock binary rejection, argument builder |
| `test_verify.py` | Byte comparison, hashes, mismatch offsets |
| `test_probe.py` | Stream type, probe fields, compatibility flag |
| `test_cli.py` | Commands, defaults, overwrite gate, JSON envelope, exit codes |
| `test_matrix.py` | Channels x rates x presets, special values, fallback, seektable |
| `test_bench.py` | Corpus report, skip behavior, totals |
| `test_process.py` | Attenuation gain, shape, float output, typed failures |

Generate fixtures with `uv run python scripts/fixtures.py`. Integration tests
skip with a clear message when no float-enabled codec is found. Unit tests run
without the codec. No network is used.
