#!/usr/bin/env python3
"""Inspect an evidence-driven proposal workspace for basic closure signals.

Usage:
  inspect_pipeline.py <workspace>            basic diagnostics
  inspect_pipeline.py --gates <workspace>    stage-gate check (exit 1 if any hard gate missing)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

SOURCE_RE = re.compile(r"\[S(\d+)\]")
GAP_RE = re.compile(r"\[G(\d+)\]")
ROUND_SOURCE_RE = re.compile(r"\[R(\d+)-S(\d+)\]")
ROUND_GAP_RE = re.compile(r"\[R(\d+)-G(\d+)\]")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": str(exc)}


def count_refs(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    return (
        len(SOURCE_RE.findall(text)),
        len(GAP_RE.findall(text)),
        len(ROUND_SOURCE_RE.findall(text)),
        len(ROUND_GAP_RE.findall(text)),
    )

def _count_gap_items(data: dict) -> int:
    for key in ("global_gaps", "unsupported_but_needed_claims", "evidence_gaps"):
        value = data.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _has_nonempty_txt(dir_path: Path) -> bool:
    if not dir_path.is_dir():
        return False
    for txt in dir_path.glob("*.txt"):
        if txt.stat().st_size > 0:
            return True
    return False


def _humanizer_accounted(root: Path) -> bool:
    """True if stage 7b (humanizer) was run OR explicitly skipped.

    Marker files: `.w7_humanizer.DONE` / `.w7_humanizer.SKIPPED`
    in the workspace root (written by w7_humanizer prompt). Falls back to
    scanning 11_定稿.md for a humanizer run/skip trace line if markers absent.
    """
    if root.joinpath(".w7_humanizer.DONE").exists() or root.joinpath(".w7_humanizer.SKIPPED").exists():
        return True
    draft = root / "11_定稿.md"
    if draft.is_file():
        try:
            text = draft.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            text = ""
        return bool(re.search(r"humanizer|文风修复", text))
    return False


def _access_status_populated(corpus: Path) -> bool:
    try:
        data = json.loads(corpus.read_text(encoding="utf-8"))
    except Exception:
        return False
    sources = data.get("sources", [])
    if not sources:
        return False
    return all(isinstance(s.get("access_status"), str) and s["access_status"].strip() for s in sources)


def check_gates(root: Path) -> int:
    """Stage-gate check. Return 0 if all hard gates pass, 1 if any missing."""
    print(f"Stage gates: {root}")
    corpus = root / "04_validated_sources.json"
    gates = [
        ("0 ", "00_topic.md", lambda: root.joinpath("00_topic.md").is_file(), "hard"),
        ("1 ", "02_raw_sources.json", lambda: root.joinpath("02_raw_sources.json").is_file(), "hard"),
        ("2 ", "03_audit_report.md", lambda: root.joinpath("03_audit_report.md").is_file(), "hard"),
        ("3 ", "04_validated_sources.json", lambda: corpus.is_file(), "hard"),
        ("3a", "reference_files/*.pdf (>=1)", lambda: any(root.joinpath("reference_files").glob("*.pdf")), "hard"),
        ("3b", "语料 access_status 无空", lambda: _access_status_populated(corpus), "hard"),
        ("3c", "pdf_text/*.txt (>=1 non-empty)", lambda: _has_nonempty_txt(root / "pdf_text"), "hard"),
        ("4 ", "06_evidence_map.json", lambda: root.joinpath("06_evidence_map.json").is_file(), "hard"),
        ("4b", "07_honest_assessment.md", lambda: root.joinpath("07_honest_assessment.md").is_file(), "hard"),
        ("5 ", "08_初稿.md", lambda: root.joinpath("08_初稿.md").is_file(), "hard"),
        ("6 ", "10_review.md", lambda: root.joinpath("10_review.md").is_file(), "hard"),
        ("7 ", "11_定稿.md", lambda: root.joinpath("11_定稿.md").is_file(), "hard"),
        ("7b", "humanizer 已跑或显式跳过（标记/文档痕迹）", lambda: _humanizer_accounted(root), "optional"),
        ("8 ", "12_外部专家意见.md", lambda: root.joinpath("12_外部专家意见.md").is_file(), "optional"),
        ("9 ", "14_专家修订稿.md", lambda: root.joinpath("14_专家修订稿.md").is_file(), "optional"),
        ("10", "*.pdf 导出", lambda: bool(list(root.glob("*.pdf"))), "optional"),
    ]
    missing_hard = []
    for label, name, check, kind in gates:
        try:
            ok = check()
        except Exception:
            ok = False
        if kind == "hard":
            status = "OK" if ok else "MISSING"
            if not ok:
                missing_hard.append(f"{label} {name}")
        else:
            status = "ok (optional)" if ok else "n/a (optional)"
        print(f"  [{label}] {name:<44} {status}")
    if missing_hard:
        print("GATES: FAIL — 硬门禁缺失:", "; ".join(missing_hard))
        return 1
    print("GATES: PASS — 硬门禁全部通过")
    return 0



def main() -> int:
    _ensure_utf8_streams()
    args = list(sys.argv[1:])
    if args and args[0] == "--gates":
        if len(args) != 2:
            print("Usage: inspect_pipeline.py --gates <workspace>")
            return 2
        root = Path(args[1]).resolve()
        if not root.exists():
            print(f"Workspace not found: {root}")
            return 2
        return check_gates(root)
    if len(args) != 1:
        print("Usage: inspect_pipeline.py <workspace> | --gates <workspace>")
        return 2

    root = Path(sys.argv[1]).resolve()
    if not root.exists():
        print(f"Workspace not found: {root}")
        return 2

    raw = root / "02_raw_sources.json"
    validated = root / "04_validated_sources.json"
    # Evidence map may use 05 or 06 prefix depending on naming convention
    evidence_map = root / "06_evidence_map.json"
    if not evidence_map.exists():
        evidence_map = root / "05_evidence_map.json"
    drafts = sorted(root.glob("*.md")) + sorted(root.glob("*/*.md"))

    print(f"Workspace: {root}")
    for path in [raw, validated, evidence_map]:
        if not path.exists():
            print(f"MISSING {path.name}")
            continue
        data = load_json(path)
        if "_error" in data:
            print(f"INVALID {path.name}: {data['_error']}")
            continue
        if not isinstance(data, dict):
            print(f"INVALID {path.name}: 顶层应为对象（dict），实际为 {type(data).__name__}")
            continue
        if path.name.endswith("sources.json"):
            print(f"OK {path.name}: sources={len(data.get('sources', []))}, gaps={len(data.get('evidence_gaps', []))}")
        elif path.name in ("05_evidence_map.json", "06_evidence_map.json"):
            sections = data.get("sections", [])
            gap_items = _count_gap_items(data)
            print(
                f"OK {path.name}: "
                f"sections={len(sections)}, "
                f"gaps={gap_items}"
            )

    if not drafts:
        print("No markdown drafts/reviews found")
    for path in drafts:
        s_refs, g_refs, round_s_refs, round_g_refs = count_refs(path)
        rel = path.relative_to(root)
        lines = path.read_text(encoding="utf-8", errors="ignore").count("\n") + 1
        print(
            f"MD {rel}: lines={lines}, "
            f"S_refs={s_refs}, G_refs={g_refs}, "
            f"round_S_refs={round_s_refs}, round_G_refs={round_g_refs}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
