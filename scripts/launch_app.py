"""PyInstaller-friendly entry point for WinDiagUSB."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from win_diag_usb.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
