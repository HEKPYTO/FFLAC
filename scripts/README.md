# scripts

| Script | Purpose |
|---|---|
| `build-codec.sh` | Clone the pinned codec, configure with float coding, build `flac` and `metaflac`, verify the capability flags |
| `fixtures.py` | Generate the float WAV corpus and the integer rejection fixtures |
| `bench.py` | Run the benchmark over a directory and print or write the report |

`build-codec.sh` honours `FLOATFLAC_SOURCE_DIR`. A non-git source directory
fails the pin check unless `FLOATFLAC_ALLOW_UNVERIFIED_SOURCE=1` is set.

`fixtures.py` writes under `tests/fixtures/`; that directory is gitignored.
