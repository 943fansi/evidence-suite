#!/usr/bin/env python3
"""Download public PDF reference files from evidence JSON corpora.

The script keeps filenames aligned with citation IDs, for example:
S1_Assessing_and_Managing_Cable_Ageing.pdf
R2-S1_Nuclear_Power_Plant_Ageing_Management.pdf
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PDF_MAGIC = b"%PDF"
DEFAULT_ROLES = {"core", "supporting"}
ID_KEYS = ("id", "source_id")
TITLE_KEYS = ("title", "title_or_name", "name")
ROLE_KEYS = ("validated_role", "evidence_role", "source_role", "role")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def iter_sources(obj: Any):
    """Yield source-like dictionaries from common evidence-corpus shapes."""
    if isinstance(obj, dict):
        if any(k in obj for k in ID_KEYS):
            yield obj
        for key in (
            "sources",
            "core_sources",
            "supporting_sources",
            "context_only_sources",
            "lead_only_sources",
            "needs_verification_sources",
        ):
            value = obj.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield from iter_sources(item)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_sources(item)


def first_value(source: dict[str, Any], keys: tuple[str, ...], default: str = "") -> str:
    for key in keys:
        value = source.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def sanitize_filename_part(text: str, max_len: int = 90) -> str:
    text = re.sub(r"[\\/:*?\"<>|]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace(" ", "_")
    text = re.sub(r"_+", "_", text)
    return text[:max_len].strip("._") or "untitled"


def build_filename(source_id: str, title: str) -> str:
    safe_id = sanitize_filename_part(source_id, max_len=24)
    safe_title = sanitize_filename_part(title, max_len=96)
    return f"{safe_id}_{safe_title}.pdf"


BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fix_pdf_url(url: str) -> str | None:
    """Transform known repository landing-page URLs into direct PDF links."""
    # OSTI biblio -> servlets/purl
    m = re.match(r"https://www\.osti\.gov/biblio/(\d+)", url)
    if m:
        return f"https://www.osti.gov/servlets/purl/{m.group(1)}"

    # OSTI servlets/purl already a direct link
    if "osti.gov/servlets/purl/" in url:
        return url

    # MDPI HTML article page -> PDF (ISSN may contain hyphens)
    m = re.match(r"(https://www\.mdpi\.com/[\d\-]+/\d+/\d+/\d+)/?$", url)
    if m:
        return m.group(1) + "/pdf"

    # HAL record -> document
    if "hal.science/" in url and "/document" not in url:
        return url.rstrip("/") + "/document"

    # Nature article -> PDF
    m = re.match(r"(https://www\.nature\.com/articles/[^/]+)/?$", url)
    if m:
        return m.group(1) + ".pdf"

    # IOP article -> PDF
    m = re.match(r"(https://iopscience\.iop\.org/article/10\.1088/[^/]+)/?$", url)
    if m:
        return m.group(1) + "/pdf"

    # BioMed Central / Springer Nature open-access articles -> counter/pdf
    m = re.match(
        r"https://(\w+)\.biomedcentral\.com/articles/(10\.\d+/[\w-]+)", url
    )
    if m:
        return f"https://{m.group(1)}.biomedcentral.com/counter/pdf/{m.group(2)}.pdf"

    # Frontiers article page -> PDF
    m = re.match(
        r"(https://www\.frontiersin\.org/articles/(?:10\.\d+/[\w\.-]+))", url
    )
    if m:
        return m.group(1) + "/pdf"

    # PMC article -> PDF (try direct NIH link)
    m = re.match(r"https://pmc\.ncbi\.nlm\.nih\.gov/articles/(PMC\d+)/?", url)
    if m:
        return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{m.group(1)}/pdf/main.pdf"

    return None


def download(url: str, timeout: int) -> tuple[bytes, str]:
    # Try original URL, then fixed URL if available
    urls_to_try = [url]
    fixed = fix_pdf_url(url)
    if fixed and fixed != url:
        urls_to_try.append(fixed)

    last_error = None
    for attempt_url in urls_to_try:
        request = Request(
            attempt_url,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "application/pdf,*/*;q=0.8",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                data = response.read()
            return data, content_type
        except Exception as exc:
            last_error = exc
    raise last_error  # type: ignore[misc]


def download_with_curl(url: str, timeout: int) -> tuple[bytes, str]:
    curl = shutil.which("curl") or shutil.which("curl.exe")
    if not curl:
        raise RuntimeError("curl is not available")

    # Try original URL, then fixed URL if available
    urls_to_try = [url]
    fixed = fix_pdf_url(url)
    if fixed and fixed != url:
        urls_to_try.append(fixed)

    with NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    last_error = None
    for attempt in range(2):  # retry once on network errors
        for attempt_url in urls_to_try:
            try:
                command = [
                    curl,
                    "--location",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    str(timeout),
                    "--user-agent",
                    BROWSER_UA,
                    "--output",
                    str(tmp_path),
                    attempt_url,
                ]
                subprocess.run(command, check=True, capture_output=True, text=True, errors="replace")
                data = tmp_path.read_bytes()
                try:
                    tmp_path.unlink()
                except FileNotFoundError:
                    pass
                return data, "application/pdf; downloader=curl"
            except Exception as exc:
                last_error = exc
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except FileNotFoundError:
                        pass
        # If first attempt failed, retry with double timeout
        if attempt == 0:
            timeout *= 2

    raise last_error  # type: ignore[misc]


def _is_valid_pdf(path: Path) -> bool:
    """Cheap sanity check: a real PDF starts with the %PDF magic bytes."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(5)
        return head.startswith(PDF_MAGIC)
    except OSError:
        return False


