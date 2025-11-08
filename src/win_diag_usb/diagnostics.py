"""
Core diagnostics logic for WinDiagUSB.

This module contains the platform helpers plus the Diagnostics class that
collects system information, SMART data, driver issues, temperatures,
network sanity checks, and bugcheck events.  It is intentionally free of
any GUI code so it can be reused by both the Tkinter front-end and any
future CLI or service wrappers.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Tuple

try:
    import psutil
except ImportError:  # pragma: no cover - optional dependency
    psutil = None  # type: ignore[assignment]

try:  # pragma: no cover - Windows-only optional dependency
    import wmi
except ImportError:
    wmi = None  # type: ignore[assignment]

APP_NAME = "WinDiagUSB"


def _default_base_dir() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller/py2exe
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = os.environ.get("WINDIAGUSB_BASE", _default_base_dir())
TOOLS_DIR = os.environ.get("WINDIAGUSB_TOOLS", os.path.join(BASE_DIR, "tools"))
SMARTCTL = os.path.join(TOOLS_DIR, "smartctl.exe")
LHM_CLI = os.path.join(TOOLS_DIR, "LibreHardwareMonitorCLI.exe")


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        return False


def run(cmd: List[str], timeout: int = 60) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


class Diagnostics:
    """Collects the various diagnostics datasets used by the GUI + CLI."""

    def __init__(self) -> None:
        self.results: Dict[str, object] = {
            "meta": {
                "app": APP_NAME,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "admin": is_admin(),
            },
            "system": {},
            "storage": [],
            "drivers": [],
            "temps": {"sources": [], "readings": []},
            "battery": {},
            "events": {"bugchecks": []},
            "network": {},
        }

    # ---- System overview ----
    def collect_system(self) -> None:
        info = {
            "platform": platform.platform(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }
        if psutil:
            info.update(
                {
                    "cpu_physical_cores": psutil.cpu_count(logical=False),
                    "cpu_logical_cores": psutil.cpu_count(logical=True),
                    "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                    "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                }
            )
            volumes = []
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    volumes.append(
                        {
                            "device": part.device,
                            "mount": part.mountpoint,
                            "fstype": part.fstype,
                            "total_gb": round(usage.total / (1024**3), 2),
                            "percent": usage.percent,
                        }
                    )
                except Exception:
                    continue
            info["volumes"] = volumes
        self.results["system"] = info

    # ---- SMART via smartctl ----
    def collect_smart(self) -> None:
        if not os.path.exists(SMARTCTL):
            self.results["storage"].append(
                {
                    "error": f"smartctl.exe not found in {TOOLS_DIR}. Place smartctl.exe there to enable SMART checks.",
                }
            )
            return
        code, out, err = run([SMARTCTL, "--scan-open"], timeout=25)
        if code != 0:
            self.results["storage"].append({"error": f"smartctl scan failed: {err or out}"})
            return
        devices = []
        for line in out.splitlines():
            match = re.match(r"^(?P<dev>\S+)", line)
            if match:
                devices.append(match.group("dev"))
        if not devices:
            self.results["storage"].append({"note": "No drives discovered by smartctl."})
            return
        for dev in devices:
            entry: Dict[str, object] = {"device": dev}
            rc, so, se = run([SMARTCTL, "-a", dev], timeout=60)
            entry["returncode"] = rc
            if rc != 0:
                entry["error"] = se or so
            else:
                entry["raw"] = so
                for line in so.splitlines():
                    if "SMART overall-health self-assessment test result" in line:
                        entry["health"] = line.split(":")[-1].strip()
                    if "Percentage Used" in line and "%" in line:
                        entry.setdefault("nvme", {})["percentage_used"] = line.split(":")[-1].strip()  # type: ignore[index]
                    if "Data Units Written" in line:
                        entry.setdefault("nvme", {})["data_units_written"] = line.split(":")[-1].strip()  # type: ignore[index]
            self.results["storage"].append(entry)

    # ---- Drivers (problem devices + outdated flag) ----
    def collect_driver_issues(self) -> None:
        if not wmi:
            return
        try:
            conn = wmi.WMI()
            cutoff_year = datetime.now().year - 2
            for driver in conn.Win32_PnPSignedDriver():
                problem = getattr(driver, "ProblemCode", None)
                if not problem:
                    continue
                year = None
                try:
                    year = int(str(driver.DriverDate)[:4]) if driver.DriverDate else None
                except Exception:
                    year = None
                self.results["drivers"].append(
                    {
                        "device": driver.DeviceName,
                        "manufacturer": driver.Manufacturer,
                        "driver_version": driver.DriverVersion,
                        "driver_date": str(driver.DriverDate),
                        "problem_code": problem,
                        "outdated": (year is not None and year < cutoff_year),
                    }
                )
        except Exception:
            return

    # ---- Temperatures ----
    def collect_temps(self) -> None:
        if os.path.exists(LHM_CLI):
            rc, so, _ = run([LHM_CLI, "--json"], timeout=30)
            if rc == 0 and so:
                try:
                    data = json.loads(so)
                    self.results["temps"]["sources"].append("LibreHardwareMonitorCLI")
                    for sensor in data.get("Sensors", []):
                        if sensor.get("Type") == "Temperature":
                            self.results["temps"]["readings"].append(
                                {
                                    "name": sensor.get("Name"),
                                    "value_c": sensor.get("Value"),
                                    "hw": sensor.get("Hardware"),
                                }
                            )
                except Exception:
                    pass
        else:
            self.results["temps"]["sources"].append("None (add LibreHardwareMonitorCLI.exe to tools/)")

    # ---- Events (recent bugchecks) ----
    def collect_bugchecks(self, max_events: int = 5) -> None:
        if os.name != "nt":
            return
        pwsh = (
            "Get-WinEvent -FilterHashtable @{LogName='System'; Id=1001} -MaxEvents %d | "
            "Select-Object TimeCreated, ProviderName, Id, LevelDisplayName, Message | ConvertTo-Json"
        ) % max_events
        rc, so, _ = run(["powershell", "-NoLogo", "-NoProfile", "-Command", pwsh], timeout=25)
        if rc == 0 and so:
            try:
                data = json.loads(so)
                if isinstance(data, dict):
                    data = [data]
                self.results["events"]["bugchecks"] = data or []
            except Exception:
                pass

    # ---- Network sanity ----
    def collect_network(self) -> None:
        checks = {"ping_ok": False, "ping_ms": "N/A", "dns_ok": False, "tracert_hops": 0}
        ping_cmd = ["ping", "1.1.1.1", "-n", "4"] if os.name == "nt" else ["ping", "-c", "4", "1.1.1.1"]
        rc, so, _ = run(ping_cmd, timeout=10)
        if rc == 0:
            checks["ping_ok"] = True
            if os.name == "nt":
                match = re.search(r"Average = (\d+)ms", so)
                checks["ping_ms"] = match.group(1) if match else "N/A"
            else:
                match = re.search(r"= [\d\.]+/([\d\.]+)/", so)
                checks["ping_ms"] = match.group(1) if match else "N/A"
        rc, so, _ = run(["nslookup", "google.com"], timeout=8)
        checks["dns_ok"] = rc == 0 and "Address" in so
        if os.name == "nt":
            rc, so, _ = run(["tracert", "-h", "3", "1.1.1.1"], timeout=10)
            if so:
                hops = [line for line in so.splitlines() if re.match(r"^\s*\d+", line)]
                checks["tracert_hops"] = len(hops)
        self.results["network"] = checks

    def run_all(self) -> Dict[str, object]:
        self.collect_system()
        self.collect_smart()
        self.collect_driver_issues()
        self.collect_temps()
        self.collect_bugchecks()
        self.collect_network()
        self.results["meta"]["completed"] = datetime.utcnow().isoformat() + "Z"
        return self.results


__all__ = [
    "APP_NAME",
    "BASE_DIR",
    "TOOLS_DIR",
    "SMARTCTL",
    "LHM_CLI",
    "Diagnostics",
    "run",
    "is_admin",
]
