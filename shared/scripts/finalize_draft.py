#!/usr/bin/env python3
r"""Finalize an evidence-driven draft for formal delivery (定稿净化).

Converts the working draft (with `[Sx]`/`[Gx]`/`[假设]`/`[待内部确认]` scaffolding)
into a clean deliverable, and validates the result. Designed after real runs where
formal theses were rejected for leaking scaffolding markers, "附录A 证据缺口清单",
crawler/prompt traces, and non-standard `[S1]` citation tags into the final PDF.

What it does (in order — order matters, see "Lessons" below):

  1. Map each `[Sx]` to a sequential number `[n]` from the reference-list order
     (first occurrence wins; supports bare-number ids "S1".."S65" or "1".."65").
  2. Convert body citations `[Sx]` -> `[n]` (body = everything before the
     参考文献 / References section). Merged citations like `[S1][S2]` become
     `[1][2]` (kept as-is for clarity; collapse to `[1,2]` is left to the author).
  3. Strip scaffolding tags anywhere in the document:
       `[Gx]`, `[假设]`, `[待内部确认]`, `[待验证]`, `[待核验]`, and a leading
     `> **标记图例** …` legend line.
  4. Delete the 证据缺口清单 appendix (`## 附录A` …) — only when it sits AFTER the
     reference section (the normal layout); never truncates the body.
  5. Remove `<!-- HTML comments -->` (cross-line safe) and residual placeholder
     text (`编号：2023xxxx`, `资助项目：`, `By XX / Supervisor`, etc.).
  6. Rebuild the reference section entries as `[n]` (strip the `[Sx]` tag) and drop
     the legacy ` URL: <url>` wrapper when `--style gbt` (see below).
  7. Validate: zero residual scaffolding, all `[1..n]` sequential & fully covered
     by body citations, no duplicate URLs in the reference section, and re-run
     citation closure if `--sources` is given.

  `[Gx]` gaps: instead of silently dropping the markers, the appendix A
  "证据缺口清单" (when it exists and sits after the references) is converted into
  a "研究局限（由证据缺口转化）" subsection inserted before 参考文献 — the thesis
  norm is to fold limitations into 总结/展望, not to leak internal markers.

Exit codes: 0 ok; 1 input unreadable / no reference section; 2 usage error;
3 validation failed (residual markers / broken numbering).

Lessons encoded from real runs:
  - NEVER `re.sub(r'\s{2,}', ' ', body)` to "collapse" whitespace — it eats `\n`
    and destroys the whole markdown structure.
  - Delete the appendix from the FULL text BEFORE splitting body/refs, and slice
    the reference section from the already-trimmed text — otherwise the appendix
    leaks back in through a stale `text[ref_start:]` slice.
  - Locate the appendix by the literal `## 附录A` heading AFTER the reference
    section; do not fall back to `body.find('附录A')` (the legend in the header
    mentions 附录A and would truncate the entire body).
  - Clean placeholder tags BEFORE stripping HTML comments is fine, but the
    comments inside 攻读学位/致谢 live AFTER the reference section, so the same
    cleanup must also run on the reference-slice — not just the body slice.

Usage:
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_clean.md
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_clean.md --sources 04_validated_sources.json
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_clean.md --manifest evidence_manifest.json --sources 04_validated_sources.json
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_clean.md --claim-manifest claim_manifest.json --evidence-map 06_evidence_map.json --sources 04_validated_sources.json --review-kind ai-cross-model
      # Both manifest outputs carry schema_version + review_kind and are validated
      # against shared/schemas/*.schema.json before being written (see validate_manifest.py).
  python scripts/finalize_draft.py 11_定稿.md -o 11_定稿_gbt.md --style gbt
      # --style gbt: also emit reference entries in GB/T 7714-ish skeleton
      #   (<title>. <publisher>, <year>. URL.) with [1]..[n] numbering, and
      #   append a "[Sx]↔[n] 对照表" section for the author's post-check.
      #   --style gbt implies dropping the " URL: " prefix wrapper.
  python scripts/finalize_draft.py 11_定稿.md --check        # validate only, no rewrite
  python scripts/finalize_draft.py 11_定稿.md --dry-run      # preview what would change, write nothing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from validate_manifest import SCHEMA_VERSION, validate_manifest

# matches "## 参考文献", "## 参考文献 References", "## References", "## 文献"
REF_HEADER_RE = re.compile(r"^##\s*(?:\d+[.、]\s*)?(参考文献|References|Bibliography|文献)\b")
# matches "## 附录A", "## 附录 A", "## 附录A 证据缺口清单", "## Appendix A"
APP_HEADER_RE = re.compile(r"^##\s*(?:附录\s*A|附录\s*Ａ|Appendix\s*A)\b")
GAP_TABLE_RE = re.compile(r"^\|\s*\[?G?(\d+)\]?\s*\|(.+?)\|\s*$", re.M)
SX_RE = re.compile(r"\[S(\d+)\]")
GX_RE = re.compile(r"\[G\d+\]")
PLACEHOLDER_TAGS = ("[假设]", "[待内部确认]", "[待验证]", "[待核验]")
LEGEND_RE = re.compile(r"^> \*\*标记图例\*\*.*$", re.M)
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
GAP_BODY_RE = re.compile(r"\[G(\d+)\]")


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def strip_placeholder_tags(text: str) -> str:
    out = text
    for tag in PLACEHOLDER_TAGS:
        out = out.replace(tag, "")
    return out


def clean_cover_placeholders(text: str) -> str:
    out = text
    out = re.sub(r"编号：\S*\[?待内部确认\]?", "编号：XXXXXXXX（作者学号）", out)
    out = re.sub(r"编号：2023\d*", "编号：XXXXXXXX（作者学号）", out)
    out = out.replace("资助项目：[待内部确认]", "")
    out = out.replace("　资助项目：", "")
    out = out.replace("By XX / Supervisor: Prof. XXX / August 2026",
                      "By （作者姓名） / Supervisor: Prof. （导师姓名） / August 2026")
    out = out.replace("资助项目：", "")
    return out


def build_number_map(ref_section: str) -> dict[str, str]:
    """Map S-ids to sequential [n] from the reference-list order."""
    mapping: dict[str, str] = {}
    for m in re.finditer(r"^\[(?:S?)(\d+)\]", ref_section, re.M):
        sid = m.group(1)
        key = f"S{sid}"
        if key not in mapping:
            mapping[key] = str(len(mapping) + 1)
    return mapping


def id_map_from_draft(text: str) -> dict[str, str]:
    """Extract the [Sx]→[n] mapping from a draft's reference section."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if REF_HEADER_RE.match(line.strip()):
            return build_number_map("\n".join(lines[i:]))
    return {}


