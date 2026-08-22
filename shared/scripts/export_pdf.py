#!/usr/bin/env python3
r"""Export evidence-driven draft Markdown to PDF with Mermaid diagram rendering.

Pipeline:
  1. Extract Mermaid code blocks, render each via mermaid.ink API → SVG
     (No Node.js needed — plain base64url, retried with deflate+base64url on
     HTTP/URL-limit errors; over-long node labels are warned and, on total
     failure, replaced with a VISIBLE fenced-warning block instead of being
     silently dropped)
  2. Replace code blocks with inline SVG image references
  3. Convert processed Markdown to standalone HTML:
     - Primary: pandoc (--embed-resources for >=2.19, --self-contained for older)
     - Fallback when pandoc is unavailable: python-markdown (pip install markdown;
       extensions: tables + fenced_code). Both paths share the same print CSS.
  4. Post-process HTML: bare URLs → <a> links (breakable), 参考文献 section →
     <section class="refs"> with hanging indent (thesis norms).
  5. Convert HTML to PDF:
     - Engine 1: weasyprint (Python-native, tried first when installed)
     - Engine 2: Chrome headless --print-to-pdf (fallback; CJK fonts via system stack)
     - Fallback: save self-contained HTML for manual browser print

Dependencies:
  - pandoc (optional; fallback needs no pandoc): winget install pandoc (Windows) /
     brew install pandoc (macOS) / apt install pandoc (Linux)
  - python-markdown (fallback only, optional): pip install markdown
  - Chrome/Edge (for headless PDF): macOS `/Applications/Google Chrome.app`;
     Windows `C:\Program Files\Google\Chrome\Application\chrome.exe` or msedge.exe
  - weasyprint (optional): pip3 install --break-system-packages weasyprint

Usage:
  python3 export_pdf.py 11_定稿.md -o 11_定稿.pdf
"""

from __future__ import annotations

import argparse
import base64
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

# ---------------------------------------------------------------------------
# Check toolchain
# ---------------------------------------------------------------------------

def _which(name: str) -> str | None:
    return shutil.which(name)


def _has_weasyprint() -> bool:
    try:
        from weasyprint import HTML  # noqa: F401
        return True
    except Exception:
        return False


def check_toolchain() -> str | None:
    """Return the pandoc binary, or None to signal the python-markdown fallback.

    pandoc missing is NOT fatal anymore — real runs hit networks where the
    pandoc installer cannot be fetched; the python-markdown path is the
    documented degraded mode (same print CSS, slightly simpler HTML).
    """
    pandoc = _which("pandoc")
    if not pandoc:
        try:
            import markdown  # noqa: F401
            print("pandoc not found — using python-markdown fallback (pip install markdown).")
        except ImportError:
            print("pandoc not found and python-markdown not installed. "
                  "Install either: winget install pandoc  |  pip install markdown",
                  file=sys.stderr)
            return ""
    return pandoc


# ---------------------------------------------------------------------------
# Mermaid rendering via mermaid.ink
# ---------------------------------------------------------------------------

MERMAID_INK = "https://mermaid.ink/svg/"

# Real-run lesson: over-long node labels (e.g. >12 CJK chars) blow past the
# mermaid.ink URL/HTTP limits and return HTTP 400/414, silently dropping the
# diagram from the PDF. Guard the label length BEFORE requesting, and never
# drop a diagram silently — on failure fall back to a visible fenced-code
# warning block instead.
MAX_LABEL_LEN = 14  # CJK chars; ASCII-ish text may use ~30
_EDGE_PAT = re.compile(r"(\w+)\s*(?:---|-->|==>|-.->|--->|-.->)[\s\[]*[^|\[\]]*[\|\[]{0,2}([^\]\n]*)")
# Node label = text inside [...] for a node declaration; also catch bare text
# right before an edge arrow (flowchart TD / graph LR default node syntax).
_NODE_LABEL_PAT = re.compile(r"\[([^\]\n]*)\]")


