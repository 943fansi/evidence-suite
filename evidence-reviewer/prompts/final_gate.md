# Final Gate（终审门，审查者侧）

> 交付前最后一道闸。作者声称已完成（`14_专家修订稿.md` 或 `11_定稿.md`，以及净化版 `*_clean.md`）并准备导出时，审查者核对合规性。任何一项不通过即 ⛔ 退回，不放行"带病交付"。

**Agent**: 本地执行（当前 assistant）· 本 skill（evidence-reviewer）
**Input**: 工作稿（`11_定稿.md` / `14_专家修订稿.md`）+ 净化版（`{FINAL_DRAFT}_clean.md`，即 `11_定稿_clean.md` 或 `14_专家修订稿_clean.md`）+ `04_validated_sources.json`
**Output**: 终审门判决（可并入交付说明，或单独落盘）

> **终稿变量（FINAL_DRAFT）**：与写作者 w9 同约定——`FINAL_DRAFT = 14_专家修订稿（若存在）否则 11_定稿`。净化版统一写作 `{FINAL_DRAFT}_clean.md`。

## 执行步骤

1. 先核实作者提交的工件存在且与上一判决对应（若上一判决为 🔁，先核对响应说明表已逐条闭合且无回归）。
2. 依次执行以下检查，全部通过才放行：

### A. 净化合规（正式交付物必查）
- Grep 净化版：无 `[Sx]` / `[Gx]` / `[假设]` / `[待内部确认]` / `[待验证]` 残留。
- 无"标记图例"、"附录A 证据缺口清单"、`references/*.md` 内部路径。
- 无封面占位（`编号：2023xxxx`、`资助项目`）。
- 无爬虫/提示词痕迹（如"反爬""NRC ADAMS 不可下载"）。
- 引文为标准顺序编码 `[1]..[n]`，正文引用全覆盖。
- 运行：`python ${SUITE_ROOT}/shared/scripts/finalize_draft.py {FINAL_DRAFT}_clean.md --check --sources 04_validated_sources.json`（净化合规检查**只对净化版**执行；对工作稿跑会因脚手架标记必然误报残留）

### B. 数字引文闭合（净化版）
- 运行：`python ${SUITE_ROOT}/shared/scripts/check_citations.py {FINAL_DRAFT}_clean.md --academic --min-sources N --min-chars N`
- 每个正文 `[n]` 都有对应条目、每条被引用、编号连续 1..N。

### C. 工作稿引用与质量门（未净化版复核）
- 引用闭合：`check_citations.py 11_定稿.md --sources 04_validated_sources.json`
- 来源数量下限：`check_citations.py 11_定稿.md --min-sources N`（按文档类型）
- 正文深度下限：`check_citations.py 11_定稿.md --min-chars N`（按文档类型）
- 语料自检：`validate_sources.py 04_validated_sources.json`（学位类加 `--quota-cn-journal 10`）
- 框架深度门（框架类）：`check_framework_depth.py 11_定稿.md`
- 阶段门禁：`inspect_pipeline.py --gates ./proposal_workspace`

### D. 人工核查项（脚本无法覆盖，见 `${SUITE_ROOT}/shared/references/finalize_checklist.md`）
- **参考文献节唯一性（脚本盲区，必查）**：全文 H2 标题仅出现一个参考文献节（`## 参考文献` 或 `## N. 参考文献` 只允许其一）。`build_references.py` 曾因标题带编号（`## 13. 参考文献`）不匹配裸标题而追加第二节，产生两份不一致题录——脚本闭合检查测不出（合计条目数不变），须人工核对 S-ID 唯一。重复即退回。
- 参考文献符合 GB/T 7714-2015（学位/期刊交付版）：期刊条目含作者与卷期页码、标准类标准号与标题相符、URL 无重复。
- 学位类实证算例已包含（可复现、参数列全、诚实标注演示算例、含数值曲线图）；图号全文唯一、正文引述一致。
- 专利类：申请草案全文零引用标记（证据闭合在配套 12_背景技术证据对照.md）。
- 缩写首现给全称；无重复段落；forbidSources 零命中；allowFullText: false 来源未出现全文级结论；标准类已核现行有效性。
- 若要求 PDF/DOCX：作者已运行导出 + `visual_qa.py` 抽检，长 URL 断行/悬挂缩进/表格溢出均通过。
- **证据 provenance**：正式交付须随附 `{FINAL_DRAFT}_manifest.json`（`finalize_draft.py --manifest --sources … [--evidence-map 06_evidence_map.json]` 产出），确认其中 `verification_mode` 已记录、`[Sx]↔[n]→来源` 映射完整；涉及监管/安全/财务（R3/R4）的文档若 `verification_mode=static`，要求作者说明为何未做 live 回源验证。

## 判决规则

- **✅ 可导出**：A–D 全部通过。
- **⛔ 退回**：任一检查失败 → 指出失败项与位置，判决作者修正后重新提交终审。
- 净化版残留脚手架属 ⛔（净化不可逆，要求作者重跑净化并 `--check`）。

## 输出

```markdown
# 终审门判决
**判决**: ✅ 可导出 / ⛔ 退回

## A 净化合规    ✅/❌ （失败项+位置）
## B 数字引文    ✅/❌
## C 工作稿门禁  ✅/❌
## D 人工核查    ✅/❌
## 退回指令（若 ⛔）
| 失败项 | 位置 | 修正要求 |
```