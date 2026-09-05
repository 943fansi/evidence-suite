#!/usr/bin/env python3
r"""Validate an evidence manifest JSON against the interop contract.

Enforces the constraints declared in shared/schemas/*.schema.json using only the
Python standard library (no jsonschema dependency), so the gate runs anywhere.

Schemas:
  - evidence_manifest (source-centric, from finalize_draft.py --manifest):
        {"schema_version", "review_kind", "verification_mode", "finalized_at",
         "mapping": [{citation, mapped, source_id, title?, url?, claims?[]}]}
  - claim_manifest (claim-centric, from finalize_draft.py --claim-manifest):
        {"schema_version", "review_kind", "verification_mode", "finalized_at",
         "claims": [{claim_id, claim_class, claim_text, evidence[]}]}

Purpose: catch missing fields / illegal enum values (support_level, freshness,
review_kind, claim_class, ...) so a malformed manifest never flows downstream
to a research agent as if it were valid provenance.

Usage:
  python shared/scripts/validate_manifest.py manifest.json
  python shared/scripts/validate_manifest.py manifest.json --schema claim_manifest
  python shared/scripts/validate_manifest.py manifest.json --json   # machine-readable
Exit codes: 0 valid; 1 invalid; 2 usage/input error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = "0.2.0"

# 版本兼容（PR-09）：LEGACY_VERSIONS 中的旧版本可以迁移到当前版本。
# 命中旧版本 → 仅告警（提示运行 migrate_manifest.py），不当作非法拒绝；
# 完全未知的版本 → 仍报错。废弃字段命中 → 告警而非硬报错。
LEGACY_VERSIONS = {
    "0.1.0": "0.2.0",
}
DEPRECATED_FIELDS = ()  # 迁移时在此登记：字段名 → 替代说明

REVIEW_KINDS = ("ai-internal", "ai-cross-model", "human-expert")
VERIFICATION_MODES = ("static", "live")
CLAIM_CLASSES = ("E", "M", "N", "L", "D", "C", "U", "J")
RISK_TIERS = ("R0", "R1", "R2", "R3", "R4")
SUPPORT_LEVELS = (
    "direct", "strong_inference", "weak_inference",
    "context_only", "contradictory", "unsupported",
)
EVIDENCE_STATUSES = (
    "verified", "supported", "partially_supported", "inferred",
    "contradicted", "unsupported", "unverified", "internal_confirm",
)
AUTHORITIES = ("A1", "A2", "A3", "B1", "B2", "C1", "C2", "D1", "D2")
FRESHNESSES = ("current", "recent", "historical", "superseded", "unknown")
RELATIONS = ("supports", "contradicts", "context_only")
CONFIDENCES = ("high", "medium", "low")
LOCATOR_KEYS = ("page", "section", "paragraph", "quote_hash", "locator_quality")
LOCATOR_QUALITIES = ("high", "medium", "low")

SOURCE_ID_RE = re.compile(r"^S\d+$")
CLAIM_ID_RE = re.compile(r"^C-\d+$")


def _is_date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        import datetime
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _check_enum(problems: list[str], obj: dict, key: str, allowed: tuple[str, ...]) -> None:
    value = obj.get(key)
    if value is not None and value not in allowed:
        problems.append(f"{key} has illegal value {value!r} (allowed: {', '.join(allowed)})")


def validate_manifest(data) -> list[str]:
    """Return a list of contract violations (empty list = valid)."""
    problems, _ = validate_manifest_full(data)
    return problems


def validate_manifest_full(data) -> tuple[list[str], list[str]]:
    """Validate and return (problems, warnings).

    Warnings are non-fatal: legacy schema_version (→ run migrate_manifest.py) and
    deprecated fields. Problems are hard contract violations.
    """
    problems: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        problems.append("root must be a JSON object")
        return problems, warnings

    version = data.get("schema_version")
    if version == SCHEMA_VERSION:
        pass
    elif version in LEGACY_VERSIONS:
        warnings.append(
            f"schema_version {version!r} is legacy — run "
            "`python shared/scripts/migrate_manifest.py <manifest>` to upgrade "
            f"to {LEGACY_VERSIONS[version]!r}; validating against the legacy shape"
        )
    else:
        problems.append(
            f"schema_version must be {SCHEMA_VERSION!r} (got {version!r}); "
            "re-run finalize_draft.py with the matching version"
        )
    for field, note in DEPRECATED_FIELDS:
        if field in data:
            warnings.append(f"deprecated field {field!r}: {note}")
    _check_enum(problems, data, "review_kind", REVIEW_KINDS)
    if "review_kind" not in data:
        problems.append("missing required field: review_kind")
    _check_enum(problems, data, "verification_mode", VERIFICATION_MODES)
    if "verification_mode" not in data:
        problems.append("missing required field: verification_mode")
    if "finalized_at" not in data:
        problems.append("missing required field: finalized_at")
    elif not _is_date(data.get("finalized_at")):
        problems.append(f"finalized_at is not a valid ISO date: {data.get('finalized_at')!r}")

    if "mapping" in data:
        problems.extend(_validate_mapping(data))
    if "claims" in data:
        problems.extend(_validate_claims(data))
    if "mapping" not in data and "claims" not in data:
        problems.append("manifest must contain either a 'mapping' array (source-centric) or a 'claims' array (claim-centric)")
    problems.extend(_validate_review_independence(data))

    return problems, warnings


def _validate_review_independence(data: dict) -> list[str]:
    """review_independence: cross-model is NOT independence if context/evidence shared."""
    problems: list[str] = []
    ri = data.get("review_independence")
    if ri is None:
        return problems
    if not isinstance(ri, dict):
        problems.append("review_independence must be an object")
        return problems
    str_fields = ("reviewer_model", "writer_model", "model_family")
    for key in str_fields:
        if key in ri and not isinstance(ri[key], str):
            problems.append(f"review_independence.{key} must be a string")
    bool_fields = ("context_shared", "evidence_shared")
    for key in bool_fields:
        if key in ri and not isinstance(ri[key], bool):
            problems.append(f"review_independence.{key} must be a boolean")
    if "human_involvement" in ri and ri["human_involvement"] not in ("none", "partial", "full"):
        problems.append(f"review_independence.human_involvement must be one of "
                        f"none/partial/full (got {ri['human_involvement']!r})")
    return problems


def _validate_mapping(data: dict) -> list[str]:
    problems: list[str] = []
    mapping = data.get("mapping")
    if not isinstance(mapping, list):
        problems.append("mapping must be an array")
        return problems
    seen_sids: set[str] = set()
    for i, entry in enumerate(mapping):
        prefix = f"mapping[{i}]"
        if not isinstance(entry, dict):
            problems.append(f"{prefix} must be an object")
            continue
        for key in ("citation", "mapped", "source_id"):
            if key not in entry:
                problems.append(f"{prefix} missing required field: {key}")
        sid = str(entry.get("source_id", ""))
        if not SOURCE_ID_RE.match(sid):
            problems.append(f"{prefix}.source_id must match ^S\\d+$ (got {sid!r})")
        if sid in seen_sids:
            problems.append(f"{prefix} duplicate source_id: {sid}")
        seen_sids.add(sid)
        if not re.match(r"^\[S\d+\]$", str(entry.get("citation", ""))):
            problems.append(f"{prefix}.citation must match ^[S\\d+]$ (got {entry.get('citation')!r})")
        if not re.match(r"^\[\d+\]$", str(entry.get("mapped", ""))):
            problems.append(f"{prefix}.mapped must match ^[\\d+]$ (got {entry.get('mapped')!r})")
        if entry.get("url") and not str(entry["url"]).startswith(("http://", "https://")):
            problems.append(f"{prefix}.url must be an http(s) URL (got {entry.get('url')!r})")
        for j, claim in enumerate(entry.get("claims") or []):
            cprefix = f"{prefix}.claims[{j}]"
            if not isinstance(claim, dict):
                problems.append(f"{cprefix} must be an object")
                continue
            if "claim_text" not in claim:
                problems.append(f"{cprefix} missing required field: claim_text")
            _check_enum(problems, claim, "claim_class", CLAIM_CLASSES)
            _check_enum(problems, claim, "support_level", SUPPORT_LEVELS)
            _check_enum(problems, claim, "evidence_status", EVIDENCE_STATUSES)
    return problems


def _validate_claims(data: dict) -> list[str]:
    problems: list[str] = []
    claims = data.get("claims")
    if not isinstance(claims, list):
        problems.append("claims must be an array")
        return problems
    seen_ids: set[str] = set()
    for i, claim in enumerate(claims):
        prefix = f"claims[{i}]"
        if not isinstance(claim, dict):
            problems.append(f"{prefix} must be an object")
            continue
        for key in ("claim_id", "claim_class", "claim_text", "evidence"):
            if key not in claim:
                problems.append(f"{prefix} missing required field: {key}")
        cid = str(claim.get("claim_id", ""))
        if not CLAIM_ID_RE.match(cid):
            problems.append(f"{prefix}.claim_id must match ^C-\\d+$ (got {cid!r})")
        if cid in seen_ids:
            problems.append(f"{prefix} duplicate claim_id: {cid}")
        seen_ids.add(cid)
        _check_enum(problems, claim, "claim_class", CLAIM_CLASSES)
        _check_enum(problems, claim, "risk", RISK_TIERS)
        _check_enum(problems, claim, "evidence_status", EVIDENCE_STATUSES)
        evidence = claim.get("evidence")
        if not isinstance(evidence, list):
            if "evidence" in claim:
                problems.append(f"{prefix}.evidence must be an array")
            continue
        for j, ev in enumerate(evidence):
            eprefix = f"{prefix}.evidence[{j}]"
            if not isinstance(ev, dict):
                problems.append(f"{eprefix} must be an object")
                continue
            for key in ("source_id", "support_level"):
                if key not in ev:
                    problems.append(f"{eprefix} missing required field: {key}")
            sid = str(ev.get("source_id", ""))
            if not SOURCE_ID_RE.match(sid):
                problems.append(f"{eprefix}.source_id must match ^S\\d+$ (got {sid!r})")
            _check_enum(problems, ev, "support_level", SUPPORT_LEVELS)
            _check_enum(problems, ev, "authority", AUTHORITIES)
            _check_enum(problems, ev, "freshness", FRESHNESSES)
            _check_enum(problems, ev, "relation", RELATIONS)
            locator = ev.get("locator")
            if locator is not None:
                if not isinstance(locator, dict):
                    problems.append(f"{eprefix}.locator must be an object")
                else:
                    for k in locator:
                        if k not in LOCATOR_KEYS:
                            problems.append(f"{eprefix}.locator has unknown key {k!r} "
                                            f"(allowed: {', '.join(LOCATOR_KEYS)})")
                        elif k == "locator_quality":
                            if locator[k] not in LOCATOR_QUALITIES:
                                problems.append(f"{eprefix}.locator.locator_quality must be one of "
                                                f"high/medium/low (got {locator[k]!r})")
                        elif k == "page" and not isinstance(locator[k], int):
                            problems.append(f"{eprefix}.locator.page must be an integer")
                        elif k == "paragraph" and not isinstance(locator[k], int):
                            problems.append(f"{eprefix}.locator.paragraph must be an integer")
        _check_enum(problems, claim, "confidence", CONFIDENCES)
        if "interpretation" in claim and not isinstance(claim.get("interpretation"), str):
            problems.append(f"{prefix}.interpretation must be a string")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="path to the manifest JSON to validate")
    parser.add_argument(
        "--schema", choices=["evidence_manifest", "claim_manifest"], default=None,
        help="explicit schema; default: auto-detect by presence of 'mapping'/'claims'",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="emit machine-readable {valid, errors[]} instead of human text",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"error: invalid JSON in {args.manifest}: {exc}", file=sys.stderr)
        return 2

    problems, warnings = validate_manifest_full(data)
    valid = not problems
    if args.json:
        print(json.dumps({"valid": valid, "warnings": warnings, "errors": problems},
                         ensure_ascii=False, indent=2))
    else:
        if valid:
            print("manifest: valid")
        else:
            for p in problems:
                print("manifest problem:", p)
        for w in warnings:
            print("manifest warning:", w)
    return 0 if valid else 1


if __name__ == "__main__":
    sys.exit(main())
