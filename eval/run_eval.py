#!/usr/bin/env python3
r"""evidence-suite eval harness — auto-score script-checkable golden cases.

Runs eval/golden/*.json against the deterministic gate scripts and reports a
per-dimension pass/fail summary (markdown report → eval/report.md).

Two kinds of golden cases:
  - kind="script": auto-scored by this harness (citation closure, suspect domain,
    superseded source, manifest schema, evidence sufficiency, SSRF guard).
  - kind="manual": agent-behavior cases (prompt injection, source mismatch,
    contradiction handling, claim grounding, hallucination) that must be run by a
    real agent and scored by a human / second model — the harness prints a scoring
    sheet for these instead of guessing.

Usage:
  python eval/run_eval.py              # score + write eval/report.md
  python eval/run_eval.py --json       # machine-readable summary
  python eval/run_eval.py --verbose    # per-case stdout detail

Exit codes: 0 all auto cases pass; 1 any auto case fails; 2 usage error.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "shared" / "scripts"
GOLDEN = ROOT / "eval" / "golden"
REPORT = ROOT / "eval" / "report.md"

CHECK = SCRIPTS / "check_citations.py"
VALIDATE = SCRIPTS / "validate_sources.py"
VALIDATE_MANIFEST = SCRIPTS / "validate_manifest.py"
SUFFICIENCY = SCRIPTS / "check_evidence_sufficiency.py"
DOWNLOADS = SCRIPTS / "download_reference_files.py"


def _ensure_utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _run(script: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout, proc.stderr


def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


def _std_asserts(case: dict, rc: int, out: str) -> tuple[bool, list[str]]:
    problems: list[str] = []
    if rc != case.get("expect_rc"):
        problems.append(f"rc={rc} != expected {case.get('expect_rc')}")
    for needle in case.get("expect_stdout_has", []):
        if needle not in out:
            problems.append(f"stdout missing {needle!r}")
    return not problems, problems


def runner_citation_closure(case: dict, paths: dict):
    rc, out, _ = _run(CHECK, str(paths["draft.md"]), *case.get("extra_args", []), "--json")
    return _std_asserts(case, rc, out)


def runner_suspect_domain(case: dict, paths: dict):
    rc, out, _ = _run(VALIDATE, str(paths["corpus.json"]), "--json")
    return _std_asserts(case, rc, out)


def runner_superseded(case: dict, paths: dict):
    rc, out, _ = _run(VALIDATE, str(paths["corpus.json"]), "--json")
    return _std_asserts(case, rc, out)


def runner_manifest_schema(case: dict, paths: dict):
    rc, out, _ = _run(VALIDATE_MANIFEST, str(paths["manifest.json"]))
    return _std_asserts(case, rc, out)


def runner_sufficiency(case: dict, paths: dict):
    rc, out, _ = _run(SUFFICIENCY, str(paths["em.json"]), str(paths["vs.json"]), "--json")
    return _std_asserts(case, rc, out)


def runner_ssrf(case: dict, paths: dict):
    spec = importlib.util.spec_from_file_location("download_reference_files", DOWNLOADS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    blocked = mod.check_url_blocked(case["url"]) is not None
    expected = bool(case.get("expect_blocked"))
    return (blocked == expected,
            [] if blocked == expected else [f"blocked={blocked} != expected {expected}"])


RUNNERS = {
    "citation_closure": runner_citation_closure,
    "source_suspect_domain": runner_suspect_domain,
    "superseded_source": runner_superseded,
    "manifest_schema": runner_manifest_schema,
    "evidence_sufficiency": runner_sufficiency,
    "ssrf_guard": runner_ssrf,
}


def run_case(case: dict) -> dict:
    if case.get("kind") == "manual":
        return {"id": case["id"], "dimension": case["dimension"],
                "expectation": case["expectation"], "status": "manual",
                "problems": []}
    runner = RUNNERS.get(case["dimension"])
    if runner is None:
        return {"id": case["id"], "dimension": case["dimension"],
                "status": "error", "problems": [f"no runner for dimension {case['dimension']!r}"]}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        paths = {}
        for name, content in (case.get("fixtures") or {}).items():
            paths[name] = _write(tmp, name, content)
        try:
            ok, problems = runner(case, paths)
        except Exception as exc:
            return {"id": case["id"], "dimension": case["dimension"],
                    "status": "error", "problems": [str(exc)]}
    return {"id": case["id"], "dimension": case["dimension"],
            "expectation": case["expectation"],
            "status": "pass" if ok else "fail", "problems": problems}


def main() -> int:
    _ensure_utf8_streams()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cases = sorted(GOLDEN.glob("*.json"))
    results = []
    for path in cases:
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            results.append({"id": path.stem, "dimension": "?", "status": "error",
                            "problems": [f"unreadable: {exc}"]})
            continue
        results.append(run_case(case))

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    manual = sum(1 for r in results if r["status"] == "manual")
    errors = sum(1 for r in results if r["status"] == "error")

    if args.json:
        print(json.dumps({"total": len(results), "passed": passed, "failed": failed,
                          "manual": manual, "errors": errors, "results": results},
                         ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = {"pass": "✅", "fail": "❌", "manual": "⏭️", "error": "💥"}[r["status"]]
            expect = r.get("expectation", "")
            line = f"{mark} {r['id']} [{r['dimension']}]"
            if expect:
                line += f" → {expect}"
            print(line)
            if args.verbose:
                for p in r["problems"]:
                    print(f"      - {p}")
            elif r["status"] in ("fail", "error"):
                for p in r["problems"]:
                    print(f"      - {p}")
        print(f"\nauto: {passed} pass / {failed} fail / {errors} error | manual: {manual}")

    lines = [
        "# Eval Report", "",
        f"Generated: {json.dumps({'date': __import__('datetime').date.today().isoformat()})}", "",
        f"| 结果 | 数量 |", "| --- | --- |",
        f"| ✅ auto pass | {passed} |", f"| ❌ auto fail | {failed} |",
        f"| 💥 error | {errors} |", f"| ⏭️ manual (需 agent + 人/第二模型打分) | {manual} |", "",
        "## 逐用例", "",
        "| ID | 维度 | 期望 | 状态 | 问题 |", "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        expect = r.get("expectation", "-")
        problems = "; ".join(r["problems"]) if r["problems"] else "-"
        lines.append(f"| {r['id']} | {r['dimension']} | {expect} | {r['status']} | {problems} |")
    lines += ["", "> manual 用例为 agent 行为层（prompt injection / 来源不符 / 矛盾处理 / 论断对齐 / 幻觉），",
              "> 需真实 agent 运行 + 人工/第二模型核对期望行为后回填。"]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not args.json:
        print(f"\nreport → {REPORT}")
    return 1 if (failed or errors) else 0


if __name__ == "__main__":
    sys.exit(main())
