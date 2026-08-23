# 最小示例（quickstart）

一行复现 evidence-suite 的完整证据工程闭环：**定稿净化 → manifest 产出 → claim 级证据充分性 → Evidence Brief → Provenance 五件套 → schema 校验**，不需要任何第三方依赖、不需要联网。

## 文件

```
quickstart/
├── input_draft.md      # 最小输入：3 条带 [Sx] 的论断 + 参考文献
├── sources.json        # 语料（04_validated_sources.json 最小版，含 authority/freshness）
├── evidence_map.json   # 证据图谱（06_evidence_map.json 最小版，含 locator/relation/confidence + 反证负结果）
├── run_demo.ps1        # Windows 一键复现
├── run_demo.sh         # macOS / Linux 一键复现
├── output/             # 脚本生成的中间物（clean.md + manifests + evidence_brief.md + provenance/）
└── expected/           # 期望输出样例（evidence_manifest.json / claim_manifest.json）
```

## 复现

PowerShell：
```powershell
./run_demo.ps1
```

或逐条执行：
```bash
# 1) 定稿净化 + source-centric manifest
python <suite>/shared/scripts/finalize_draft.py input_draft.md -o output/clean.md \
    --manifest output/evidence_manifest.json --sources sources.json --review-kind ai-internal

# 2) claim-centric manifest（互操作契约，含 relation/locator/confidence）
python <suite>/shared/scripts/finalize_draft.py input_draft.md \
    --claim-manifest output/claim_manifest.json --evidence-map evidence_map.json \
    --sources sources.json --review-kind ai-internal

# 3) claim 级证据充分性（按 R2/R3 判定 primary/独立来源/现行性/反证覆盖）
python <suite>/shared/scripts/check_evidence_sufficiency.py evidence_map.json sources.json

# 4) Evidence Brief（L1）：claim→evidence→平衡→置信度 表格 + 评分 + 充分性
python <suite>/shared/scripts/build_evidence_brief.py evidence_map.json sources.json \
    -o output/evidence_brief.md

# 5) Provenance 五件套（机器审计：claims/evidence/source-map/review.json）
python <suite>/shared/scripts/export_provenance.py \
    --draft input_draft.md --sources sources.json --evidence-map evidence_map.json \
    -o output/provenance

# 6) 契约校验（缺字段 / 非法枚举会报错并拒绝）
python <suite>/shared/scripts/validate_manifest.py output/evidence_manifest.json
python <suite>/shared/scripts/validate_manifest.py output/claim_manifest.json
```

`<suite>` 替换为 evidence-suite 克隆路径（`run_demo.*` 脚本已自动定位，无需手工替换）。

## 期望结果

- 各步均 `exit 0`；充分性输出 `2/2 claims sufficient`，Provenance 输出 4 个 `report.*.json`，manifest 校验 `manifest: valid`。
- `output/evidence_manifest.json` 含 `schema_version` / `review_kind` / `mapping[]`；`output/claim_manifest.json` 含 `claims[]`（evidence 带 `relation`/`locator`，claim 带 `confidence`/`interpretation`），与 `expected/` 样例一致。
- `output/evidence_brief.md` 含评分列（Evidence Score + 等级）；`output/provenance/report.source-map.json` 给出正文 `[n]`→source_id 对账表。
- 若校验报 `manifest problem:`、充分性报 `❌` 或 Provenance 校验失败，说明产物不满足契约/证据不足，应修复源头而非绕过校验。