def role_allowed(source: dict[str, Any], allowed_roles: set[str], include_all: bool) -> bool:
    if include_all:
        return True
    role = first_value(source, ROLE_KEYS, default="").strip()
    return role in allowed_roles if role else True


def collect_sources(paths: list[Path]) -> list[dict[str, Any]]:
    """Collect sources from multiple JSON files. Merge URLs across files:
    if a source from one file has a URL but the same-ID source from another
    file does not, inherit the URL.
    """
    url_map: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []

    # First pass: harvest all URLs by source_id for cross-file fallback
    for path in paths:
        data = load_json(path)
        for source in iter_sources(data):
            source_id = first_value(source, ID_KEYS)
            url = str(source.get("url", "")).strip()
            if source_id and url and source_id not in url_map:
                url_map[source_id] = url

    # Second pass: collect sources, filling missing URLs from the map
    for path in paths:
        data = load_json(path)
        for source in iter_sources(data):
            source_id = first_value(source, ID_KEYS)
            url = str(source.get("url", "")).strip()
            # Cross-file URL fallback: use URL from another file if this source lacks one
            if source_id and not url and source_id in url_map:
                url = url_map[source_id]
            if not source_id:
                continue
            if not url:
                continue
            key = (source_id, url)
            if key in seen:
                continue
            seen.add(key)
            normalized = dict(source)
            normalized["url"] = url
            normalized["_input_file"] = str(path)
            sources.append(normalized)
    return sources


