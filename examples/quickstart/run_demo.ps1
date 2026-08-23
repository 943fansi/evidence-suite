# 最小一键复现：evidence-suite 证据驱动校验 Demo（Windows PowerShell）
$ErrorActionPreference = "Stop"
$quick = $PSScriptRoot
$suite = Split-Path -Parent (Split-Path -Parent $quick)
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Error "python not found in PATH"; exit 1 }
New-Item -ItemType Directory -Force -Path (Join-Path $quick "output") | Out-Null

& $py.Source (Join-Path $suite "shared\scripts\finalize_draft.py") (Join-Path $quick "input_draft.md") -o (Join-Path $quick "output\clean.md") --manifest (Join-Path $quick "output\evidence_manifest.json") --sources (Join-Path $quick "sources.json") --review-kind ai-internal
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $py.Source (Join-Path $suite "shared\scripts\finalize_draft.py") (Join-Path $quick "input_draft.md") --claim-manifest (Join-Path $quick "output\claim_manifest.json") --evidence-map (Join-Path $quick "evidence_map.json") --sources (Join-Path $quick "sources.json") --review-kind ai-internal
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $py.Source (Join-Path $suite "shared\scripts\check_evidence_sufficiency.py") (Join-Path $quick "evidence_map.json") (Join-Path $quick "sources.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $py.Source (Join-Path $suite "shared\scripts\build_evidence_brief.py") (Join-Path $quick "evidence_map.json") (Join-Path $quick "sources.json") -o (Join-Path $quick "output\evidence_brief.md")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $py.Source (Join-Path $suite "shared\scripts\export_provenance.py") --draft (Join-Path $quick "input_draft.md") --sources (Join-Path $quick "sources.json") --evidence-map (Join-Path $quick "evidence_map.json") -o (Join-Path $quick "output\provenance")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $py.Source (Join-Path $suite "shared\scripts\validate_manifest.py") (Join-Path $quick "output\evidence_manifest.json")
& $py.Source (Join-Path $suite "shared\scripts\validate_manifest.py") (Join-Path $quick "output\claim_manifest.json")

Write-Host ""
Write-Host "Demo OK: 净化 -> manifest -> 充分性 -> Evidence Brief -> Provenance -> 校验 全部通过。样例见 output/ 与 expected/"
