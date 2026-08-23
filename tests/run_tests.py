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
  - check_evidence_sufficiency.py: claim-weighted sufficiency (primary/independent/
    currentness/contradiction coverage) + quickstart fixtures + --review-mode.
  - select_sources.py: registry ranking (priority/authority/source_origin) + discovery.
  - build_evidence_brief.py: L1 brief rendering + Evidence Score.
  - export_provenance.py: five-piece provenance bundle + review verdict parsing.
  - audit_provenance.py: machine-auditability gate (locator-backed high-risk claims).
  - probe_capabilities.py: runtime capability profile emission.
  - init_case.py: research_case workspace scaffold.
  - eval/run_eval.py: auto-scored golden cases stay green.
  - export_docx.py: 2-char first-line indent, Mermaid PNG embedding + failure
    placeholder. export_pdf.py: print CSS first-line indent (on/off).

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
SUFFICIENCY = SCRIPTS / "check_evidence_sufficiency.py"
EVAL = ROOT / "eval" / "run_eval.py"
SELECT = SCRIPTS / "select_sources.py"
BRIEF = SCRIPTS / "build_evidence_brief.py"
PROBE = SCRIPTS / "probe_capabilities.py"
FRAMEWORK = SCRIPTS / "check_framework_depth.py"
INIT_CASE = SCRIPTS / "init_case.py"
AUDIT = SCRIPTS / "audit_provenance.py"


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

BAD_ORIGIN_CORPUS = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed",
     "type": "report", "authority": "B1", "freshness": "recent", "source_origin": "hacker"}
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


