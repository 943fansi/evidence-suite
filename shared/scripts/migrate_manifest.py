#!/usr/bin/env python3
r"""Upgrade legacy evidence manifests to the current schema (PR-09).

Old manifest files must not be silently rejected nor silently mis-read. This
tool migrates them forward so `validate_manifest.py` can accept the result.

Registered migrations (source of truth = validate_manifest.LEGACY_VERSIONS):
  0.1.0 → 0.2.0  (V2 evidence model)
    - evidence[] entries gain `relation` derived from `support_level`
      (contradictory→contradicts, context_only→context_only, else supports).
    - manifest gains a default `review_independence`
      ({context_shared: true, evidence_shared: true, human_involvement: none})
      when absent — matches the ai-internal default finalize_draft.py writes.

Migration is idempotent: re-running on an already-current manifest is a no-op
with an informational message. Unknown / unregistered versions are refused
(they may need a manual merge, not a mechanical one).

Usage:
  python shared/scripts/migrate_manifest.py old.json
  python shared/scripts/migrate_manifest.py old.json -o migrated.json
  python shared/scripts/migrate_manifest.py old.json --dry-run   # preview, no write
Exit codes: 0 migrated/current; 1 unknown version (refused); 2 usage/input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from validate_manifest import LEGACY_VERSIONS, SCHEMA_VERSION


def _derive_relation(ev: dict) -> str:
    level = ev.get("support_level", "")
    if level == "contradictory":
        return "contradicts"
    if level == "context_only":
        return "context_only"
    return "supports"


def _default_review_independence() -> dict:
    return {
        "human_involvement": "none",
        "context_shared": True,
        "evidence_shared": True,
    }


def _migrate_0_1_0_to_0_2_0(data: dict) -> dict:
    out = json.loads(json.dumps(data))  # deep copy
    out["schema_version"] = "0.2.0"
    out.setdefault("review_independence", _default_review_independence())
    claims = out.get("claims")
    if isinstance(claims, list):
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            evidence = claim.get("evidence")
            if not isinstance(evidence, list):
                continue
            for ev in evidence:
                if not isinstance(ev, dict):
                    continue
                if "relation" not in ev:
                    ev["relation"] = _derive_relation(ev)
    return out


MIGRATIONS = {
    "0.1.0": _migrate_0_1_0_to_0_2_0,
}


def migrate(data: dict) -> tuple[dict | None, str | None]:
    """Return (migrated, error). (None, None) when already current."""
    version = data.get("schema_version") if isinstance(data, dict) else None
    if version == SCHEMA_VERSION:
        return None, None
    if version not in MIGRATIONS:
        return None, (
            f"schema_version {version!r} is not registered for migration "
            f"(current {SCHEMA_VERSION!r}); migrate manually or re-generate "
            f"with finalize_draft.py"
        )
    return MIGRATIONS[version](data), None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="legacy manifest JSON to migrate")
    parser.add_argument("-o", "--output", type=Path, default=None,
                        help="write migrated manifest here (default: overwrite in place)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the migration summary without writing any file")
    args = parser.parse_args()

    if not args.manifest.exists():
        print(f"error: manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"error: invalid JSON in {args.manifest}: {exc}", file=sys.stderr)
        return 2

    migrated, error = migrate(data)
    if error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if migrated is None:
        print(f"no migration needed: already schema_version {SCHEMA_VERSION!r}")
        return 0

    changes = _change_summary(data, migrated)
    print(f"migrated: {data.get('schema_version')} -> {migrated['schema_version']}")
    for line in changes:
        print("  " + line)

    if args.dry_run:
        print("dry-run: no file written")
        return 0

    target = args.output or args.manifest
    target.write_text(json.dumps(migrated, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote -> {target}")
    return 0


def _change_summary(before: dict, after: dict) -> list[str]:
    lines: list[str] = []
    if "review_independence" not in before and "review_independence" in after:
        lines.append("+ review_independence (default ai-internal: shared context/evidence, no human)")
    old_claims = {c.get("claim_id"): c for c in before.get("claims", []) if isinstance(c, dict)}
    for claim in after.get("claims", []):
        if not isinstance(claim, dict):
            continue
        old = old_claims.get(claim.get("claim_id"), {})
        old_ev = old.get("evidence") if isinstance(old.get("evidence"), list) else []
        new_ev = claim.get("evidence") if isinstance(claim.get("evidence"), list) else []
        gained = sum(
            1 for i, ev in enumerate(new_ev)
            if isinstance(ev, dict) and "relation" in ev
            and not (i < len(old_ev) and isinstance(old_ev[i], dict) and "relation" in old_ev[i])
        )
        if gained:
            lines.append(f"+ claims[{claim.get('claim_id')}] derived relation for {gained} evidence entries")
    return lines


if __name__ == "__main__":
    sys.exit(main())
