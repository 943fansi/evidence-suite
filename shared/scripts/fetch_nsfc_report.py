#!/usr/bin/env python3
"""Fetch NSFC project completion reports (结题报告) from the NSFC portal.

NSFC's knowledge-service portal (https://kd.nsfc.cn, id `nsfc_npd` in the
source registry) serves completion reports as per-page images. Responses are
encrypted with DES-ECB (key `IFROMC86`, PKCS7 padding, base64-encoded); image
URLs are signed and short-lived, refreshed on every request.

Mechanism (mirrors the NsfcReportExport browser-extension behaviour):
  1. (optional) search by 批准号 → report id:
     POST /api/baseQuery/completionQueryResultsData   (plain JSON, encrypted reply)
  2. project info:  POST /api/baseQuery/conclusionProjectInfo/<report_id>
  3. per-page image URL: POST /api/baseQuery/completeProjectReport
     body `id=<report_id>&index=<n>` (form-encoded, encrypted reply → data.url)
  4. pagination: a fresh URL is requested per page and HEAD-checked
     immediately; the first definitive 404 / empty URL is the end
     (maxpage cached in maxpage.json so re-runs skip probing).
  5. page images are GET-ed and saved; optionally rebuilt into a PDF
     (PyMuPDF) and OCR-ed (easyocr) into ocr_full.txt.

Dependencies:
  - requests, pycryptodome (required)
  - PyMuPDF (--pdf), easyocr + numpy (--ocr, heavy; needs torch)

Usage:
  python scripts/fetch_nsfc_report.py --approval-no 52069029 -o nsfc_52069029 --pdf
  python scripts/fetch_nsfc_report.py --keyword "管道损伤识别" -o nsfc_pipe --pdf --ocr
  python scripts/fetch_nsfc_report.py --report-id 573abc3fdca62aba9cb2b848dbe0b03d -o nsfc_xxx --pdf --ocr

Mechanism is topic-independent: search takes any keyword (批准号 / 项目名称 /
关键词) via the portal's fuzzy search; a real funded project will be located and
its completion report downloaded the same way.

⚠️ SECURITY / TERMS NOTICE
This script accesses NSFC's public completion-report data by reversing the
portal's browser-extension API (kd.nsfc.cn). The DES-ECB key `IFROMC86` is a
response-obfuscation constant recovered from the open-source NsfcReportExport
extension — it is NOT a credential and grants no authenticated access. The
fetched data is publicly viewable 结题报告. Before use:
  1. Confirm your use complies with the NSFC portal terms of service.
  2. The API, key, or signed-URL scheme may change or stop working at any time.
  3. Keep request rates low (defaults sleep + backoff) to avoid load.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

import requests
from Crypto.Cipher import DES

BASE = "https://kd.nsfc.cn"
KEY = b"IFROMC86"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0 Safari/537.36")


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def decrypt(data: str) -> str:
    """Return plaintext if already JSON, otherwise DES-ECB decrypt (PKCS7)."""
    stripped = data.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    try:
        ct = base64.b64decode(stripped)
        if len(ct) % 8 != 0:
            return stripped
        pt = DES.new(KEY, DES.MODE_ECB).decrypt(ct)
        pad = pt[-1]
        if 1 <= pad <= 8:
            pt = pt[:-pad]
        return pt.decode("utf-8", errors="replace")
    except Exception:
        return stripped


class NSFCClient:
    def __init__(self, report_id: str, retries: int = 4):
        self.report_id = report_id
        self.retries = retries
        self.session = requests.Session()
        self.api_headers = {
            "User-Agent": _UA,
            "accept": "application/json, text/plain, */*",
            "content-type": "application/x-www-form-urlencoded",
            "origin": BASE,
            "referer": f"{BASE}/finalDetails?id={report_id}",
        }
        self.img_headers = {
            "User-Agent": _UA,
            "Referer": f"{BASE}/finalDetails?id={report_id}",
        }

    def _post(self, path: str, *, data: str | None = None, payload: dict | None = None,
              json_ct: bool = False) -> str | None:
        headers = dict(self.api_headers)
        if json_ct:
            headers["content-type"] = "application/json"
        for attempt in range(self.retries):
            try:
                r = self.session.post(
                    f"{BASE}{path}", headers=headers,
                    data=data if not json_ct else None,
                    json=payload if json_ct else None,
                    timeout=(8, 40),
                )
                return r.text
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        return None

    def report_page_url(self, index: int) -> str | None:
        """Fresh signed image URL for page `index`, or None when the API returns nothing."""
        body = f"id={self.report_id}&index={index}"
        for _ in range(self.retries):
            raw = self._post("/api/baseQuery/completeProjectReport", data=body)
            if raw is None:
                continue
            text = decrypt(raw)
            if text.startswith("{"):
                try:
                    j = json.loads(text)
                except Exception:
                    time.sleep(2.0)
                    continue
                if (j.get("code") or 200) != 200:
                    time.sleep(2.0)
                    continue
                url = (j.get("data") or {}).get("url")
                return url if url else None
            time.sleep(2.0)
        return None

    def project_info(self) -> dict | None:
        raw = self._post(f"/api/baseQuery/conclusionProjectInfo/{self.report_id}")
        if not raw:
            return None
        text = decrypt(raw)
        if not text.startswith("{"):
            return None
        try:
            return json.loads(text)
        except Exception:
            return None

    def _head_ok(self, url: str) -> bool | None:
        """True=live, False=404 (end), None=indeterminate after retries."""
        full = BASE + url
        for _ in range(self.retries):
            try:
                r = self.session.head(full, headers=self.img_headers, timeout=(8, 30))
                if r.status_code in (200, 403, 405):  # 403/405: server rejects HEAD → verify via GET later
                    return True
                if r.status_code == 404:
                    return False
                time.sleep(1.0)
            except Exception:
                time.sleep(1.5)
        return None

    def _get_ok(self, url: str) -> bytes | None:
        full = BASE + url
        for _ in range(5):
            try:
                r = self.session.get(full, headers=self.img_headers, timeout=(10, 50))
                if r.status_code == 200 and len(r.content) > 1000:
                    return r.content
                if r.status_code == 404:
                    return None
                if 400 <= r.status_code < 500:
                    return None
                time.sleep(1.2)
            except Exception:
                time.sleep(1.5)
        return None

    def probe_maxpage(self, limit: int, sleep_s: float) -> int:
        """Scan 1..limit; first index with no URL (x3 confirm) or HEAD 404 is maxpage."""
        maxpage = None
        for index in range(1, limit + 1):
            u = self.report_page_url(index)
            if u is None:
                still = [self.report_page_url(index) for _ in range(2)]
                if all(x is None for x in still):
                    maxpage = index
                    print(f"  maxpage via no-url: {index}", flush=True)
                    break
                u = next((x for x in still if x), None)
            ok = self._head_ok(u)
            if ok is False:
                maxpage = index
                print(f"  maxpage via HEAD404: {index}", flush=True)
                break
            time.sleep(sleep_s)
        if maxpage is None:
            maxpage = limit + 1
            print(f"  maxpage not found within limit, assuming {maxpage}", flush=True)
        return maxpage


def search_reports(keyword: str) -> list[dict]:
    """Fuzzy-search the completion-query API by keyword (批准号 / 题目 / 关键词).

    ``data.resultsData`` is a list of positional arrays:
    [0]=report id, [1]=title, [2]=批准号, [3]=项目类型, [4]=依托单位,
    [5]=负责人, [7]=批准年度, [15]=结题年度.
    """
    payload = {
        "complete": True, "fuzzyKeyword": keyword, "isFuzzySearch": True,
        "conclusionYear": "", "dependUnit": "", "keywords": "",
        "pageNum": 0, "pageSize": 10, "projectType": "", "projectTypeName": "",
        "code": "", "ratifyYear": "", "order": "", "ordering": "desc",
        "codeScreening": "", "dependUnitScreening": "", "keywordsScreening": "",
        "projectTypeNameScreening": "",
    }
    headers = {
        "User-Agent": _UA,
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": BASE,
        "referer": f"{BASE}/finalSearchList?s={keyword}",
    }
    out: list[dict] = []
    for attempt in range(4):
        try:
            r = requests.post(f"{BASE}/api/baseQuery/completionQueryResultsData",
                              headers=headers, json=payload, timeout=(8, 40))
            if r.status_code != 200:
                if 400 <= r.status_code < 500 and r.status_code != 429:
                    print(f"  search failed: completionQueryResultsData HTTP {r.status_code}", file=sys.stderr)
                    return out
                raise RuntimeError(f"completionQueryResultsData HTTP {r.status_code}")
            text = decrypt(r.text)
            j = json.loads(text)
            data = j.get("data") or {}
            rows = data.get("resultsData") or []
            out = []
            for row in rows:
                if isinstance(row, dict):
                    out.append({"id": row.get("id"), "title": row.get("title") or row.get("name"),
                                "projectNo": row.get("projectNo") or row.get("prjNo")})
                elif isinstance(row, (list, tuple)) and row:
                    out.append({"id": row[0],
                                "title": row[1] if len(row) > 1 else None,
                                "projectNo": row[2] if len(row) > 2 else None})
            if out:
                return out
        except Exception as exc:
            if attempt == 3:
                print(f"  search failed after 4 attempts: {exc}", file=sys.stderr)
        if attempt < 3:  # empty / error → back off and retry (portal fuzzy search can be flaky)
            time.sleep(3.0 + 1.5 * attempt)
    return out


def rebuild_pdf(pages_dir: Path, maxpage: int, out_pdf: Path) -> None:
    import fitz  # PyMuPDF
    doc = fitz.open()
    for i in range(1, maxpage):
        fn = pages_dir / f"page_{i:03d}.png"
        if not fn.exists():
            continue
        img = fitz.open(fn)
        rect = img[0].rect
        img.close()
        page = doc.new_page(width=rect.width, height=rect.height)
        page.insert_image(page.rect, filename=str(fn))
    doc.save(str(out_pdf), deflate=True)
    print(f"  PDF saved: {out_pdf} ({doc.page_count} pages)")
    doc.close()


def ocr_pages(pages_dir: Path, maxpage: int, out_txt: Path, gpu: bool = False) -> None:
    import easyocr
    reader = easyocr.Reader(["ch_sim", "en"], gpu=gpu, verbose=False)
    all_text = []
    t0 = time.time()
    for i in range(1, maxpage):
        fn = pages_dir / f"page_{i:03d}.png"
        if not fn.exists():
            all_text.append(f"===== PAGE {i} (missing) =====\n")
            continue
        try:
            res = reader.readtext(str(fn), detail=0, paragraph=False)
            text = "\n".join(res)
        except Exception as exc:
            text = f"[OCR ERROR: {exc}]"
        all_text.append(f"===== PAGE {i} ({fn.name}) =====\n{text}\n")
        if i % 10 == 0:
            print(f"  ocr {i}/{maxpage - 1} in {time.time() - t0:.0f}s", flush=True)
    out_txt.write_text("\n".join(all_text), encoding="utf-8")
    print(f"  OCR saved: {out_txt} (total {sum(len(t) for t in all_text):,} chars)")


def main(argv: list[str]) -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-no", help="NSFC 批准号 (e.g. 52069029) to locate the report via search")
    parser.add_argument("--keyword", help="Search keyword (项目名称/关键词/批准号) to locate the report")
    parser.add_argument("--report-id", help="Report id (finalDetails?id=...) to skip search")
    parser.add_argument("-o", "--out-dir", type=Path, help="Output directory (default: ./nsfc_report_<key>)")
    parser.add_argument("--maxpage", type=int, default=None, help="Skip probing, use known maxpage")
    parser.add_argument("--limit", type=int, default=120, help="Upper bound for probing (default 120)")
    parser.add_argument("--sleep", type=float, default=0.4, help="Seconds between page fetches (default 0.4)")
    parser.add_argument("--pdf", action="store_true", help="Rebuild pages into a PDF (needs PyMuPDF)")
    parser.add_argument("--ocr", action="store_true", help="OCR pages into ocr_full.txt (needs easyocr)")
    parser.add_argument("--gpu", action="store_true", help="Use GPU for OCR (default: CPU)")
    args = parser.parse_args(argv)

    if not args.report_id and not args.approval_no and not args.keyword:
        print("ERROR: need --approval-no, --keyword, or --report-id", file=sys.stderr)
        return 2

    report_id = args.report_id
    if not report_id:
        search_key = args.keyword or args.approval_no
        rows = search_reports(search_key)
        if not rows:
            print(f"ERROR: no completion report found for {search_key}", file=sys.stderr)
            return 1
        print(f"Matched {len(rows)} report(s):")
        for i, r in enumerate(rows):
            no = r.get("projectNo") or ""
            print(f"  [{i}] {r['id']}  {r['title']}  (批准号: {no})")

        # When --approval-no was given, the fuzzy search may return several rows;
        # pick the exact 批准号 match instead of blindly taking rows[0].
        idx = None
        if args.approval_no:
            exact = [i for i, r in enumerate(rows)
                     if (r.get("projectNo") or "") == args.approval_no]
            if len(exact) == 1:
                idx = exact[0]
            elif len(exact) > 1:
                print(f"ERROR: {len(exact)} reports share 批准号 {args.approval_no}; "
                      f"use --report-id to disambiguate", file=sys.stderr)
                return 2
            else:
                print(f"ERROR: no report matched 批准号 {args.approval_no} exactly; "
                      f"returned rows are fuzzy matches only", file=sys.stderr)
                return 2

        if idx is None:
            if len(rows) > 1:
                try:
                    choice = input("Select report index (Enter = first): ").strip()
                    idx = int(choice) if choice else 0
                except (ValueError, EOFError):
                    # Non-interactive stdin (piped/CI) → refuse to guess instead of
                    # silently picking rows[0].
                    print("ERROR: cannot prompt for report selection in non-interactive "
                          "stdin; pass --report-id explicitly", file=sys.stderr)
                    return 2
                if not 0 <= idx < len(rows):
                    print(f"ERROR: invalid index {idx}", file=sys.stderr)
                    return 2
            else:
                idx = 0
        report_id = rows[idx]["id"]

    out_dir = args.out_dir or Path(f"nsfc_report_{report_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir
    client = NSFCClient(report_id)

    info = client.project_info()
    if info:
        info_file = out_dir / "project_info.json"
        info_file.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Project info → {info_file.name}")

    maxpage = args.maxpage
    if maxpage is None:
        cached = out_dir / "maxpage.json"
        if cached.exists():
            try:
                maxpage = int(json.loads(cached.read_text(encoding="utf-8")).get("maxpage"))
                print(f"Using cached maxpage={maxpage} from {cached.name}")
            except Exception:
                maxpage = None
    if maxpage is None:
        print("Probing maxpage...")
        maxpage = client.probe_maxpage(args.limit, args.sleep)
        (out_dir / "maxpage.json").write_text(
            json.dumps({"maxpage": maxpage}, ensure_ascii=False), encoding="utf-8")

    manifest = {}
    manifest_file = out_dir / "manifest.json"
    if manifest_file.exists():
        try:
            manifest = {int(k): v for k, v in json.loads(manifest_file.read_text(encoding="utf-8")).items()}
        except Exception:
            manifest = {}

    missing = [i for i in range(1, maxpage) if i not in manifest]
    print(f"Downloading pages 1..{maxpage - 1}: {len(missing)} to fetch, {len(manifest)} already have")
    for index in missing:
        u = client.report_page_url(index)
        if not u:
            print(f"  index={index} no url → stop", flush=True)
            break
        if client._head_ok(u) is False:
            print(f"  index={index} HEAD404 → stop", flush=True)
            break
        data = client._get_ok(u)
        if data is None:
            for _ in range(3):
                u2 = client.report_page_url(index)
                if u2:
                    data = client._get_ok(u2)
                    if data:
                        break
        if data:
            fn = pages_dir / f"page_{index:03d}.png"
            fn.write_bytes(data)
            manifest[index] = str(fn)
            print(f"  index={index} OK {len(data)}B", flush=True)
        else:
            print(f"  index={index} FAILED", flush=True)
        time.sleep(args.sleep)

    manifest_file.write_text(
        json.dumps({str(k): v for k, v in manifest.items()}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(f"manifest pages: {len(manifest)}")

    if args.pdf:
        rebuild_pdf(out_dir, maxpage, out_dir / f"NSFC_{args.approval_no or report_id}_结题报告.pdf")
    if args.ocr:
        ocr_pages(out_dir, maxpage, out_dir / "ocr_full.txt", gpu=args.gpu)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))