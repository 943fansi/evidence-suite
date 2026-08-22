#!/usr/bin/env python3
r"""Visual QA for exported drafts: screenshot the first page and key sections.

Why: citation/gate checks are textual — they cannot see ragged reference lists,
overflowing URLs, or broken tables. Real runs shipped a PDF whose reference
section was visually broken while every machine check passed. This script makes
the "look at it" step semi-automatic: it renders the draft with the same print
CSS used by export_pdf.py, then captures PNG slices for human/visual-model
inspection BEFORE delivery.

Inputs:
  - a draft .md (converted here with python-markdown + PRINT_CSS, no mermaid
    rendering — Mermaid blocks appear as code text in QA shots), or
  - a full .html produced by export_pdf.py.

Screenshots written to -o dir (default ./qa/):
  first_page.png           — top of the document
  section_<name>.png       — one per --sections entry (default: 参考文献)
  (--sections "参考文献,1 绪论" matches <h2> headings by substring)

Usage:
  python scripts/visual_qa.py 11_定稿.md
  python scripts/visual_qa.py 11_定稿.html -o qa/ --sections "参考文献,摘要" --width 1100

Exit codes: 0 ok; 1 chrome/conversion failure; 2 usage error.
Note: Chrome's --screenshot needs an ABSOLUTE output path on Windows (relative
paths fail with access-denied), so we always resolve().
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_pdf import PRINT_CSS, _find_chrome  # noqa: E402


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def load_html(source: Path) -> str:
    if source.suffix.lower() == ".html":
        return source.read_text(encoding="utf-8")
    import markdown
    body = markdown.markdown(source.read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code"])
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "</head><body>" + body + "</body></html>")


_H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL)
_NEXT_H2_RE = re.compile(r"<h2[^>]*>")


def slice_section(html: str, keyword: str) -> str | None:
    """Return the html from the <h2> whose text contains keyword to the next <h2>."""
    for m in _H2_RE.finditer(html):
        heading_text = re.sub(r"<[^>]+>", "", m.group(1))
        if keyword in heading_text:
            end_m = _NEXT_H2_RE.search(html, m.end())
            end = end_m.start() if end_m else len(html)
            return html[m.start():end]
    return None


def shoot(chrome: str, html_path: Path, out_png: Path, width: int, height: int) -> bool:
    cmd = [
        chrome, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
        f"--screenshot={out_png.resolve()}",
        f"--window-size={width},{height}",
        html_path.resolve().as_uri(),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
        return result.returncode == 0 and out_png.exists() and out_png.stat().st_size > 1000
    except Exception as exc:
        print(f"  Chrome screenshot failed: {exc}", file=sys.stderr)
        return False


def wrap_slice(slice_html: str, width: int) -> str:
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            f"{PRINT_CSS}</head><body style='width:{width - 40}px'>{slice_html}</body></html>")


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Draft .md or exported .html")
    parser.add_argument("-o", "--out-dir", type=Path, default=Path("qa"),
                        help="Output dir for PNG shots (default ./qa/)")
    parser.add_argument("--sections", type=str, default="参考文献",
                        help="Comma-separated <h2> heading substrings to capture")
    parser.add_argument("--width", type=int, default=1100, help="Viewport width (default 1100)")
    parser.add_argument("--height", type=int, default=1600, help="Viewport height (default 1600)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"File not found: {args.input}", file=sys.stderr)
        return 2
    chrome = _find_chrome()
    if not chrome:
        print("Chrome/Edge not found — visual QA unavailable", file=sys.stderr)
        return 1

    html = load_html(args.input)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    ok_all = True
    with tempfile.TemporaryDirectory(prefix="eq_vqa_") as td:
        tmp = Path(td)
        # Shot 1: first page (top of document)
        top_html = tmp / "top.html"
        styled = html.replace("</head>", f"{PRINT_CSS}\n</head>")
        top_html.write_text(styled, encoding="utf-8")
        png = args.out_dir / "first_page.png"
        ok = shoot(chrome, top_html, png, args.width, args.height)
        print(f"  first_page.png {'OK' if ok else 'FAILED'} ({png.stat().st_size:,} B)" if ok
              else "  first_page.png FAILED", file=sys.stderr if not ok else sys.stdout)
        ok_all &= ok

        # Shots 2..n: requested sections
        for keyword in [s.strip() for s in args.sections.split(",") if s.strip()]:
            slice_html = slice_section(html, keyword)
            if slice_html is None:
                print(f"  section '{keyword}': no matching <h2> — skipped", file=sys.stderr)
                continue
            sec_html = tmp / "section.html"
            sec_html.write_text(wrap_slice(slice_html, args.width), encoding="utf-8")
            safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", keyword).strip("_")
            png = args.out_dir / f"section_{safe}.png"
            ok = shoot(chrome, sec_html, png, args.width, min(args.height * 2, 4000))
            print(f"  section_{safe}.png {'OK' if ok else 'FAILED'}")
            ok_all &= ok

    if not ok_all:
        return 1
    print(f"Visual QA shots → {args.out_dir.resolve()}")
    print("Inspect manually (or with a vision model) BEFORE delivering the PDF:")
    print("  - reference entries hang-indent, no overflowing URLs, no ', .' artifacts")
    print("  - tables fit page width; headings/figures not orphaned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
