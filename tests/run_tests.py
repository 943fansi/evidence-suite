#!/usr/bin/env python3
"""Minimal regression suite for evidence-suite deterministic gates.

Runs the gate scripts as subprocesses against inline fixtures and asserts exit
codes / JSON output. No third-party deps (Python stdlib only).

Coverage:
  - check_citations.py: citation closure (orphaned/unused), missing URL,
    --min-sources / --min-chars gates, --academic numeric closure.
  - validate_sources.py: clean corpus pass, duplicate URL block, suspect domain block,
    missing authority/freshness block, superseded freshness block, illegal authority block.
  - finalize_draft.py: manifest generation (source/claim-centric), dry-run preview.
  - validate_manifest.py: contract validation (missing fields / illegal enums).
  - download_reference_files.py: SSRF guard (pure function, no network).
  - rule_profile.py: rules loader + scenario profiles + YAML fallback parser;
    validate_sources --profile; check_citations --doc-type/--profile.

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
VALIDATE_MANIFEST = SCRIPTS / "validate_manifest.py"


def run(script: Path, *args: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
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
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed", "type": "journal_paper", "authority": "C1", "freshness": "recent"},
    {"source_id": "S2", "title": "B", "url": "https://example.com/b", "access_status": "web_accessible", "type": "report", "authority": "B1", "freshness": "current"}
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

MISSING_META_CORPUS = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed", "type": "report"}
  ]
}
"""

SUPERSEDED_CORPUS = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed",
     "type": "standard", "authority": "A3", "freshness": "superseded"}
  ]
}
"""

ILLEGAL_AUTHORITY_CORPUS = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed",
     "type": "report", "authority": "E5", "freshness": "recent"}
  ]
}
"""

