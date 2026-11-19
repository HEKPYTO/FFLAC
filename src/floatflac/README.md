# floatflac package

| Module | Responsibility |
|---|---|
| `cli.py` | Argparse commands, defaults, exit codes |
| `codec.py` | Locate the float-enabled binaries, run them, build the doctor report |
| `wav.py` | RIFF/WAVE parser, float32 validation, float WAV writer |
| `verify.py` | Raw f32le comparison and SHA-256 hashing |
| `probe.py` | `metaflac` fields and frame-mode heuristic |
| `bench.py` | Corpus ratio and real-time factor |
| `process.py` | Peak attenuation to a target dBFS |
| `report.py` | `floatflac/v1` JSON envelope and human errors |
| `errors.py` | Typed errors and exit-code mapping |

Invariants:

- Default encode path is lossless. The lossy force flags never appear.
- `decode`, `probe`, and `verify` reject non-float streams before touching
  samples.
- Verification compares raw float bytes and hashes; it never trusts codec
  stdout.
- Temp files live in `TemporaryDirectory`. No network calls.

Entry point: `floatflac.cli:main`.
