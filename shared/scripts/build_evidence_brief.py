#!/usr/bin/env python3
r"""Render a human-readable Evidence Brief (L1 mode) from the evidence map.

Turns 06_evidence_map.json + 04_validated_sources.json into a claim→evidence→
balance→confidence table with per-claim detail — the "Evidence Brief" the L0–L4
ladder asks for (5–20 claims): question → sources → claim/evidence table →
conclusion. The script produces the evidence table + sufficiency verdicts; the
conclusion section is filled by the agent / user (the script never invents one).

For each claim it reports:
  support / against / context sources (with authority, freshness, support_level,
  relation, locator), balance (+/−/=), evidence_status / verdict, confidence,
  and the claim-weighted evidence-sufficiency verdict (reused from
  check_evidence_sufficiency.py, review-mode aware).

Usage:
  python scripts/build_evidence_brief.py 06_evidence_map.json 04_validated_sources.json
  python scripts/build_evidence_brief.py em.json vs.json -o evidence_brief.md
  python scripts/build_evidence_brief.py em.json vs.json --review-mode conservative --json
Exit codes: 0 ok; 2 usage/input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_evidence_sufficiency import DEFAULT_TIER, check_claim
from rule_profile import load_rules

PRIMARY_AUTHORITIES = ("A1", "A2", "A3", "B1", "B2")
RELATION_OF = {
    "direct": "supports", "strong_inference": "supports", "weak_inference": "supports",
    "contradictory": "contradicts", "context_only": "context_only", "unsupported": "unsupported",
}


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _balance_mark(support: list, against: list, context: list) -> str:
    if against and (len(against) > len(support)):
        return "−"
    if support and not against:
        return "+"
    if support and against:
        return "±"
    if context and not support:
        return "="
    return "?"


def _source_label(source_by_id: dict, sid: str, lvl: str, rel: str, loc: dict | None) -> str:
    s = source_by_id.get(sid, {})
    bits = [f"S{sid}" if not sid.startswith("S") else sid,
            str(s.get("authority", "") or "?"),
            str(s.get("freshness", "") or "?")]
    if rel:
        bits.append(rel)
    if lvl:
        bits.append(lvl)
    label = f"{'/'.join(bits)}"
    if isinstance(loc, dict) and loc:
        locstr = " ".join(f"{k}={v}" for k, v in sorted(loc.items()))
        label += f" @{locstr}"
    return label


def build_brief(em: dict, vs: dict, rules: dict, review_mode: str | None = None) -> str:
    source_by_id = {str(s.get("source_id", "")).strip(): s for s in vs.get("sources", [])}
    sufficiency = rules.get("evidence_sufficiency") or {}
    mode = review_mode or rules.get("review_mode") or "balanced"
    mode_cfg = rules.get("review_modes", {}).get(mode) or {}
    multiplier = float(mode_cfg.get("evidence_multiplier", 1.0))
    live_for_all = bool(mode_cfg.get("live_for_all", False))

    rows: list[str] = []
    details: list[str] = []
    sufficient = 0
    total = 0
    for i, claim in enumerate(em.get("evidence_map", []), 1):
        if not isinstance(claim, dict):
            continue
        total += 1
        cid = f"C-{i:03d}"
        claim_class = str(claim.get("claim_class", "")).strip()
        risk = str(claim.get("risk", "R1")).strip()
        text = str(claim.get("claim_to_write", "")).strip()
        levels = claim.get("source_support_levels") or {}
        if not isinstance(levels, dict):
            levels = {}
        relations = claim.get("source_relations") or {}
        if not isinstance(relations, dict):
            relations = {}
        locators = claim.get("source_locators") or {}
        if not isinstance(locators, dict):
            locators = {}
        status = str(claim.get("evidence_status", "")).strip()
        verdict = str((claim.get("reconciliation") or {}).get("verdict", "")).strip() or status
        confidence = str(claim.get("confidence", "")).strip() or "medium"

        support, against, context = [], [], []
        for sid, lvl in levels.items():
            rel = str(relations.get(sid, "") or RELATION_OF.get(str(lvl), "supports"))
            loc = locators.get(sid) if isinstance(locators.get(sid), dict) else None
            label = _source_label(source_by_id, str(sid), str(lvl), rel, loc)
            if rel == "contradicts":
                against.append(label)
            elif rel == "context_only":
                context.append(label)
            else:
                support.append(label)
        balance = _balance_mark(support, against, context)

        tier = dict(DEFAULT_TIER)
        tier.update(sufficiency.get(risk, {}) if isinstance(sufficiency.get(risk), dict) else {})
        outcome = check_claim(claim, source_by_id, tier,
                              multiplier=multiplier, live_for_all=live_for_all)
        if outcome["pass"]:
            sufficient += 1

        rows.append(f"| {cid} | {claim_class} | {risk} | {text[:60]} | "
                    f"{len(support)} | {len(against)} | {status or '-'} | {balance} | "
                    f"{confidence} |")

        details.append(f"### {cid} [{risk}/{claim_class}] {text}")
        if support:
            details.append(f"- 支持：{'；'.join(support)}")
        if against:
            details.append(f"- 反证：{'；'.join(against)}")
        if context:
            details.append(f"- 背景：{'；'.join(context)}")
        details.append(f"- 状态/判决：{status or '-'} / {verdict} | 平衡：{balance} | 置信度：{confidence}")
        if outcome["pass"]:
            details.append(f"- 充分性：✅ 达标（{mode}，乘数 {multiplier:g}）")
        else:
            details.append(f"- 充分性：❌ 不足（{mode}，乘数 {multiplier:g}）：")
            for reason in outcome["reasons"]:
                details.append(f"    - {reason}")

    header = f"""# Evidence Brief

- 生成时间：{__import__('datetime').date.today().isoformat()}
- 审查模式：{mode}（evidence 乘数 {multiplier:g}）｜profile：{rules.get('active_profile') or 'default'}
- 声明：本表只呈现证据与充分性判定，**结论由 agent/用户填写**，脚本不代写。

## 汇总

| Claim | class | risk | 论断 | 支持 | 反证 | status | 平衡 | 置信度 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
"""
    brief = header + "\n".join(rows)
    brief += f"\n\n证据充分性：**{sufficient}/{total}** claim 达标。\n\n## 逐条详情\n\n" + "\n\n".join(details)
    brief += "\n\n## 结论（由 Agent 填写）\n\n> 基于上表证据态势，给出结论；证据不足处如实降级/留白，不得越过充分性判定下强结论。\n"
    return brief


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence_map", type=Path, help="06_evidence_map.json")
    parser.add_argument("validated_sources", type=Path, help="04_validated_sources.json")
    parser.add_argument("-o", "--output", type=Path, default=None, help="write brief to file")
    parser.add_argument("--rules", type=Path, default=None, help="rules override file")
    parser.add_argument("--profile", type=str, default=None, help="scenario profile")
    parser.add_argument("--review-mode", choices=["conservative", "balanced", "exploratory"],
                        default=None, help="override review mode")
    parser.add_argument("--json", action="store_true",
                        help="output machine-readable {brief, summary} instead of markdown")
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

    brief = build_brief(em, vs, rules, args.review_mode)
    if args.json:
        print(json.dumps({"brief": brief, "review_mode": args.review_mode or rules.get("review_mode")},
                         ensure_ascii=False, indent=2))
    elif args.output:
        args.output.write_text(brief, encoding="utf-8")
        print(f"brief → {args.output}")
    else:
        sys.stdout.write(brief)
    return 0


if __name__ == "__main__":
    sys.exit(main())