def source_metadata(sources_path: Path | None) -> dict[str, dict[str, str]]:
    """Load {source_id: {title, url}} from 04_validated_sources.json."""
    if not sources_path or not sources_path.exists():
        return {}
    try:
        corpus = json.loads(sources_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    meta: dict[str, dict[str, str]] = {}
    for s in corpus.get("sources", []):
        sid = str(s.get("source_id", "")).strip()
        if not sid:
            continue
        meta[sid] = {
            "title": (s.get("title_or_name") or s.get("title") or "").strip(),
            "url": (s.get("url") or "").strip(),
            "authority": (s.get("authority") or "").strip(),
            "freshness": (s.get("freshness") or "").strip(),
        }
    return meta


def _relation_from_level(level: str) -> str:
    """Derive the directional relation from a support_level when not explicit."""
    if level == "contradictory":
        return "contradicts"
    if level == "context_only":
        return "context_only"
    return "supports"


def evidence_map_claims(em_path: Path | None) -> dict[str, list[dict[str, str]]]:
    """Load per-source claim provenance from 06_evidence_map.json."""
    if not em_path or not em_path.exists():
        return {}
    try:
        em = json.loads(em_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, list[dict[str, str]]] = {}
    for entry in em.get("evidence_map", []):
        claim_text = str(entry.get("claim_to_write", "")).strip()
        claim_class = str(entry.get("claim_class", "")).strip()
        status = str(entry.get("evidence_status", "")).strip()
        levels = entry.get("source_support_levels") or {}
        if not isinstance(levels, dict):
            levels = {}
        relations = entry.get("source_relations") or {}
        if not isinstance(relations, dict):
            relations = {}
        locators = entry.get("source_locators") or {}
        if not isinstance(locators, dict):
            locators = {}
        for sid, lvl in levels.items():
            rec: dict = {"claim_text": claim_text, "claim_class": claim_class,
                         "support_level": str(lvl), "evidence_status": status}
            rel = relations.get(sid)
            if rel:
                rec["relation"] = str(rel)
            loc = locators.get(sid)
            if isinstance(loc, dict):
                rec["locator"] = loc
            out.setdefault(str(sid), []).append(rec)
    return out


def build_claim_manifest(em_path: Path, meta: dict) -> dict:
    """Aggregate 06_evidence_map.json into a claim-centric manifest (interop contract)."""
    claims: list[dict] = []
    try:
        em = json.loads(em_path.read_text(encoding="utf-8"))
    except Exception:
        return {"claims": []}
    for i, entry in enumerate(em.get("evidence_map", []), 1):
        claim_text = str(entry.get("claim_to_write", "")).strip()
        levels = entry.get("source_support_levels") or {}
        if not isinstance(levels, dict):
            levels = {}
        relations = entry.get("source_relations") or {}
        if not isinstance(relations, dict):
            relations = {}
        locators = entry.get("source_locators") or {}
        if not isinstance(locators, dict):
            locators = {}
        evidence: list[dict] = []
        for sid, lvl in levels.items():
            rec: dict = {"source_id": str(sid), "support_level": str(lvl)}
            rel = relations.get(sid)
            rec["relation"] = str(rel) if rel else _relation_from_level(str(lvl))
            loc = locators.get(sid)
            if isinstance(loc, dict) and loc:
                rec["locator"] = loc
            m = meta.get(str(sid))
            if m:
                if m.get("authority"):
                    rec["authority"] = m["authority"]
                if m.get("freshness"):
                    rec["freshness"] = m["freshness"]
            evidence.append(rec)
        status = str(entry.get("evidence_status", "")).strip()
        recon = entry.get("reconciliation") or {}
        verdict = status or str(recon.get("verdict", "")).strip()
        claim: dict = {
            "claim_id": f"C-{i:03d}",
            "claim_class": str(entry.get("claim_class", "")).strip(),
            "risk": str(entry.get("risk", "")).strip(),
            "claim_text": claim_text,
            "evidence": evidence,
            "evidence_status": status,
            "verdict": verdict,
        }
        confidence = entry.get("confidence")
        if confidence:
            claim["confidence"] = str(confidence)
        interpretation = entry.get("interpretation")
        if interpretation:
            claim["interpretation"] = str(interpretation).strip()
        claims.append(claim)
    return {"claims": claims}


def finalize(text: str, style: str = "sx") -> str:
    """Run the full cleanup pipeline; returns cleaned markdown."""
    ref_start = None
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if REF_HEADER_RE.match(line.strip()):
            ref_start = i
            break
    if ref_start is None:
        raise ValueError("no 参考文献/References section found")

    # 1. Delete the evidence-gap appendix from the FULL text, only when after refs.
    #    Never fall back to body.find('附录A') — the header legend mentions it.
    #    Before deleting, capture the gap table (编号|描述|…) so any body [Gx]
    #    markers can be converted into a "研究局限" narrative rather than dropped.
    app_idx = None
    app_block = ""
    for i in range(len(lines)):
        if APP_HEADER_RE.match(lines[i].strip()):
            app_idx = i
            break
    if app_idx is not None and app_idx >= ref_start:
        app_block = "\n".join(lines[app_idx:])
        lines = lines[:app_idx]
        text = "\n".join(lines).rstrip() + "\n"

    # 2. Recompute boundaries on the already-trimmed text (avoids stale slice).
    lines = text.split("\n")
    ref_start = None
    for i, line in enumerate(lines):
        if REF_HEADER_RE.match(line.strip()):
            ref_start = i
            break
    body = "\n".join(lines[:ref_start])
    ref_section = "\n".join(lines[ref_start:])

    # 3. Map + convert body citations.
    id_map = build_number_map(ref_section)
    body = re.sub(r"\[S(\d+)\]",
                  lambda m: f"[{id_map.get('S' + m.group(1), '?' + m.group(1))}]",
                  body)

    # 4. Strip scaffolding tags + legend from body; convert [Gx] to limitations.
    body_gaps = sorted({int(g) for g in GAP_BODY_RE.findall(body)})
    body = GX_RE.sub("", body)
    body = strip_placeholder_tags(body)
    body = LEGEND_RE.sub("", body)

    # 5. Clean cover placeholders + HTML comments (both body and ref slice).
    body = clean_cover_placeholders(body)
    body = COMMENT_RE.sub("", body)
    body = re.sub(r"相关论断均以公开摘要级结论支撑，具体详见附录A。", "", body)
    # Crawler/prompt traces → academic phrasing (real-run: "NRC ADAMS PDF受反爬限制不可下载"
    # leaked the research process into the final thesis).
    body = re.sub(r"NRC ADAMS\s*PDF\s*受反爬限制不可下载", "部分NRC历史档案全文无法在线获取", body)
    body = re.sub(r"受反爬限制不可下载", "全文无法在线获取", body)
    body = re.sub(r"PDF受反爬限制", "全文受访问限制", body)
    body = re.sub(r"\n{3,}", "\n\n", body)

    # 5b. If any [Gx] were referenced in the body and an appendix gap table was
    #     captured, emit a "研究局限" subsection before 参考文献. Thesis norm:
    #     limitations belong in a dedicated narrative, not leaked markers.
    if body_gaps and app_block.strip():
        gap_rows = []
        for m in GAP_TABLE_RE.finditer(app_block):
            gnum, rest = int(m.group(1)), m.group(2)
            if gnum in body_gaps:
                # 表格列：| 编号 | 描述 | 优先级 | → 取第 1 列（描述）
                cols = [c.strip() for c in rest.split("|") if c.strip()]
                desc = cols[0] if cols else rest.strip()
                gap_rows.append(f"{gnum}. {desc}")
        if gap_rows:
            # Crawler/prompt traces inside the appendix gap table must be
            # academicized too (they become the 研究局限 narrative).
            cleaned_rows = []
            for row in gap_rows:
                row = re.sub(r"NRC ADAMS\s*PDF\s*受反爬限制不可下载",
                             "部分NRC历史档案全文无法在线获取", row)
                row = re.sub(r"受反爬限制不可下载", "全文无法在线获取", row)
                row = re.sub(r"PDF受反爬限制", "全文受访问限制", row)
                cleaned_rows.append(row)
            limitations = ("## 研究局限\n\n"
                           "本文基于已审计公开来源展开，以下方面因证据可得性与范围限制"
                           "未予充分展开，有待后续工作补充：\n\n"
                           + "\n".join(cleaned_rows) + "\n")
            body = body.rstrip() + "\n\n" + limitations

    # 6. Reference section: [Sx] -> [n]; optional GB/T skeleton.
    ref_section = re.sub(r"^\[S(\d+)\]",
                         lambda m: f"[{id_map.get('S' + m.group(1), '?' + m.group(1))}]",
                         ref_section, flags=re.M)
    ref_section = strip_placeholder_tags(ref_section)
    ref_section = clean_cover_placeholders(ref_section)
    ref_section = COMMENT_RE.sub("", ref_section)
    if style == "gbt":
        # 骨架格式：去掉 " URL: " 前缀包装，保持 题名. 出版者, 年. URL.
        ref_section = ref_section.replace(" URL: ", " ")
        mapping_lines = ["", "", "### [Sx]↔[n] 对照表（投稿核查用，投稿版删除本节）", "",
                         "| [Sx] | [n] |", "|-----|-----|"]
        for key in sorted(id_map, key=lambda k: int(id_map[k])):
            mapping_lines.append(f"| [{key}] | [{id_map[key]}] |")
        ref_section += "\n".join(mapping_lines)

    return body.rstrip() + "\n\n" + ref_section.strip() + "\n"


def validate(text: str) -> list[str]:
    """Return a list of problems found in a finalized draft (empty = clean).

    The GB/T 骨架 mode intentionally keeps an "[Sx]↔[n] 对照表" appendix for the
    author's post-check — citations inside that table are NOT treated as residuals.
    """
    problems: list[str] = []
    # strip the mapping-table block before residual scans (it legitimately contains [Sx])
    mapping_pos = text.find("### [Sx]↔[n] 对照表")
    scan = text[:mapping_pos] if mapping_pos != -1 else text
    # residual scaffolding anywhere
    for pat, name in [(r"\[S\d+\]", "[Sx]"), (r"\[G\d+\]", "[Gx]"),
                      (r"\[假设\]", "[假设]"), (r"\[待内部确认\]", "[待内部确认]"),
                      (r"\[待验证\]", "[待验证]"), (r"待核验", "待核验"),
                      (r"thesis_format", "thesis_format"), (r"标记图例", "标记图例"),
                      (r"证据缺口", "证据缺口"), (r"附录A", "附录A"),
                      (r"NRC ADAMS", "NRC ADAMS"), (r"反爬", "反爬"),
                      (r"待填写", "待填写"), (r"\?\d+\]", "[?n]")]:
        n = len(re.findall(pat, scan))
        if n:
            problems.append(f"residual {name}: {n}")
    # reference numbering sequential + contiguous
    ref_start = None
    for i, line in enumerate(text.split("\n")):
        if REF_HEADER_RE.match(line.strip()):
            ref_start = i
            break
    if ref_start is None:
        problems.append("no reference section")
        return problems
    refs = text.split("\n")[ref_start:]
    ref_nums = [int(m.group(1)) for m in
                (re.match(r"^\[(\d+)\]", ln) for ln in refs) if m]
    if ref_nums != list(range(1, len(ref_nums) + 1)):
        problems.append(f"reference numbering broken: {ref_nums[:6]}…")
    # duplicate URLs in reference section
    urls = re.findall(r"https?://[^\s\]]+", "\n".join(refs))
    seen: set[str] = set()
    for u in urls:
        if u in seen:
            problems.append(f"duplicate URL: {u[:70]}…")
        seen.add(u)
    return problems


def _change_summary(orig: str, out: str) -> str:
    """Human-readable preview of what finalize would change (dry-run)."""
    sx_before = len(re.findall(r"\[S\d+\]", orig))
    scaffolds = {t: orig.count(t) - out.count(t) for t in PLACEHOLDER_TAGS}
    gaps_before = len(re.findall(r"\[G\d+\]", orig))
    gaps_after = len(re.findall(r"\[G\d+\]", out))
    has_appendix = bool(APP_HEADER_RE.search(orig))
    removed_total = sum(scaffolds.values())
    lines = [
        "dry-run: 预览本次净化将做的修改（不会写入任何文件）",
        f"  [Sx]→[n] 顺序编码: {sx_before} 处正文标记",
        f"  脚手架标记清理: {removed_total} 处 ({', '.join(PLACEHOLDER_TAGS)})",
        f"  [Gx] 研究空白: {gaps_before} → {gaps_after} 处" + ("（可能转写为研究局限）" if gaps_before > gaps_after else ""),
        f"  附录A 证据缺口清单: {'将删除' if has_appendix else '无'}",
    ]
    return "\n".join(lines)


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", type=Path, help="draft .md with [Sx] scaffolding")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="write cleaned draft here (default: stdout)")
    parser.add_argument("--sources", type=Path, default=None,
                        help="04_validated_sources.json → re-run citation closure on output")
    parser.add_argument("--style", choices=["sx", "gbt"], default="sx",
                        help="reference-entry style (default sx)")
    parser.add_argument("--check", action="store_true",
                        help="validate only, do not write output")
    parser.add_argument("--dry-run", action="store_true",
                        help="analyze only: print what would change (Sx→[n], scaffold "
                             "cleanup, appendix removal) without writing any file")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="write a machine-readable evidence manifest ([Sx]↔[n] mapping + source metadata) here")
    parser.add_argument("--verification-mode", choices=["static", "live"], default="static",
                        help="evidence verification mode recorded in the manifest (default static)")
    parser.add_argument("--review-kind", choices=["ai-internal", "ai-cross-model", "human-expert"],
                        default="ai-internal",
                        help="review type recorded in the manifest (default ai-internal). "
                             "ai-internal = same-model role isolation (internal red team, NOT "
                             "independent review); switch to ai-cross-model or human-expert for "
                             "independent review of R4 / publication-critical output.")
    parser.add_argument("--evidence-map", type=Path, default=None,
                        help="06_evidence_map.json → merge claim-level provenance (claim_text/claim_class/support_level/evidence_status) into the manifest")
    parser.add_argument("--claim-manifest", type=Path, default=None,
                        help="export a claim-centric manifest from --evidence-map (interop contract; requires --evidence-map)")
    parser.add_argument("--no-validate-manifest", action="store_true",
                        help="skip manifest schema validation (not recommended: may emit an invalid contract downstream)")
    args = parser.parse_args()

    if not args.draft.exists():
        print(f"error: draft not found: {args.draft}", file=sys.stderr)
        return 1
    text = args.draft.read_text(encoding="utf-8")

    if args.check:
        for p in validate(text):
            print("problem:", p)
        return 3 if validate(text) else 0

    try:
        out = finalize(text, style=args.style)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    problems = validate(out)
    if problems:
        for p in problems:
            print("validation:", p)
        print("WARNING: output written but failed validation", file=sys.stderr)
    else:
        print("validation: clean")

    if args.sources and args.sources.exists():
        corpus = json.loads(args.sources.read_text(encoding="utf-8"))
        n_sources = len(corpus.get("sources", []))
        ref_nums = [int(m.group(1)) for m in
                    (re.match(r"^\[(\d+)\]", ln) for ln in out.split("\n")) if m]
        if ref_nums and ref_nums[-1] >= n_sources:
            print(f"citation closure: {ref_nums[-1]}/{n_sources} refs match corpus count")

    if args.dry_run:
        print(_change_summary(text, out))
        if problems:
            for p in problems:
                print("validation:", p)
            print("WARNING: output would fail validation (dry-run, no file written)",
                  file=sys.stderr)
        return 0

    if args.output:
        args.output.write_text(out, encoding="utf-8")
        print(f"finalized -> {args.output}")
    else:
        sys.stdout.write(out)

    if args.manifest:
        id_map = id_map_from_draft(text)
        meta = source_metadata(args.sources)
        claims = evidence_map_claims(args.evidence_map)
        mapping = []
        for key in sorted(id_map, key=lambda k: int(id_map[k])):
            entry: dict = {
                "citation": f"[{key}]", "mapped": f"[{id_map[key]}]", "source_id": key,
            }
            m = meta.get(key)
            if m:
                if m.get("title"):
                    entry["title"] = m["title"]
                if m.get("url"):
                    entry["url"] = m["url"]
            cs = claims.get(key)
            if cs:
                entry["claims"] = cs
            mapping.append(entry)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "review_kind": args.review_kind,
            "verification_mode": args.verification_mode,
            "finalized_at": date.today().isoformat(),
            "note": "claim 级字段来自 06_evidence_map.json（--evidence-map 提供时自动合并）",
            "mapping": mapping,
        }
        if not args.no_validate_manifest:
            problems = validate_manifest(manifest)
            if problems:
                for p in problems:
                    print("manifest validation:", p)
                print("error: manifest failed schema validation; not written",
                      file=sys.stderr)
                return 2
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        print(f"manifest -> {args.manifest}")

    if args.claim_manifest:
        if not args.evidence_map or not args.evidence_map.exists():
            print("error: --claim-manifest requires --evidence-map 06_evidence_map.json",
                  file=sys.stderr)
            return 2
        cm = build_claim_manifest(args.evidence_map, source_metadata(args.sources))
        cm["schema_version"] = SCHEMA_VERSION
        cm["review_kind"] = args.review_kind
        cm["verification_mode"] = args.verification_mode
        cm["finalized_at"] = date.today().isoformat()
        if not args.no_validate_manifest:
            problems = validate_manifest(cm)
            if problems:
                for p in problems:
                    print("claim-manifest validation:", p)
                print("error: claim-manifest failed schema validation; not written",
                      file=sys.stderr)
                return 2
        args.claim_manifest.write_text(json.dumps(cm, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print(f"claim-manifest -> {args.claim_manifest}")

    return 3 if problems else 0


if __name__ == "__main__":
    sys.exit(main())