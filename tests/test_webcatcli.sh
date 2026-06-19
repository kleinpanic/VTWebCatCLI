#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/vtwebcatcli/classic/tests/test_webcatcli.sh" "$@"
