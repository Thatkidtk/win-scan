"""
Tkinter front-end for WinDiagUSB.
"""

from __future__ import annotations

import json
import os
import queue
import threading
from typing import Dict

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # pragma: no cover - tkinter not always available
    tk = None  # type: ignore[assignment]
    ttk = filedialog = messagebox = None  # type: ignore[assignment]

from .diagnostics import APP_NAME, Diagnostics, TOOLS_DIR, run
from .reports import render_html


if tk is not None:

    class TextPane(ttk.Frame):  # type: ignore[misc]
        def __init__(self, master):
            super().__init__(master)
            self.text = tk.Text(self, wrap="word", height=20)
            self.text.configure(font=("Consolas", 10))
            self.text.pack(fill="both", expand=True)

        def set(self, content: str) -> None:
            self.text.delete("1.0", "end")
            self.text.insert("end", content)

    class App(ttk.Frame):  # type: ignore[misc]
        def __init__(self, master):
            super().__init__(master)
            self.master = master
            self.pack(fill="both", expand=True)
            self.result = None
            self.q: "queue.Queue" = queue.Queue()

            hdr = ttk.Frame(self)
            hdr.pack(fill="x", padx=8, pady=6)
            ttk.Label(hdr, text=f"{APP_NAME} — Windows Diagnostics", font=("Segoe UI", 12, "bold")).pack(side="left")
            ttk.Button(hdr, text="Run diagnostics", command=self.run_diagnostics).pack(side="right")
            ttk.Button(hdr, text="Export…", command=self.export_report).pack(side="right", padx=(0, 6))
            ttk.Button(hdr, text="Open tools", command=self.open_tools).pack(side="right", padx=(0, 6))
            ttk.Button(hdr, text="RAM test", command=self.ram_test_reminder).pack(side="right", padx=(0, 6))

            self.nb = ttk.Notebook(self)
            self.nb.pack(fill="both", expand=True, padx=8, pady=8)
            self.tabs: Dict[str, TextPane] = {}
            for name in ("Summary", "Overview", "Storage", "Drivers", "Temps", "Network", "Events", "Raw"):
                frame = TextPane(self.nb)
                self.nb.add(frame, text=name)
                self.tabs[name] = frame

            self.after(200, self.poll_queue)

        def run_diagnostics(self) -> None:
            if getattr(self, "worker", None) and self.worker.is_alive():
                messagebox.showinfo(APP_NAME, "Diagnostics already running…")
                return
            for tab in self.tabs.values():
                tab.set("Collecting…\n")
            self.worker = threading.Thread(target=self._worker, daemon=True)
            self.worker.start()

        def _worker(self) -> None:
            try:
                diag = Diagnostics()
                result = diag.run_all()
                self.q.put(("done", result))
            except Exception as exc:  # pragma: no cover - UI thread
                self.q.put(("error", str(exc)))

        def poll_queue(self) -> None:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                self.after(200, self.poll_queue)
                return

            if kind == "done":
                self.result = payload
                self.render(payload)
            elif kind == "error":
                messagebox.showerror(APP_NAME, f"Diagnostics error: {payload}")
            self.after(200, self.poll_queue)

        def badge(self, ok: bool) -> str:
            return "✅" if ok else "⚠️"

        def render(self, result: Dict[str, object]) -> None:
            meta = result.get("meta", {})
            lines = []
            if not meta.get("admin", False):
                lines.append("⚠️ Not running as Admin — some NVMe SMART/temp data may be missing.\n")
            storage_ok = True
            any_storage = False
            for drive in result.get("storage", []):
                if drive.get("error"):
                    storage_ok = False
                if drive.get("health") and not str(drive["health"]).startswith("PASSED"):
                    storage_ok = False
                any_storage = True
            storage_ok = storage_ok and any_storage
            bad_drivers = len(result.get("drivers", []))
            temps = result.get("temps", {}).get("readings", [])
            avg_temp = sum([(t.get("value_c") or 0) for t in temps]) / len(temps) if temps else None
            net = result.get("network", {})

            lines.append(f"{self.badge(storage_ok)} SMART: {'OK' if storage_ok else 'Issues found or unavailable'}")
            lines.append(
                f"{self.badge(bad_drivers == 0)} Drivers: {'OK' if bad_drivers == 0 else f'{bad_drivers} with problems'}"
            )
            lines.append(
                f"{self.badge(avg_temp is not None)} Temps: {('avg %.1f°C' % avg_temp) if avg_temp is not None else 'Unknown'}"
            )
            lines.append(
                f"{self.badge(net.get('ping_ok'))} Network: ping {net.get('ping_ms')} ms | DNS "
                f"{'OK' if net.get('dns_ok') else 'FAIL'} | hops {net.get('tracert_hops')}"
            )
            self.tabs["Summary"].set("\n".join(lines))

            system = result.get("system", {})
            overview_lines = []
            for key in (
                "platform",
                "release",
                "version",
                "machine",
                "processor",
                "cpu_physical_cores",
                "cpu_logical_cores",
                "memory_total_gb",
                "boot_time",
            ):
                if key in system:
                    overview_lines.append(f"{key:>20}: {system[key]}")
            if system.get("volumes"):
                overview_lines.append("\nVolumes:")
                for volume in system["volumes"]:
                    overview_lines.append(
                        f"  {volume['device']} -> {volume['mount']} | {volume.get('fstype','')} | "
                        f"{volume['total_gb']} GB, used {volume['percent']}%"
                    )
            self.tabs["Overview"].set("\n".join(overview_lines))

            storage_lines = []
            for drive in result.get("storage", []):
                if drive.get("error"):
                    storage_lines.append(f"ERROR {drive.get('device','?')}: {drive['error']}")
                    continue
                storage_lines.append(f"Device: {drive.get('device')}")
                storage_lines.append(f"  Health: {drive.get('health', 'Unknown')}")
                if drive.get("nvme"):
                    for key, value in drive["nvme"].items():
                        storage_lines.append(f"  NVMe {key}: {value}")
                if drive.get("raw"):
                    head = "\n".join(drive["raw"].splitlines()[:20])
                    storage_lines.append("  smartctl output (head):\n" + "\n".join("    " + ln for ln in head.splitlines()))
                storage_lines.append("")
            if not storage_lines:
                storage_lines = ["No storage data."]
            self.tabs["Storage"].set("\n".join(storage_lines))

            driver_lines = []
            for driver in result.get("drivers", []):
                driver_lines.append(
                    f"{driver.get('device')} | {driver.get('manufacturer')} | v{driver.get('driver_version')} | "
                    f"ProblemCode={driver.get('problem_code')} | outdated={driver.get('outdated')}"
                )
            if not driver_lines:
                driver_lines = ["All drivers OK (no ProblemCode reported)."]
            self.tabs["Drivers"].set("\n".join(driver_lines))

            temp_lines = []
            sources = result.get("temps", {}).get("sources", [])
            if sources:
                temp_lines.append(f"Sources: {', '.join(sources)}")
            for sensor in result.get("temps", {}).get("readings", []):
                name = sensor.get("name")
                value = sensor.get("value_c")
                try:
                    temp_lines.append(f"{name}: {float(value):.1f} °C")
                except Exception:
                    temp_lines.append(f"{name}: {value} °C")
            if not temp_lines:
                temp_lines = ["No temperature sensors read. Tip: add LibreHardwareMonitorCLI.exe to tools/ and re-run."]
            self.tabs["Temps"].set("\n".join(temp_lines))

            network = result.get("network", {})
            self.tabs["Network"].set(
                f"Ping 1.1.1.1: {'OK' if network.get('ping_ok') else 'FAIL'} ({network.get('ping_ms')} ms)\n"
                f"DNS lookup: {'OK' if network.get('dns_ok') else 'FAIL'}\n"
                f"Tracert (3 hops): {network.get('tracert_hops')} hops"
            )

            event_lines = []
            for evt in result.get("events", {}).get("bugchecks", []):
                if isinstance(evt, dict):
                    event_lines.append(
                        f"{evt.get('TimeCreated')} | {evt.get('ProviderName')} | {evt.get('Id')} | "
                        f"{evt.get('LevelDisplayName')}\n{(evt.get('Message') or '')[:600]}\n"
                    )
                else:
                    event_lines.append(str(evt))
            if not event_lines:
                event_lines = ["No recent bugchecks (ID 1001) found."]
            self.tabs["Events"].set("\n".join(event_lines))

            self.tabs["Raw"].set(json.dumps(result, indent=2))

        def export_report(self) -> None:
            if not self.result:
                messagebox.showinfo(APP_NAME, "Run diagnostics first.")
                return
            filename = filedialog.asksaveasfilename(
                defaultextension=".zip",
                filetypes=[("Zip bundle", "*.zip"), ("JSON only", "*.json"), ("All files", "*.*")],
            )
            if not filename:
                return
            try:
                if filename.lower().endswith(".json"):
                    with open(filename, "w", encoding="utf-8") as handle:
                        json.dump(self.result, handle, indent=2)
                    html_fn = os.path.splitext(filename)[0] + ".html"
                    with open(html_fn, "w", encoding="utf-8") as handle:
                        handle.write(render_html(self.result))
                    messagebox.showinfo(APP_NAME, f"Saved:\n{filename}\n{html_fn}")
                else:
                    import zipfile

                    with zipfile.ZipFile(filename, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                        archive.writestr("report.json", json.dumps(self.result, indent=2))
                        archive.writestr("report.html", render_html(self.result))
                        for idx, drive in enumerate(self.result.get("storage", [])):
                            if drive.get("raw"):
                                archive.writestr(f"smartctl_{idx}.txt", drive["raw"])
                    messagebox.showinfo(APP_NAME, f"Bundle saved: {filename}")
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Export failed: {exc}")

        def open_tools(self) -> None:
            os.makedirs(TOOLS_DIR, exist_ok=True)
            try:
                os.startfile(TOOLS_DIR)  # type: ignore[attr-defined]
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Could not open tools folder: {exc}")

        def ram_test_reminder(self) -> None:
            rc, so, se = run(["mdsched.exe"], timeout=5)
            if rc != 0:
                messagebox.showerror(APP_NAME, f"Could not launch Windows Memory Diagnostic: {se or so}")
            else:
                messagebox.showinfo(APP_NAME, "Windows Memory Diagnostic launched. Choose when to restart to test RAM.")

else:
    TextPane = None
    App = None


def gui_available() -> bool:
    return tk is not None


def run_gui() -> None:
    if os.name != "nt":
        raise RuntimeError("WinDiagUSB targets Windows only.")
    if tk is None or App is None:
        raise RuntimeError("Tkinter is not available. Install python3-tk / Tk runtime and retry.")
    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("1024x720")
    try:
        style = ttk.Style()
        style.theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()