EVIDENCE_MAP = """\
{
  "evidence_map": [
    {"claim_to_write": "某论断A", "claim_class": "M", "risk": "R2", "evidence_status": "supported",
     "source_support_levels": {"S1": "direct"}},
    {"claim_to_write": "某论断B", "claim_class": "N", "risk": "R3", "evidence_status": "partially_supported",
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

    def test_missing_authority_freshness_blocks(self):
        rc, out, _ = run(VALIDATE, str(write(self.tmp, "meta.json", MISSING_META_CORPUS)), "--json")
        self.assertEqual(rc, 1)
        data = json.loads(out)
        joined = "\n".join(data["problems"])
        self.assertIn("missing authority", joined)
        self.assertIn("missing freshness", joined)

    def test_superseded_freshness_blocks(self):
        rc, out, _ = run(VALIDATE, str(write(self.tmp, "sup.json", SUPERSEDED_CORPUS)), "--json")
        self.assertEqual(rc, 1)
        self.assertIn("superseded", "\n".join(json.loads(out)["problems"]))

    def test_illegal_authority_blocks(self):
        rc, out, _ = run(VALIDATE, str(write(self.tmp, "iauth.json", ILLEGAL_AUTHORITY_CORPUS)), "--json")
        self.assertEqual(rc, 1)
        self.assertIn("illegal authority value", "\n".join(json.loads(out)["problems"]))


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

    def test_claim_manifest(self):
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        emap = write(self.tmp, "emap.json", EVIDENCE_MAP)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        cm = self.tmp / "claim_manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "--claim-manifest", str(cm),
                       "--evidence-map", str(emap), "--sources", str(sources))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        data = json.loads(cm.read_text(encoding="utf-8"))
        self.assertEqual(data["verification_mode"], "static")
        self.assertEqual(data["schema_version"], "0.1.0")
        self.assertEqual(data["review_kind"], "ai-internal")
        self.assertEqual(len(data["claims"]), 2)
        first = data["claims"][0]
        self.assertEqual(first["claim_id"], "C-001")
        self.assertEqual(first["risk"], "R2")
        self.assertEqual(first["evidence"][0]["source_id"], "S1")
        self.assertEqual(first["evidence"][0]["authority"], "C1")
        self.assertEqual(data["claims"][1]["evidence"][0]["freshness"], "current")

    def test_dry_run_previews_without_writing(self):
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        out = self.tmp / "clean.md"
        man = self.tmp / "manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "--dry-run", "-o", str(out), "--manifest", str(man))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        self.assertIn("dry-run", o)
        self.assertFalse(out.exists(), "dry-run must not write the cleaned draft")
        self.assertFalse(man.exists(), "dry-run must not write the manifest")


class ManifestSchemaTests(unittest.TestCase):
    """validate_manifest.py enforces the interop contract (shared/schemas/*.json)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_generated_source_manifest_validates(self):
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        out = self.tmp / "clean.md"
        man = self.tmp / "manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "-o", str(out), "--manifest", str(man),
                       "--sources", str(sources), "--review-kind", "ai-cross-model")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        rc, out, err = run(VALIDATE_MANIFEST, str(man))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        data = json.loads(man.read_text(encoding="utf-8"))
        self.assertEqual(data["review_kind"], "ai-cross-model")
        self.assertEqual(data["schema_version"], "0.1.0")

    def test_generated_claim_manifest_validates(self):
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        emap = write(self.tmp, "emap.json", EVIDENCE_MAP)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        cm = self.tmp / "claim.json"
        rc, o, e = run(FINALIZE, str(draft), "--claim-manifest", str(cm),
                       "--evidence-map", str(emap), "--sources", str(sources))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        rc, out, err = run(VALIDATE_MANIFEST, str(cm))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")

    def test_illegal_enum_blocks(self):
        bad = write(self.tmp, "bad.json", """\
{
  "schema_version": "0.1.0",
  "review_kind": "ai-internal",
  "verification_mode": "static",
  "finalized_at": "2026-08-22",
  "claims": [
    {"claim_id": "C-001", "claim_class": "X", "claim_text": "t",
     "evidence": [{"source_id": "S1", "support_level": "bogus"}]}
  ]
}
""")
        rc, out, err = run(VALIDATE_MANIFEST, str(bad))
        self.assertEqual(rc, 1)
        self.assertIn("claim_class has illegal value 'X'", out)
        self.assertIn("support_level has illegal value 'bogus'", out)

    def test_missing_review_kind_blocks(self):
        bad = write(self.tmp, "nork.json", """\
{
  "schema_version": "0.1.0",
  "verification_mode": "static",
  "finalized_at": "2026-08-22",
  "claims": []
}
""")
        rc, out, err = run(VALIDATE_MANIFEST, str(bad))
        self.assertEqual(rc, 1)
        self.assertIn("review_kind", out)

    def test_missing_mapping_claim_blocks(self):
        bad = write(self.tmp, "empty.json", """\
{
  "schema_version": "0.1.0",
  "review_kind": "ai-internal",
  "verification_mode": "static",
  "finalized_at": "2026-08-22"
}
""")
        rc, out, err = run(VALIDATE_MANIFEST, str(bad))
        self.assertEqual(rc, 1)
        self.assertIn("either a 'mapping' array", out)


class SsrfGuardTests(unittest.TestCase):
    """download_reference_files.py SSRF guard (pure function, no network)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "download_reference_files", SCRIPTS / "download_reference_files.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.check = staticmethod(mod.check_url_blocked)
        cls.BlockedURLError = mod.BlockedURLError

    def test_public_literal_ip_allowed(self):
        self.assertIsNone(self.check("http://93.184.216.34/a.pdf"))

    def test_loopback_blocked(self):
        self.assertIsNotNone(self.check("http://127.0.0.1/x"))
        self.assertIsNotNone(self.check("http://[::1]/x"))

    def test_private_blocks_blocked(self):
        self.assertIsNotNone(self.check("http://10.0.0.5/x"))
        self.assertIsNotNone(self.check("http://192.168.1.5/x"))
        self.assertIsNotNone(self.check("http://172.16.0.1/x"))
        self.assertIsNotNone(self.check("http://169.254.169.254/latest/meta-data/"))

    def test_bad_scheme_blocked(self):
        self.assertIsNotNone(self.check("ftp://example.com/a"))
        self.assertIsNotNone(self.check("file:///etc/passwd"))

    def test_localhost_hostname_blocked_without_dns(self):
        self.assertIsNotNone(self.check("http://localhost/x"))
        self.assertIsNotNone(self.check("http://foo.local/x"))

    def test_help_exposes_max_bytes(self):
        rc, out, err = run(SCRIPTS / "download_reference_files.py", "--help")
        self.assertEqual(rc, 0)
        self.assertIn("--max-bytes", out)


class RuleProfileTests(unittest.TestCase):
    """rule_profile.py loads/merges shared/config/rules.yaml (no network)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rule_profile", SCRIPTS / "rule_profile.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.rp = mod

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_default_rules(self):
        rules = self.rp.load_rules()
        self.assertEqual(rules["risk_tiers"]["R3"]["authority_min"], "A2")
        self.assertEqual(rules["doc_minimums"]["proposal"],
                         {"min_sources": 15, "min_chars": 6000})
        self.assertEqual(rules["doc_minimums"]["thesis_phd"]["min_sources"], 60)
        self.assertGreaterEqual(len(rules["suspect_domains"]), 10)

    def test_medical_profile_overrides(self):
        rules = self.rp.load_rules(profile="medical")
        self.assertEqual(rules["risk_tiers"]["R2"]["authority_min"], "A2")
        self.assertEqual(rules["risk_tiers"]["R3"]["authority_min"], "A1")
        self.assertEqual(rules["doc_minimums"]["paper_journal"]["min_sources"], 20)
        self.assertEqual(rules["active_profile"], "medical")

    def test_general_tech_profile_relaxes(self):
        rules = self.rp.load_rules(profile="general_tech")
        self.assertEqual(rules["risk_tiers"]["R3"]["authority_min"], "B1")
        self.assertEqual(rules["doc_minimums"]["proposal"]["min_sources"], 10)

    def test_unknown_profile_raises(self):
        with self.assertRaises(KeyError):
            self.rp.load_rules(profile="no_such_profile")

    def test_explicit_rules_override(self):
        with tempfile.TemporaryDirectory() as td:
            over = Path(td) / "rules.user.yaml"
            over.write_text("doc_minimums:\n  proposal:\n    min_sources: 99\n",
                            encoding="utf-8")
            rules = self.rp.load_rules(rules_path=over)
            self.assertEqual(rules["doc_minimums"]["proposal"]["min_sources"], 99)
            self.assertEqual(rules["doc_minimums"]["thesis_phd"]["min_sources"], 60)

    def test_minimal_parser_matches_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("pyyaml not installed")
        text = (ROOT / "shared" / "config" / "rules.yaml").read_text(encoding="utf-8")
        self.assertEqual(self.rp._minimal_yaml(text), yaml.safe_load(text))

    def test_validate_sources_profile_suspect_domains(self):
        corpus = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://jianshu.com/p/xx",
     "access_status": "confirmed", "type": "journal_paper", "authority": "C1",
     "freshness": "recent"}
  ]
}
"""
        p = write(self.tmp, "jianshu.json", corpus)
        rc, out, _ = run(VALIDATE, str(p), "--profile", "medical", "--json")
        self.assertEqual(rc, 1)
        self.assertIn("jianshu.com", "\n".join(json.loads(out)["problems"]))
        rc, out, _ = run(VALIDATE, str(p), "--json")
        self.assertEqual(rc, 0, "default profile must not block jianshu.com")

    def test_check_citations_doc_type_applies_minimums(self):
        draft = write(self.tmp, "dt.md", CLEAN_DRAFT)
        rc, out, err = run(CHECK, str(draft), "--doc-type", "thesis_phd", "--json")
        self.assertEqual(rc, 1)
        data = json.loads(out)
        self.assertEqual(data["min_sources"], 60)
        self.assertEqual(data["min_chars"], 35000)
        self.assertTrue(data["min_sources_violated"])
        self.assertIn("min_sources=60", err)

    def test_check_citations_profile_relaxes_minimums(self):
        draft = write(self.tmp, "dt2.md", CLEAN_DRAFT)
        rc, out, err = run(CHECK, str(draft), "--doc-type", "proposal",
                           "--profile", "general_tech", "--json")
        data = json.loads(out)
        self.assertEqual(data["min_sources"], 10)
        self.assertEqual(data["min_chars"], 4000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
