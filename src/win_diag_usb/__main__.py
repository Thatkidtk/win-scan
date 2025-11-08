"""Module entry-point so `python -m win_diag_usb` works."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
