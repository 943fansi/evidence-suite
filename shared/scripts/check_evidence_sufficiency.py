#!/usr/bin/env python3
r"""Claim-weighted evidence sufficiency gate（证据充分性，按 claim 逐条判定）.

P0-① of the V2 review: decouple "reference count" from evidence quality.
Document-level min_sources (rules.yaml doc_minimums) is only a writing-format
floor (institution/journal requirement). Whether a claim is actually supported
enough is judged HERE, per claim, against its risk tier's evidence_sufficiency:

  for each claim in 06_evidence_map.json:
    tier    = rules.evidence_sufficiency[claim.risk]
    sources = claim.source_support_levels keys
    primary = sources whose corpus authority ∈ {A1,A2,A3,B1,B2}
    checked = primary_count  ≥ tier.min_primary_sources
            and independent_count ≥ tier.min_independent_sources
            and (not tier.live or currentness_ok or verification live)
            and (not tier.contradiction_coverage or contradiction_covered)

`live` for N-class (normative) claims requires ≥1 primary source with
freshness=current; for non-N claims it requires the claim's verification_mode
to be recorded as live (or a live audit note), else flagged as "requires live".

Usage:
  python scripts/check_evidence_sufficiency.py 06_evidence_map.json 04_validated_sources.json
  python scripts/check_evidence_sufficiency.py em.json vs.json --profile medical
  python scripts/check_evidence_sufficiency.py em.json vs.json --review-mode conservative
  python scripts/check_evidence_sufficiency.py em.json vs.json --changed C-001,C-003
  python scripts/check_evidence_sufficiency.py em.json vs.json --json

Exit codes: 0 all claims sufficient; 1 any claim fails; 2 usage/input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rule_profile import load_rules

PRIMARY_AUTHORITIES = ("A1", "A2", "A3", "B1", "B2")
CLAIM_CLASSES = ("E", "M", "N", "L", "D", "C", "U", "J")
DEFAULT_TIER = {"min_primary_sources": 0, "min_independent_sources": 1,
                "live": False, "contradiction_coverage": False}
REVIEW_MODES = ("conservative", "balanced", "exploratory")


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _authority_of(source: dict) -> str:
    return str(source.get("authority", "")).strip()


def _freshness_of(source: dict) -> str:
    return str(source.get("freshness", "")).strip()


def _coverage_ok(claim: dict) -> bool:
    """Contradiction coverage: counter evidence recorded, or a documented
    negative search result ("本次检索未找到公开反证")."""
    ce = claim.get("counter_evidence") or {}
    if isinstance(ce, dict) and (ce.get("evidence_against") or ce.get("unknown")):
        return True
    for key in ("counter_evidence_search", "counter_search"):
        val = claim.get(key)
        if isinstance(val, list) and val:
            return True
        if isinstance(val, dict) and val:
            return True
        if isinstance(val, str) and val.strip() and "反证" in val:
            return True
    recon = claim.get("reconciliation") or {}
    if isinstance(recon, dict):
        if str(recon.get("contradiction_summary", "")).strip():
            return True
        rationale = str(recon.get("rationale", "")).strip()
        if rationale and ("反证" in rationale or "未找到" in rationale or "未发现" in rationale):
            return True
    return False


def check_claim(claim: dict, source_by_id: dict, tier: dict,
                multiplier: float = 1.0, live_for_all: bool = False) -> dict:
    """Return {pass, reasons[], stats} for one claim against its tier.

    multiplier: review_mode evidence multiplier applied to primary/independent
    thresholds (rounded up). live_for_all: force live/currentness for every claim.
    """
    import math
    risk = str(claim.get("risk", "R1")).strip()
    claim_class = str(claim.get("claim_class", "")).strip()
    levels = claim.get("source_support_levels") or {}
    if not isinstance(levels, dict):
        levels = {}
    source_ids = [str(s) for s in levels.keys() if str(s).startswith("S")]
    independent_count = len(set(source_ids))
    primary_ids = [sid for sid in source_ids
                   if _authority_of(source_by_id.get(sid, {})) in PRIMARY_AUTHORITIES]
    primary_count = len(set(primary_ids))
    current_primary = any(
        _freshness_of(source_by_id.get(sid, {})) == "current"
        for sid in primary_ids
    )
    min_primary = math.ceil(tier.get("min_primary_sources", 0) * multiplier)
    min_independent = math.ceil(tier.get("min_independent_sources", 1) * multiplier)
    live_required = bool(tier.get("live")) or live_for_all
    contradiction_required = bool(tier.get("contradiction_coverage"))
    covered = _coverage_ok(claim)

    reasons: list[str] = []
    if primary_count < min_primary:
        reasons.append(
            f"primary sources {primary_count} < required {min_primary} "
            f"(authority ∈ {', '.join(PRIMARY_AUTHORITIES)})")
    if independent_count < min_independent:
        reasons.append(f"independent sources {independent_count} < required {min_independent}")
    if live_required:
        if claim_class == "N":
            if not current_primary:
                reasons.append("normative claim requires a current (freshness=current) "
                               "primary source (live 现行性核验)")
        elif not str(claim.get("verification_mode", "")).strip().lower() == "live":
            reasons.append("R3/R4 非规范类 claim 要求 live 回源核验（verification_mode=live）")
    if contradiction_required and not covered:
        reasons.append("要求反证覆盖：须记录 counter_evidence 或 counter_evidence_search "
                       "的负结果（本次检索未找到公开反证）")

    stats = {
        "risk": risk,
        "claim_class": claim_class,
        "independent_sources": independent_count,
        "primary_sources": primary_count,
        "current_primary": current_primary,
        "contradiction_covered": covered,
    }
    return {"pass": not reasons, "reasons": reasons, "stats": stats}


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_map", type=Path, help="06_evidence_map.json")
    parser.add_argument("validated_sources", type=Path, help="04_validated_sources.json")
    parser.add_argument("--rules", type=Path, default=None, help="rules override file")
    parser.add_argument("--profile", type=str, default=None, help="scenario profile")
    parser.add_argument("--review-mode", choices=list(REVIEW_MODES), default=None,
                        help="override review mode (conservative/balanced/exploratory); "
                             "default from rules.yaml review_mode")
    parser.add_argument("--changed", type=str, default="",
                        help="incremental mode: comma-separated claim ids (C-001,C-003) to "
                             "re-check only; unchanged claims are skipped (assumed still valid). "
                             "Suitable for large-document iteration where only some claims changed.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if not args.evidence_map.exists() or not args.validated_sources.exists():
        print("error: evidence_map / validated_sources not found", file=sys.stderr)
        return 2
    try:
        em = json.loads(args.evidence_map.read_text(encoding="utf-8"))
        vs = json.loads(args.validated_sources.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"error: cannot read inputs: {exc}", file=sys.stderr)
        return 2
    try:
        rules = load_rules(rules_path=args.rules, profile=args.profile)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: cannot load rules: {exc}", file=sys.stderr)
        return 2

    mode = args.review_mode or rules.get("review_mode") or "balanced"
    mode_cfg = rules.get("review_modes", {}).get(mode) or {}
    multiplier = float(mode_cfg.get("evidence_multiplier", 1.0))
    live_for_all = bool(mode_cfg.get("live_for_all", False))

    changed = {c.strip() for c in args.changed.split(",") if c.strip()}
    if changed and not all(c.startswith("C-") for c in changed):
        print("error: --changed must be comma-separated claim ids like C-001,C-003",
              file=sys.stderr)
        return 2

    sufficiency = rules.get("evidence_sufficiency") or {}
    source_by_id = {str(s.get("source_id", "")).strip(): s for s in vs.get("sources", [])}

    results: list[dict] = []
    skipped = 0
    for i, claim in enumerate(em.get("evidence_map", []), 1):
        if not isinstance(claim, dict):
            continue
        claim_id = f"C-{i:03d}"
        if changed and claim_id not in changed:
            skipped += 1
            continue
        risk = str(claim.get("risk", "R1")).strip()
        tier = dict(DEFAULT_TIER)
        tier.update(sufficiency.get(risk, {}) if isinstance(sufficiency.get(risk), dict) else {})
        outcome = check_claim(claim, source_by_id, tier,
                              multiplier=multiplier, live_for_all=live_for_all)
        results.append({"claim_id": claim_id,
                        "claim_class": str(claim.get("claim_class", "")).strip(),
                        "risk": risk,
                        "claim_text": str(claim.get("claim_to_write", "")).strip()[:80],
                        "pass": outcome["pass"],
                        "reasons": outcome["reasons"],
                        "stats": outcome["stats"]})

    passed = sum(1 for r in results if r["pass"])
    failed = len(results) - passed
    if args.json:
        print(json.dumps({"profile": rules.get("active_profile"),
                          "review_mode": mode,
                          "evidence_multiplier": multiplier,
                          "incremental": {"changed": sorted(changed) or None, "skipped": skipped},
                          "results": results, "passed": passed, "failed": failed},
                         ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "✅" if r["pass"] else "❌"
            print(f"{mark} {r['claim_id']} [{r['risk']}/{r['claim_class']}] {r['claim_text']}")
            for reason in r["reasons"]:
                print(f"      - {reason}")
        suffix = f"（增量：仅重审 {len(changed)} 条，跳过 {skipped} 条未变 claim）" if changed else ""
        print(f"\nEvidence sufficiency: {passed}/{len(results)} claims sufficient "
              f"(mode={mode}, multiplier={multiplier:g}, "
              f"profile={rules.get('active_profile') or 'default'}){suffix}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
