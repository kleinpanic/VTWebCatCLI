#!/usr/bin/env bash
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  printf 'FAIL %s\n' "$1" >&2
  exit 1
}

pass() {
  printf 'PASS %s\n' "$1"
}

tracked="$(git ls-files)"

printf '%s\n' "$tracked" | grep -E '(^|/)__pycache__/|\.pyc$' >/dev/null &&
  fail "tracked Python bytecode is not allowed"

case_conflicts="$(printf '%s\n' "$tracked" | awk '
  {
    key = tolower($0)
    if (seen[key] != "" && seen[key] != $0) {
      print seen[key] " <-> " $0
    }
    seen[key] = $0
  }')"
[ -z "$case_conflicts" ] || {
  printf '%s\n' "$case_conflicts" >&2
  fail "tracked paths must not differ only by case"
}

printf '%s\n' "$tracked" | grep -E '^legacy/VTWebCatCLI/' >/dev/null &&
  fail "duplicate classic implementation tree is not allowed"

private_patterns='(^|/)(\.env|\.webcat\.toml|\.webcat\.local\.toml|\.webcat\.secrets|\.planning)(/|$)|(^|/)(Web-CAT\.pdf|student-submission\.jar)$|(^|/)(id_rsa|id_ed25519)(\.pub)?$|(\.pem|\.p12|\.jks|\.key)$|(^|/)(cookies?|sessions?|secrets?|tokens?)(/|$)'
private_hits="$(printf '%s\n' "$tracked" | grep -Ei "$private_patterns" || true)"
if [ -n "$private_hits" ]; then
  printf '%s\n' "$private_hits" >&2
  fail "private config, reports, credentials, or local submission artifacts must not be tracked"
fi

[ ! -e legacy/VTWebCatCLI ] || fail "legacy/VTWebCatCLI should not exist"
[ ! -e .planning ] || fail ".planning must stay off public main"
[ ! -e doc ] || fail "use docs/, not duplicate top-level doc/"
[ ! -e test ] || fail "use tests/, not duplicate top-level test/"
[ ! -e lua ] || fail "Neovim integration belongs under plugin/, not duplicate top-level lua/"
[ ! -e vtwebcatcli/classic ] || fail "classic source is vtwebcatcli/classic.py, not a nested duplicate directory"

for path in \
  WebcatCLI.py \
  vtwebcatcli/classic.py \
  requirements.txt \
  tests/test_webcatcli.sh \
  tests/classic-webcatcli.sh \
  docs/classic/README.md \
  docs/classic/_webcatcli \
  docs/classic/webcatcli.1 \
  docs/classic/webcatcli.bash \
  licenses/COPYING \
  licenses/COPYING.LESSER \
  licenses/LICENSE \
  licenses/LICENSE-junit.txt \
  templates/CS2114.rules.json \
  templates/student.jar \
  templates/CarranoDataStructures.jar \
  templates/CS2-GraphWindowLib.jar
do
  [ -e "$path" ] || fail "missing original public path: $path"
done

[ -x WebcatCLI.py ] || fail "WebcatCLI.py must be executable"
[ -x bin/webcat ] || fail "bin/webcat must be executable"
[ -x tests/test_webcatcli.sh ] || fail "tests/test_webcatcli.sh must be executable"
[ -x tests/classic-webcatcli.sh ] || fail "tests/classic-webcatcli.sh must be executable"

python3 -m py_compile WebcatCLI.py vtwebcatcli/classic.py

if rg -n '\blegacy\b' README.md PUBLISHING.md PROVENANCE.md docs lib profiles .github WebcatCLI.py >/tmp/webcat-legacy-word.out; then
  cat /tmp/webcat-legacy-word.out >&2
  fail "public docs/code should describe classic support without legacy wording"
fi
rm -f /tmp/webcat-legacy-word.out

pass "repository health"
