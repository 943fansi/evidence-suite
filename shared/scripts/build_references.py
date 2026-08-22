#!/usr/bin/env python3
r"""Generate the 参考文献 section mechanically from a validated-sources corpus.

Why: stage5 rule 14 states the reference list is a mechanical
"extract → format → concatenate" operation, not generative writing. Hand-copying
55+ entries by the LLM invites exactly the defects observed in real runs:
broken ", ." punctuation for sources whose year is null, merged entries, and
silently reworded titles. This script is the single source of truth for that
formatting.

Format rules (canonical, mirrors w5_draft.md rule 13/14):
  [S<id>] <title verbatim>. <publisher verbatim>, <year>. URL: <url verbatim>
  - year empty/null  → omit the ", <year>" segment entirely (never render ", .").
  - url empty        → append " (URL unavailable)".
  - title/publisher/url are copied verbatim from the corpus; nothing is reworded.
  - entries are separated by blank lines; each entry is one paragraph.

Usage:
  python scripts/build_references.py 04_validated_sources.json            # print section
  python scripts/build_references.py 04.json -o refs_section.md          # write to file
  python scripts/build_references.py 04.json --body 11_定稿.md -o 11_定稿.md
      # --body: replace (or append) the ## 参考文献 section inside the given
      # markdown draft in place, keeping everything before/after intact.
  python scripts/build_references.py 04.json --style gbt -o refs_gbt.md
      # --style gbt: GB/T 7714-2015 类型感知条目（期刊/标准/报告/网络），顺序编号
      # [1]..[n] + [Sx]↔[n] 映射表。识别语料可选字段 authors / series / type /
      # city；缺失字段输出可回溯骨架，不虚构。不支持 --body。

Exit codes: 0 ok; 1 corpus unreadable/no sources; 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REF_HEADER = "## 参考文献"
# Tolerant match: templates may number the section ("## 13. 参考文献") — the
# exact "## 参考文献" prefix match misses those and would append a second,
# duplicate section (real defect in split-skill run: M0). Mirrors
# finalize_draft.py / check_citations.py REF_HEADER_RE.
REF_HEADER_RE = re.compile(r"^##\s*(?:\d+[.、]\s*)?(参考文献|References|Bibliography)\b")


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _get_title(source: dict) -> str:
    """Corpus title, accepting both `title` and `title_or_name` keys.

    Real corpora have used both field names; reading only `title` caused
    45/45 title-consistency failures in one thesis run. Prefer `title`,
    fall back to `title_or_name`.
    """
    t = source.get("title")
    if not isinstance(t, str) or not t.strip():
        t = source.get("title_or_name")
    return str(t or "").strip()


def format_entry(source: dict) -> str:
    """Format one reference entry. All fields verbatim from the corpus."""
    sid = str(source.get("source_id", "")).strip()
    title = _get_title(source)
    publisher = str(source.get("publisher", "")).strip()
    year = source.get("year")
    url = str(source.get("url", "")).strip()

    # corpus ids already carry the S prefix ("S1"); accept bare numbers too
    tag = sid if re.fullmatch(r"S\d+", sid) else f"S{sid}"
    year_text = str(year).strip() if year is not None else ""
    entry = f"[{tag}] {title}."
    if publisher:
        entry += f" {publisher}"
        if year_text:
            entry += f", {year_text}"
        entry += "."
    elif year_text:
        entry += f" {year_text}."
    if url:
        entry += f" URL: {url}"
    else:
        entry += " (URL unavailable)"
    return entry


def build_section(corpus: dict) -> str:
    sources = corpus.get("sources", [])
    if not sources:
        raise ValueError("corpus has no sources[]")
    entries = [format_entry(s) for s in sources]
    return REF_HEADER + "\n\n" + "\n\n".join(entries) + "\n"


def replace_in_draft(draft_text: str, section: str) -> str:
    """Replace the existing 参考文献 section (up to the next `## ` header or EOF).

    Preserves everything before the header and any following sections (附录A…).
    If the draft's reference heading is numbered ("## 13. 参考文献"), keep that
    heading verbatim instead of substituting the bare REF_HEADER — avoids both a
    duplicate section (missing a numbered header) and a style regression.
    """
    lines = draft_text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if REF_HEADER_RE.match(line.strip()):
            start = i
            break
    if start is None:
        # No reference section yet — insert before the first 附录 header, else append.
        for i, line in enumerate(lines):
            if line.strip().startswith("## 附录"):
                return "".join(lines[:i]) + section + "\n" + "".join(lines[i:])
        return draft_text.rstrip("\n") + "\n\n" + section
    heading = lines[start]
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    body = section.split("\n", 1)[1].rstrip("\n")
    return "".join(lines[:start]) + heading.rstrip("\n") + "\n" + body + "\n" + "".join(lines[end:])


def format_entry_gbt(source: dict) -> str:
    """GB/T 7714-2015 类型感知条目（学位论文/期刊投稿排版用）。

    支持语料中的可选字段：authors / series(含 刊名,年,卷(期):页码) / type。
    类型推断：
      - journal_paper → [J]，authors + series 原样拼接（series 须含 刊名, 年, 卷(期): 页）
      - china_standard / international_standard → [S]，series(标准号) 前缀
      - 其余（报告/导则/网络）→ [R] 或 [EB/OL]，出版机构为责任者
    缺失字段不虚构：作者缺失时不加作者段，出版地缺失时不加"城市:"前缀。
    """
    title = _get_title(source)
    publisher = str(source.get("publisher", "")).strip()
    year = source.get("year")
    url = str(source.get("url", "")).strip()
    stype = str(source.get("type", "")).strip()
    series = str(source.get("series", "")).strip()
    authors = str(source.get("authors", "")).strip()

    year_text = str(year).strip() if year is not None else ""

    if stype in ("journal_paper",):
        tag = "[J]"
        core = f"{authors}. {title}{tag}. {series}." if authors else f"{title}{tag}. {series}."
        return core
    if stype in ("china_standard", "international_standard", "safety_standard"):
        tag = "[S]"
        code = series
        if code:
            return f"{code}. {title}{tag}."
        return f"{title}{tag}."
    if stype in ("epri_web", "industry_article"):
        tag = "[EB/OL]"
        city = str(source.get("city", "")).strip()
        base = f"{publisher}. {title}{tag}." if publisher else f"{title}{tag}."
        if year_text:
            base = base.replace(f"{tag}.", f"{tag}. {year_text}[引用日期见正文].")
        if url:
            base += f" {url}."
        return base
    # 报告 / 导则 / 其他 → [R]
    tag = "[R]"
    city = str(source.get("city", "")).strip()
    head = f"{publisher}. " if publisher else ""
    tail = f"{city}: {publisher}, {year_text}." if city and publisher and year_text else (
        f"{publisher}, {year_text}." if publisher and year_text else (
        f"{city}: {publisher}." if city and publisher else (
        f"{publisher}." if publisher else (f"{year_text}." if year_text else ""))))
    entry = f"{head}{title}{tag}. "
    if series:
        entry += f"{series}. "
    entry += tail
    if url:
        entry += f" {url}."
    return entry


def build_section_gbt(corpus: dict) -> str:
    """GB/T 7714 骨架（期刊投稿/学位论文排版用）：顺序编号 [1]..[n] + [Sx]↔[n] 映射表。

    使用 format_entry_gbt 输出类型感知条目（作者/卷期页/标准号取自语料可选字段；
    语料无这些字段时输出可回溯骨架，投稿前由作者按目标刊格式补全）。
    禁止 --body 原位回填（会破坏 [Sx] 版的引用闭合门禁）。
    """
    sources = corpus.get("sources", [])
    if not sources:
        raise ValueError("corpus has no sources[]")
    lines = [REF_HEADER, ""]
    mapping = ["### [Sx]↔[n] 对照表（投稿核查用，投稿版删除本节）", "",
               "| [Sx] | [n] |", "|-----|-----|"]
    for n, s in enumerate(sources, start=1):
        entry = format_entry_gbt(s)
        entry_n = f"[{n}] {entry}"
        lines.append(entry_n)
        lines.append("")
        sid = str(s.get("source_id", "")).strip()
        tag = sid if re.fullmatch(r"S\d+", sid) else f"S{sid}"
        mapping.append(f"| [{tag}] | [{n}] |")
    return "\n".join(lines) + "\n" + "\n".join(mapping) + "\n"


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="04_validated_sources.json")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="Write section here (default: stdout)")
    parser.add_argument("--body", type=Path, default=None,
                        help="Draft markdown whose 参考文献 section is replaced in place "
                             "(--output then means the draft itself)")
    parser.add_argument("--style", choices=["default", "gbt"], default="default",
                        help="default=[Sx] 可审计条目；gbt=期刊投稿 GB/T 7714 骨架"
                             "（顺序编号+[Sx]↔[n] 映射表，仅输出到 -o/stdout，不支持 --body）")
    args = parser.parse_args()

    try:
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read corpus {args.corpus}: {exc}", file=sys.stderr)
        return 1
    if not isinstance(corpus, dict) or not corpus.get("sources"):
        print("ERROR: corpus must be an object with a non-empty sources[]", file=sys.stderr)
        return 1

    if args.style == "gbt" and args.body:
        print("ERROR: --style gbt 用于投稿排版，不支持 --body 原位回填"
              "（会破坏 [Sx] 版引用闭合门禁）；请输出到 -o 文件后另存投稿版",
              file=sys.stderr)
        return 2

    try:
        section = build_section(corpus) if args.style == "default" else build_section_gbt(corpus)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    bad = [s["source_id"] for s in corpus["sources"] if not str(s.get("source_id", "")).strip()]
    if bad:
        print(f"ERROR: sources with empty source_id: {bad}", file=sys.stderr)
        return 1

    if args.body:
        body_path = args.body
        out_path = args.output if args.output and args.output != body_path else body_path
        if not body_path.exists():
            print(f"ERROR: draft not found: {body_path}", file=sys.stderr)
            return 2
        draft = body_path.read_text(encoding="utf-8")
        out_path.write_text(replace_in_draft(draft, section), encoding="utf-8")
        print(f"Replaced 参考文献 section in {out_path} ({len(corpus['sources'])} entries)")
        return 0

    if args.output:
        args.output.write_text(section, encoding="utf-8")
        print(f"Wrote {args.output} ({len(corpus['sources'])} entries)")
    else:
        sys.stdout.write(section)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
