#!/usr/bin/env sh
# 最小一键复现：evidence-suite 证据驱动校验 Demo（macOS / Linux）
set -e
quick="$(cd "$(dirname "$0")" && pwd)"
suite="$(cd "$quick/../.." && pwd)"
mkdir -p "$quick/output"

python "$suite/shared/scripts/finalize_draft.py" "$quick/input_draft.md" \
  -o "$quick/output/clean.md" \
  --manifest "$quick/output/evidence_manifest.json" \
  --sources "$quick/sources.json" --review-kind ai-internal

python "$suite/shared/scripts/finalize_draft.py" "$quick/input_draft.md" \
  --claim-manifest "$quick/output/claim_manifest.json" \
  --evidence-map "$quick/evidence_map.json" \
  --sources "$quick/sources.json" --review-kind ai-internal

python "$suite/shared/scripts/check_evidence_sufficiency.py" \
  "$quick/evidence_map.json" "$quick/sources.json"

python "$suite/shared/scripts/build_evidence_brief.py" \
  "$quick/evidence_map.json" "$quick/sources.json" -o "$quick/output/evidence_brief.md"

python "$suite/shared/scripts/export_provenance.py" \
  --draft "$quick/input_draft.md" \
  --sources "$quick/sources.json" \
  --evidence-map "$quick/evidence_map.json" \
  -o "$quick/output/provenance"

python "$suite/shared/scripts/validate_manifest.py" "$quick/output/evidence_manifest.json"
python "$suite/shared/scripts/validate_manifest.py" "$quick/output/claim_manifest.json"

echo ""
echo "Demo OK: 净化 -> manifest -> 充分性 -> Evidence Brief -> Provenance -> 校验 全部通过。样例见 output/ 与 expected/"
