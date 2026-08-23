#!/usr/bin/env python3
r"""Export the machine-auditable provenance bundle alongside the final artifact.

P2-⑩ of the V2 review: PDF/DOCX are for humans; the evidence JSONs are for
machine audit. After finalizing a deliverable, run this to emit:

  provenance/report.claims.json      claim-centric manifest (relation/locator/confidence)
  provenance/report.evidence.json    source-centric manifest ([n]→source_id/url/claims)
  provenance/report.source-map.json  [n] → source_ids + locations (audit trail)
  provenance/report.review.json      review decisions (per-stage verdicts + review_kind)

The source-map + review JSONs let a downstream auditor reconcile "citation 17
in the PDF" → claim → sources → locators, without trusting the prose.

Usage:
  python scripts/export_provenance.py \
      --draft 11_定稿.md --sources 04_validated_sources.json --evidence-map 06_evidence_map.json \
      --review-dir ./proposal_workspace --review-kind ai-internal --verification-mode static \
      -o provenance/
Exit codes: 0 ok; 1 validation failed; 2 usage/input error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from finalize_draft import build_claim_manifest, build_source_manifest, validate_manifest
from validate_manifest import SCHEMA_VERSION

VERDICT_RE = re.compile(r"\*\*判决\*\*\s*[:：]\s*(.+)")
STAGE_OF = {
    "03_audit_report": "r1 来源审计",
    "07_honest_assessment": "r2 诚实性自评",
    "10_review": "r4 初稿审查",
    "12_外部专家意见": "r5 外部专家评审",
    "final_gate": "终审门",
}


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _stage_of(stem: str) -> str:
    for key, label in STAGE_OF.items():
        if stem.startswith(key):
            return label
    return stem


def collect_review_verdicts(review_dir: Path) -> list[dict]:
    """Parse `**判决**: …` lines from reviewer judgment markdown files."""
    if not review_dir or not review_dir.is_dir():
        return []
    entries: list[dict] = []
    for path in sorted(review_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        m = VERDICT_RE.search(text)
        if m:
            entries.append({"file": path.name, "stage": _stage_of(path.stem),
                            "verdict": m.group(1).strip()})
    return entries


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, required=True, help="cleaned deliverable markdown")
    parser.add_argument("--sources", type=Path, required=True, help="04_validated_sources.json")
    parser.add_argument("--evidence-map", type=Path, required=True, help="06_evidence_map.json")
    parser.add_argument("--review-dir", type=Path, default=None,
                        help="workspace dir containing reviewer judgment .md files "
                             "(verdicts parsed from `**判决**:` lines)")
    parser.add_argument("--review-kind", choices=["ai-internal", "ai-cross-model", "human-expert"],
                        default="ai-internal")
    parser.add_argument("--verification-mode", choices=["static", "live"], default="static")
    parser.add_argument("-o", "--output", type=Path, default=Path("provenance"),
                        help="output directory for the provenance bundle")
    args = parser.parse_args()

    for path, label in ((args.draft, "draft"), (args.sources, "sources"),
                        (args.evidence_map, "evidence-map")):
        if not path.exists():
            print(f"error: {label} not found: {path}", file=sys.stderr)
            return 2
    args.output.mkdir(parents=True, exist_ok=True)

    text = args.draft.read_text(encoding="utf-8")

    evidence = build_source_manifest(text, args.sources, args.evidence_map,
                                     args.review_kind, args.verification_mode)

    claims = build_claim_manifest(args.evidence_map, _meta_from_sources(args.sources))
    claims["schema_version"] = SCHEMA_VERSION
    claims["review_kind"] = args.review_kind
    claims["verification_mode"] = args.verification_mode
    claims["finalized_at"] = date.today().isoformat()

    source_map = {
        "schema_version": SCHEMA_VERSION,
        "finalized_at": date.today().isoformat(),
        "note": "正文 [n] 引文 → source_id 的审计对账表（由 evidence_manifest.mapping 聚合）",
        "mapping": evidence["mapping"],
    }

    review = {
        "schema_version": SCHEMA_VERSION,
        "review_kind": args.review_kind,
        "verification_mode": args.verification_mode,
        "finalized_at": date.today().isoformat(),
        "note": "同模型自审（ai-internal）≠ 独立评审；R4/投稿/安全关键须 human-expert",
        "stages": collect_review_verdicts(args.review_dir),
    }

    problems = validate_manifest(claims)
    problems += validate_manifest(evidence)
    if problems:
        for p in problems:
            print("provenance validation:", p)
        print("error: provenance bundle failed schema validation; not written", file=sys.stderr)
        return 1

    files = {
        "report.claims.json": claims,
        "report.evidence.json": evidence,
        "report.source-map.json": source_map,
        "report.review.json": review,
    }
    for name, data in files.items():
        target = args.output / name
        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name} -> {target}")
    print(f"\nprovenance bundle -> {args.output}/ "
          f"(PDF/DOCX 给人看，evidence JSON 给机器审计)")
    return 0


def _meta_from_sources(sources_path: Path) -> dict:
    """Minimal {source_id: {authority, freshness, url, title}} used by build_claim_manifest."""
    from finalize_draft import source_metadata
    return source_metadata(sources_path)


if __name__ == "__main__":
    sys.exit(main())
