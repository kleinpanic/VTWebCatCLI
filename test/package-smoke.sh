#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
tmp="${TMPDIR:-/tmp}/vtwebcatcli-package-$$"

cleanup() {
  rm -rf "$tmp"
}
trap cleanup EXIT

mkdir -p "$tmp/package" "$tmp/extract"
cd "$ROOT"

tar czf "$tmp/package/webcatcli-test.tar.gz" \
  WebcatCLI.py bin lib profiles vtwebcatcli \
  templates doc docs lua plugin tests test \
  README.md CHANGELOG.md TODO.MD PUBLISHING.md PROVENANCE.md \
  LICENSE licenses requirements.txt

tar xzf "$tmp/package/webcatcli-test.tar.gz" -C "$tmp/extract"

"$tmp/extract/WebcatCLI.py" --version >/tmp/webcat-package-version.out
"$tmp/extract/bin/webcat" --profile cs2505 doctor | python3 -m json.tool >/tmp/webcat-package-cs2505.json
"$tmp/extract/bin/webcat" --profile cs3114 doctor | python3 -m json.tool >/tmp/webcat-package-cs3114.json

grep -F '"profile": "cs2505"' /tmp/webcat-package-cs2505.json >/dev/null
grep -F '"profile": "cs3114"' /tmp/webcat-package-cs3114.json >/dev/null

rm -f /tmp/webcat-package-version.out /tmp/webcat-package-cs2505.json /tmp/webcat-package-cs3114.json
printf 'PASS release package smoke\n'
