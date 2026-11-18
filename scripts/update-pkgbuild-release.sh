#!/usr/bin/env bash
# Update PKGBUILD from the source archive of an existing immutable tag.
set -euo pipefail

if (( $# != 1 )) || [[ ! $1 =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'Usage: %s VERSION (e.g. 1.0.0)\n' "$0" >&2
    exit 2
fi
version=$1
cd "$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"

if ! git diff --quiet -- PKGBUILD || ! git diff --cached --quiet -- PKGBUILD; then
    echo 'PKGBUILD has uncommitted changes; commit or stash them first.' >&2
    exit 1
fi
archive=$(mktemp)
contents=$(mktemp)
trap 'rm -f "$archive" "$contents"' EXIT
url="https://github.com/username227/cinnamon-remove-application/archive/refs/tags/v$version.tar.gz"
printf 'Downloading %s\n' "$url"
curl --fail --silent --show-error --location --retry 3 -o "$archive" "$url"
tar -tzf "$archive" > "$contents"
if grep -Eq '(^|/)PKGBUILD$' "$contents"; then
    echo 'Release archive contains PKGBUILD. Was export-ignore tagged?' >&2
    exit 1
fi
if ! grep -Eq '/usr/bin/cinnamon-remove-application$' "$contents"; then
    echo 'Release archive does not contain the application.' >&2
    exit 1
fi
checksum=$(sha256sum "$archive" | cut -d' ' -f1)
python3 - "$version" "$checksum" <<'PY'
from pathlib import Path
import re
import sys
version, checksum = sys.argv[1:]
path = Path("PKGBUILD")
original = path.read_text(encoding="utf-8")
updated, count_version = re.subn(
    r"(?m)^pkgver=[^\n]+$", f"pkgver={version}", original)
updated, count_hash = re.subn(
    r"(?m)^sha256sums=\('[0-9a-f]{64}'\)$",
    f"sha256sums=('{checksum}')", updated)
if count_version != 1 or count_hash != 1:
    raise SystemExit("Expected one pkgver and one SHA-256 source checksum; not updated.")
path.write_text(updated, encoding="utf-8")
PY
printf 'PKGBUILD updated to v%s, SHA-256 %s\n' "$version" "$checksum"
printf 'Review: git diff -- PKGBUILD\nTest: makepkg -Csi\n'
printf 'Commit and push the recipe after testing. Do not move the tag.\n'