def _mermaid_label_warnings(code: str) -> list[str]:
    """Warn about node labels that are likely too long for mermaid.ink."""
    warnings: list[str] = []
    seen: set[str] = set()
    for m in _NODE_LABEL_PAT.finditer(code):
        label = m.group(1).strip()
        if not label or label in seen:
            continue
        seen.add(label)
        cjk = sum(1 for ch in label if ord(ch) > 0x2E00)
        eff_len = cjk * 2 + (len(label) - cjk)
        if eff_len > MAX_LABEL_LEN * 2:  # CJK counts double
            warnings.append(f"label too long ({eff_len}): '{label[:20]}…'")
    return warnings[:5]


def _encode_mermaid(text: str) -> str:
    """Encode Mermaid text for mermaid.ink API (plain base64url, no compression)."""
    encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
    return MERMAID_INK + encoded


def _encode_mermaid_compressed(text: str) -> str:
    """Encode Mermaid text for mermaid.ink using deflate+base64url (smaller URL).

    mermaid.ink accepts a deflate-compressed payload encoded as base64url when
    the plain form would exceed URL limits. Falls back gracefully if zlib is
    unavailable (it is in the stdlib).
    """
    import zlib
    raw = zlib.compress(text.encode("utf-8"), level=9)
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return MERMAID_INK + encoded


def render_mermaid_blocks(text: str, out_dir: Path) -> str:
    """Find ```mermaid blocks, render to SVG, replace with image refs.

    Per-block: warn on over-long labels, request the plain URL first, retry
    with the deflate-compressed URL on HTTP/URL-limit errors, and on total
    failure leave a visible ```fenced-warning block instead of silently
    dropping the diagram.
    """
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    blocks = list(pattern.finditer(text))
    if not blocks:
        print("  No Mermaid blocks found — skipping rendering.")
        return text

    out_dir.mkdir(parents=True, exist_ok=True)
    for i, match in enumerate(blocks):
        mermaid_code = match.group(1).strip()
        for w in _mermaid_label_warnings(mermaid_code):
            print(f"  ⚠️  Mermaid block {i + 1}: {w} — shorten labels (≤~12 CJK chars) "
                  f"or use short IDs + a caption, else mermaid.ink returns HTTP 400.",
                  file=sys.stderr)
        urls = [_encode_mermaid(mermaid_code), _encode_mermaid_compressed(mermaid_code)]
        img_path = out_dir / f"mermaid_diagram_{i + 1}.svg"
        svg_data: bytes | None = None
        err: Exception | None = None
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    svg_data = resp.read()
                if len(svg_data) > 0:
                    break
            except Exception as exc:  # HTTP 400/414/network
                err = exc
                svg_data = None
        if svg_data is None:
            print(f"  Mermaid block {i + 1}: FAILED after both encodings ({err})", file=sys.stderr)
            # Fall back to a VISIBLE warning block so the missing diagram is
            # never silent in the final PDF.
            original = match.group(0)
            replacement = (f"```\n⚠️ 图 {i + 1} 渲染失败（mermaid.ink HTTP 400/414）。"
                           f"请精简节点标签后重跑 export_pdf.py。\n原始代码：\n{mermaid_code}\n```")
            text = text.replace(original, replacement, 1)
            continue
        img_path.write_bytes(svg_data)
        # Patch SVG to add CJK fonts (macOS/Linux fallback)
        try:
            svg_text = svg_data.decode("utf-8")
            cjk_font = "STHeiti, 'Noto Sans CJK SC', 'PingFang SC', 'Microsoft YaHei',"
            svg_text = svg_text.replace(
                'font-family:"trebuchet ms",verdana,arial,sans-serif',
                f'font-family:{cjk_font}"trebuchet ms",verdana,arial,sans-serif'
            )
            img_path.write_bytes(svg_text.encode("utf-8"))
        except Exception:
            pass
        print(f"  Mermaid block {i + 1}: rendered → {img_path.name} ({len(svg_data):,} bytes)")
        original = match.group(0)
        replacement = f"![技术路线图](figures/mermaid_diagram_{i + 1}.svg)"
        text = text.replace(original, replacement, 1)
    return text


