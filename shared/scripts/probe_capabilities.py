#!/usr/bin/env python3
r"""Probe the runtime environment and emit a capability profile.

P3 / review §十六: make evidence-suite OS / agent / shell independent by
detecting what the runtime can actually do, then let skills auto-select the
best path (pandoc missing → python-markdown fallback, mmdc missing → remote
mermaid.ink, pdfplumber missing → warn instead of silently failing, …).

Writes runtime/capability.local.json (gitignored). Agents should read it when
loading a skill; `--human` prints a readable summary.

Checks (all local, no network unless --network):
  - python version / platform / shell type
  - python libs: markdown, python-docx, pdfplumber, PyPDF2, PyMuPDF, weasyprint,
    matplotlib, numpy, pyyaml, easyocr
  - tools: pandoc, chrome/edge, mermaid-cli (mmdc), curl
  - filesystem write test
  - network reachability (--network, best-effort with 5s timeout)

Usage:
  python scripts/probe_capabilities.py                 # write runtime/capability.local.json
  python scripts/probe_capabilities.py --human          # readable summary
  python scripts/probe_capabilities.py --network        # include network probe
Exit codes: 0 ok; 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = SUITE_ROOT / "runtime" / "capability.yaml"
OUTPUT = SUITE_ROOT / "runtime" / "capability.local.json"

PY_LIBS = {
    "markdown": "markdown",
    "docx": "docx",
    "pdfplumber": "pdfplumber",
    "pypdf2": "PyPDF2",
    "pymupdf": "fitz",
    "weasyprint": "weasyprint",
    "matplotlib": "matplotlib",
    "numpy": "numpy",
    "yaml": "yaml",
    "ocr": "easyocr",
}
TOOLS = {
    "pandoc": "pandoc",
    "mmdc": "mmdc",
    "curl": "curl",
}


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _shell_type() -> str:
    if platform.system() == "Windows" or os.environ.get("COMSPEC"):
        return "powershell"
    if os.environ.get("SHELL"):
        return "bash"
    return "unknown"


def _find_chrome() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    for path in candidates:
        if Path(path).exists():
            return "chrome/edge"
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        if shutil.which(name):
            return name
    return None


def _has_lib(mod: str) -> bool:
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _fs_writable() -> bool:
    try:
        with tempfile.TemporaryDirectory() as td:
            Path(td, "probe").write_text("ok", encoding="utf-8")
        return True
    except Exception:
        return False


def _network_reachable(timeout: int = 5) -> bool:
    import socket
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=timeout).close()
        return True
    except Exception:
        return False


def probe(network: bool = False) -> dict:
    caps = {"python_version": platform.python_version(),
            "platform": platform.system().lower(),
            "shell": _shell_type(),
            "filesystem": _fs_writable()}
    for key, mod in PY_LIBS.items():
        caps[key] = _has_lib(mod)
    for key, exe in TOOLS.items():
        caps[key] = shutil.which(exe) is not None
    caps["pdf_render"] = caps["weasyprint"] or _find_chrome() is not None
    caps["web_search"] = caps["network"] = network and _network_reachable()
    caps["web_fetch"] = caps["network"]
    caps["parallel_agents"] = False
    return caps


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human", action="store_true", help="print readable summary")
    parser.add_argument("--network", action="store_true",
                        help="include a network reachability probe (best-effort)")
    parser.add_argument("--output", type=Path, default=OUTPUT,
                        help="where to write capability.local.json")
    args = parser.parse_args()

    caps = probe(network=args.network)
    target = args.output or OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(caps, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.human:
        lines = [
            f"runtime capability: python {caps['python_version']} / {caps['platform']} / {caps['shell']}",
            f"  python libs: " + ", ".join(k for k in PY_LIBS if caps.get(k)) or " (none)",
            f"  tools: " + ", ".join(k for k in TOOLS if caps.get(k)) or " (none)",
            f"  pdf_render={caps['pdf_render']} filesystem={caps['filesystem']} "
            f"network={caps['network']}",
        ]
        print("\n".join(lines))
    print(f"capability -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
