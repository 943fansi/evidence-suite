# w3: Validated Corpus（验证语料，写作者侧 · 全局阶段 3）

> 本阶段依据审核方 r1 的审计报告，从 `02_raw_sources.json` **创建** `04_validated_sources.json` 语料，并落地为可机械验证的实物（PDF + 抽取文本）。来源可信度审计属审核方 r1（全局2）；证据图谱属本 skill w4。

**Agent**: 本地执行（当前 assistant）· 本 skill（evidence-writer）
**Input**: `02_raw_sources.json` + `03_audit_report.md`（审核方 r1 审计通过后）
**Output**: `04_validated_sources.json`（新建）+ `reference_files/*.pdf` + `pdf_text/*.txt`

## 前置条件

- 审核方已出具 `03_audit_report.md` 且判决允许进入 w3（不可跳过审计直接构造语料）。
- 若审核方判决为"退回补搜"，先按清单补检索重走 w2→r1，再回来。
- **`04_validated_sources.json` 由本阶段创建**：审核方 r1 不生成语料，只产 `03_audit_report.md`。

## 执行步骤

1. 依据 `03_audit_report.md` 的审计结论对 `02_raw_sources.json` 逐条处理，**创建** `04_validated_sources.json`：
   - 删除 `suggested_action="delete"` 的来源；按审计建议降级 role（`sources_to_avoid_as_core_evidence` → 仅作背景/线索）；保留 URL。
   - 补字段：`role`、`access_status`、`url_verified`、`registry_id`（w2 清单内 id 或 `"supplementary"`+理由）、`allow_full_text`（取来源路由清单 `allowFullText`；清单外补充来源默认 true 待核）。
   - 审计指出的证据缺口（`weak_evidence` / `missing_fields`）保留为一级条目，不得静默丢弃。
2. **依次执行 3 个强制子步骤，任一缺失 w3 视为未完成**（审核方门禁会校验）：
   - **3a 批量下载 PDF**：`python ${SUITE_ROOT}/shared/scripts/download_reference_files.py 04_validated_sources.json -o reference_files/ --update-sources`
   - **3b 下载校验**：确认每条来源的 `access_status`（`confirmed`=PDF已下载 / `web_accessible`=URL存在未下载 / `unavailable`=下载失败或非PDF），语料中不得留空值。
   - **3c PDF 文本抽取**：`python ${SUITE_ROOT}/shared/scripts/extract_pdf_text.py --manifest reference_files/manifest.json --sources 04_validated_sources.json --pdf-dir reference_files --update-sources --extract-quotes`
3. 校验完成后在 `04_validated_sources.json` 中标注 `pdf_text_extracted: true/false`，供 w4/w5 区分「原文验证」与「搜索摘要」。
4. 语料自检命令由审核方在门禁时运行；作者可先自查字段完整性（无重复 URL、无缺 title/source_id、`access_status` 无空）。

## 完成标准

- 语料 `access_status` 无空值；`pdf_text_extracted` 已标注。
- 语料内每条来源含 `registry_id`（清单内 id 或 `"supplementary"`+理由）。
- 参考文件 ≥1 个 PDF、抽取文本 ≥1 个非空 txt。

完成后进入 w4（证据图谱），无需本阶段单独提交审查。