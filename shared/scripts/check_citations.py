#!/usr/bin/env python3
"""Check citation closure in evidence-driven draft markdown.

Scans a draft .md file for:
  - [Sx] references in body vs reference list → orphaned / unused
  - [Gx] references in body vs appendix → orphaned gaps
  - C-level source overuse warnings
  - URL presence in reference entries
  - Title consistency: when --sources is provided, checks that each reference entry
    whose S-ID exists in the validated corpus has a title similar to the corpus title.
    Flags mismatches that suggest the LLM assigned its own S-ID numbering.
  - --academic mode: the draft already uses sequential [1..n] numbering (e.g. a
    finalized thesis), so citation closure is checked against bare numbers instead
    of [Sx] — every body [n] must resolve to a reference-list entry and every
    reference entry must be cited (bidirectional closure), with sequential check.

Usage:
  python3 check_citations.py <draft.md> [--threshold 5] [--json]
  python3 check_citations.py <draft.md> --sources 04_validated_sources.json
  python3 check_citations.py <draft.md> --min-sources 15   # enforce minimum reference count
  python3 check_citations.py <draft.md> --min-chars 25000  # enforce minimum body depth (chars)
  python3 check_citations.py <draft.md> --academic        # numeric [1..n] closure (finalized drafts)
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


SOURCE_RE = re.compile(r"\[S(\d+)\](?!\()")  # [S1] but not [S1](url)
NUM_RE = re.compile(r"(?<!\[)[\[（](\d{1,3})[\]）](?!\()")  # [12] / （12）, not [S12], not [12](url)
GAP_RE = re.compile(r"\[G(\d+)\]")
GAP_RE_BARE = re.compile(r"(?<![\[A-Za-z])G(\d+)(?![\]\d])")  # G1 without brackets (appendix tables)

REF_SECTION_RE = re.compile(r"^##\s*(?:\d+[.、]\s*)?(参考文献|References|Bibliography|文献)\s*$")
APP_SECTION_RE = re.compile(r"^##\s*(?:\d+[.、]\s*)?(附录A|附录 A|Appendix A|Appendix)(?=$|[\s:：])")
# 附录标题允许带编号与后缀，如 "## 附录A 证据缺口清单"、"## 附录 A：证据缺口清单"


def split_body_and_refs(text: str) -> tuple[str, str, str]:
    """Split markdown into body, reference section, and appendix section."""
    ref_start = None
    app_start = None
    lines = text.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if REF_SECTION_RE.match(stripped):
            ref_start = i
        if APP_SECTION_RE.match(stripped):
            app_start = i

    body_end = ref_start if ref_start else (app_start if app_start else len(lines))
    ref_end = app_start if app_start else len(lines)

    body = "\n".join(lines[:body_end])
    refs = "\n".join(lines[body_end:ref_end]) if ref_start else ""
    appendix = "\n".join(lines[ref_end:]) if app_start else ""
    return body, refs, appendix


def extract_set(text: str, pattern: re.Pattern) -> set[str]:
    return {f"{m}" for m in pattern.findall(text)}


def count_refs(text: str, pattern: re.Pattern) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in pattern.findall(text):
        counts[m] = counts.get(m, 0) + 1
    return counts


def check_urls_in_refs(refs_text: str, academic: bool = False) -> set[str]:
    """Return source IDs whose reference entries lack an http/https URL.

    Splits entries on the leading tag: `[Sx]` (default) or `[n]` (--academic).
    """
    url_re = re.compile(r"https?://")
    missing: set[str] = set()
    tag_re = re.compile(r"\[(S\d+|\d+)\]")
    split_re = re.compile(r"\n(?=\[(?:S\d+|\d+)\])")
    entries = split_re.split(refs_text)
    for entry in entries:
        m = re.search(tag_re, entry)
        if m and not url_re.search(entry):
            missing.add(m.group(1))
    return missing


def _strip_title(text: str) -> str:
    """Normalize a reference entry title for comparison."""
    text = re.sub(r'\s+', ' ', text).strip().lower()
    text = text.rstrip('.')
    return text


def check_title_consistency(refs_text: str, sources_path: Path) -> tuple[list[str], str]:
    """Return (mismatch warnings, summary line) for reference entries whose title
    mismatches the corpus title under the same S-ID."""
    if not sources_path or not sources_path.exists():
        return [], ""

    with open(sources_path, "r", encoding="utf-8") as fh:
        vs = json.load(fh)

    id_title = {}
    for s in vs.get("sources", []):
        sid = s.get("source_id", "")
        title = (s.get("title_or_name") or s.get("title") or "").strip()
        if sid and title:
            id_title[sid] = _strip_title(title)

    warnings: list[str] = []
    entries = re.split(r"\n\n(?=\[)", refs_text)
    total = 0
    mismatched = 0
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        m = re.match(r'\[(S\d+)\]', entry)
        if not m:
            continue
        sid = m.group(1)
        corp_title = id_title.get(sid, "")
        if not corp_title:
            continue
        total += 1
        ref_text = entry[m.end():].split("http")[0]
        # Two candidate extractions, score = best of both:
        #  (a) whole prefix (title + publisher) — fails short titles with long
        #      publisher strings; fine for titles containing ". " abbreviations.
        #  (b) first ". " segment — matches build_references' "title. publisher"
        #      boundary; fails titles like "Series No. SSG-48".
        ref_whole = _strip_title(ref_text)
        first_period = ref_text.find(". ")
        ref_first = _strip_title(ref_text[:first_period] if first_period != -1 else ref_text)
        score = max(
            difflib.SequenceMatcher(None, ref_whole, corp_title).ratio(),
            difflib.SequenceMatcher(None, ref_first, corp_title).ratio(),
        )
        if score < 0.6:
            mismatched += 1
            warnings.append(f"[{sid}] title mismatch ({score:.0%}): corpus '{corp_title[:60]}'")

    summary = ""
    if mismatched > 0:
        summary = (
            f"Title consistency: {mismatched}/{total} entries have titles that don't match "
            f"the validated corpus under the same S-ID. This suggests the LLM used its own "
            f"S-ID numbering — verify that body citations point to the correct reference "
            f"entries by title, not just by S-ID."
        )
    return warnings, summary


def main() -> int:
    _ensure_utf8_streams()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path, help="Draft markdown file")
    parser.add_argument("--threshold", type=int, default=5, help="Warn if C-level source appears more than this")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--c-level", type=str, default="", help="Comma-separated C-level source IDs")
    parser.add_argument("--sources", type=Path, default=None, help="Path to 04_validated_sources.json for title consistency check")
    parser.add_argument("--min-sources", type=int, default=None, help="Fail if total reference entries are below this count")
    parser.add_argument("--min-chars", type=int, default=None,
                        help="Fail if body character count (excluding references/appendix and "
                             "whitespace) is below this floor — enforces content depth per doc type")
    parser.add_argument("--academic", action="store_true",
                        help="Draft uses sequential [1..n] citation numbers (finalized thesis/journals): "
                             "check numeric citation closure instead of [Sx]; requires every body [n] to "
                             "resolve to a reference entry and every reference entry to be cited")
    args = parser.parse_args()

    if not args.draft.exists():
        print(f"File not found: {args.draft}", file=sys.stderr)
        return 2

    text = args.draft.read_text(encoding="utf-8")

    body, refs_text, appendix = split_body_and_refs(text)

    if args.academic:
        # Numeric citation closure: [n] in body must exist in the reference list,
        # every reference entry must be cited, and numbers must be sequential 1..N.
        body_nums = {int(m) for m in NUM_RE.findall(body)}
        ref_nums = {int(m.group(1)) for m in
                    (re.match(r"^\[(\d+)\]", ln) for ln in refs_text.split("\n")) if m}
        missing_ref = sorted(body_nums - ref_nums)          # body cites a non-existent entry
        missing_cite = sorted(ref_nums - body_nums)         # reference entry never cited
        broken_seq = sorted(set(range(1, max(ref_nums or [0]) + 1)) - ref_nums)  # gap in 1..N
        if args.json:
            result = {
                "file": str(args.draft),
                "mode": "academic",
                "body_num_refs": sorted(body_nums),
                "ref_num_entries": sorted(ref_nums),
                "orphaned_nums": missing_ref,
                "unused_nums": missing_cite,
                "sequential_gaps": broken_seq,
                "total_ref_entries": len(ref_nums),
                "min_sources": args.min_sources,
                "min_sources_violated": bool(
                    args.min_sources is not None and len(ref_nums) < args.min_sources),
                "body_chars": len(re.sub(r"\s", "", body)),
                "min_chars": args.min_chars,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if (missing_ref or missing_cite or broken_seq or
                         (args.min_sources is not None and len(ref_nums) < args.min_sources) or
                         (args.min_chars is not None and
                          len(re.sub(r"\s", "", body)) < args.min_chars)) else 0

        print(f"File: {args.draft}  (mode: academic — numeric [n] citations)")
        print(f"Body [n] citations: {len(body_nums)} | Reference entries: {len(ref_nums)}")
        if missing_ref:
            print(f"\n❌ ORPHANED (body cites non-existent entry): {missing_ref}")
        else:
            print("\n✅ No orphaned numeric citations")
        if missing_cite:
            print(f"\n⚠️  UNUSED (in reference list but never cited in body): {missing_cite}")
        else:
            print("✅ All reference entries cited")
        if broken_seq:
            print(f"\n❌ SEQUENTIAL GAP in 1..{max(ref_nums or [0])}: missing {broken_seq}")
        else:
            print("✅ Reference numbering sequential 1..N")

        body_chars_ac = len(re.sub(r"\s", "", body))
        if args.min_sources is not None:
            print(("❌ " if len(ref_nums) < args.min_sources else "✅ ")
                  + f"Reference count {len(ref_nums)} {'< minimum ' + str(args.min_sources) if len(ref_nums) < args.min_sources else 'meets minimum ' + str(args.min_sources)}")
        if args.min_chars is not None:
            print(("❌ " if body_chars_ac < args.min_chars else "✅ ")
                  + f"Body depth {body_chars_ac} chars {'< minimum ' + str(args.min_chars) if body_chars_ac < args.min_chars else 'meets minimum ' + str(args.min_chars)}")
        issues = (len(missing_ref) + len(missing_cite) + len(broken_seq)
                  + (1 if args.min_sources is not None and len(ref_nums) < args.min_sources else 0)
                  + (1 if args.min_chars is not None and body_chars_ac < args.min_chars else 0))
        if issues == 0:
            print("\n✅ PASS — All numeric citations closed.")
        else:
            print(f"\n❌ {issues} issue(s) found. Review and fix before finalizing.")
            return 1
        return 0

    body_s_refs = extract_set(body, SOURCE_RE)
    ref_s_refs = extract_set(refs_text, SOURCE_RE)
    body_g_refs = extract_set(body, GAP_RE)
    app_g_refs = extract_set(appendix, GAP_RE) | extract_set(appendix, GAP_RE_BARE)

    s_counts = count_refs(body, SOURCE_RE)
    g_counts = count_refs(body, GAP_RE)

    c_level: set[str] = set()
    b_level: set[str] = set()
    if args.c_level:
        c_level |= {s.strip() for s in args.c_level.split(",") if s.strip()}

    # When --sources is provided, derive source levels from the validated corpus
    # instead of relying on any hardcoded defaults.
    if args.sources and args.sources.exists():
        with open(args.sources, "r", encoding="utf-8") as fh:
            vs = json.load(fh)
        for s in vs.get("sources", []):
            sid = s.get("source_id", "")
            m = re.match(r"S(\d+)", sid)
            if not m:
                continue
            lvl = (s.get("source_level") or "").upper()
            if lvl == "C":
                c_level.add(m.group(1))
            elif lvl == "B":
                b_level.add(m.group(1))

    # --c-level arg accepts numbers only (e.g., --c-level "11,19")
    c_level.discard("")

    # C-level source usage
    c_usage = {s: s_counts[s] for s in c_level if s in s_counts}
    warnings = [
        f"{s}: {c} occurrences"
        for s, c in c_usage.items()
        if c > args.threshold
    ]

    orphaned_s = body_s_refs - ref_s_refs
    unused_s = ref_s_refs - body_s_refs
    orphaned_g = body_g_refs - app_g_refs
    unused_g = app_g_refs - body_g_refs

    missing_urls = check_urls_in_refs(refs_text)

    title_warnings, title_summary = check_title_consistency(refs_text, args.sources) if args.sources else ([], "")

    min_sources_warning = ""
    if args.min_sources is not None and len(ref_s_refs) < args.min_sources:
        min_sources_warning = (
            f"Reference count {len(ref_s_refs)} is below the required minimum of "
            f"{args.min_sources} — insufficient research depth."
        )

    # Body depth floor: non-whitespace chars of body only (refs/appendix excluded).
    body_chars = len(re.sub(r"\s", "", body))
    min_chars_warning = ""
    if args.min_chars is not None and body_chars < args.min_chars:
        min_chars_warning = (
            f"Body depth {body_chars} chars is below the required minimum of "
            f"{args.min_chars} — content too thin; revise with stage 5 expansion."
        )

    if args.json:
        result = {
            "file": str(args.draft),
            "body_s_refs": sorted(body_s_refs),
            "ref_s_refs": sorted(ref_s_refs),
            "orphaned_s": sorted(orphaned_s),
            "unused_s": sorted(unused_s),
            "body_g_refs": sorted(body_g_refs),
            "app_g_refs": sorted(app_g_refs),
            "orphaned_g": sorted(orphaned_g),
            "unused_g": sorted(unused_g),
            "c_level_overuse_warnings": warnings,
            "s_ref_counts": {k: v for k, v in sorted(s_counts.items(), key=lambda x: -x[1])},
            "missing_urls": sorted(missing_urls),
            "total_ref_entries": len(ref_s_refs),
            "min_sources": args.min_sources,
            "min_sources_violated": bool(min_sources_warning),
            "body_chars": body_chars,
            "min_chars": args.min_chars,
            "min_chars_violated": bool(min_chars_warning),
            "title_consistency_warnings": title_warnings,
            "title_consistency_summary": title_summary,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        # Both text and JSON modes must gate on the same issue set; a draft that
        # fails in text mode must never pass --json gate control.
        if (orphaned_s or unused_s or orphaned_g or unused_g
                or min_sources_warning or min_chars_warning or missing_urls
                or warnings or title_warnings):
            return 1
        return 0
    else:
        print(f"File: {args.draft}")
        print(f"Body [Sx] refs: {len(body_s_refs)} | Ref list [Sx]: {len(ref_s_refs)}")

        if orphaned_s:
            print(f"\n❌ ORPHANED (body but not in reference list): {sorted(orphaned_s)}")
        else:
            print("\n✅ No orphaned source references")

        if unused_s:
            print(f"⚠️  UNUSED (in reference list but not in body): {sorted(unused_s)}")
        else:
            print("✅ No unused source references")

        if orphaned_g:
            print(f"\n❌ ORPHANED GAPS (body but not in appendix): {sorted(orphaned_g)}")
        else:
            print("\n✅ No orphaned gap references")

        if unused_g:
            print(f"⚠️  UNUSED GAPS (appendix but not in body): {sorted(unused_g)}")

        if warnings:
            print(f"\n⚠️  C-LEVEL OVERUSE (threshold={args.threshold}):")
            for w in warnings:
                print(f"   {w}")
        else:
            print("\n✅ C-level sources within threshold")

        if missing_urls:
            print(f"\n❌ MISSING URLS ({len(missing_urls)}/{len(ref_s_refs)} entries): {sorted(missing_urls)}")
        else:
            print("\n✅ All reference entries include URLs")

        # Title consistency check (computed above; shared with JSON mode)
        if title_warnings:
            print(f"\n⚠️  TITLE CONSISTENCY WARNINGS:")
            print(f"   {title_summary}")
            for w in title_warnings:
                print(f"   {w}")

        # Minimum source count check
        if min_sources_warning:
            print(f"\n❌ MIN SOURCES: {min_sources_warning}")
        elif args.min_sources is not None:
            print(f"\n✅ Reference count {len(ref_s_refs)} meets minimum {args.min_sources}")

        # Body depth check
        if min_chars_warning:
            print(f"\n❌ MIN CHARS: {min_chars_warning}")
        elif args.min_chars is not None:
            print(f"\n✅ Body depth {body_chars} chars meets minimum {args.min_chars}")

        # Top 5 most-cited sources
        print("\nTop 5 most-cited sources:")
        for s, c in sorted(s_counts.items(), key=lambda x: -x[1])[:5]:
            level = "C" if s in c_level else ("B" if s in b_level else "A")
            print(f"   [S{s}]: {c}× (level {level})")

        # Summary — issue set identical to JSON gate (incl. unused_g, min_chars)
        issues = (len(orphaned_s) + len(unused_s) + len(orphaned_g) + len(unused_g)
                  + len(warnings) + len(missing_urls) + len(title_warnings)
                  + (1 if min_sources_warning else 0) + (1 if min_chars_warning else 0))
        if issues == 0:
            print("\n✅ PASS — All citations closed, no issues.")
        else:
            print(f"\n❌ {issues} issue(s) found. Review and fix before finalizing.")
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
