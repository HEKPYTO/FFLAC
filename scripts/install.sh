#!/bin/sh
set -eu

VERSION_TAG="${FLOATFLAC_VERSION:-v0.2.0}"
PREFIX="${FLOATFLAC_PREFIX:-$HOME/.local}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      [ "$#" -ge 2 ] || { echo "ERROR: --version needs a value" >&2; exit 1; }
      VERSION_TAG=$2
      shift 2
      ;;
    --prefix)
      [ "$#" -ge 2 ] || { echo "ERROR: --prefix needs a value" >&2; exit 1; }
      PREFIX=$2
      shift 2
      ;;
    *)
      echo "Usage: $0 [--version TAG] [--prefix DIR]" >&2
      exit 1
      ;;
  esac
done

VERSION="${VERSION_TAG#v}"
BASE_URL="${FLOATFLAC_BASE_URL:-https://github.com/HEKPYTO/FFLAC/releases/download/$VERSION_TAG}"
AUTH_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"

case "$(uname -s):$(uname -m)" in
  Linux:x86_64) PLATFORM=linux-x86_64 ;;
  Darwin:arm64) PLATFORM=macos-arm64 ;;
  *) echo "ERROR: unsupported platform $(uname -s) $(uname -m)" >&2; exit 1 ;;
esac

for tool in curl tar python3; do
  command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: $tool is required" >&2; exit 1; }
done
if command -v sha256sum >/dev/null 2>&1; then
  check_sums() { sha256sum -c "$1"; }
elif command -v shasum >/dev/null 2>&1; then
  check_sums() { shasum -a 256 -c "$1"; }
else
  echo "ERROR: sha256sum or shasum is required" >&2
  exit 1
fi

WHEEL="floatflac-$VERSION-py3-none-any.whl"
CODEC="floatflac-codec-$VERSION-$PLATFORM.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM

download() {
  if [ -n "$AUTH_TOKEN" ]; then
    if curl -fsSL -H "Authorization: Bearer $AUTH_TOKEN" "$BASE_URL/$1" -o "$TMP/$1" 2>/dev/null; then
      return
    fi
    case "$BASE_URL" in
      https://github.com/*)
        ASSET_ID="$(curl -fsSL -H "Authorization: Bearer $AUTH_TOKEN" "https://api.github.com/repos/HEKPYTO/FFLAC/releases/tags/$VERSION_TAG" | python3 -c 'import json,sys; print(next(a["id"] for a in json.load(sys.stdin)["assets"] if a["name"] == sys.argv[1]))' "$1")"
        curl -fsSL -H "Authorization: Bearer $AUTH_TOKEN" -H 'Accept: application/octet-stream' "https://api.github.com/repos/HEKPYTO/FFLAC/releases/assets/$ASSET_ID" -o "$TMP/$1"
        ;;
      *)
        return 1
        ;;
    esac
  else
    curl -fsSL "$BASE_URL/$1" -o "$TMP/$1"
  fi
}

for file in "$WHEEL" "$CODEC" SHA256SUMS; do
  echo "Downloading $file"
  download "$file"
done

for file in "$WHEEL" "$CODEC"; do
  awk -v f="$file" '$2 == f { print $1 "  " $2 }' "$TMP/SHA256SUMS" > "$TMP/$file.sha256"
  if [ ! -s "$TMP/$file.sha256" ]; then
    echo "ERROR: $file is missing from SHA256SUMS" >&2
    exit 1
  fi
  (cd "$TMP" && check_sums "$file.sha256")
done

mkdir -p "$PREFIX"
PREFIX="$(cd "$PREFIX" && pwd)"
CODEC_DIR="$PREFIX/libexec/floatflac/codec"
VENV="$PREFIX/libexec/floatflac/venv"

mkdir -p "$PREFIX/libexec/floatflac" "$PREFIX/bin"
rm -rf "$CODEC_DIR"
mkdir -p "$CODEC_DIR"
tar -xzf "$TMP/$CODEC" -C "$CODEC_DIR" --strip-components=1

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --quiet --no-index "$TMP/$WHEEL"

cat > "$PREFIX/bin/floatflac" <<EOF
#!/bin/sh
export FLOATFLAC_BIN_DIR="$CODEC_DIR/bin"
exec "$VENV/bin/floatflac" "\$@"
EOF
chmod 755 "$PREFIX/bin/floatflac"

echo "Installed floatflac $VERSION to $PREFIX"
echo "Add it to PATH: export PATH=\"$PREFIX/bin:\$PATH\""
