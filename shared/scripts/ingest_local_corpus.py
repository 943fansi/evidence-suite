#!/usr/bin/env python3
r"""Ingest a folder of local reference PDFs as a first-class corpus (w2/w3a).

Real-run gap: w2 is web-search-first and w3 downloads by URL, so a user's
existing local library (e.g. 45 journal-paper PDFs) could only enter the
corpus by hand-authoring 04_validated_sources.json entries one by one — with
descriptor titles and NO bibliographic metadata, which later collapsed the
GB/T 7714 reference list into bare skeletons. This script makes the local
folder an equal-entry path:

  1. scan *.pdf, dedup by md5;
  2. extract first-page text (pdfplumber, PyPDF2 fallback via extract_pdf_text);
  3. best-effort bibliographic metadata from the PDF header: real title /
     authors / 刊名 / year / 卷(期) / 页码(文章编号) / DOI / language —
     full-width digits normalized; anything not found stays EMPTY (never
     fabricated) and is listed in the report for human backfill;
  4. copy each PDF into reference_files/ under the suite filename convention
     ({Sx}_{title}.pdf, reusing download_reference_files.build_filename);
  5. append status="exists" rows to reference_files/manifest.json so
     extract_pdf_text.py --manifest picks them up for full-text extraction.

Metadata confidence is recorded per source in `meta_confidence`
(high/medium/low). Extraction is heuristic — 卷期页 for camera-ready two-column
PDFs with OCR noise may fail; the report says which fields to verify.

Exit codes: 0 ok; 1 nothing ingested; 2 usage error.

Usage:
  python scripts/ingest_local_corpus.py --pdf-dir "D:/参考论文" --case research_case
  python scripts/ingest_local_corpus.py --pdf-dir refs/ --case . --start-id 46 --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from download_reference_files import build_filename  # noqa: E402
from extract_pdf_text import extract_text  # noqa: E402

# 全角→半角（扫描版/排版 PDF 常混全角数字与标点）
_FW = {ord(f): ord(t) for f, t in zip(
    "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ．，：；（）－％",
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,:;()-%")}
DOI_RE = re.compile(r"DOI[:：]?\s*(10\.\d{4,5}/[^\s，。；]+)")
WENZHANG_RE = re.compile(r"文章编号[:：]?\s*(\d{4})[-]?(\d{4})\((\d{2,4})\)-(\d{4,5})-(\d{1,3})")
CN_JOURNAL_RE = re.compile(r"([\u4e00-\u9fff]{2,10})[ \t]*(\d{4})[，,][ \t]*(\d{1,3})[ \t]*\((\d{1,2})\)")
VOL_ISSUE_RE = re.compile(r"第\s*(\d{1,3})\s*卷\s*第\s*(\d{1,3})\s*期")
EN_JOURNAL_RE = re.compile(r"([A-Z][A-Za-z &]{5,60}?)\s*Vol\.?\s*(\d{1,3})\s*No\.?\s*(\d{1,3})")
MONTH_YEAR_RE = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})")
BAD_TITLE = re.compile(
    r"摘要|关键词|中图分类|DOI|Vol\.|No\.|第.{1,4}卷|收稿|基金|作者简介|文章编号|abstract|keywords"
    r"|\d{4}\s*年\s*第|\d{4}\s*年\s*\d{1,2}\s*月|总第|标准与检测|前沿视点|研究方向|Frontier|FRONTIER|等[：:]"
    r"|［\d+］|\[\d+\]|IEEE\s*Std|提出", re.I)
BANNER_RE = re.compile(r"^.{1,10}等[：:]\s*(.+?)[\s]+[\u4e00-\u9fff]{2,10}\s*\d{4}[，,]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _norm(s: str) -> str:
    return s.translate(_FW)


def extract_metadata(text: str, fallback_year: int | None) -> dict:
    """Best-effort bibliographic fields from the first-page text; empty = unknown.

    顺序：DOI/文章编号 → 标题+作者（块拼接） → 刊名/卷期（须与标题互斥） → 年份/语言。
    任何字段抽取不到就留空，由 meta_confidence 与报告提示人工回填，绝不虚构。
    """
    meta: dict = {"title": "", "authors": "", "journal": "", "year": None,
                  "volume": "", "issue": "", "page": "", "doi": "", "lang": ""}
    t = _norm(text)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    head = chr(10).join(lines[:40])

    m = DOI_RE.search(head)
    if m:
        meta["doi"] = m.group(1).rstrip(".,;")
    m = WENZHANG_RE.search(head)
    if m:
        yy = m.group(2)
        meta["year"] = int(yy) if len(yy) == 4 else int("20" + yy[-2:])
        meta["issue"] = str(int(m.group(3)))
        p0, plen = int(m.group(4)), int(m.group(5))
        meta["page"] = f"{p0}-{p0 + plen - 1}"

    # ---- 标题 + 作者 ----
    def is_cjk_cand(ln: str) -> bool:
        if "。" in ln or "；" in ln or BAD_TITLE.search(ln):
            return False
        if len(re.findall(r"[，,]", ln)) >= 2:  # 多逗号≈正文句
            return False
        if re.search(r"公司|大学|研究院|研究所|学院|邮编|\d{6}$", ln):  # 单位行
            return False
        return 6 <= len(ln) <= 60 and CJK_RE.search(ln) and not re.match(r"^[（(]", ln)

    def parse_authors(ln: str) -> list[str] | None:
        s = _norm(ln)
        ns = re.sub(r"[\s\d*＊]+", "", s)
        names = re.fullmatch(r"[\u4e00-\u9fff·]{2,4}(?:[，,、][\u4e00-\u9fff·]{2,4}){1,11}", ns)
        if names:
            return re.split(r"[，,、]", ns)
        if "，" not in s and "," not in s and "、" not in s:  # 「苏斓1 左宇翔2 …」
            sp = re.fullmatch(
                r"[\u4e00-\u9fff·]{2,4}(?:\d{0,2}[ \u3000]+[\u4e00-\u9fff·]{2,4}){1,11}\d{0,3}[,，]?", s)
            if sp:
                return [x for x in re.split(r"\d{0,2}[ \u3000]+", s) if x]
        return None

    def is_acronym_cont(ln: str) -> bool:
        return bool(cur) and bool(re.fullmatch(r"[A-Za-z0-9\-（）()/]{1,12}", ln))

    blocks: list[str] = []
    block_authors: list[str] = []
    cur: list[str] = []
    started = False
    for li, ln in enumerate(lines[:44]):
        au = parse_authors(ln) if cur else None
        if au:
            block_authors.append("，".join(au))
            blocks.append(re.sub(r"\s{2,}", " ", "".join(cur)).strip())
            cur = []
            started = False
            continue
        if is_cjk_cand(ln) or is_acronym_cont(ln):
            if not cur and li >= 28:
                continue
            cur.append(ln)
            started = True
        elif started and len(ln) <= 3:
            cur.append(ln)
        else:
            if cur:
                blocks.append(re.sub(r"\s{2,}", " ", "".join(cur)).strip())
            cur = []
            started = False
    if cur:
        blocks.append(re.sub(r"\s{2,}", " ", "".join(cur)).strip())

    banner = BANNER_RE.search(head)
    if banner:
        frag = re.sub(r"\s{2,}", " ", banner.group(1)).strip()
        blocks.insert(0, frag)
    t_nospace = re.sub(r"[\s　]", "", t)
    scored = []
    for b in blocks:
        if not (6 <= len(b) <= 90):
            continue
        key = re.sub(r"[\s　]", "", b)[:12]
        reps = len(re.findall(re.escape(key), t_nospace))
        scored.append((reps >= 2, len(b), b))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    # 无重复支撑时，只信首屏短块（正文长句绝不当标题）
    if scored and (scored[0][0] or len(scored[0][2]) <= 40):
        meta["title"] = scored[0][2]
        meta["title"] = re.sub(r"(?<=[一-鿿])[ 　]+(?=[一-鿿])", "", meta["title"])
        meta["authors"] = block_authors[0] if block_authors else ""
    else:  # 英文论文：首屏连续大写词行拼接
        en: list[str] = []
        for ln in lines[:25]:
            if re.match(r"^[A-Z][A-Za-z0-9,\-() ]{3,80}$", ln) and not BAD_TITLE.search(ln):
                en.append(ln.strip())
            elif en:
                break
        if en:
            meta["title"] = re.sub(r"\s{2,}", " ", " ".join(en))[:120]

    # ---- 刊名 / 卷(期)：与标题互斥，只在页眉带内取 ----
    m = CN_JOURNAL_RE.search(head[:600])
    if m:
        j = m.group(1).strip()
        if 2 <= len(j) <= 10 and j not in (meta["title"] or ""):
            meta["journal"] = j
            meta["volume"], meta["issue"] = m.group(3), m.group(4)
            meta["year"] = meta["year"] or int(m.group(2))
    if not meta["journal"]:
        mv = VOL_ISSUE_RE.search(head)
        if mv:
            meta["volume"], meta["issue"] = mv.group(1), mv.group(2)
            for ln in lines[:12]:
                ln2 = ln.strip("　 ").strip("□？?■")
                if 2 <= len(ln2) <= 12 and CJK_RE.search(ln2) and not BAD_TITLE.search(ln2) \
                        and not re.search(r"[\d，,、]", ln2) and ln2 not in (meta["title"] or ""):
                    meta["journal"] = ln2.replace(" ", "")
                    break
    me = EN_JOURNAL_RE.search(head)
    if me and not meta["journal"]:
        meta["journal"] = re.sub(r"\s+", " ", me.group(1)).strip().strip(",")
        meta["volume"], meta["issue"] = me.group(2), me.group(3)

    # ---- 年份 ----
    if not meta["year"]:
        mj = MONTH_YEAR_RE.search(head) or re.search(r"(20\d{2})\s*年", head)              or re.search(r"[，,]\s*(20\d{2})[，,]", head)
        if mj:
            meta["year"] = int(mj.group(mj.lastindex if mj.lastindex else 1))
    meta["year"] = meta["year"] or fallback_year
    meta["lang"] = "zh" if CJK_RE.search(meta["title"] or "") or CJK_RE.search(meta["journal"] or "") else "en"
    meta["title"] = re.sub(r"\s{2,}", " ", meta["title"]).strip()
    return meta


def confidence(meta: dict) -> str:
    filled = sum(bool(meta[k]) for k in ("title", "authors", "journal", "year", "volume"))
    if filled >= 4 and meta["authors"]:
        return "high"
    if filled >= 3:
        return "medium"
    return "low"


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    ap = argparse.ArgumentParser(description="Ingest local PDF folder as validated corpus (w2/w3a)")
    ap.add_argument("--pdf-dir", required=True, type=Path, help="folder of reference PDFs")
    ap.add_argument("--case", type=Path, default=Path("."), help="research case root (corpus/manifest/pdf dir)")
    ap.add_argument("--start-id", type=int, default=1, help="first source number (S<start>, S<start+1>, …)")
    ap.add_argument("--type", default="journal_paper", help="source type for entries (default journal_paper)")
    ap.add_argument("--source-origin", default="user", choices=("user", "discovered"),
                    help="source_origin tag (default user)")
    ap.add_argument("--no-copy", action="store_true", help="do not copy PDFs into reference_files/")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.pdf_dir.is_dir():
        print(f"error: pdf dir not found: {args.pdf_dir}", file=sys.stderr)
        return 2
    corpus_path = args.case / "04_validated_sources.json"
    pdf_dir = args.case / "reference_files"
    manifest_path = pdf_dir / "manifest.json"

    corpus = {"sources": []}
    if corpus_path.exists():
        corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    existing_ids = {s.get("source_id") for s in corpus.get("sources", [])}
    manifest = []
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    existing_files = {row.get("filename") for row in manifest}

    pdfs = sorted(args.pdf_dir.glob("*.pdf"))
    seen_md5 = {hashlib.md5((pdf_dir / r["filename"]).read_bytes()).hexdigest()
                for r in manifest if (pdf_dir / r.get("filename", "")).exists()}
    n = args.start_id - 1
    added, low_meta = [], []
    for pdf in pdfs:
        md5 = hashlib.md5(pdf.read_bytes()).hexdigest()
        if md5 in seen_md5:
            continue
        seen_md5.add(md5)
        while f"S{n + 1}" in existing_ids:
            n += 1
        n += 1
        sid = f"S{n}"
        text, chars, _trunc = extract_text(pdf, 12, 6000)
        fb_year = None
        m = re.match(r"^(\d{4})", pdf.stem)
        if m:
            fb_year = int(m.group(1))
        meta = extract_metadata(text or "", fb_year) if chars else {k: ("" if k != "lang" else "") for k in
                                                                    ("title", "authors", "journal", "year", "volume", "issue", "page", "doi", "lang")}
        conf = confidence(meta)
        if conf == "low":
            low_meta.append(sid)
        series = ""
        if meta["journal"] and meta["year"]:
            series = f"{meta['journal']}, {meta['year']}"
            if meta["volume"]:
                series += f", {meta['volume']}({meta['issue'] or '?'})"
                if meta["page"]:
                    series += f": {meta['page']}"
        title = meta["title"] or pdf.stem
        entry = {
            "source_id": sid,
            "title": title,
            "title_or_name": pdf.stem,
            "authors": meta["authors"],
            "series": series,
            "publisher_or_source": meta["journal"],
            "year": meta["year"],
            "doi": meta["doi"],
            "lang": meta["lang"],
            "url": pdf.resolve().as_uri(),
            "type": args.type,
            "authority": "C1",
            "freshness": "recent" if (meta["year"] or 0) >= 2018 else "historical",
            "source_origin": args.source_origin,
            "access_status": "confirmed",
            "meta_confidence": conf,
        }
        added.append((sid, entry, pdf, title))
        print(f"[{sid}] {conf:>6} | {meta['authors'] or '?'} | {title[:38]} | {series or '?'}"
              + (f" | DOI:{meta['doi']}" if meta["doi"] else ""))

    if args.dry_run:
        print(f"\ndry-run: {len(added)} would be ingested (use without --dry-run)")
        return 0
    if not added:
        print("nothing to ingest (all PDFs already in corpus/manifest)")
        return 1

    if not args.no_copy:
        pdf_dir.mkdir(parents=True, exist_ok=True)
    for sid, entry, pdf, title in added:
        corpus["sources"].append(entry)
        fname = build_filename(sid, title)
        if not args.no_copy and fname not in existing_files:
            shutil.copy2(pdf, pdf_dir / fname)
        manifest.append({"id": sid, "title": title, "filename": fname, "status": "exists"})

    corpus_path.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ningested {len(added)} sources -> {corpus_path}")
    print(f"manifest rows -> {manifest_path} (next: extract_pdf_text.py --manifest …)")
    if low_meta:
        print(f"⚠️  low-confidence metadata (人工核对标题/作者/卷期): {', '.join(low_meta)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
