#!/usr/bin/env python3
r"""Shared Mermaid diagram rendering for export_pdf.py (SVG) and export_docx.py (PNG).

Single source of truth for the mermaid pipeline both exporters use:

  1. Local-first: mermaid-cli (mmdc) renders to SVG or PNG on-machine — prefer it
     for sensitive (核/国防/工业) content (--mermaid-engine local forbids network).
  2. Remote fallback (auto/remote): mermaid.ink API —
       https://mermaid.ink/svg/...  → SVG   (export_pdf)
       https://mermaid.ink/img/...  → PNG   (export_docx)
     Over-long node labels are warned before requesting (mermaid.ink 400/414).
  3. On total failure, never drop a diagram silently — callers substitute a
     visible fenced-warning block instead.

Everything is stdlib-only; no third-party dependency beyond optional mermaid-cli.
"""

from __future__ import annotations

import base64
import re
import shutil
import subprocess
import sys
import urllib.request
import zlib
from pathlib import Path

MERMAID_INK_SVG = "https://mermaid.ink/svg/"
MERMAID_INK_IMG = "https://mermaid.ink/img/"

# Real-run lesson: over-long node labels (e.g. >12 CJK chars) blow past the
# mermaid.ink URL/HTTP limits and return HTTP 400/414, silently dropping the
# diagram. Guard the label length BEFORE requesting.
MAX_LABEL_LEN = 14  # CJK chars; ASCII-ish text may use ~30
_NODE_LABEL_PAT = re.compile(r"\[([^\]\n]*)\]")


def mermaid_label_warnings(code: str) -> list[str]:
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


def _encode_mermaid(text: str, endpoint: str) -> str:
    """Encode Mermaid text for mermaid.ink API (plain base64url, no compression)."""
    encoded = base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
    return endpoint + encoded


def _encode_mermaid_compressed(text: str, endpoint: str) -> str:
    """Encode using deflate+base64url (smaller URL when plain form exceeds limits)."""
    raw = zlib.compress(text.encode("utf-8"), level=9)
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return endpoint + encoded


def _render_mermaid_local(code: str, out_path: Path, fmt: str) -> bytes | None:
    """Render via local mermaid-cli (mmdc); return bytes or None if unavailable/failed."""
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return None
    src = out_path.with_suffix(".mmd")
    src.write_text(code, encoding="utf-8")
    background = "transparent" if fmt == "svg" else "white"
    try:
        res = subprocess.run(
            [mmdc, "-i", str(src), "-o", str(out_path), "-b", background],
            capture_output=True, timeout=120,
        )
        if res.returncode == 0 and out_path.exists():
            return out_path.read_bytes()
    except Exception:
        pass
    finally:
        src.unlink(missing_ok=True)
    return None


def render_mermaid(code: str, out_path: Path, engine: str = "auto",
                   fmt: str = "svg") -> bytes | None:
    """Render one Mermaid snippet to SVG or PNG.

    engine: "auto" (local mmdc first, mermaid.ink fallback), "local" (mmdc only,
    no network), "remote" (mermaid.ink only). fmt: "svg" (export_pdf) or "png"
    (export_docx). Returns the rendered bytes and writes out_path; None on failure.
    """
    local_ok = engine in ("auto", "local")
    remote_ok = engine in ("auto", "remote")
    endpoint = MERMAID_INK_SVG if fmt == "svg" else MERMAID_INK_IMG

    data: bytes | None = None
    err: Exception | None = None
    if local_ok:
        data = _render_mermaid_local(code, out_path, fmt)
        if data:
            print(f"  rendered locally (mmdc, {fmt})")
    if data is None and remote_ok:
        urls = [_encode_mermaid(code, endpoint), _encode_mermaid_compressed(code, endpoint)]
        for url in urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read()
                if len(data) > 0:
                    print(f"  rendered via mermaid.ink ({fmt}, 远程，图内容已发送第三方；"
                          f"敏感内容请装 mermaid-cli 用 --mermaid-engine local)")
                    break
            except Exception as exc:
                err = exc
                data = None
    if data is None:
        print(f"  render FAILED ({err if err else 'renderer unavailable'})", file=sys.stderr)
        return None
    out_path.write_bytes(data)
    return data


def _patch_svg_cjk_fonts(img_path: Path) -> None:
    """Inject CJK font fallbacks into an SVG (macOS/Linux browsers lack CJK glyphs)."""
    try:
        svg_text = img_path.read_text(encoding="utf-8")
        cjk_font = "STHeiti, 'Noto Sans CJK SC', 'PingFang SC', 'Microsoft YaHei',"
        svg_text = svg_text.replace(
            'font-family:"trebuchet ms",verdana,arial,sans-serif',
            f'font-family:{cjk_font}"trebuchet ms",verdana,arial,sans-serif'
        )
        img_path.write_text(svg_text, encoding="utf-8")
    except Exception:
        pass


def render_mermaid_blocks(text: str, out_dir: Path, engine: str = "auto",
                          fmt: str = "svg") -> str:
    """Replace ```mermaid blocks with image references; return the modified text.

    Replaces each block with `![技术路线图](figures/mermaid_diagram_{i+1}.{ext})`.
    On failure the block is replaced with a VISIBLE fenced-warning block instead
    of being silently dropped. fmt "svg" (export_pdf) or "png" (export_docx).
    """
    pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
    blocks = list(pattern.finditer(text))
    if not blocks:
        print("  No Mermaid blocks found — skipping rendering.")
        return text

    out_dir.mkdir(parents=True, exist_ok=True)
    ext = "svg" if fmt == "svg" else "png"
    for i, match in enumerate(blocks):
        mermaid_code = match.group(1).strip()
        for w in mermaid_label_warnings(mermaid_code):
            print(f"  ⚠️  Mermaid block {i + 1}: {w} — shorten labels (≤~12 CJK chars) "
                  f"or use short IDs + a caption, else mermaid.ink returns HTTP 400.",
                  file=sys.stderr)
        img_path = out_dir / f"mermaid_diagram_{i + 1}.{ext}"
        data = render_mermaid(mermaid_code, img_path, engine=engine, fmt=fmt)
        if data is None:
            original = match.group(0)
            replacement = (f"```\n⚠️ 图 {i + 1} 渲染失败。"
                           f"请精简节点标签、或安装 mermaid-cli（本地渲染）后重跑导出。\n"
                           f"原始代码：\n{mermaid_code}\n```")
            text = text.replace(original, replacement, 1)
            continue
        if fmt == "svg":
            _patch_svg_cjk_fonts(img_path)
        print(f"  Mermaid block {i + 1}: rendered → {img_path.name} ({len(data):,} bytes)")
        replacement = f"![技术路线图](figures/mermaid_diagram_{i + 1}.{ext})"
        text = text.replace(match.group(0), replacement, 1)
    return text