# ---------------------------------------------------------------------------
# Pandoc HTML conversion
# ---------------------------------------------------------------------------

def _pandoc_embed_flag(pandoc: str) -> list[str]:
    """Return the self-contained HTML flag for the installed pandoc version.

    pandoc >=2.19 renamed ``--self-contained`` to ``--embed-resources``;
    ``--self-contained`` was removed in pandoc 3.x. Windows `pandoc --version`
    prints `pandoc.exe 3.x.y` on the first line, so the binary name must be
    optional in the regex. Unknown versions default to `--embed-resources`
    (the modern flag) rather than the removed legacy one.
    """
    try:
        out = subprocess.run(
            [pandoc, "--version"], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=10,
        ).stdout
        first_line = out.splitlines()[0] if out else ""
        match = re.search(r"pandoc(?:\.exe)?\s+v?(\d+)\.(\d+)", first_line)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            if major > 2 or (major == 2 and minor >= 19):
                return ["--embed-resources"]
            return ["--self-contained"]
    except Exception:
        pass
    # Unknown / unparseable version → prefer the modern flag (pandoc 3.x removed --self-contained)
    return ["--embed-resources"]


# ---------------------------------------------------------------------------
# Thesis print CSS + HTML post-processing (shared by pandoc and fallback paths)
# ---------------------------------------------------------------------------

PRINT_CSS = """
<style>
  @media print {
    @page { size: A4; margin: 2cm 1.8cm 2.5cm 1.8cm; }
  }
  body {
    font-family: "PingFang SC", "Microsoft YaHei", "STHeiti", "Hiragino Sans", sans-serif;
    font-size: 11pt; line-height: 1.6; color: #1a1a1a;
    max-width: none; width: 100%; margin: 0; padding: 0;
  }
  h1 { font-size: 16pt; font-weight: bold; margin-top: 1.5em; border-bottom: 1.5pt solid #666; page-break-after: avoid; }
  h2 { font-size: 13pt; font-weight: bold; margin-top: 1.3em; page-break-after: avoid; }
  h3 { font-size: 12pt; font-weight: bold; margin-top: 1.1em; page-break-after: avoid; }
  h4 { font-size: 11pt; font-weight: bold; page-break-after: avoid; }
  h5 { font-size: 10pt; font-weight: bold; }
  p { margin: 0.4em 0; text-align: justify; widows: 2; orphans: 2; }
  table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 9pt; table-layout: fixed; word-break: break-all; page-break-inside: avoid; }
  th, td { border: 0.5pt solid #999; padding: 3px 5px; overflow-wrap: break-word; }
  th { background: #e8e8e8; font-weight: bold; }
  img { max-width: 100%; height: auto; display: block; margin: 1em auto; page-break-inside: avoid; }
  blockquote { border-left: 3pt solid #ccc; padding-left: 1em; color: #555; margin: 0.8em 0; }
  code { background: #f5f5f5; padding: 1px 4px; font-size: 9pt; border-radius: 2px; }
  pre { background: #f5f5f5; padding: 8px; font-size: 8pt; white-space: pre-wrap; word-wrap: break-word; overflow-x: visible; border-radius: 4px; }
  pre code { background: none; padding: 0; }
  a { color: inherit; text-decoration: none; overflow-wrap: anywhere; word-break: break-all; }
  /* 参考文献区：悬挂缩进 + 可断行 URL + 宋体/Times 混排（学位论文规范） */
  section.refs p {
    text-indent: -4em; padding-left: 4em; margin: 0.45em 0;
    text-align: left; font-size: 9pt; line-height: 1.55;
    font-family: "Times New Roman", "SimSun", "Songti SC", serif;
    overflow-wrap: anywhere;
  }
</style>
"""