EVIDENCE_MAP_RICH = """\
{
  "evidence_map": [
    {"claim_to_write": "某论断A", "claim_class": "M", "risk": "R2",
     "evidence_status": "supported", "confidence": "high",
     "interpretation": "S1 原文直接陈述",
     "source_support_levels": {"S1": "direct"},
     "source_relations": {"S1": "supports"},
     "source_locators": {"S1": {"page": 12, "section": "2.1", "paragraph": 3}}},
    {"claim_to_write": "某论断B", "claim_class": "N", "risk": "R3",
     "evidence_status": "contradicted",
     "source_support_levels": {"S2": "contradictory"}}
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

    def test_illegal_source_origin_blocks(self):
        rc, out, _ = run(VALIDATE, str(write(self.tmp, "oorig.json", BAD_ORIGIN_CORPUS)), "--json")
        self.assertEqual(rc, 1)
        self.assertIn("illegal source_origin 'hacker'", "\n".join(json.loads(out)["problems"]))


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
        self.assertEqual(data["schema_version"], "0.2.0")
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

    def test_claim_manifest_evidence_model(self):
        """V2 model: relation derived, locator/confidence/interpretation carried."""
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        emap = write(self.tmp, "emap.json", EVIDENCE_MAP_RICH)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        cm = self.tmp / "claim_manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "--claim-manifest", str(cm),
                       "--evidence-map", str(emap), "--sources", str(sources))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        data = json.loads(cm.read_text(encoding="utf-8"))
        first = data["claims"][0]
        self.assertEqual(first["confidence"], "high")
        self.assertIn("interpretation", first)
        ev = first["evidence"][0]
        self.assertEqual(ev["relation"], "supports")
        self.assertEqual(ev["locator"]["page"], 12)
        self.assertEqual(ev["locator"]["section"], "2.1")
        # relation derived from contradictory support_level when not explicit
        second = data["claims"][1]
        self.assertEqual(second["evidence"][0]["relation"], "contradicts")
        self.assertNotIn("confidence", second)

    def test_manifest_embeds_review_independence_default(self):
        """ai-internal default records honest independence: shared context/evidence, no human."""
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        out = self.tmp / "clean.md"
        man = self.tmp / "manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "-o", str(out), "--manifest", str(man),
                       "--sources", str(sources))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        data = json.loads(man.read_text(encoding="utf-8"))
        ri = data["review_independence"]
        self.assertEqual(ri["human_involvement"], "none")
        self.assertTrue(ri["context_shared"])
        self.assertTrue(ri["evidence_shared"])

    def test_manifest_review_independence_override_file(self):
        draft = write(self.tmp, "draft.md", CLEAN_DRAFT)
        sources = write(self.tmp, "sources.json", CLEAN_CORPUS)
        ri = write(self.tmp, "ri.json",
                   '{"reviewer_model": "modelB", "writer_model": "modelA", '
                   '"model_family": "familyX", "context_shared": false, '
                   '"evidence_shared": true, "human_involvement": "partial"}')
        out = self.tmp / "clean.md"
        man = self.tmp / "manifest.json"
        rc, o, e = run(FINALIZE, str(draft), "-o", str(out), "--manifest", str(man),
                       "--sources", str(sources), "--review-kind", "ai-cross-model",
                       "--review-independence", str(ri))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        data = json.loads(man.read_text(encoding="utf-8"))
        self.assertEqual(data["review_independence"]["reviewer_model"], "modelB")
        self.assertFalse(data["review_independence"]["context_shared"])


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
        self.assertEqual(data["schema_version"], "0.2.0")

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
  "schema_version": "0.2.0",
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
  "schema_version": "0.2.0",
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
  "schema_version": "0.2.0",
  "review_kind": "ai-internal",
  "verification_mode": "static",
  "finalized_at": "2026-08-22"
}
""")
        rc, out, err = run(VALIDATE_MANIFEST, str(bad))
        self.assertEqual(rc, 1)
        self.assertIn("either a 'mapping' array", out)

    def test_illegal_relation_locator_confidence_blocks(self):
        bad = write(self.tmp, "badrel.json", """\
{
  "schema_version": "0.2.0",
  "review_kind": "ai-internal",
  "verification_mode": "static",
  "finalized_at": "2026-08-22",
  "claims": [
    {"claim_id": "C-001", "claim_class": "N", "claim_text": "t",
     "confidence": "certain",
     "evidence": [{"source_id": "S1", "support_level": "direct",
                   "relation": "rejects", "locator": {"page": "x"}}]}
  ]
}
""")
        rc, out, err = run(VALIDATE_MANIFEST, str(bad))
        self.assertEqual(rc, 1)
        self.assertIn("relation has illegal value 'rejects'", out)
        self.assertIn("locator.page must be an integer", out)
        self.assertIn("confidence has illegal value 'certain'", out)

    def test_illegal_review_independence_blocks(self):
        bad = write(self.tmp, "badri.json", """\
{
  "schema_version": "0.2.0",
  "review_kind": "ai-internal",
  "verification_mode": "static",
  "finalized_at": "2026-08-22",
  "review_independence": {"human_involvement": "maybe", "context_shared": "yes"},
  "claims": []
}
""")
        rc, out, err = run(VALIDATE_MANIFEST, str(bad))
        self.assertEqual(rc, 1)
        self.assertIn("human_involvement must be one of", out)
        self.assertIn("context_shared must be a boolean", out)


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


MERMAID_MD = """\
# 示例文档

## 引言

正文段落。[S1]

```mermaid
graph TD
    A[老化管理] --> B[监测]
    B --> C[评估]
```

## 参考文献

[S1] 来源一. https://example.com/a
"""

# 1x1 transparent PNG built programmatically (valid; python-docx reads its header)
def _one_px_png() -> bytes:
    import struct
    import zlib

    def chunk(typ: bytes, data: bytes) -> bytes:
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    idat = chunk(b"IDAT", zlib.compress(b"\x00" + b"\x00\x00\x00\x00"))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


