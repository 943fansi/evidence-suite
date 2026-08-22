#!/usr/bin/env python3
"""Minimal regression suite for evidence-suite deterministic gates.

Runs the gate scripts as subprocesses against inline fixtures and asserts exit
codes / JSON output. No third-party deps (Python stdlib only).

Coverage:
  - check_citations.py: citation closure (orphaned/unused), missing URL,
    --min-sources / --min-chars gates, --academic numeric closure.
  - validate_sources.py: clean corpus pass, duplicate URL block, suspect domain block.

Usage:
  python tests/run_tests.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "shared" / "scripts"
CHECK = SCRIPTS / "check_citations.py"
VALIDATE = SCRIPTS / "validate_sources.py"
FINALIZE = SCRIPTS / "finalize_draft.py"


def run(script: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, encoding="utf-8",
    )
    return proc.returncode, proc.stdout, proc.stderr


def write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


CLEAN_DRAFT = """\
# 正文

这是一个论断 [S1]，另一个 [S2]。

## 参考文献

[S1] 某来源标题一. http://example.com/a
[S2] 某来源标题二. http://example.com/b
"""

ORPHANED_DRAFT = """\
# 正文

这是一个论断 [S1]，还有一个没来源的 [S3]。

## 参考文献

[S1] 某来源标题一. http://example.com/a
"""

UNUSED_DRAFT = """\
# 正文

这是一个论断 [S1]。

## 参考文献

[S1] 某来源标题一. http://example.com/a
[S2] 某来源标题二. http://example.com/b
"""

NOURL_DRAFT = """\
# 正文

这是一个论断 [S1]。

## 参考文献

[S1] 某来源标题一. (无 URL)
"""

ACADEMIC_CLEAN = """\
# 正文

一个论断 [1]，另一个 [2]。

## 参考文献

[1] A. http://example.com/a
[2] B. http://example.com/b
"""

ACADEMIC_ORPHANED = """\
# 正文

一个论断 [1]，另一个孤儿 [3]。

## 参考文献

[1] A. http://example.com/a
[2] B. http://example.com/b
"""

CLEAN_CORPUS = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed", "type": "journal_paper"},
    {"source_id": "S2", "title": "B", "url": "https://example.com/b", "access_status": "web_accessible", "type": "report"}
  ]
}
"""

DUPLICATE_URL_CORPUS = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/same", "access_status": "confirmed", "type": "report"},
    {"source_id": "S2", "title": "B", "url": "https://example.com/same", "access_status": "confirmed", "type": "report"}
  ]
}
"""

SUSPECT_DOMAIN_CORPUS = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://baike.baidu.com/item/xxx", "access_status": "confirmed", "type": "report"}
  ]
}
"""

EVIDENCE_MAP = """\
{
  "evidence_map": [
    {"claim_to_write": "某论断A", "claim_class": "M", "evidence_status": "supported",
     "source_support_levels": {"S1": "direct"}},
    {"claim_to_write": "某论断B", "claim_class": "N", "evidence_status": "partially_supported",
     "source_support_levels": {"S2": "weak_inference"}}
  ]
}
"""


class CitationClosureTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_draft_passes(self):
        rc, out, err = run(CHECK, str(write(self.tmp, "clean.md", CLEAN_DRAFT)), "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        data = json.loads(out)
        self.assertEqual(data["orphaned_s"], [])
        self.assertEqual(data["unused_s"], [])

    def test_orphaned_source_blocks(self):
        rc, out, _ = run(CHECK, str(write(self.tmp, "orphan.md", ORPHANED_DRAFT)), "--json")
        self.assertEqual(rc, 1)
        self.assertIn("3", json.loads(out)["orphaned_s"])

    def test_unused_reference_blocks(self):
        rc, out, _ = run(CHECK, str(write(self.tmp, "unused.md", UNUSED_DRAFT)), "--json")
        self.assertEqual(rc, 1)
        self.assertIn("2", json.loads(out)["unused_s"])

    def test_missing_url_blocks(self):
        rc, out, _ = run(CHECK, str(write(self.tmp, "nourl.md", NOURL_DRAFT)), "--json")
        self.assertEqual(rc, 1)
        self.assertIn("S1", json.loads(out)["missing_urls"])

    def test_min_sources_gate(self):
        rc, out, _ = run(CHECK, str(write(self.tmp, "min.md", CLEAN_DRAFT)), "--min-sources", "5", "--json")
        self.assertEqual(rc, 1)
        self.assertTrue(json.loads(out)["min_sources_violated"])

    def test_min_chars_gate(self):
        rc, out, _ = run(CHECK, str(write(self.tmp, "minc.md", CLEAN_DRAFT)), "--min-chars", "50000", "--json")
        self.assertEqual(rc, 1)
        self.assertTrue(json.loads(out)["min_chars_violated"])

    def test_academic_clean_passes(self):
        rc, out, err = run(CHECK, str(write(self.tmp, "ac.md", ACADEMIC_CLEAN)), "--academic", "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")

    def test_academic_orphaned_blocks(self):
        rc, out, _ = run(CHECK, str(write(self.tmp, "ac2.md", ACADEMIC_ORPHANED)), "--academic", "--json")
        self.assertEqual(rc, 1)
        self.assertIn(3, json.loads(out)["orphaned_nums"])


class ValidateSourcesTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_corpus_passes(self):
        rc, out, err = run(VALIDATE, str(write(self.tmp, "clean.json", CLEAN_CORPUS)), "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")

    def test_duplicate_url_blocks(self):
        rc, out, _ = run(VALIDATE, str(write(self.tmp, "dup.json", DUPLICATE_URL_CORPUS)), "--json")
        self.assertEqual(rc, 1)
        self.assertGreaterEqual(json.loads(out)["count"], 1)

    def test_suspect_domain_blocks(self):
        rc, out, _ = run(VALIDATE, str(write(self.tmp, "sus.json", SUSPECT_DOMAIN_CORPUS)), "--json")
        self.assertEqual(rc, 1)
        self.assertGreaterEqual(json.loads(out)["count"], 1)


class FinalizeManifestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_manifest_generated(self):
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        out = self.tmp / "clean.md"
        man = self.tmp / "manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "-o", str(out), "--manifest", str(man), "--sources", str(sources))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        data = json.loads(man.read_text(encoding="utf-8"))
        self.assertEqual(data["verification_mode"], "static")
        ids = [m["source_id"] for m in data["mapping"]]
        self.assertIn("S1", ids)
        self.assertIn("S2", ids)

    def test_manifest_with_evidence_map(self):
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        emap = write(self.tmp, "emap.json", EVIDENCE_MAP)
        out = self.tmp / "clean.md"
        man = self.tmp / "manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "-o", str(out), "--manifest", str(man),
                       "--sources", str(sources), "--evidence-map", str(emap))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        data = json.loads(man.read_text(encoding="utf-8"))
        by_id = {m["source_id"]: m for m in data["mapping"]}
        self.assertIn("claims", by_id["S1"])
        self.assertEqual(by_id["S1"]["claims"][0]["support_level"], "direct")
        self.assertEqual(by_id["S2"]["claims"][0]["support_level"], "weak_inference")


if __name__ == "__main__":
    unittest.main(verbosity=2)