def write_manifest(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    manifest_json = out_dir / "manifest.json"
    manifest_csv = out_dir / "manifest.csv"
    manifest_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    fieldnames = [
        "id",
        "title",
        "url",
        "role",
        "status",
        "filename",
        "content_type",
        "bytes",
        "reason",
        "input_file",
    ]
    with manifest_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _update_sources_corpus(rows: list[dict[str, Any]]) -> None:
    """Write access_status back into each input corpus JSON based on download outcome.

    Mapping: downloaded→confirmed, exists→confirmed, stale→(re-downloaded, see
    outcome), role_excluded→(unchanged — no network check was ever performed,
    so the source keeps its prior status), dry_run→(unchanged), failed→unavailable.
    """
    by_file: dict[str, dict[str, str]] = {}
    for row in rows:
        input_file = row.get("input_file", "")
        if not input_file:
            continue
        status = row.get("status")
        if status in ("downloaded", "exists"):
            value = "confirmed"
        elif status == "not_pdf":
            value = "web_accessible"
        elif status == "failed":
            value = "unavailable"
        else:
            # role_excluded / dry_run / pending / stale-unknown → leave unchanged
            continue
        by_file.setdefault(input_file, {})[str(row["id"])] = value

    for input_file, status_map in by_file.items():
        path = Path(input_file)
        try:
            data = load_json(path)
        except Exception:
            continue
        changed = 0
        for source in iter_sources(data):
            sid = first_value(source, ID_KEYS)
            if sid in status_map:
                source["access_status"] = status_map[sid]
                changed += 1
        if changed:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  access_status updated: {path.name} ({changed} sources)")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_files", nargs="+", type=Path, help="Evidence JSON files to scan.")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=Path("reference_files"),
        help="Directory where PDFs and manifests are saved.",
    )
    parser.add_argument(
        "--roles",
        default="core,supporting",
        help="Comma-separated evidence roles to download by default.",
    )
    parser.add_argument("--include-all", action="store_true", help="Download all source roles.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing PDFs.")
    parser.add_argument("--dry-run", action="store_true", help="Only write manifest; do not download.")
    parser.add_argument(
        "--no-curl-fallback",
        action="store_true",
        help="Disable curl fallback when Python's downloader fails.",
    )
    parser.add_argument("--timeout", type=int, default=30, help="Network timeout in seconds.")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between downloads in seconds.")
    parser.add_argument(
        "--update-sources",
        action="store_true",
        help="Write access_status back into the input corpus JSON(s): "
        "downloaded→confirmed, not_pdf→web_accessible, failed→unavailable. "
        "Requires the row's `_input_file` bookkeeping used by collect_sources().",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    allowed_roles = {role.strip() for role in args.roles.split(",") if role.strip()}
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    sources = collect_sources(args.json_files)

    for source in sources:
        source_id = first_value(source, ID_KEYS)
        title = first_value(source, TITLE_KEYS, default=source_id)
        url = str(source.get("url", "")).strip()
        role = first_value(source, ROLE_KEYS, default="")
        filename = build_filename(source_id, title)
        target = out_dir / filename
        row = {
            "id": source_id,
            "title": title,
            "url": url,
            "role": role,
            "status": "pending",
            "filename": filename,
            "content_type": "",
            "bytes": 0,
            "reason": "",
            "input_file": source.get("_input_file", ""),
        }

        if not role_allowed(source, allowed_roles, args.include_all):
            row["status"] = "role_excluded"
            row["reason"] = f"role not selected: {role}"
            rows.append(row)
            continue

        if args.dry_run:
            # Dry-run must never mutate the filesystem: no magic-byte check, no unlink.
            row["status"] = "dry_run"
            rows.append(row)
            continue

        if target.exists() and not args.overwrite:
            if _is_valid_pdf(target):
                row["status"] = "exists"
                row["bytes"] = target.stat().st_size
                rows.append(row)
                continue
            # Existing file is corrupt/HTML → re-download instead of trusting it
            row["status"] = "stale"
            row["reason"] = "existing file lacks %PDF magic — re-downloading"
            try:
                target.unlink()
            except OSError:
                pass

        try:
            try:
                data, content_type = download(url, timeout=args.timeout)
            except Exception as primary_exc:
                if args.no_curl_fallback:
                    raise
                try:
                    data, content_type = download_with_curl(url, timeout=args.timeout)
                except Exception as fallback_exc:
                    raise RuntimeError(
                        f"python downloader failed: {primary_exc}; "
                        f"curl fallback failed: {fallback_exc}"
                    ) from fallback_exc
            row["content_type"] = content_type
            if not data.startswith(PDF_MAGIC):
                row["status"] = "not_pdf"
                row["reason"] = (
                    f"not a PDF: magic_bytes={data[:4]!r}, "
                    f"content_type={content_type or 'unknown'}"
                )
            else:
                target.write_bytes(data)
                row["status"] = "downloaded"
                row["bytes"] = len(data)
        except Exception as exc:
            row["status"] = "failed"
            row["reason"] = str(exc)

        rows.append(row)
        if args.sleep:
            time.sleep(args.sleep)

    write_manifest(out_dir, rows)
    if args.update_sources:
        _update_sources_corpus(rows)
    downloaded = sum(1 for row in rows if row["status"] == "downloaded")
    existing = sum(1 for row in rows if row["status"] == "exists")
    not_pdf = sum(1 for row in rows if row["status"] == "not_pdf")
    role_excluded = sum(1 for row in rows if row["status"] == "role_excluded")
    failed = sum(1 for row in rows if row["status"] == "failed")
    print(
        f"references={len(rows)} downloaded={downloaded} "
        f"existing={existing} not_pdf={not_pdf} role_excluded={role_excluded} "
        f"failed={failed} out={out_dir}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
