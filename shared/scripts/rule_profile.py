#!/usr/bin/env python3
r"""Load & merge evidence-suite rule profiles (规则配置加载器).

Rules live in shared/config/rules.yaml (the single source of truth for
risk_tiers / claim_classes / doc_minimums / suspect_domains / stop_rule).
This loader resolves the effective rules with layered overrides:

  1. shared/config/rules.yaml            (repository default)
  2. <SUITE_ROOT>/config/rules.user.yaml (repository-level user override, auto-loaded)
  3. --rules <path>                      (explicit override file)
  4. --profile <scenario>                (scenario profile, deep-merged last)

Dependency policy: prefers PyYAML when installed, but falls back to a built-in
minimal YAML-subset parser so core scripts stay stdlib-only. The default
config is written in block style (no flow mappings) to be parseable by the
fallback; do not introduce inline {...} structures there.

Usage:
  from rule_profile import load_rules
  rules = load_rules()                       # defaults + auto user override
  rules = load_rules(profile="medical")      # apply scenario profile
  rules = load_rules(rules_path="my.yaml", profile="general_tech")
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RULES = SUITE_ROOT / "shared" / "config" / "rules.yaml"
USER_RULES = SUITE_ROOT / "config" / "rules.user.yaml"


def _scalar(s: str):
    """Coerce a YAML scalar string to the closest Python literal."""
    s = s.strip()
    if not s or s in ("null", "~", "None"):
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [_scalar(x.strip()) for x in inner.split(",")] if inner else []
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _minimal_yaml(text: str):
    """Parse a restricted YAML subset without PyYAML.

    Supports: '#' comments, nested mappings by 2-space indentation, scalar
    values, and '-' sequence items of scalars (no nested sequences/mappings
    inside list items). Throws on anything it cannot safely represent.
    """
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # strip inline comments only when the '#' is not inside a quoted string
        line = _strip_inline_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2 != 0:
            raise ValueError(f"unsupported indentation (not multiple of 2): {raw!r}")
        lines.append((indent, line.strip()))

    def parse_block(idx: int, indent: int):
        if idx >= len(lines) or lines[idx][0] < indent:
            return None, idx
        if lines[idx][0] != indent:
            raise ValueError(f"unexpected indentation at line {idx}: {lines[idx]!r}")

        # sequence block
        if lines[idx][1].startswith("- "):
            items: list = []
            while idx < len(lines) and lines[idx][0] == indent and lines[idx][1].startswith("- "):
                rest = lines[idx][1][2:].strip()
                if rest:
                    items.append(_scalar(rest))
                    idx += 1
                else:
                    child, idx = parse_block(idx + 1, indent + 2)
                    items.append(child)
            return items, idx

        # mapping block
        obj: dict = {}
        while idx < len(lines) and lines[idx][0] == indent and not lines[idx][1].startswith("- "):
            m = re.match(r"^([^:]+):\s*(.*)$", lines[idx][1])
            if not m:
                raise ValueError(f"cannot parse line {idx}: {lines[idx][1]!r}")
            key = m.group(1).strip().strip('"').strip("'")
            rest = m.group(2).strip()
            idx += 1
            if rest:
                obj[key] = _scalar(rest)
            else:
                child, idx = parse_block(idx, indent + 2)
                obj[key] = child
        return obj, idx

    if not lines:
        return {}
    value, _ = parse_block(0, lines[0][0])
    return value or {}


def _strip_inline_comment(line: str) -> str:
    """Remove a trailing # comment, respecting single/double quotes."""
    quote: str | None = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ('"', "'"):
            quote = ch
        elif ch == "#":
            return line[:i].rstrip()
    return line


def _read(path: Path):
    """Read a YAML or JSON rules file (JSON allows keys like R3 unquoted)."""
    if not path.exists():
        raise FileNotFoundError(f"rules file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".json",):
        return json.loads(text)
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except ImportError:
        return _minimal_yaml(text)


def merge_deep(base, override):
    """Deep-merge override into base. dicts recurse; lists/scalars replace."""
    if not isinstance(base, dict) or not isinstance(override, dict):
        return override if override is not None else base
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge_deep(out[key], value)
        else:
            out[key] = value
    return out


def load_rules(rules_path: str | Path | None = None,
               profile: str | None = None) -> dict:
    """Return the effective rules dict after layered merging.

    Raises FileNotFoundError if an explicit rules_path is missing, or KeyError
    if an unknown profile is requested.
    """
    base = _read(DEFAULT_RULES)
    if USER_RULES.exists():
        base = merge_deep(base, _read(USER_RULES))
    if rules_path is not None:
        base = merge_deep(base, _read(Path(rules_path)))
    if profile:
        profiles = base.get("scenario_profiles") or {}
        if profile not in profiles:
            raise KeyError(f"unknown profile {profile!r}; available: {sorted(profiles)}")
        base = merge_deep(base, profiles[profile])
        base["active_profile"] = profile
    return base


def effective_suspect_domains(rules: dict, cli_extra: list[str] | None = None) -> tuple[str, ...]:
    """Resolve the suspect-domain blocklist: config base + scenario extra + CLI extra."""
    domains: list[str] = []
    cfg = rules.get("suspect_domains")
    if isinstance(cfg, list):
        domains = [str(d) for d in cfg]
    for d in rules.get("suspect_domains_extra") or []:
        if str(d) not in domains:
            domains.append(str(d))
    for d in cli_extra or []:
        if d not in domains:
            domains.append(d)
    return tuple(domains)


def doc_minimum(rules: dict, doc_type: str) -> dict:
    """Return {min_sources, min_chars} for a doc type, or {} if not configured."""
    return dict(rules.get("doc_minimums", {}).get(doc_type, {}))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules", type=Path, default=None, help="extra rules override file")
    parser.add_argument("--profile", type=str, default=None, help="scenario profile name")
    parser.add_argument("--show", action="store_true", help="print the effective rules as JSON")
    args = parser.parse_args()
    try:
        effective = load_rules(rules_path=args.rules, profile=args.profile)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
    if args.show:
        print(json.dumps(effective, ensure_ascii=False, indent=2))
    print(f"rules loaded from {DEFAULT_RULES}"
          + (f" + user override {USER_RULES}" if USER_RULES.exists() else "")
          + (f" + --rules {args.rules}" if args.rules else "")
          + (f" + profile {args.profile!r}" if args.profile else ""))
    sys.exit(0)
