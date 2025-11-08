# WinDiagUSB

Portable Windows health diagnostics with a Tkinter UI, CLI exports, and PyInstaller packaging.

## Highlights

- **One-click desktop app** – Tkinter dashboard with live tabs for system, SMART, drivers, temps, network, and event logs.
- **Headless exports** – `python -m win_diag_usb --json` prints structured results; additional flags save HTML and ZIP bundles.
- **Drop-in tooling** – Place `smartctl.exe` and `LibreHardwareMonitorCLI.exe` in the `tools/` folder for best coverage.
- **Portable build script** – `scripts/build_windows_portable.ps1` wraps PyInstaller to produce a ready-to-ship folder or EXE.
- **Single-source package** – Installable via `pip` and ready for GitHub Releases with semantic versioning (`pyproject.toml`).

## Requirements

| Component | Notes |
| --- | --- |
| Windows 10/11 | GUI mode + diagnostics were validated on recent Windows builds. |
| Python 3.9+ | Includes Tkinter on the official Windows installer; otherwise install `python3-tk`. |
| Optional binaries | Drop [smartctl](https://www.smartmontools.org/wiki/Download) and [LibreHardwareMonitorCLI](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) into `tools/` for advanced drive/temp data. |

## Repository Layout

```
.
├── pyproject.toml               # Build + dependency metadata
├── src/win_diag_usb/            # Package code (diagnostics, GUI, CLI, reports)
├── scripts/                     # Helper entry point + build tooling
├── tools/                       # (Ignored) place third-party binaries here
├── dist/                        # PyInstaller output (generated)
└── README.md
```

## Installation

```powershell
git clone https://github.com/Thatkidtk/win-scan.git
cd win-scan
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -e .
```

## Usage

### Launch the GUI

```powershell
python -m win_diag_usb
# or
windiagusb
```

The GUI automatically runs on Windows when Tkinter is available. You can drop `smartctl.exe` and `LibreHardwareMonitorCLI.exe` into `tools/` before launching to enable SMART + temperature readings.

### Headless / CLI mode

```powershell
# Print JSON to stdout
python -m win_diag_usb --json

# Save JSON + HTML + ZIP bundle in one go
python -m win_diag_usb --headless --save-json reports\scan.json --save-html reports\scan.html --zip reports\bundle.zip
```

Flags:

| Flag | Description |
| --- | --- |
| `--headless` | Skip the GUI even if Tkinter is present. |
| `--json` | Print the diagnostics payload to stdout. |
| `--save-json PATH` | Write `report.json`. |
| `--save-html PATH` | Export a styled HTML report. |
| `--zip PATH` | Bundle JSON, HTML, and raw SMART logs. |
| `--pretty` | Force multi-line JSON formatting. |
| `--quiet` | Suppress progress messages. |

## Building a Portable Release

1. Ensure the `tools/` directory contains any helper binaries you plan to ship (optional but recommended).
2. From PowerShell:

```powershell
.\scripts\build_windows_portable.ps1
```

3. The PyInstaller output lives under `dist\WinDiagUSB`. Zip that folder or wrap it in an installer of your choice.

> Tip: create a GitHub Release and upload the ZIP plus the `tools/` instructions so users can simply download and run.

## Testing & Verification

- **GUI**: launch via `python -m win_diag_usb` on Windows and click “Run diagnostics”.
- **CLI**: `python -m win_diag_usb --json`.
- **Packaging**: `scripts\build_windows_portable.ps1`, then test the produced executable on a clean Windows VM.

## Publishing Workflow

1. Commit changes locally.
2. Run the build script to ensure the portable bundle succeeds.
3. Push to `https://github.com/Thatkidtk/win-scan.git`.
4. Create a release tag (`git tag v1.3.0 && git push origin v1.3.0`) and attach the PyInstaller ZIP.

## Contributing

Issues and PRs are welcome! Key areas for contributions:

- Improved hardware coverage (e.g., battery telemetry, GPU metrics).
- Automated tests or CI pipelines (GitHub Actions suggested).
- Additional export targets (PDF, CSV).

---

Maintained by [Thatkidtk](https://github.com/Thatkidtk). Use at your own risk; always review diagnostics output before sharing.
