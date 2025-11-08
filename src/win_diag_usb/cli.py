"""
Command-line entry point for WinDiagUSB.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

from .diagnostics import APP_NAME, Diagnostics
from .gui import gui_available, run_gui
from .reports import render_html


def run_headless() -> dict:
    diag = Diagnostics()
    return diag.run_all()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def cli(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"{APP_NAME} — Windows diagnostics toolkit")
    parser.add_argument("--json", action="store_true", help="Print full diagnostics JSON to stdout")
    parser.add_argument("--save-json", type=Path, help="Write diagnostics JSON to the given path")
    parser.add_argument("--save-html", type=Path, help="Write diagnostics HTML report beside the JSON output")
    parser.add_argument("--zip", type=Path, help="Create a portable ZIP bundle containing JSON, HTML, and SMART logs")
    parser.add_argument("--headless", action="store_true", help="Run in CLI/headless mode even if Tkinter is available")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output (default when printing)")
    parser.add_argument("--quiet", action="store_true", help="Suppress friendly status messages")
    args = parser.parse_args(list(argv) if argv is not None else None)

    headless = args.headless or args.json or args.save_json or args.save_html or args.zip

    if not headless:
        if os.name != "nt":
            parser.error("The GUI is only supported on Windows. Use --headless to run CLI diagnostics.")
        if not gui_available():
            parser.error("Tkinter is missing. Install python3-tk or use --headless for CLI output.")
        run_gui()
        return 0

    results = run_headless()
    if not args.quiet:
        print(f"{APP_NAME}: diagnostics completed at {results.get('meta', {}).get('completed')}")

    if args.json or (not args.save_json and not args.save_html and not args.zip):
        indent = 2 if args.pretty or args.json or (not args.save_json and not args.save_html and not args.zip) else None
        json.dump(results, sys.stdout, indent=indent)
        print()

    if args.save_json:
        write_json(args.save_json, results)
        if not args.quiet:
            print(f"JSON saved to {args.save_json}")

    if args.save_html:
        html = render_html(results)
        args.save_html.parent.mkdir(parents=True, exist_ok=True)
        args.save_html.write_text(html, encoding="utf-8")
        if not args.quiet:
            print(f"HTML saved to {args.save_html}")

    if args.zip:
        import zipfile

        args.zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("report.json", json.dumps(results, indent=2))
            archive.writestr("report.html", render_html(results))
            for idx, drive in enumerate(results.get("storage", [])):
                if drive.get("raw"):
                    archive.writestr(f"smartctl_{idx}.txt", drive["raw"])
        if not args.quiet:
            print(f"ZIP bundle saved to {args.zip}")

    return 0


def main() -> int:
    return cli()


if __name__ == "__main__":
    raise SystemExit(main())
