# floatflac

The Python wrapper. It ships no codec binaries; discovery, validation, and
verification live here.

| Module | Responsibility |
|---|---|
| `cli.py` | Subcommands, argparse flags, defaults, exit codes, plain and JSON output |
| `codec.py` | Find `flac`/`metaflac`, check float support, run encode/decode, assemble `doctor` |
| `wav.py` | RIFF/WAVE chunk parser, float32 validation, WAV writer, raw sample chunks |
| `verify.py` | Raw f32le comparison, SHA-256 of samples and file, first differing offset |
| `probe.py` | Stream fields via `metaflac`, frame-mode heuristic, compatibility flag |
| `bench.py` | Corpus encode/decode timing, ratios, skip reasons, totals |
| `process.py` | Peak attenuation to a target dBFS, float WAV output |
| `report.py` | `floatflac/v1` JSON envelope, compatibility warning, error output |
| `errors.py` | Typed errors and exit-code mapping (1 for failures, 2 for usage) |

Invariants:

- Entry point is `floatflac.cli:main`. The package has no third-party runtime
  dependencies and makes no network calls.
- Codec discovery checks `FLOATFLAC_BIN_DIR` first, then the local build tree,
  then `PATH`. Both binaries must advertise float support before use.
- Only float32 WAV is accepted: format tag 3, or extensible tag 0xfffe with
  subformat 3. Integer, RF64/W64, and malformed chunks are rejected.
- Encode uses preset 5 unless told otherwise, passes the codec `--verify`, then
  hashes and compares every source and decoded sample byte. No lossy flags are
  exposed.
- `decode`, `probe`, `verify`, and attenuation reject streams that
  `metaflac --show-sample-type` does not report as floating point.
- Verification hashes come from raw bytes, never codec stdout. A mismatch
  reports the first differing byte offset.
- `probe` marks every stream incompatible with standard decoders; its frame
  mode is a heuristic from `flac -a` analysis output.
- Scratch files live in `TemporaryDirectory`.
