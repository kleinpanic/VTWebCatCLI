#!/usr/bin/env python3
import subprocess
import sys


def main():
    if len(sys.argv) < 3:
        print("usage: run_timeout.py SECONDS COMMAND...", file=sys.stderr)
        return 2

    timeout = int(sys.argv[1])
    cmd = sys.argv[2:]
    try:
        return subprocess.run(cmd, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
