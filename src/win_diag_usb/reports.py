"""
Report rendering helpers for WinDiagUSB.
"""

from __future__ import annotations

import json

from .diagnostics import APP_NAME


def _esc(value) -> str:
    value = "" if value is None else str(value)
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(payload: dict) -> str:
    blocks = []
    meta = payload.get("meta", {})
    blocks.append(f"<h1>{APP_NAME} report</h1><p>UTC: {_esc(meta.get('completed',''))} | Admin: {meta.get('admin')}</p>")
    for section in ("system", "storage", "drivers", "temps", "network", "events"):
        blocks.append(f"<h2>{section.title()}</h2><pre>" + _esc(json.dumps(payload.get(section, {}), indent=2)) + "</pre>")
    return (
        "<!doctype html><meta charset='utf-8'><style>"
        "body{font:14px system-ui,Segoe UI,Tahoma,Arial}"
        " pre{background:#f7f7f7;padding:12px;border-radius:8px;overflow:auto}"
        "</style>" + "".join(blocks)
    )


__all__ = ["render_html"]
