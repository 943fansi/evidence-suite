#!/usr/bin/env python3
r"""Validate a validated-sources corpus BEFORE drafting (语料自检).

Runs after stage 3, before stage 5 drafting. Real-run lesson: corpus entries
were batch-generated and multiple different standards pointed at the same
wrong domain (bjjcyjy.com / antpedia / stm-publishing), which reviewers called
out on first glance as "references systematically wrong". Catching URL
duplication and unreliable domains here costs seconds; catching them in the
final thesis costs a full round of rework.

Checks:
  1. source_id uniqueness (no duplicate S-ids).
  2. Required fields present & non-empty: source_id / title (or title_or_name).
  3. URL duplication across entries (different standards sharing one URL is
     the #1 red flag). Also flags missing URLs (weak evidence).
  4. Unreliable/suspect domains: a hardcoded blocklist (bjjcyjy.com, antpedia,
     stm-publishing*, baike sites, qq/zhihu/wikipedia, AI-marketing blogs) plus
     an opt-in --extra-domains list.
  5. access_status empty (stage 3b gate coverage).
  6. Optional: per-registry_id quota report, e.g. to enforce a "中文期刊 ≥10"
     quota (see --quota-cn-journal).

Exit codes: 0 ok (all checks pass); 1 problems found; 2 usage error.

Usage:
  python scripts/validate_sources.py 04_validated_sources.json
  python scripts/validate_sources.py 04.json --json            # machine-readable
  python scripts/validate_sources.py 04.json --extra-domains bjjyjy.com,example.cn
  python scripts/validate_sources.py 04.json --quota-cn-journal 10 --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Domains that have burned real runs with systematically-wrong standards links.
# baike/zhihu/q.wenku are not authoritative for citation; AI-marketing blogs are
# forbidSources-adjacent. Expand via --extra-domains for topic-specific hits.
SUSPECT_DOMAIN_SUBSTR = (
    "bjjcyjy", "antpedia", "stm-publishing", "baike.baidu", "baike.com",
    "zhihu.com", "q.wenku", "wenku.baidu", "docin.com", "doc88.com",
    "wikipedia", "futunn", "openai.com/blog", "anthropic.com/research",
    "samaltman", "36kr", "jiqizhixin", "sohu.com", "163.com", "toutiao",
)


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _get_title(s: dict) -> str:
    t = s.get("title")
    if not isinstance(t, str) or not t.strip():
        t = s.get("title_or_name")
    return str(t or "").strip()


def _problems(corpus: dict, extra_domains: list[str], quota_cn_journal: int) -> list[str]:
    sources = corpus.get("sources", [])
    problems: list[str] = []
    suspect_domains = tuple(SUSPECT_DOMAIN_SUBSTR) + tuple(extra_domains)

    seen_ids: set[str] = set()
    url_owner: dict[str, list[str]] = {}
    cn_journals = 0

    for s in sources:
        sid = str(s.get("source_id", "")).strip()
        if not sid:
            problems.append("entry with empty source_id")
            continue
        if sid in seen_ids:
            problems.append(f"duplicate source_id: {sid}")
        seen_ids.add(sid)

        if not _get_title(s):
            problems.append(f"[{sid}] missing title/title_or_name")

        url = str(s.get("url", "")).strip()
        if url:
            url_owner.setdefault(url, []).append(sid)
            for dom in suspect_domains:
                if dom in url:
                    problems.append(f"[{sid}] suspect domain '{dom}' in URL: {url[:90]}…")
                    break
        else:
            problems.append(f"[{sid}] missing URL (weak evidence — reviewer red flag)")

        acc = str(s.get("access_status", "")).strip()
        if not acc:
            problems.append(f"[{sid}] access_status empty (run stage 3a --update-sources)")

        if str(s.get("type", "")).strip() == "journal_paper":
            cn_journals += 1

    for url, sids in url_owner.items():
        if len(sids) > 1:
            problems.append(f"duplicate URL shared by {len(sids)} entries "
                            f"{sorted(sids)}: {url[:90]}…")

    if quota_cn_journal > 0 and cn_journals < quota_cn_journal:
        problems.append(f"中文期刊（type=journal_paper）仅 {cn_journals} 条，"
                        f"低于配额 {quota_cn_journal}——学位论文需 ≥10 条国内期刊支撑「国内学术对话」")

    return problems


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="04_validated_sources.json")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--extra-domains", type=str, default="",
                        help="comma-separated additional suspect-domain substrings")
    parser.add_argument("--quota-cn-journal", type=int, default=0,
                        help="enforce a minimum count of type=journal_paper entries "
                             "(thesis: recommend ≥10 for 国内学术对话)")
    args = parser.parse_args()

    if not args.corpus.exists():
        print(f"ERROR: corpus not found: {args.corpus}", file=sys.stderr)
        return 2
    try:
        corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: cannot read corpus {args.corpus}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(corpus, dict) or not corpus.get("sources"):
        print("ERROR: corpus must be an object with a non-empty sources[]", file=sys.stderr)
        return 2

    extra = [d.strip() for d in args.extra_domains.split(",") if d.strip()]
    problems = _problems(corpus, extra, args.quota_cn_journal)

    if args.json:
        print(json.dumps({"problems": problems, "count": len(problems)},
                         ensure_ascii=False, indent=2))
    else:
        if problems:
            for p in problems:
                print(f"❌ {p}")
            print(f"\n{len(problems)} problem(s) — fix in 04_validated_sources.json "
                  f"before stage 5 drafting.")
        else:
            print(f"✅ Corpus clean ({len(corpus['sources'])} entries): "
                  f"unique ids/urls, required fields present, no suspect domains.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