_URL_RE = re.compile(r"(https?://[^\s<>\"']+)")
_TAG_RE = re.compile(r"(<[^>]+>)")


def _linkify_html(html: str) -> str:
    """Turn bare URLs in text segments into <a> tags (breakable in print).

    Splits on tags first so URLs already inside attributes (href=...) are never
    double-wrapped. Long unbreakable plain-text URLs were the #1 cause of
    ragged reference-list layout in real exports.
    """
    parts = _TAG_RE.split(html)
    out = []
    for i, part in enumerate(parts):
        if part.startswith("<"):
            out.append(part)
        else:
            out.append(_URL_RE.sub(r'<a href="\1">\1</a>', part))
    return "".join(out)


_REFS_H2_RE = re.compile(r"(<h2[^>]*>[^<]*参考文献[^<]*</h2>)")


def _wrap_refs_section(html: str) -> str:
    """Wrap the 参考文献 section (h2 → next h2/end) in <section class="refs">.

    Works for both pandoc (<h2 id="...">) and python-markdown (<h2>) output.
    """
    m = _REFS_H2_RE.search(html)
    if not m:
        return html
    start = m.start()
    next_h2 = re.compile(r"<h2[^>]*>").search(html, m.end())
    end = next_h2.start() if next_h2 else len(html)
    wrapped = '<section class="refs">' + html[start:end] + "</section>"
    return html[:start] + wrapped + html[end:]


def _markdown_to_html_fallback(md_path: Path) -> str:
    """Degraded MD→HTML when pandoc is unavailable (python-markdown)."""
    import markdown
    body = markdown.markdown(md_path.read_text(encoding="utf-8"),
                             extensions=["tables", "fenced_code"])
    title = md_path.stem
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            f"<title>{title}</title></head><body>{body}</body></html>")


