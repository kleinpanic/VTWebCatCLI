#!/usr/bin/env python3
"""Compatibility entrypoint for the classic VTWebCatCLI checker."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "vtwebcatcli" / "classic" / "WebcatCLI.py"
    runpy.run_path(str(target), run_name="__main__")
