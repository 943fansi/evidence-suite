#!/usr/bin/env python3
"""Source routing selector: pick authoritative sources from the writing source registry.

Reads `writingSourceList` from a registry JSON (default: the skill snapshot
`references/source_registry.json`, override with --registry <path> to a
user-maintained master list),
filters sources by `topic_domain` (see `references/domain_routing.md`), and emits
per-source search directives for Stage 1.

Usage:
    python scripts/select_sources.py --domain nuclear [--registry PATH] [--output FILE]
    python scripts/select_sources.py --list-domains
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except (AttributeError, io.UnsupportedOperation):
    pass

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = SKILL_DIR / "references" / "source_registry.json"

ROUTING = {
    "nuclear": [
        "international_regulator", "international_industry", "industry_technical",
        "nuclear_data", "china_regulator", "china_standard",
        "technical_report_library", "international_standard",
    ],
    "materials": [
        "materials_data", "materials_engineering_data", "materials_scientific_database",
        "international_standard", "china_standard", "nuclear_data",
        "technical_report_library", "cross_technical_report_library",
    ],
    "energy": [
        "energy_international", "energy_data", "government_agency", "national_lab",
        "china_regulator", "china_technical", "industry_technical",
    ],
    "education": [
        "education_statistics", "education_research", "china_regulator", "scholarly_index",
    ],
    "ai": [
        "ai_research", "ai_index", "ai_policy", "ai_standard",
        "ai_china_standard", "china_technical", "scholarly_index",
    ],
    "funding": [
        "china_funding_repository", "china_tech_report_system",
        "cross_technical_report_library", "scholarly_index",
    ],
    "engineering": [
        "international_standard", "china_standard", "technical_report_library",
        "cross_technical_report_library", "materials_engineering_data",
        "china_funding_repository",
    ],
    "general": [],  # fallback: all categories
}

STANDARD_KEYWORDS = ("standard", "标准")


def load_registry(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read registry {path}: {exc}", file=sys.stderr)
        raise SystemExit(2)
    root = data.get("writingSourceList") or data
    if not isinstance(root, dict) or "authoritativeSources" not in root:
        print(f"ERROR: registry {path} lacks 'writingSourceList.authoritativeSources'", file=sys.stderr)
        raise SystemExit(2)
    return root


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host


def make_directive(source: dict) -> str:
    dom = domain_of(source.get("url", ""))
    allow_full = bool(source.get("allowFullText", False))
    base = f"site:{dom}"
    if not allow_full:
        return (
            f"{base} —— 仅取题录/摘要与文档编号，禁止虚构全文；"
            f"{source.get('usageHint', '')}"
        )
    return f"{base} —— 可取全文/下载PDF；{source.get('usageHint', '')}"


def build_rules(root: dict) -> list[str]:
    rules = root.get("skillPromptRules") or {}
    out = []
    for key in sorted(rules):
        val = str(rules[key]).strip()
        if val:
            out.append(f"{key}: {val}")
    forbids = root.get("forbidSources") or []
    for item in forbids:
        out.append(f"forbid/{item.get('id', '')}: {item.get('description', '')}")
    return out


def select(registry: dict, domain: str) -> dict:
    if domain not in ROUTING:
        raise ValueError(
            f"unknown topic_domain: {domain!r}; supported: {', '.join(sorted(ROUTING))}"
        )
    categories = ROUTING[domain]
    sources = registry["authoritativeSources"]
    if categories:
        picked = [s for s in sources if s.get("category") in categories]
        skipped = [s for s in sources if s.get("category") not in categories]
    else:
        picked = list(sources)
        skipped = []
    picked = sorted(picked, key=lambda s: s.get("id", ""))

    selected = []
    for s in picked:
        is_standard = any(k in str(s.get("category", "")).lower() for k in STANDARD_KEYWORDS)
        selected.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "url": s.get("url"),
            "category": s.get("category"),
            "allowFullText": bool(s.get("allowFullText", False)),
            "usageHint": s.get("usageHint", ""),
            "search_directive": make_directive(s),
            "must_verify_standard_current": is_standard,
        })

    return {
        "domain": domain,
        "selected_category_count": len(set(s.get("category") for s in picked)),
        "selected_source_count": len(selected),
        "skipped_source_count": len(skipped),
        "selected_sources": selected,
        "forbidden_and_rules": build_rules(registry),
        "note": "将 selected_sources 的 search_directive 注入 Stage 1 检索 prompt；allowFullText=false 的来源仅可引编号与摘要。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Source routing selector for evidence-proposal Stage 1")
    parser.add_argument("--domain", help="topic_domain: nuclear/materials/energy/education/ai/funding/engineering/general")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="path to source registry JSON")
    parser.add_argument("--output", help="write JSON to file instead of stdout")
    parser.add_argument("--list-domains", action="store_true", help="print supported domains and exit")
    args = parser.parse_args()

    if args.list_domains:
        print("supported domains: " + ", ".join(sorted(ROUTING)))
        return 0

    if not args.domain:
        print("ERROR: --domain required (use --list-domains to see choices)", file=sys.stderr)
        return 2

    registry = load_registry(Path(args.registry))
    try:
        result = select(registry, args.domain)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    payload = {
        "topic_domain": result["domain"],
        "registry_source": str(Path(args.registry).resolve()),
        "generated_at": __import__("datetime").date.today().isoformat(),
        **result,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"WROTE {out.resolve()}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())