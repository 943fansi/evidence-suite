#!/usr/bin/env python3
"""Source routing selector: pick authoritative sources from the writing source registry.

Reads `writingSourceList` from a registry JSON (default: the skill snapshot
`references/source_registry.json`, override with --registry <path> to a
user-maintained master list),
filters sources by `topic_domain` (see `references/domain_routing.md`), and emits
per-source search directives for Stage 1.

The registry is a PRIORITY knowledge base, not a whitelist: each selected source
is annotated with `authority` / `priority` / `role` from
`config/source_ranking.yaml` and sorted by priority. With `--allow-discovery`,
discovered / user-supplied / emergent sources are permitted into the candidate
pool (tagged `source_origin`), so "not in the registry ≠ not good evidence".

Usage:
    python scripts/select_sources.py --domain nuclear [--registry PATH] [--output FILE]
    python scripts/select_sources.py --domain nuclear --allow-discovery
    python scripts/select_sources.py --list-domains
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from rule_profile import load_source_ranking, rank_source

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except (AttributeError, io.UnsupportedOperation):
    pass

SUITE_ROOT = Path(__file__).resolve().parents[2]  # evidence-suite/ 根目录
SHARED_DIR = SUITE_ROOT / "shared"  # 等价于 parents[1]
DEFAULT_REGISTRY = SHARED_DIR / "references" / "source_registry.json"

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


DISCOVERY_DIRECTIVES = [
    "候选池不限于 Registry：允许进入「外部发现 / 用户提供 / 涌现」来源，"
    "并按 authority 分级后与 Registry 来源一起参与候选——'没进 Registry ≠ 不是好证据'。",
    "发现型来源示例（核能/工程域）：厂商技术报告、国家实验室报告、EDF/CNSC/JAEA/UJV 等机构公开文件、"
    "国内公开科技报告、学术会议论文。",
    "凡非 Registry 命中的来源，须在语料标注 source_origin ∈ {discovered, user, emergent}，"
    "并在 r1 来源审计按 authority 重新定级（厂商/二手默认 D 级，官方报告 B 级）。",
]


def select(registry: dict, domain: str, allow_discovery: bool = False,
           ranking: dict | None = None) -> dict:
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
    ranking = ranking or {}

    selected = []
    for s in picked:
        is_standard = any(k in str(s.get("category", "")).lower() for k in STANDARD_KEYWORDS)
        rank = rank_source(s, ranking)
        selected.append({
            "id": s.get("id"),
            "name": s.get("name"),
            "url": s.get("url"),
            "category": s.get("category"),
            "authority": rank["authority"],
            "priority": rank["priority"],
            "role": rank["role"],
            "source_origin": "registry",
            "allowFullText": bool(s.get("allowFullText", False)),
            "usageHint": s.get("usageHint", ""),
            "search_directive": make_directive(s),
            "must_verify_standard_current": is_standard,
        })
    # Registry = 优先级清单：按 priority 降序，同优先级按 id
    selected.sort(key=lambda x: (-x["priority"], x["id"]))

    result = {
        "domain": domain,
        "selected_category_count": len(set(s.get("category") for s in picked)),
        "selected_source_count": len(selected),
        "skipped_source_count": len(skipped),
        "selected_sources": selected,
        "forbidden_and_rules": build_rules(registry),
        "allow_discovery": allow_discovery,
        "note": "将 selected_sources 的 search_directive 注入 Stage 1 检索 prompt；"
                "allowFullText=false 的来源仅可引编号与摘要。Registry 为优先级清单而非白名单。",
    }
    if allow_discovery:
        result["discovery_directives"] = DISCOVERY_DIRECTIVES
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Source routing selector for evidence-proposal Stage 1")
    parser.add_argument("--domain", help="topic_domain: nuclear/materials/energy/education/ai/funding/engineering/general")
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="path to source registry JSON")
    parser.add_argument("--allow-discovery", action="store_true",
                        help="把 Registry 当优先级清单而非白名单：允许外部发现/用户提供/涌现来源"
                             "进入候选池，并标注 source_origin（见 discovery_directives）")
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
    ranking = load_source_ranking()
    try:
        result = select(registry, args.domain,
                        allow_discovery=args.allow_discovery, ranking=ranking)
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