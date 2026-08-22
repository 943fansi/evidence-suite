# 最小示例（quickstart）

一行复现 evidence-suite 的核心闭环：**定稿净化 → manifest 产出 → schema 校验**，不需要任何第三方依赖、不需要联网。

## 文件

```
quickstart/
├── input_draft.md      # 最小输入：2 条带 [Sx] 的论断 + 参考文献
├── sources.json        # 语料（04_validated_sources.json 最小版，含 authority/freshness）
├── evidence_map.json   # 证据图谱（06_evidence_map.json 最小版，含 reconciliation）
├── run_demo.ps1        # Windows 一键复现
├── run_demo.sh         # macOS / Linux 一键复现
├── output/             # 脚本生成的中间物（clean.md + 两个 manifest）
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

# 2) claim-centric manifest（互操作契约）
python <suite>/shared/scripts/finalize_draft.py input_draft.md \
    --claim-manifest output/claim_manifest.json --evidence-map evidence_map.json \
    --sources sources.json --review-kind ai-internal

# 3) 契约校验（缺字段 / 非法枚举会报错并拒绝）
python <suite>/shared/scripts/validate_manifest.py output/evidence_manifest.json
python <suite>/shared/scripts/validate_manifest.py output/claim_manifest.json
```

`<suite>` 替换为 evidence-suite 克隆路径（`run_demo.*` 脚本已自动定位，无需手工替换）。

## 期望结果

- 三条命令均 `exit 0`，manifest 校验输出 `manifest: valid`。
- `output/evidence_manifest.json` 含 `schema_version` / `review_kind` / `mapping[]`；`output/claim_manifest.json` 含 `claims[]`，与 `expected/` 样例一致。
- 若校验报 `manifest problem:`，说明产物不满足契约（缺字段 / 非法枚举），应修复源头而非绕过校验。
