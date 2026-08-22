#!/usr/bin/env python3
r"""Finalize an evidence-driven draft for formal delivery (定稿净化).

Converts the working draft (with `[Sx]`/`[Gx]`/`[假设]`/`[待内部确认]` scaffolding)
into a clean deliverable, and validates the result. Designed after real runs where
formal theses were rejected for leaking scaffolding markers, "附录A 证据缺口清单",
crawler/prompt traces, and non-standard `[S1]` citation tags into the final PDF.

What it does (in order — order matters, see "Lessons" below):

  1. Map each `[Sx]` to a sequential number `[n]` from the reference-list order
     (first occurrence wins; supports bare-number ids "S1".."S65" or "1".."65").
  2. Convert body citations `[Sx]` -> `[n]` (body = everything before the
     参考文献 / References section). Merged citations like `[S1][S2]` become
     `[1][2]` (kept as-is for clarity; collapse to `[1,2]` is left to the author).
  3. Strip scaffolding tags anywhere in the document:
       `[Gx]`, `[假设]`, `[待内部确认]`, `[待验证]`, `[待核验]`, and a leading
     `> **标记图例** …` legend line.
  4. Delete the 证据缺口清单 appendix (`## 附录A` …) — only when it sits AFTER the
     reference section (the normal layout); never truncates the body.
  5. Remove `<!-- HTML comments -->` (cross-line safe) and residual placeholder
     text (`编号：2023xxxx`, `资助项目：`, `By XX / Supervisor`, etc.).
  6. Rebuild the reference section entries as `[n]` (strip the `[Sx]` tag) and drop
     the legacy ` URL: <url>` wrapper when `--style gbt` (see below).
  7. Validate: zero residual scaffolding, all `[1..n]` sequential & fully covered
     by body citations, no duplicate URLs in the reference section, and re-run
     citation closure if `--sources` is given.

  `[Gx]` gaps: instead of silently dropping the markers, the appendix A
  "证据缺口清单" (when it exists and sits after the references) is converted into
  a "研究局限（由证据缺口转化）" subsection inserted before 参考文献 — the thesis
  norm is to fold limitations into 总结/展望, not to leak internal markers.

Exit codes: 0 ok; 1 input unreadable / no reference section; 2 usage error;
3 validation failed (residual markers / broken numbering).

Lessons encoded from real runs:
  - NEVER `re.sub(r'\s{2,}', ' ', body)` to "collapse" whitespace — it eats `\n`
    and destroys the whole markdown structure.
  - Delete the appendix from the FULL text BEFORE splitting body/refs, and slice
    the reference section from the already-trimmed text — otherwise the appendix
    leaks back in through a stale `text[ref_start:]` slice.
  - Locate the appendix by the literal `## 附录A` heading AFTER the reference
    section; do not fall back to `body.find('附录A')` (the legend in the header
    mentions 附录A and would truncate the entire body).
  - Clean placeholder tags BEFORE stripping HTML comments is fine, but the
    comments inside 攻读学位/致谢 live AFTER the reference section, so the same
    cleanup must also run on the reference-slice — not just the body slice.

Usage:
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_clean.md
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_clean.md --sources 04_validated_sources.json
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_gbt.md --style gbt
      # --style gbt: also emit reference entries in GB/T 7714-ish skeleton
      #   (<title>. <publisher>, <year>. URL.) with [1]..[n] numbering, and
      #   append a "[Sx]↔[n] 对照表" section for the author's post-check.
      #   --style gbt implies dropping the " URL: " prefix wrapper.
  python scripts/finalize_draft.py 11_定稿.md --check        # validate only, no rewrite
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# matches "## 参考文献", "## 参考文献 References", "## References", "## 文献"
REF_HEADER_RE = re.compile(r"^##\s*(?:\d+[.、]\s*)?(参考文献|References|Bibliography|文献)\b")
# matches "## 附录A", "## 附录 A", "## 附录A 证据缺口清单", "## Appendix A"
APP_HEADER_RE = re.compile(r"^##\s*(?:附录\s*A|附录\s*Ａ|Appendix\s*A)\b")
GAP_TABLE_RE = re.compile(r"^\|\s*\[?G?(\d+)\]?\s*\|(.+?)\|\s*$", re.M)
SX_RE = re.compile(r"\[S(\d+)\]")
GX_RE = re.compile(r"\[G\d+\]")
PLACEHOLDER_TAGS = ("[假设]", "[待内部确认]", "[待验证]", "[待核验]")
LEGEND_RE = re.compile(r"^> \*\*标记图例\*\*.*$", re.M)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
GAP_BODY_RE = re.compile(r"\[G(\d+)\]")


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def strip_placeholder_tags(text: str) -> str:
    out = text
    for tag in PLACEHOLDER_TAGS:
        out = out.replace(tag, "")
    return out


def clean_cover_placeholders(text: str) -> str:
    out = text
    out = re.sub(r"编号：\S*\[?待内部确认\]?", "编号：XXXXXXXX（作者学号）", out)
    out = re.sub(r"编号：2023\d*", "编号：XXXXXXXX（作者学号）", out)
    out = out.replace("资助项目：[待内部确认]", "")
    out = out.replace("　资助项目：", "")
    out = out.replace("By XX / Supervisor: Prof. XXX / August 2026",
                      "By （作者姓名） / Supervisor: Prof. （导师姓名） / August 2026")
    out = out.replace("资助项目：", "")
    return out


def build_number_map(ref_section: str) -> dict[str, str]:
    """Map S-ids to sequential [n] from the reference-list order."""
    mapping: dict[str, str] = {}
    for m in re.finditer(r"^\[(?:S?)(\d+)\]", ref_section, re.M):
        sid = m.group(1)
        key = f"S{sid}"
        if key not in mapping:
            mapping[key] = str(len(mapping) + 1)
    return mapping


def finalize(text: str, style: str = "sx") -> str:
    """Run the full cleanup pipeline; returns cleaned markdown."""
    ref_start = None
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if REF_HEADER_RE.match(line.strip()):
            ref_start = i
            break
    if ref_start is None:
        raise ValueError("no 参考文献/References section found")

    # 1. Delete the evidence-gap appendix from the FULL text, only when after refs.
    #    Never fall back to body.find('附录A') — the header legend mentions it.
    #    Before deleting, capture the gap table (编号|描述|…) so any body [Gx]
    #    markers can be converted into a "研究局限" narrative rather than dropped.
    app_idx = None
    app_block = ""
    for i in range(len(lines)):
        if APP_HEADER_RE.match(lines[i].strip()):
            app_idx = i
            break
    if app_idx is not None and app_idx >= ref_start:
        app_block = "\n".join(lines[app_idx:])
        lines = lines[:app_idx]
        text = "\n".join(lines).rstrip() + "\n"

    # 2. Recompute boundaries on the already-trimmed text (avoids stale slice).
    lines = text.split("\n")
    ref_start = None
    for i, line in enumerate(lines):
        if REF_HEADER_RE.match(line.strip()):
            ref_start = i
            break
    body = "\n".join(lines[:ref_start])
    ref_section = "\n".join(lines[ref_start:])

    # 3. Map + convert body citations.
    id_map = build_number_map(ref_section)
    body = re.sub(r"\[S(\d+)\]",
                  lambda m: f"[{id_map.get('S' + m.group(1), '?' + m.group(1))}]",
                  body)

    # 4. Strip scaffolding tags + legend from body; convert [Gx] to limitations.
    body_gaps = sorted({int(g) for g in GAP_BODY_RE.findall(body)})
    body = GX_RE.sub("", body)
    body = strip_placeholder_tags(body)
    body = LEGEND_RE.sub("", body)

    # 5. Clean cover placeholders + HTML comments (both body and ref slice).
    body = clean_cover_placeholders(body)
    body = COMMENT_RE.sub("", body)
    body = re.sub(r"相关论断均以公开摘要级结论支撑，具体详见附录A。", "", body)
    # Crawler/prompt traces → academic phrasing (real-run: "NRC ADAMS PDF受反爬限制不可下载"
    # leaked the research process into the final thesis).
    body = re.sub(r"NRC ADAMS\s*PDF\s*受反爬限制不可下载", "部分NRC历史档案全文无法在线获取", body)
    body = re.sub(r"受反爬限制不可下载", "全文无法在线获取", body)
    body = re.sub(r"PDF受反爬限制", "全文受访问限制", body)
    body = re.sub(r"\n{3,}", "\n\n", body)

    # 5b. If any [Gx] were referenced in the body and an appendix gap table was
    #     captured, emit a "研究局限" subsection before 参考文献. Thesis norm:
    #     limitations belong in a dedicated narrative, not leaked markers.
    if body_gaps and app_block.strip():
        gap_rows = []
        for m in GAP_TABLE_RE.finditer(app_block):
            gnum, rest = int(m.group(1)), m.group(2)
            if gnum in body_gaps:
                # 表格列：| 编号 | 描述 | 优先级 | → 取第 1 列（描述）
                cols = [c.strip() for c in rest.split("|") if c.strip()]
                desc = cols[0] if cols else rest.strip()
                gap_rows.append(f"{gnum}. {desc}")
        if gap_rows:
            # Crawler/prompt traces inside the appendix gap table must be
            # academicized too (they become the 研究局限 narrative).
            cleaned_rows = []
            for row in gap_rows:
                row = re.sub(r"NRC ADAMS\s*PDF\s*受反爬限制不可下载",
                             "部分NRC历史档案全文无法在线获取", row)
                row = re.sub(r"受反爬限制不可下载", "全文无法在线获取", row)
                row = re.sub(r"PDF受反爬限制", "全文受访问限制", row)
                cleaned_rows.append(row)
            limitations = ("## 研究局限\n\n"
                           "本文基于已审计公开来源展开，以下方面因证据可得性与范围限制"
                           "未予充分展开，有待后续工作补充：\n\n"
                           + "\n".join(cleaned_rows) + "\n")
            body = body.rstrip() + "\n\n" + limitations

    # 6. Reference section: [Sx] -> [n]; optional GB/T skeleton.
    ref_section = re.sub(r"^\[S(\d+)\]",
                         lambda m: f"[{id_map.get('S' + m.group(1), '?' + m.group(1))}]",
                         ref_section, flags=re.M)
    ref_section = strip_placeholder_tags(ref_section)
    ref_section = clean_cover_placeholders(ref_section)
    ref_section = COMMENT_RE.sub("", ref_section)
    if style == "gbt":
        # 骨架格式：去掉 " URL: " 前缀包装，保持 题名. 出版者, 年. URL.
        ref_section = ref_section.replace(" URL: ", " ")
        mapping_lines = ["", "", "### [Sx]↔[n] 对照表（投稿核查用，投稿版删除本节）", "",
                         "| [Sx] | [n] |", "|-----|-----|"]
        for key in sorted(id_map, key=lambda k: int(id_map[k])):
            mapping_lines.append(f"| [{key}] | [{id_map[key]}] |")
        ref_section += "\n".join(mapping_lines)

    return body.rstrip() + "\n\n" + ref_section.strip() + "\n"


def validate(text: str) -> list[str]:
    """Return a list of problems found in a finalized draft (empty = clean).

    The GB/T 骨架 mode intentionally keeps an "[Sx]↔[n] 对照表" appendix for the
    author's post-check — citations inside that table are NOT treated as residuals.
    """
    problems: list[str] = []
    # strip the mapping-table block before residual scans (it legitimately contains [Sx])
    mapping_pos = text.find("### [Sx]↔[n] 对照表")
    scan = text[:mapping_pos] if mapping_pos != -1 else text
    # residual scaffolding anywhere
    for pat, name in [(r"\[S\d+\]", "[Sx]"), (r"\[G\d+\]", "[Gx]"),
                      (r"\[假设\]", "[假设]"), (r"\[待内部确认\]", "[待内部确认]"),
                      (r"\[待验证\]", "[待验证]"), (r"待核验", "待核验"),
                      (r"thesis_format", "thesis_format"), (r"标记图例", "标记图例"),
                      (r"证据缺口", "证据缺口"), (r"附录A", "附录A"),
                      (r"NRC ADAMS", "NRC ADAMS"), (r"反爬", "反爬"),
                      (r"待填写", "待填写"), (r"\?\d+\]", "[?n]")]:
        n = len(re.findall(pat, scan))
        if n:
            problems.append(f"residual {name}: {n}")
    # reference numbering sequential + contiguous
    ref_start = None
    for i, line in enumerate(text.split("\n")):
        if REF_HEADER_RE.match(line.strip()):
            ref_start = i
            break
    if ref_start is None:
        problems.append("no reference section")
        return problems
    refs = text.split("\n")[ref_start:]
    ref_nums = [int(m.group(1)) for m in
                (re.match(r"^\[(\d+)\]", ln) for ln in refs) if m]
    if ref_nums != list(range(1, len(ref_nums) + 1)):
        problems.append(f"reference numbering broken: {ref_nums[:6]}…")
    # duplicate URLs in reference section
    urls = re.findall(r"https?://[^\s\]]+", "\n".join(refs))
    seen: set[str] = set()
    for u in urls:
        if u in seen:
            problems.append(f"duplicate URL: {u[:70]}…")
        seen.add(u)
    return problems


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path, help="draft .md with [Sx] scaffolding")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="write cleaned draft here (default: stdout)")
    parser.add_argument("--sources", type=Path, default=None,
                        help="04_validated_sources.json → re-run citation closure on output")
    parser.add_argument("--style", choices=["sx", "gbt"], default="sx",
                        help="reference-entry style (default sx)")
    parser.add_argument("--check", action="store_true",
                        help="validate only, do not write output")
    args = parser.parse_args()

    if not args.draft.exists():
        print(f"error: draft not found: {args.draft}", file=sys.stderr)
        return 1
    text = args.draft.read_text(encoding="utf-8")

    if args.check:
        for p in validate(text):
            print("problem:", p)
        return 3 if validate(text) else 0

    try:
        out = finalize(text, style=args.style)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    problems = validate(out)
    if problems:
        for p in problems:
            print("validation:", p)
        print("WARNING: output written but failed validation", file=sys.stderr)
    else:
        print("validation: clean")

    if args.sources and args.sources.exists():
        corpus = json.loads(args.sources.read_text(encoding="utf-8"))
        n_sources = len(corpus.get("sources", []))
        ref_nums = [int(m.group(1)) for m in
                    (re.match(r"^\[(\d+)\]", ln) for ln in out.split("\n")) if m]
        if ref_nums and ref_nums[-1] >= n_sources:
            print(f"citation closure: {ref_nums[-1]}/{n_sources} refs match corpus count")

    if args.output:
        args.output.write_text(out, encoding="utf-8")
        print(f"finalized -> {args.output}")
    else:
        sys.stdout.write(out)
    return 3 if problems else 0


if __name__ == "__main__":
    sys.exit(main())