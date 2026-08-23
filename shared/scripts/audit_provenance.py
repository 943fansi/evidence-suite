#!/usr/bin/env python3
r"""Machine-auditability gate over the provenance bundle (机器可审计性门禁).

P2-⑩ companion: "PDF/DOCX 给人看，evidence JSON 给机器审计" only works if the
evidence JSON actually lets a machine reconcile each citation to a location.
This script checks that every claim's supporting evidence carries a `locator`
(page/section/paragraph/quote_hash) — and REQUIRES it for high-risk claims
(R3 / R4 / normative N), where "引用到某篇" without a location is not enough.

Input: report.claims.json (from export_provenance.py) or any claim-centric
manifest. Optionally --source-map to cross-reference [n] citations.

Output: per-claim auditability + summary ratio; exit 1 if any high-risk claim
has support evidence without a locator (cannot be machine-audited).

Usage:
  python scripts/audit_provenance.py --claims research_case/provenance/report.claims.json
  python scripts/audit_provenance.py --provenance-dir research_case/provenance --json
Exit codes: 0 all auditable (high-risk claims locator-backed); 1 any high-risk gap; 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HIGH_RISK = {"R3", "R4"}
HIGH_RISK_CLASSES = {"N"}
LOCATOR_KEYS = ("page", "section", "paragraph", "quote_hash")


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _evidence_has_locator(ev: dict) -> bool:
    loc = ev.get("locator")
    if not isinstance(loc, dict):
        return False
    return any(loc.get(k) for k in LOCATOR_KEYS)


def audit(claims: list[dict]) -> dict:
    results = []
    high_risk_total = high_risk_ok = 0
    for i, claim in enumerate(claims, 1):
        if not isinstance(claim, dict):
            continue
        cid = str(claim.get("claim_id", f"C-{i:03d}"))
        risk = str(claim.get("risk", "")).strip()
        claim_class = str(claim.get("claim_class", "")).strip()
        high_risk = risk in HIGH_RISK or claim_class in HIGH_RISK_CLASSES
        evidence = claim.get("evidence") or []
        support = [ev for ev in evidence
                   if isinstance(ev, dict) and ev.get("relation") != "contradicts"]
        missing: list[str] = []
        for ev in support:
            sid = str(ev.get("source_id", "?"))
            if not _evidence_has_locator(ev):
                missing.append(sid)
        ok = not missing
        if high_risk:
            high_risk_total += 1
            if ok:
                high_risk_ok += 1
        results.append({
            "claim_id": cid,
            "risk": risk,
            "claim_class": claim_class,
            "high_risk": high_risk,
            "support_evidence_count": len(support),
            "support_without_locator": missing,
            "auditable": ok,
        })
    auditable = sum(1 for r in results if r["auditable"])
    return {
        "claims_total": len(results),
        "claims_auditable": auditable,
        "auditability_ratio": round(auditable / len(results), 3) if results else 1.0,
        "high_risk_total": high_risk_total,
        "high_risk_auditable": high_risk_ok,
        "high_risk_missing_locator": high_risk_total - high_risk_ok,
        "results": results,
    }


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", type=Path, default=None,
                        help="report.claims.json / claim-centric manifest")
    parser.add_argument("--provenance-dir", type=Path, default=None,
                        help="provenance dir → auto-load report.claims.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    claims_path = args.claims
    if claims_path is None and args.provenance_dir:
        claims_path = Path(args.provenance_dir) / "report.claims.json"
    if claims_path is None or not claims_path.exists():
        print("error: --claims (or --provenance-dir with report.claims.json) not found",
              file=sys.stderr)
        return 2
    try:
        data = json.loads(claims_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"error: cannot read claims manifest: {exc}", file=sys.stderr)
        return 2

    report = audit(data.get("claims", []) if isinstance(data, dict) else data)
    high_risk_gaps = [r for r in report["results"]
                      if r["high_risk"] and not r["auditable"]]

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for r in report["results"]:
            mark = "✅" if r["auditable"] else "⚠️"
            hr = " [R3/R4/N]" if r["high_risk"] else ""
            print(f"{mark} {r['claim_id']}{hr} ({r['risk']}/{r['claim_class']}) "
                  f"support={r['support_evidence_count']} "
                  f"无locator={'；'.join(r['support_without_locator']) if r['support_without_locator'] else '无'}")
        print(f"\nMachine auditability: {report['claims_auditable']}/{report['claims_total']} "
              f"claims locator-backed (ratio {report['auditability_ratio']:.0%}); "
              f"高险 claim（R3/R4/N）缺失 locator: {report['high_risk_missing_locator']}")
    return 1 if high_risk_gaps else 0


if __name__ == "__main__":
    sys.exit(main())
