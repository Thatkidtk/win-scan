"""WinDiagUSB package metadata and convenience exports."""

from .diagnostics import APP_NAME, Diagnostics
from .cli import cli, main

__all__ = ["APP_NAME", "Diagnostics", "cli", "main"]
