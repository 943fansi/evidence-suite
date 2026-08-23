#!/usr/bin/env python3
r"""Framework depth gate for framework-type documents (框架深度门, Stage 5b).

Real-run lesson: a thesis's chapter 4 was judged "有名无实、不能定稿" because
it was a single mermaid diagram + two paragraphs — an outline, not developed
sections. The stage-5 gate only checked structure and markers, so a hollow
framework passed. This script enforces that each substantive chapter actually
DEVELOPS its framework elements as independent subsections.

For each `## 第X章 …` chapter (skipping 绪论/总结), it checks that the chapter
body contains the four-element skeleton — 目标 / 方法(手段/活动/措施) /
输入输出(输入/输出/流程) / 标准依据(标准/规范/依据/要求/准则) — either as
explicit `###` subsections or as keyword-bearing prose, AND that each chapter is
substantive (non-whitespace char count above a floor, e.g. 1200).

Checks:
  - per-chapter: which of the 4 skeleton elements are present (as ### heading
    or as keyword in prose);
  - per-chapter: body depth (non-whitespace chars);
  - report: chapters missing >=2 elements OR below the char floor are FAILED.

Exit codes: 0 all chapters pass; 1 any chapter fails; 2 usage error.

Usage:
  python scripts/check_framework_depth.py 11_定稿.md [--min-chars-per-chapter 1200]
  python scripts/check_framework_depth.py 11_定稿.md --json
  python scripts/check_framework_depth.py 11_定稿.md --profile general_tech
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from rule_profile import load_rules

# Chapter header: "## 第一章 绪论", "## 第4章 …", "## 4. 方法", "## 第二章 研究现状"
CH_RE = re.compile(r"^##\s*(?:第\s*[一二三四五六七八九十\d]+\s*章|[\d]+[.、])\s*(.*)$")

# Elements the framework must develop. Each maps to heading keywords (### level)
# and prose keywords. Chapter 1 (绪论) and the final chapter (总结/展望) are exempt.
SKELETON = {
    "目标": (["目标", "目的", "任务", "要求", "总体目标"], ["目标", "目的", "任务", "要求"]),
    "方法": (["方法", "手段", "活动", "措施", "方案", "技术路线"], ["方法", "手段", "活动", "措施", "方案", "技术", "模型", "算法"]),
    "输入输出": (["输入", "输出", "流程", "过程", "步骤", "实施"], ["输入", "输出", "流程", "过程", "步骤", "实施"]),
    "标准依据": (["标准依据", "依据", "标准", "规范", "准则", "要求"], ["标准", "规范", "依据", "准则", "要求", "导则", "规程"]),
}

# Exempt chapters: 绪论 / 引言 / 总结 / 展望 / 结论 / ABSTRACT / 摘要 / 目录
EXEMPT = re.compile(r"(绪论|引言|前言|总结|展望|结论|摘要|ABSTRACT|目录|致谢|参考文献|研究局限|攻读)")


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _elements_in_block(block: str, h3_pat: re.Pattern) -> dict[str, list[str]]:
    """Return {element: [how matched]} for the 4 skeleton elements in a chapter."""
    found: dict[str, list[str]] = {}
    h3_titles = [h3_pat.match(ln).group(1) for ln in block.split("\n") if h3_pat.match(ln)]
    for element, (head_kw, prose_kw) in SKELETON.items():
        reasons = []
        for kw in head_kw:
            if any(kw in t for t in h3_titles):
                reasons.append(f"###含「{kw}」")
                break
        if not reasons:
            for kw in prose_kw:
                if kw in block:
                    reasons.append(f"正文含「{kw}」")
                    break
        if reasons:
            found[element] = reasons
    return found


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path, help="draft .md")
    parser.add_argument("--min-chars-per-chapter", type=int, default=None,
                        help="non-whitespace char floor per substantive chapter "
                             "(default: rules.yaml framework_depth.min_chars_per_chapter = 1200)")
    parser.add_argument("--rules", type=Path, default=None, help="rules override file")
    parser.add_argument("--profile", type=str, default=None, help="scenario profile")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.draft.exists():
        print(f"ERROR: draft not found: {args.draft}", file=sys.stderr)
        return 2
    try:
        rules = load_rules(rules_path=args.rules, profile=args.profile)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: cannot load rules: {exc}", file=sys.stderr)
        return 2
    fd = rules.get("framework_depth") or {}
    min_chars = args.min_chars_per_chapter or int(fd.get("min_chars_per_chapter", 1200))
    text = args.draft.read_text(encoding="utf-8")

    lines = text.split("\n")
    h3_pat = re.compile(r"^###\s+([^#].*)$")

    # Split into chapters.
    chapters: list[tuple[str, list[str]]] = []
    current_title, current_lines = "", []
    for ln in lines:
        m = CH_RE.match(ln.strip())
        if m:
            if current_title:
                chapters.append((current_title, current_lines))
            current_title = m.group(1).strip()
            current_lines = [ln]
        elif current_title:
            current_lines.append(ln)
    if current_title:
        chapters.append((current_title, current_lines))

    results = []
    failed = 0
    for title, ch_lines in chapters:
        if EXEMPT.search(title):
            continue
        block = "\n".join(ch_lines)
        chars = len(re.sub(r"\s", "", block))
        elements = _elements_in_block(block, h3_pat)
        missing = [e for e in SKELETON if e not in elements]
        thin = chars < min_chars
        ok = not missing and not thin
        if not ok:
            failed += 1
        results.append({
            "chapter": title,
            "chars": chars,
            "thin": thin,
            "missing_elements": missing,
            "elements_found": {k: v for k, v in elements.items()},
            "pass": ok,
        })

    if args.json:
        print(json.dumps({"chapters": results, "failed": failed},
                         ensure_ascii=False, indent=2))
        return 1 if failed else 0
    else:
        for r in results:
            flag = "✅" if r["pass"] else "❌"
            print(f"{flag} {r['chapter']}  ({r['chars']:,} chars)")
            if r["missing_elements"]:
                print(f"     缺少骨架要素: {r['missing_elements']}")
            if r["thin"]:
                print(f"     篇幅过薄 <{min_chars} 非空白字符")
        if failed == 0:
            print(f"\n✅ PASS — all {len(results)} substantive chapters develop the "
                  f"目标/方法/输入输出/标准依据 skeleton.")
        else:
            print(f"\n❌ {failed}/{len(results)} chapter(s) FAILED — expand framework "
                  f"elements into subsections (目标–关键活动–输入输出–标准依据) before "
                  f"considering the draft final.")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())