def _find_chrome() -> str | None:
    candidates = [
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        # Windows
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        candidates.append(str(Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe"))
    for path in candidates:
        if Path(path).exists():
            return path
    return _which("google-chrome") or _which("chromium") or _which("chrome") or _which("msedge")


def _chrome_headless_pdf(chrome: str, html_path: Path, pdf_path: Path) -> bool:
    try:
        # file:// URI must use forward slashes on Windows; Path.as_uri() is the
        # portable way (handles backslashes, spaces, and non-ASCII).
        uri = html_path.resolve().as_uri()
        result = subprocess.run([
            chrome, "--headless", "--disable-gpu", "--no-sandbox",
            f"--print-to-pdf={pdf_path.resolve()}",
            "--print-to-pdf-no-header",
            "--no-pdf-header-footer",
            uri,
        ], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if result.returncode != 0:
            print(f"  Chrome error: {result.stderr.strip()[:200]}", file=sys.stderr)
            return False
        return pdf_path.exists() and pdf_path.stat().st_size > 1024
    except Exception as exc:
        print(f"  Chrome failed: {exc}", file=sys.stderr)
        return False


def html_to_pdf_via_weasyprint(html: str, output_path: Path) -> bool:
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(str(output_path))
        return True
    except Exception as exc:
        print(f"  weasyprint failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input markdown file (e.g., 11_定稿.md).")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Output PDF path (default: input.html or input.pdf).")
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"File not found: {args.input}", file=sys.stderr)
        return 2

    pandoc = check_toolchain()
    # check_toolchain returns "" (fatal: neither pandoc nor python-markdown) or
    # the pandoc path / None (None = fallback mode with python-markdown).
    if pandoc == "":
        return 1

    base_dir = args.input.parent.resolve()
    figures_dir = base_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    text = args.input.read_text(encoding="utf-8")
    print(f"Processing: {args.input}")
    print(f"  Characters: {len(text):,}")

    # Step 1: Render Mermaid to SVG
    print("Step 1: Rendering Mermaid diagrams...")
    text = render_mermaid_blocks(text, figures_dir)

    # Step 2: Fix image paths to absolute so pandoc can embed them.
    # Use file:// URIs (via as_uri) — handles spaces and non-ASCII on Windows,
    # where bare paths in markdown image targets get truncated at whitespace.
    print("Step 2: Fixing image paths...")
    text = re.sub(
        r'!\[([^\]]*)\]\(figures/([^)]+)\)',
        lambda m: f'![{m.group(1)}]({(figures_dir / m.group(2)).resolve().as_uri()})',
        text
    )

    # Step 3: Write processed markdown with absolute paths
    processed = base_dir / f"_{args.input.stem}_processed.md"
    processed.write_text(text, encoding="utf-8")
    print(f"Step 3: Processed markdown → {processed.name}")

    try:
        return _run_pipeline(args, base_dir, figures_dir, text, processed, pandoc)
    finally:
        processed.unlink(missing_ok=True)


def _run_pipeline(args, base_dir: Path, figures_dir: Path, text: str,
                  processed: Path, pandoc) -> int:
    # Step 4: Convert to standalone HTML (pandoc primary, python-markdown fallback)
    print("Step 4: Converting to HTML...")
    if pandoc:
        html_result = subprocess.run(
            [pandoc, str(processed), "--to", "html5", "--standalone",
             *_pandoc_embed_flag(pandoc), "--metadata", "title=", "--wrap=none"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        if html_result.returncode != 0:
            print(f"  pandoc error: {html_result.stderr}", file=sys.stderr)
            return 1
        html = html_result.stdout
    else:
        html = _markdown_to_html_fallback(processed)

    # Inject thesis print CSS (shared by both conversion paths)
    html = html.replace("</head>", f"{PRINT_CSS}\n</head>")

    # Step 4b: post-process — linkify bare URLs, wrap 参考文献 for hanging indent
    html = _linkify_html(html)
    html = _wrap_refs_section(html)

    # Step 5: Convert HTML to PDF
    pdf_ok = False
    if args.output:
        # Honor user-supplied output name; append .pdf if the suffix is missing
        pdf_path = args.output if args.output.suffix == ".pdf" else args.output.with_suffix(".pdf")
    else:
        pdf_path = base_dir / f"{args.input.stem}.pdf"

    # Engine 1: weasyprint (Python-native)
    if _has_weasyprint():
        print("Step 5a: Trying weasyprint PDF engine...")
        pdf_ok = html_to_pdf_via_weasyprint(html, pdf_path)

    # Engine 2: Chrome headless --print-to-pdf
    if not pdf_ok:
        chrome = _find_chrome()
        if chrome:
            print("Step 5b: Trying Chrome headless PDF engine...")
            html_path = base_dir / f"{args.input.stem}.html"
            html_path.write_text(html, encoding="utf-8")
            pdf_ok = _chrome_headless_pdf(chrome, html_path, pdf_path)
            html_path.unlink(missing_ok=True)
        else:
            print("Step 5b: Chrome not found — skipping.")

    if pdf_ok:
        size_mb = pdf_path.stat().st_size / (1024 * 1024)
        print(f"\n✅ PDF generated: {pdf_path} ({size_mb:.1f} MB)")
    else:
        print("Step 5c: No PDF engine available. Saving self-contained HTML...")
        html_out = base_dir / f"{args.input.stem}.html"
        html_out.write_text(html, encoding="utf-8")
        print(f"Done: {html_out}")
        print()
        print("  ┌─────────────────────────────────────────────────────────┐")
        print("  │  PDF export hint:                                       │")
        print("  │  Open this HTML file in Safari/Chrome                   │")
        print("  │  Then: File → Print → PDF → Save as PDF                 │")
        print("  │  This produces a professional A4 academic PDF.          │")
        print("  └─────────────────────────────────────────────────────────┘")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
