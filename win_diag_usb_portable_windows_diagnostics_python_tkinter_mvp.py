#!/usr/bin/env python3
"""
Legacy launcher that now delegates to the packaged WinDiagUSB app.

Keeping this file ensures existing shortcuts or documentation that still
point at the original prototype continue to work after the repo was
converted into a proper Python package.
"""

from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from win_diag_usb.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
