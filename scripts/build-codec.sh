#!/usr/bin/env bash
set -euo pipefail

PIN=05536fce4e43d06d5b71e75912007893ca0b8ca0
REPO=https://github.com/aliheidary1381/flac-with-float-coding
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/.build/flac-float"

if [[ -n "${FLOATFLAC_SOURCE_DIR:-}" ]]; then
  SRC="$FLOATFLAC_SOURCE_DIR"
  echo "Using source dir: $SRC"
else
  if [[ ! -d "$SRC/.git" ]]; then
    mkdir -p "$(dirname "$SRC")"
    git clone "$REPO" "$SRC"
  fi
  git -C "$SRC" checkout "$PIN"
fi

if git -C "$SRC" rev-parse --git-dir >/dev/null 2>&1; then
  HEAD="$(git -C "$SRC" rev-parse HEAD)"
  if [[ "$HEAD" != "$PIN" ]]; then
    echo "ERROR: source HEAD $HEAD does not match pin $PIN" >&2
    exit 1
  fi
  echo "Codec commit: $HEAD"
else
  if [[ "${FLOATFLAC_ALLOW_UNVERIFIED_SOURCE:-}" != "1" ]]; then
    echo "ERROR: source dir is not a git checkout; cannot verify pin ${PIN:0:8}...; set FLOATFLAC_ALLOW_UNVERIFIED_SOURCE=1 to override" >&2
    exit 1
  fi
  echo "Codec commit: unverified (override)"
fi

cmake -S "$SRC" -B "$SRC/build" \
  -DENABLE_EXPERIMENTAL_FLOAT_SAMPLE_CODING=ON \
  -DWITH_OGG=OFF \
  -DBUILD_TESTING=ON \
  -DBUILD_DOCS=OFF \
  -DINSTALL_MANPAGES=OFF \
  -DCMAKE_BUILD_TYPE=Release

cmake --build "$SRC/build" --target flacapp metaflac --parallel 4

FLAC="$SRC/build/src/flac/flac"
METAFLAC="$SRC/build/src/metaflac/metaflac"
echo "flac:     $FLAC"
echo "metaflac: $METAFLAC"

FLAC_HELP="$("$FLAC" --help)"
META_HELP="$("$METAFLAC" --help)"
if [[ "$FLAC_HELP" != *"--sample-type"* ]]; then
  echo "ERROR: flac lacks --sample-type" >&2
  exit 1
fi
if [[ "$META_HELP" != *"--show-sample-type"* ]]; then
  echo "ERROR: metaflac lacks --show-sample-type" >&2
  exit 1
fi
echo "Capability check OK"
