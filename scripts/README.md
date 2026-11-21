# scripts

| Script | Purpose |
|---|---|
| `build-codec.sh` | Clone the pinned codec, configure float sample coding, build `flac` and `metaflac`, check their float flags |
| `fixtures.py` | Write the float WAV corpus and the integer rejection case under `tests/fixtures/`, then encode two FLAC samples |
| `bench.py` | Forward arguments to the CLI `bench` command |
| `install.sh` | Install a public release wheel and codec archive into a prefix, verifying `SHA256SUMS` |
| `package-codec.sh` | Stage the built binaries, licences, source archive, and checksums into a release tarball |

`build-codec.sh` writes `.build/flac-float/` and uses these variables:

| Variable | Effect |
|---|---|
| `FLOATFLAC_SOURCE_DIR` | Build from an existing git checkout; the script verifies HEAD matches the pinned commit and fails otherwise. |
| `FLOATFLAC_ALLOW_UNVERIFIED_SOURCE=1` | Allow a non-git source directory; the pin cannot be verified. |

The CLI, tests, and `fixtures.py` find codec binaries through
`FLOATFLAC_BIN_DIR`: set it to a directory containing both `flac` and
`metaflac`. Without it they look in the local build tree and then `PATH`.

`install.sh` takes `--version TAG` and `--prefix DIR`. It reads
`FLOATFLAC_VERSION`, `FLOATFLAC_PREFIX`, and `FLOATFLAC_BASE_URL` as defaults.
Public releases need no credentials.

`bench.py` takes the same arguments as `uv run floatflac bench`, for example
`uv run python scripts/bench.py tests/fixtures --out report.json`.

`package-codec.sh [OUT]` writes to `dist` by default and uses `CC` for the
compiler line in its build note.