class ExportDocxTests(unittest.TestCase):
    """export_docx.py typography + Mermaid embedding (python-docx available)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location(
            "export_docx", SCRIPTS / "export_docx.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.dx = mod

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _read_document_xml(self, docx_path):
        import zipfile
        with zipfile.ZipFile(str(docx_path)) as zf:
            return zf.read("word/document.xml").decode("utf-8")

    def test_docx_has_two_char_first_line_indent(self):
        md = write(self.tmp, "demo.md", MERMAID_MD)
        out = self.tmp / "demo.docx"
        rc = self.dx.convert(md, out, body_size=12.0, line_spacing=1.5, indent=True,
                             heiti="黑体", songti="宋体", kaiti="楷体",
                             western="Times New Roman", mermaid_engine="local")
        self.assertEqual(rc, 0)
        self.assertTrue(out.exists())
        self.assertIn('w:firstLineChars="200"', self._read_document_xml(out))

    def test_docx_embeds_mermaid_png(self):
        png = _one_px_png()
        orig = self.dx.render_mermaid
        def fake_render(code, out_path, engine="auto", fmt="png"):
            out_path.write_bytes(png)
            return png
        self.dx.render_mermaid = fake_render
        try:
            md = write(self.tmp, "mm.md", MERMAID_MD)
            out = self.tmp / "mm.docx"
            rc = self.dx.convert(md, out, body_size=12.0, line_spacing=1.5, indent=True,
                                 heiti="黑体", songti="宋体", kaiti="楷体",
                                 western="Times New Roman", mermaid_engine="auto")
            self.assertEqual(rc, 0)
            import zipfile
            with zipfile.ZipFile(str(out)) as zf:
                names = zf.namelist()
                self.assertTrue(any("word/media/" in n and n.endswith(".png") for n in names),
                                f"no embedded PNG in {names}")
                xml = zf.read("word/document.xml").decode("utf-8")
                self.assertIn("blip", xml)
        finally:
            self.dx.render_mermaid = orig

    def test_docx_mermaid_failure_placeholder(self):
        md = write(self.tmp, "fail.md", MERMAID_MD)
        out = self.tmp / "fail.docx"
        rc = self.dx.convert(md, out, body_size=12.0, line_spacing=1.5, indent=True,
                             heiti="黑体", songti="宋体", kaiti="楷体",
                             western="Times New Roman", mermaid_engine="local")
        self.assertEqual(rc, 0)
        self.assertIn("mermaid", self._read_document_xml(out))
        import zipfile
        with zipfile.ZipFile(str(out)) as zf:
            self.assertFalse(any("word/media/" in n for n in zf.namelist()),
                             "failed render must not embed an image")


class ExportPdfCssTests(unittest.TestCase):
    """export_pdf.py print CSS: 2-char first-line indent (on by default)."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.spec_from_file_location(
            "export_pdf", SCRIPTS / "export_pdf.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cls.pdf = mod

    def test_css_indent_on_by_default(self):
        css = self.pdf._print_css(indent=True)
        self.assertIn("text-indent: 2em", css)
        self.assertIn("blockquote p { text-indent: 0; }", css)
        self.assertIn("li p { text-indent: 0; }", css)
        self.assertIn("section.refs p {", css)

    def test_css_no_indent_flag(self):
        css = self.pdf._print_css(indent=False)
        self.assertIn("text-indent: 0", css)
        self.assertNotIn("text-indent: 2em", css)


EM_SUFFICIENT = """\
{
  "evidence_map": [
    {"claim_to_write": "某论断A", "claim_class": "M", "risk": "R2",
     "evidence_status": "supported",
     "source_support_levels": {"S1": "direct", "S2": "direct"},
     "counter_evidence_search": ["本次检索未找到公开反证"]},
    {"claim_to_write": "某论断B", "claim_class": "N", "risk": "R3",
     "evidence_status": "supported",
     "source_support_levels": {"S2": "direct", "S3": "direct"},
     "counter_evidence_search": ["本次检索未找到公开反证"]}
  ]
}
"""

EM_INSUFFICIENT = """\
{
  "evidence_map": [
    {"claim_to_write": "单源弱证据论断", "claim_class": "M", "risk": "R2",
     "evidence_status": "partially_supported",
     "source_support_levels": {"S1": "weak_inference"}}
  ]
}
"""

EM_STALE_NORMATIVE = """\
{
  "evidence_map": [
    {"claim_to_write": "用已废止标准作现行依据", "claim_class": "N", "risk": "R3",
     "evidence_status": "supported",
     "source_support_levels": {"S1": "direct", "S2": "direct"},
     "counter_evidence_search": ["本次检索未找到公开反证"]}
  ]
}
"""

