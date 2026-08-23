#!/usr/bin/env python3
r"""Scaffold a research_case workspace (P2-⑨ / review §十八).

A research case = one question's full archive: question → claims → evidence →
conflicts → decisions → revisions → final artifact. This script creates the
skeleton (files + .gitignore) so both skills write into a consistent layout
instead of inventing files ad hoc.

Creates under the target dir (default ./research_case/):
  README.md                 case conventions + file contract
  .gitignore                ignore runtime artifacts (PDFs, figures, provenance…)
  00_topic.md               Topic Card template (question / domain / skeleton / gaps)
  02_raw_sources.json       empty retrieval scaffold (w2)
  04_validated_sources.json empty corpus scaffold (w3)
  06_evidence_map.json      empty evidence map scaffold (w4)

Usage:
  python scripts/init_case.py                        # → ./research_case/
  python scripts/init_case.py -o cases/my_topic      # → cases/my_topic/
  python scripts/init_case.py --force                # overwrite existing files
Exit codes: 0 ok; 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_FILES = {
    "README.md": """# Research Case

> 一个研究问题（question）的完整档案：**question → claims → evidence → conflicts
> → decisions → revisions → final artifact**。写作方（evidence-writer）与审查方
> （evidence-reviewer）共用本目录与文件契约。

## 文件契约

| 文件 | 阶段 | 归属 |
| --- | --- | --- |
| `00_topic.md` | w1 | 写作者（Topic Card） |
| `02_raw_sources.json` | w2 | 写作者（检索候选，含 source_origin） |
| `03_audit_report.md` | r1 | 审查方 |
| `04_validated_sources.json` | w3 | 写作者（语料） |
| `reference_files/*.pdf` | 3a | 下载的原文 |
| `pdf_text/*.txt` | 3c | PDF 抽取文本 |
| `06_evidence_map.json` | w4 | 写作者（claims + evidence + conflicts） |
| `07_honest_assessment.md` | r2 | 审查方 |
| `08_初稿.md` | w5 | 写作者 |
| `10_review.md` | r4 | 审查方 |
| `11_定稿.md` | w6 | 写作者 |
| `12_外部专家意见.md` | r5 | 审查方 |
| `14_专家修订稿.md` | w8 | 写作者 |
| `11_定稿_clean.md` | 净化 | 交付版 |
| `provenance/report.*.json` | 终审后 | 机器审计五件套 |
| `{name}.pdf/.docx` | w9 | 交付物 |

## 流程

`finalize_draft.py --manifest` 产出 manifest → `check_evidence_sufficiency.py`
claim 级充分性 → `build_evidence_brief.py` 证据简报 → `export_provenance.py`
机器审计五件套 → 审查方判决 → 交付。
""",
    ".gitignore": """# research case 运行时产物（勿提交）
*.pdf
reference_files/
pdf_text/
figures/
qa/
provenance/
""",
    "00_topic.md": """# 00_topic.md · Topic Card

> w1 硬门禁产物：动手起草前锁定问题、类型、骨架与预期证据缺口。

- **核心问题（1–2 个）**：
- **文档类型与硬约束**：（开题/本/硕/博/调研/可行性/白皮书/GF/实施方案/期刊/专利；字数/格式/评审标准）
- **topic_domain**：（nuclear / materials / energy / education / ai / funding / engineering / general）
- **已知来源基调**：（领域、奠基文献、方法谱系、主要争议）
- **论证骨架（Mermaid）**：（3 关键问题 P1–P3 + 3 关键技术 T1–T3 + 3 结构层次）
- **证据缺口预期**：（哪些论点大概率缺来源 → 预埋 `[Gx]`）
- **语义最小集**：（最少哪几个来源，核心论点才站得住）
""",
}


def _empty_json_sources() -> str:
    return json.dumps({"sources": []}, ensure_ascii=False, indent=2)


def _empty_json_evidence_map() -> str:
    return json.dumps({"evidence_map": []}, ensure_ascii=False, indent=2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=Path("research_case"),
                        help="target directory for the research case (default ./research_case)")
    parser.add_argument("--force", action="store_true",
                        help="overwrite existing files instead of skipping them")
    args = parser.parse_args()

    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    created, skipped = [], []
    for name, content in {
        **DEFAULT_FILES,
        "02_raw_sources.json": _empty_json_sources(),
        "04_validated_sources.json": _empty_json_sources(),
        "06_evidence_map.json": _empty_json_evidence_map(),
    }.items():
        target = out / name
        if target.exists() and not args.force:
            skipped.append(name)
            continue
        target.write_text(content, encoding="utf-8")
        created.append(name)

    for name in created:
        print(f"  created {out / name}")
    for name in skipped:
        print(f"  skipped (exists, use --force) {out / name}")
    print(f"\nresearch case -> {out}  "
          f"({len(created)} created, {len(skipped)} skipped)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
