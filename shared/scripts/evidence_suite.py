#!/usr/bin/env python3
r"""evidence-suite 统一 CLI 入口（PR-02）.

把 shared/scripts/ 下分散的确定性工具封装为 `evidence-suite <subcommand>`，
子命令通过 subprocess 代理到对应脚本，逐字透传剩余参数——不重复实现任何逻辑，
退出码 / stdout / stderr 与直接调用脚本完全一致。

子命令与脚本映射：
  validate      → validate_manifest.py          （manifest 契约校验）
  finalize      → finalize_draft.py             （定稿净化 + manifest 产出）
  check         → check_citations.py            （引用闭合）
  sufficiency   → check_evidence_sufficiency.py （claim 级证据充分性）
  framework     → check_framework_depth.py      （框架深度门）
  audit-provenance → audit_provenance.py        （机器可审计性门，0.2.1 推荐名）
  audit         → audit_provenance.py           （【已弃用别名】0.2.0 旧名 → audit-provenance）
  brief         → build_evidence_brief.py       （L1 Evidence Brief）
  download      → download_reference_files.py   （来源 PDF 下载，含 SSRF/审计）
  extract       → extract_pdf_text.py           （PDF 抽文本）
  validate-src  → validate_sources.py           （语料自检）
  select        → select_sources.py             （Registry 选源）
  export pdf    → export_pdf.py                 （PDF 导出，--manifest 可标注 review_kind）
  export docx   → export_docx.py                （DOCX 导出，--manifest 可标注 review_kind）
  provenance    → export_provenance.py          （Provenance 五件套）
  probe         → probe_capabilities.py         （运行时能力探测）
  init-case     → init_case.py                  （research_case 工作区脚手架）

用法示例：
  python shared/scripts/evidence_suite.py validate out/manifest.json
  python shared/scripts/evidence_suite.py sufficiency 06_evidence_map.json 04_validated_sources.json --json
  python shared/scripts/evidence_suite.py export pdf 11_定稿.md --manifest out/manifest.json
  python shared/scripts/evidence_suite.py --list
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent

COMMANDS = {
    "validate": ("validate_manifest.py", False),
    "finalize": ("finalize_draft.py", False),
    "check": ("check_citations.py", False),
    "sufficiency": ("check_evidence_sufficiency.py", False),
    "framework": ("check_framework_depth.py", False),
    "audit-provenance": ("audit_provenance.py", False),  # F4 (P0): canonical name
    "audit": ("audit_provenance.py", False),            # legacy alias (deprecated)
    "brief": ("build_evidence_brief.py", False),
    "download": ("download_reference_files.py", False),
    "extract": ("extract_pdf_text.py", False),
    "validate-src": ("validate_sources.py", False),
    "select": ("select_sources.py", False),
    "provenance": ("export_provenance.py", False),
    "probe": ("probe_capabilities.py", False),
    "init-case": ("init_case.py", False),
    "export": ("export_dispatch.py", True),
}

SUBCMD_HELP = {
    "export": "export pdf <input.md> [--manifest …] | export docx <input.md> [--manifest …]",
}


def _dispatch_export(rest: list[str]) -> int:
    """Export subcommand: `export pdf|docx <input> [args…]`."""
    if not rest:
        print("error: export requires a target: pdf | docx", file=sys.stderr)
        return 2
    target, *forward = rest
    mapping = {"pdf": "export_pdf.py", "docx": "export_docx.py"}
    script = mapping.get(target)
    if script is None:
        print(f"error: unknown export target {target!r} (expected pdf | docx)", file=sys.stderr)
        return 2
    return _run(script, forward)


def _run(script: str, forward: list[str]) -> int:
    path = SCRIPTS_DIR / script
    if not path.exists():
        print(f"error: {path} not found — evidence-suite must run from the repository "
              "(shared/scripts must be present)", file=sys.stderr)
        return 2
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.call([sys.executable, str(path), *forward], env=env)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: evidence-suite <subcommand> [args…]")
        print("       evidence-suite --list   | --version")
        print()
        print("subcommands:")
        for name in sorted(COMMANDS):
            extra = f"   ({SUBCMD_HELP[name]})" if name in SUBCMD_HELP else ""
            print(f"  {name:14s} → {COMMANDS[name][0]}{extra}")
        print()
        print("所有子命令的参数/退出码与对应脚本完全一致；用 'evidence-suite <sub> --help' 查看细节。")
        return 0 if not argv else 0

    if argv[0] == "--list":
        for name in sorted(COMMANDS):
            print(name)
        return 0
    if argv[0] == "--version":
        print("evidence-suite 0.2.1")
        return 0

    cmd = argv[0]
    rest = list(argv[1:])
    if cmd == "export":
        return _dispatch_export(rest)
    # F4 (P0): print a deprecation warning when the legacy `audit` subcommand is
    # invoked, then transparently forward to the canonical `audit-provenance`.
    # Kept so existing CI scripts / muscle-memory callers keep working; will be
    # removed in evidence-suite 0.3.0.
    if cmd == "audit":
        print("warning: 'evidence-suite audit' is deprecated; use "
              "'evidence-suite audit-provenance' (will be removed in 0.3.0)",
              file=sys.stderr)
        cmd = "audit-provenance"
    entry = COMMANDS.get(cmd)
    if entry is None:
        print(f"error: unknown subcommand {cmd!r} — 'evidence-suite --list' 查看可用命令", file=sys.stderr)
        return 2
    script, _ = entry
    return _run(script, rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