SOURCES_SUFFICIENT = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed",
     "type": "journal_paper", "authority": "C1", "freshness": "recent"},
    {"source_id": "S2", "title": "B", "url": "https://example.com/b", "access_status": "confirmed",
     "type": "technical_report", "authority": "B1", "freshness": "current"},
    {"source_id": "S3", "title": "C", "url": "https://example.com/c", "access_status": "confirmed",
     "type": "standard", "authority": "A2", "freshness": "current"}
  ]
}
"""

SOURCES_STALE = """\
{
  "sources": [
    {"source_id": "S1", "title": "A", "url": "https://example.com/a", "access_status": "confirmed",
     "type": "standard", "authority": "A3", "freshness": "superseded"},
    {"source_id": "S2", "title": "B", "url": "https://example.com/b", "access_status": "confirmed",
     "type": "technical_report", "authority": "B1", "freshness": "recent"}
  ]
}
"""


class EvidenceSufficiencyTests(unittest.TestCase):
    """check_evidence_sufficiency.py: claim-weighted gate, decoupled from min_sources."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_sufficient_claims_pass(self):
        em = write(self.tmp, "em.json", EM_SUFFICIENT)
        vs = write(self.tmp, "vs.json", SOURCES_SUFFICIENT)
        rc, out, err = run(SUFFICIENCY, str(em), str(vs), "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        data = json.loads(out)
        self.assertEqual(data["passed"], 2)
        self.assertEqual(data["failed"], 0)

    def test_single_weak_source_fails(self):
        em = write(self.tmp, "em2.json", EM_INSUFFICIENT)
        vs = write(self.tmp, "vs2.json", SOURCES_SUFFICIENT)
        rc, out, err = run(SUFFICIENCY, str(em), str(vs), "--json")
        self.assertEqual(rc, 1)
        data = json.loads(out)
        self.assertEqual(data["failed"], 1)
        joined = "\n".join(data["results"][0]["reasons"])
        self.assertIn("primary sources", joined)
        self.assertIn("independent sources", joined)

    def test_stale_normative_source_fails(self):
        em = write(self.tmp, "em3.json", EM_STALE_NORMATIVE)
        vs = write(self.tmp, "vs3.json", SOURCES_STALE)
        rc, out, err = run(SUFFICIENCY, str(em), str(vs), "--json")
        self.assertEqual(rc, 1)
        joined = "\n".join(json.loads(out)["results"][0]["reasons"])
        self.assertIn("current", joined)

    def test_quickstart_fixtures_pass(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        rc, out, err = run(SUFFICIENCY, str(em), str(vs), "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        self.assertEqual(json.loads(out)["passed"], 2)

    def test_incremental_changed_only(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        rc, out, err = run(SUFFICIENCY, str(em), str(vs), "--changed", "C-001", "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        data = json.loads(out)
        self.assertEqual(data["passed"], 1)
        self.assertEqual(data["incremental"]["skipped"], 1)
        ids = [r["claim_id"] for r in data["results"]]
        self.assertEqual(ids, ["C-001"])

    def test_score_option_reports_grade(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        rc, out, err = run(SUFFICIENCY, str(em), str(vs), "--score", "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        data = json.loads(out)
        first = data["results"][0]
        self.assertIn("score", first)
        self.assertIn("grade", first)
        self.assertGreaterEqual(first["score"], 0)
        self.assertLessEqual(first["score"], 100)
        self.assertIn(first["grade"], ("Strong", "Good", "Moderate", "Weak", "Insufficient"))


class EvalHarnessTests(unittest.TestCase):
    """eval/run_eval.py: auto-scored golden cases must stay green."""

    def test_auto_golden_cases_pass(self):
        rc, out, err = run(EVAL, "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        data = json.loads(out)
        self.assertEqual(data["failed"], 0)
        self.assertEqual(data["errors"], 0)
        self.assertGreaterEqual(data["passed"], 15)
        self.assertGreaterEqual(data["manual"], 4, "agent-behavior golden cases should exist")


class P1RegistryRankingTests(unittest.TestCase):
    """select_sources.py: registry is a priority list, not a whitelist."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_registry_ranked_and_discovery(self):
        out = self.tmp / "sel.json"
        rc, o, e = run(SELECT, "--domain", "nuclear", "--allow-discovery", "--output", str(out))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(data["allow_discovery"])
        self.assertIn("discovery_directives", data)
        sources = data["selected_sources"]
        self.assertTrue(sources)
        priorities = [s["priority"] for s in sources]
        self.assertEqual(priorities, sorted(priorities, reverse=True),
                         "selected sources must be sorted by priority desc")
        for s in sources:
            self.assertEqual(s["source_origin"], "registry")
            self.assertIn(s["authority"],
                          ("A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1", "D2"))
        by_id = {s["id"]: s for s in sources}
        self.assertEqual(by_id["iaea"]["authority"], "A1")
        self.assertGreaterEqual(by_id["iaea"]["priority"], 90)


class P1ReviewModeTests(unittest.TestCase):
    """check_evidence_sufficiency.py --review-mode scales thresholds."""

    def test_conservative_stricter_than_balanced(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        rc_bal, out_bal, _ = run(SUFFICIENCY, str(em), str(vs), "--json")
        rc_cons, out_cons, _ = run(SUFFICIENCY, str(em), str(vs),
                                   "--review-mode", "conservative", "--json")
        self.assertEqual(rc_bal, 0)
        self.assertEqual(rc_cons, 1)
        bal = json.loads(out_bal)
        cons = json.loads(out_cons)
        self.assertEqual(bal["passed"], 2)
        self.assertEqual(cons["review_mode"], "conservative")
        self.assertGreater(bal["passed"], cons["passed"])


class P1EvidenceBriefTests(unittest.TestCase):
    """build_evidence_brief.py: L1 human-readable evidence brief."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_brief_renders(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        out = self.tmp / "brief.md"
        rc, o, e = run(BRIEF, str(em), str(vs), "-o", str(out))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        text = out.read_text(encoding="utf-8")
        self.assertIn("# Evidence Brief", text)
        self.assertIn("| C-001", text)
        self.assertIn("| C-002", text)
        self.assertIn("结论（由 Agent 填写）", text)
        self.assertIn("充分性", text)
        self.assertIn("平衡", text)
        self.assertIn("Evidence Score", text)
        self.assertIn("Good", text)
        self.assertIn("Strong", text)


PROVENANCE = SCRIPTS / "export_provenance.py"


class ProvenanceExportTests(unittest.TestCase):
    """export_provenance.py: machine-auditable five-piece bundle."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_provenance_bundle_emitted(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        draft = ROOT / "examples" / "quickstart" / "input_draft.md"
        out = self.tmp / "provenance"
        rc, o, e = run(PROVENANCE, "--draft", str(draft), "--sources", str(vs),
                       "--evidence-map", str(em), "--review-kind", "ai-cross-model",
                       "-o", str(out))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        expected = ["report.claims.json", "report.evidence.json",
                    "report.source-map.json", "report.review.json"]
        for name in expected:
            self.assertTrue((out / name).exists(), f"missing {name}")
        claims = json.loads((out / "report.claims.json").read_text(encoding="utf-8"))
        self.assertEqual(claims["review_kind"], "ai-cross-model")
        self.assertEqual(claims["schema_version"], "0.2.0")
        self.assertEqual(len(claims["claims"]), 2)
        source_map = json.loads((out / "report.source-map.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(source_map["mapping"]), 2)

    def test_provenance_parses_review_verdicts(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        draft = ROOT / "examples" / "quickstart" / "input_draft.md"
        review_dir = self.tmp / "workspace"
        review_dir.mkdir()
        (review_dir / "10_review.md").write_text(
            "# 10_review.md\n\n## 一、总体判决\n**判决**: 🔧 小修后通过\n",
            encoding="utf-8")
        out = self.tmp / "prov"
        rc, o, e = run(PROVENANCE, "--draft", str(draft), "--sources", str(vs),
                       "--evidence-map", str(em), "--review-dir", str(review_dir),
                       "-o", str(out))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        review = json.loads((out / "report.review.json").read_text(encoding="utf-8"))
        self.assertEqual(len(review["stages"]), 1)
        self.assertEqual(review["stages"][0]["file"], "10_review.md")
        self.assertIn("小修后通过", review["stages"][0]["verdict"])


class CapabilityProbeTests(unittest.TestCase):
    """probe_capabilities.py: runtime capability profile (all-local checks)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_probe_emits_profile(self):
        out = self.tmp / "cap.json"
        rc, o, e = run(PROBE, "--output", str(out))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        caps = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn(caps["platform"], ("windows", "linux", "darwin"))
        self.assertTrue(caps["filesystem"])
        for key in ("markdown", "docx", "pdfplumber", "pypdf2", "pymupdf",
                    "weasyprint", "matplotlib", "numpy", "yaml", "ocr",
                    "pandoc", "mmdc", "curl", "pdf_render"):
            self.assertIsInstance(caps.get(key), bool, f"{key} must be boolean")
        self.assertIn("shell", caps)
        self.assertIn("python_version", caps)


THIN_FRAMEWORK_DRAFT = """\
# 文档

## 第一章 方法实现

### 目标

内容。

### 方法

内容。

### 输入输出

内容。

### 标准依据

内容。

## 参考文献

[S1] 来源一. http://example.com/a
"""


class FrameworkDepthRulesTests(unittest.TestCase):
    """check_framework_depth.py reads min-chars floor from rules.yaml."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_rules_default_floor_flags_thin_chapter(self):
        draft = write(self.tmp, "thin.md", THIN_FRAMEWORK_DRAFT)
        rc, out, err = run(FRAMEWORK, str(draft), "--json")
        self.assertEqual(rc, 1, f"rc={rc}\nstdout={out}\nstderr={err}")
        data = json.loads(out)
        self.assertEqual(len(data["chapters"]), 1)
        self.assertTrue(data["chapters"][0]["thin"])

    def test_explicit_lower_floor_passes(self):
        draft = write(self.tmp, "thin.md", THIN_FRAMEWORK_DRAFT)
        rc, out, err = run(FRAMEWORK, str(draft), "--min-chars-per-chapter", "10", "--json")
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        self.assertFalse(json.loads(out)["chapters"][0]["thin"])


class InitCaseTests(unittest.TestCase):
    """init_case.py scaffolds a research_case workspace."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_scaffold_created(self):
        out = self.tmp / "research_case"
        rc, o, e = run(INIT_CASE, "-o", str(out))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        for name in ("README.md", ".gitignore", "00_topic.md",
                     "02_raw_sources.json", "04_validated_sources.json",
                     "06_evidence_map.json"):
            self.assertTrue((out / name).exists(), f"missing {name}")
        emap = json.loads((out / "06_evidence_map.json").read_text(encoding="utf-8"))
        self.assertEqual(emap["evidence_map"], [])
        self.assertIn("Topic Card", (out / "00_topic.md").read_text(encoding="utf-8"))

    def test_scaffold_skips_existing_without_force(self):
        out = self.tmp / "case"
        run(INIT_CASE, "-o", str(out))
        (out / "00_topic.md").write_text("# 已有内容\n", encoding="utf-8")
        rc, o, e = run(INIT_CASE, "-o", str(out))
        self.assertEqual(rc, 0)
        self.assertIn("skipped", o)
        self.assertIn("已有内容", (out / "00_topic.md").read_text(encoding="utf-8"))


AUDIT_R3_NO_LOCATOR = """\
{
  "schema_version": "0.2.0",
  "review_kind": "ai-internal",
  "claims": [
    {"claim_id": "C-001", "claim_class": "N", "risk": "R3", "claim_text": "某规范论断",
     "evidence": [{"source_id": "S1", "support_level": "direct", "relation": "supports"}]}
  ]
}
"""


class AuditProvenanceTests(unittest.TestCase):
    """audit_provenance.py: machine-auditability gate (locator-backed citations)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_quickstart_provenance_auditable(self):
        em = ROOT / "examples" / "quickstart" / "evidence_map.json"
        vs = ROOT / "examples" / "quickstart" / "sources.json"
        draft = ROOT / "examples" / "quickstart" / "input_draft.md"
        prov = self.tmp / "provenance"
        rc, o, e = run(PROVENANCE, "--draft", str(draft), "--sources", str(vs),
                       "--evidence-map", str(em), "-o", str(prov))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={o}\nstderr={e}")
        rc, out, err = run(AUDIT, "--claims", str(prov / "report.claims.json"))
        self.assertEqual(rc, 0, f"rc={rc}\nstdout={out}\nstderr={err}")
        self.assertIn("100%", out)

    def test_r3_without_locator_blocks(self):
        claims = write(self.tmp, "claims.json", AUDIT_R3_NO_LOCATOR)
        rc, out, err = run(AUDIT, "--claims", str(claims))
        self.assertEqual(rc, 1)
        self.assertIn("缺失 locator", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
