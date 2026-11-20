#!/usr/bin/env bash
set -euo pipefail
export COPYFILE_DISABLE=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-dist}"
SRC="$ROOT/.build/flac-float"
PIN=05536fce4e43d06d5b71e75912007893ca0b8ca0
SHORT_PIN="${PIN:0:8}"
FLAC="$SRC/build/src/flac/flac"
METAFLAC="$SRC/build/src/metaflac/metaflac"

if [[ ! -x "$FLAC" || ! -x "$METAFLAC" ]]; then
  "$ROOT/scripts/build-codec.sh"
fi

case "$(uname -s):$(uname -m)" in
  Linux:x86_64) PLATFORM=linux-x86_64 ;;
  Darwin:arm64) PLATFORM=macos-arm64 ;;
  *) echo "ERROR: unsupported platform $(uname -s) $(uname -m)" >&2; exit 1 ;;
esac

VERSION="$(sed -n 's/^__version__ = "\([^"]*\)".*/\1/p' "$ROOT/src/floatflac/__init__.py")"
if [[ -z "$VERSION" ]]; then
  echo "ERROR: cannot read version from src/floatflac/__init__.py" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  SUM=(sha256sum)
else
  SUM=(shasum -a 256)
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
NAME="floatflac-codec-$VERSION-$PLATFORM"
STAGE="$WORK/$NAME"
mkdir -p "$STAGE/bin" "$STAGE/licenses" "$STAGE/source"

cp "$FLAC" "$STAGE/bin/flac"
cp "$METAFLAC" "$STAGE/bin/metaflac"
chmod 755 "$STAGE/bin/flac" "$STAGE/bin/metaflac"

GPL="$SRC/COPYING"
if [[ ! -f "$GPL" ]]; then
  GPL="$SRC/COPYING.GPL"
fi
cp "$GPL" "$STAGE/licenses/GPL-2.0.txt"
cp "$SRC/COPYING.Xiph" "$STAGE/licenses/BSD-3-Clause-libFLAC.txt"
cp "$ROOT/LICENSE" "$STAGE/LICENSE"
cp "$ROOT/NOTICE" "$STAGE/NOTICE"

git -C "$SRC" archive --format=tar.gz \
  --prefix="flac-float-$SHORT_PIN/" "$PIN" \
  > "$STAGE/source/flac-float-$SHORT_PIN.tar.gz"

BRANCH="$(git -C "$SRC" rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" == HEAD ]]; then
  BRANCH=detached
fi
printf '%s\n' \
  "codec commit: $PIN" \
  "branch: $BRANCH" \
  "platform: $PLATFORM" \
  "cmake version: $(cmake --version | head -1)" \
  "compiler version: $("${CC:-cc}" --version | head -1)" \
  "cmake flags:" \
  "  -DENABLE_EXPERIMENTAL_FLOAT_SAMPLE_CODING=ON" \
  "  -DWITH_OGG=OFF" \
  "  -DBUILD_TESTING=ON" \
  "  -DBUILD_DOCS=OFF" \
  "  -DINSTALL_MANPAGES=OFF" \
  "  -DCMAKE_BUILD_TYPE=Release" \
  "flac version: $("$FLAC" --version)" \
  "build date (UTC): $(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
  > "$STAGE/BUILD.txt"

(cd "$STAGE" && find . -type f ! -name SHA256SUMS -print | LC_ALL=C sort | while IFS= read -r f; do "${SUM[@]}" "${f#./}"; done) > "$STAGE/SHA256SUMS"

mkdir -p "$OUT"
ARCHIVE="$OUT/$NAME.tar.gz"
tar --no-xattrs -czf "$ARCHIVE" -C "$WORK" "$NAME"
(cd "$OUT" && "${SUM[@]}" "$NAME.tar.gz") > "$ARCHIVE.sha256"

echo "Archive: $ARCHIVE"
echo "Size: $(wc -c < "$ARCHIVE" | awk '{print $1}') bytes"
