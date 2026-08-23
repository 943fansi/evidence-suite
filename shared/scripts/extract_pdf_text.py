#!/usr/bin/env python3
"""Extract readable text from downloaded reference PDFs and enrich the validated source corpus.

Called after Stage 3 sub-step 3b (Validate Download Status). Reads manifest.json to find which PDFs
were successfully downloaded, extracts text from each using pdfplumber (with PyPDF2 fallback),
saves per-source .txt files, and optionally updates 04_validated_sources.json with extraction
metadata so that downstream stages (evidence map, draft) can prefer PDF-verified content
over search-agent evidence summaries.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

try:
    import pdfplumber  # noqa: F401

    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import PyPDF2  # noqa: F401

    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False


DEFAULT_MAX_PAGES = 500
DEFAULT_MAX_CHARS = 5_000_000


def sanitize_filename(text: str, max_len: int = 90) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" ", "_")
    text = re.sub(r"_+", "_", text)
    return text[:max_len].strip("._") or "untitled"


def extract_with_pdfplumber(pdf_path: Path, max_pages: int = DEFAULT_MAX_PAGES,
                            max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, int, bool]:
    """Extract text using pdfplumber. Returns (text, char_count, truncated).

    Defensive against malicious/oversized PDFs (zombie OCR, zip-bomb-style huge
    extraction): caps page count and extracted chars; `truncated=True` marks a
    truncated extraction instead of letting one PDF blow up memory/disk.
    """
    parts: list[str] = []
    total = 0
    truncated = False
    with pdfplumber.open(str(pdf_path)) as pdf:
        pages = pdf.pages
        for page in pages[:max_pages]:
            page_text = page.extract_text()
            if page_text:
                parts.append(page_text)
                total += len(page_text)
                if total > max_chars:
                    truncated = True
                    break
        if len(pages) > max_pages:
            truncated = True
    text = "\n\n".join(parts)
    return text, len(text), truncated


def extract_with_pypdf2(pdf_path: Path, max_pages: int = DEFAULT_MAX_PAGES,
                        max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, int, bool]:
    """Extract text using PyPDF2 as fallback (same page/char caps)."""
    with open(pdf_path, "rb") as fh:
        reader = PyPDF2.PdfReader(fh)
        parts: list[str] = []
        total = 0
        truncated = False
        for page in reader.pages[:max_pages]:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                parts.append(page_text)
                total += len(page_text)
                if total > max_chars:
                    truncated = True
                    break
        if len(reader.pages) > max_pages:
            truncated = True
    text = "\n\n".join(parts)
    return text, len(text), truncated


def extract_text(pdf_path: Path, max_pages: int = DEFAULT_MAX_PAGES,
                 max_chars: int = DEFAULT_MAX_CHARS) -> tuple[str, int, bool] | tuple[None, None, None]:
    """Try pdfplumber first, fall back to PyPDF2. Returns (text, chars, truncated)."""
    if HAS_PDFPLUMBER:
        try:
            return extract_with_pdfplumber(pdf_path, max_pages, max_chars)
        except Exception:
            pass
    if HAS_PYPDF2:
        try:
            return extract_with_pypdf2(pdf_path, max_pages, max_chars)
        except Exception:
            pass
    return None, None, None


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Path to reference_files/manifest.json.")
    parser.add_argument("--sources", type=Path, required=True,
                        help="Path to 04_validated_sources.json (read + write-back).")
    parser.add_argument("--pdf-dir", type=Path, required=True,
                        help="Directory containing the downloaded PDFs.")
    parser.add_argument("--out-dir", type=Path, default=None,
                        help="Directory for extracted .txt files (default: same as --pdf-dir/pdf_text).")
    parser.add_argument("--extract-quotes", action="store_true",
                        help="Also search for key sentences matching topic keywords.")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                        help=f"Abort extraction of any PDF exceeding this page count "
                             f"(default {DEFAULT_MAX_PAGES}; anti-malicious-PDF guard)")
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                        help=f"Stop extracting once a single PDF exceeds this many chars "
                             f"(default {DEFAULT_MAX_CHARS:,}; anti-zip-bomb guard)")
    parser.add_argument("--update-sources", action="store_true",
                        help="Write extraction metadata back into 04_validated_sources.json.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without writing files.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    if not HAS_PDFPLUMBER and not HAS_PYPDF2:
        print("Neither pdfplumber nor PyPDF2 is installed.", file=sys.stderr)
        print("Install with: pip3 install --break-system-packages pdfplumber", file=sys.stderr)
        print("(PyPDF2 will be used as fallback if pdfplumber fails on a given PDF.)", file=sys.stderr)
        return 1

    manifest = load_json(args.manifest)
    if not args.out_dir:
        args.out_dir = args.pdf_dir.parent / "pdf_text"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Build source-id → metadata map from the validated corpus
    sources_data = load_json(args.sources)
    id_to_source: dict[str, dict] = {}
    for src in sources_data.get("sources", []):
        sid = src.get("source_id")
        if sid:
            id_to_source[sid] = src

    # Build manifest entry map for quick lookup
    manifest_map: dict[str, dict] = {}
    for row in manifest:
        sid = row.get("id", "")
        if sid:
            manifest_map[sid] = row

    downloaded = [row for row in manifest if row.get("status") in ("downloaded", "exists")]
    if not downloaded:
        print("No downloaded/existing PDFs found in manifest.")
        return 0

    success, failed, total_chars = 0, 0, 0
    for row in downloaded:
        sid = row.get("id", "?")
        title = row.get("title", sid)
        filename = row.get("filename", "")
        pdf_path = args.pdf_dir / filename
        txt_filename = filename.replace(".pdf", ".txt")
        txt_path = args.out_dir / txt_filename

        if not pdf_path.exists():
            print(f"  [{sid}] PDF not found at {pdf_path}")
            failed += 1
            _mark_source(id_to_source.get(sid), False, 0, "")
            continue

        if args.dry_run:
            print(f"  [{sid}] dry-run: would extract {pdf_path} → {txt_path}")
            continue

        text, chars, truncated = extract_text(pdf_path, args.max_pages, args.max_chars)
        if text is None or chars == 0:
            print(f"  [{sid}] FAILED (no extractable text — likely scanned PDF): {title[:70]}")
            failed += 1
            _mark_source(id_to_source.get(sid), False, 0, "")
            continue

        if truncated:
            print(f"  [{sid}] ⚠️  TRUNCATED (>{args.max_pages} pages or >{args.max_chars:,} chars) — "
                  f"extraction capped; 注意该 PDF 可能为恶意超大文档")

        # Write text file with metadata header
        source = id_to_source.get(sid, {})
        source_url = source.get("url", row.get("url", ""))
        safe_rel = str(txt_path.relative_to(args.out_dir.parent)) if args.out_dir.parent else str(txt_path)
        header = (
            f"[{sid}] {title}\n"
            f"URL: {source_url}\n"
            f"Chars: {chars}" + (" (TRUNCATED)" if truncated else "") + "\n"
            f"{'=' * 60}\n\n"
        )
        with open(txt_path, "w", encoding="utf-8") as fh:
            fh.write(header + text)

        # Optionally extract key quotes
        verified_quote = ""
        if args.extract_quotes and chars > 100:
            verified_quote = _extract_quote(text, sources_data.get("topic", ""))

        _mark_source(id_to_source.get(sid), True, chars, safe_rel, verified_quote, truncated)

        print(f"  [{sid}] OK {chars:>7} chars  {title[:65]}")
        success += 1
        total_chars += chars

    if args.update_sources and not args.dry_run:
        save_json(args.sources, sources_data)
        print(f"\nUpdated {args.sources} ({len(id_to_source)} sources)")

    pct = success / len(downloaded) * 100 if downloaded else 0
    print(f"\nDone: {success} extracted, {failed} failed ({pct:.0f}% success), {total_chars:,} chars total")
    print(f"Text files: {args.out_dir}/")
    return 0


def _mark_source(source: dict | None, ok: bool, chars: int, path: str, quote: str = "",
                 truncated: bool = False) -> None:
    if source is None:
        return
    source["pdf_text_extracted"] = ok
    source["pdf_text_chars"] = chars
    source["pdf_text_path"] = path
    source["pdf_text_truncated"] = truncated
    if quote:
        source["verified_quote"] = quote


def _extract_quote(text: str, topic: str) -> str:
    """Find a representative sentence that matches topic keywords."""
    keywords = _topic_keywords(topic)
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for kw in keywords:
        for sent in sentences:
            if kw.lower() in sent.lower() and 80 < len(sent) < 500:
                return sent.strip()
    return ""


def _topic_keywords(topic: str) -> list[str]:
    """Extract a small set of high-signal keywords from the topic string."""
    # Strip common Chinese/English stop-words and return distinctive tokens
    tokens = re.findall(r"[\u4e00-\u9fff\w]+", topic.lower())
    stop = {"的", "与", "和", "研究", "基于", "the", "of", "in", "on", "and", "a", "for", "to", "by"}
    return [t for t in tokens if t not in stop and len(t) > 2][:5]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
