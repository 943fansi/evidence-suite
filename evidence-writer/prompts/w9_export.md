# w9: Export（导出，写作者侧 · 全局阶段 10）

> 前置：审核方终审门已通过（或用户明确不要求外部评审）。正式交付物在导出前必须先运行 `finalize_draft.py` 净化（见下文"定稿净化"）。

**Agent**: 本地执行（当前 assistant）· 本 skill（evidence-writer）
**Input**: `14_专家修订稿.md` 或 `11_定稿.md`（审核方终审通过版）
**Output**: `{filename}.pdf` / `{filename}.docx` + `qa/*.png`

> **终稿变量（FINAL_DRAFT）**：目标稿可能是 `11_定稿`（未走 r5/w8）或 `14_专家修订稿`（已走外部专家评审，优先）。先判定：
> `FINAL_DRAFT = 14_专家修订稿（若该文件存在）否则 11_定稿`
> 下文所有 `{FINAL_DRAFT}` 均按此取值替换（净化版即 `{FINAL_DRAFT}_clean.md`，导出 PDF/DOCX 亦以它为准）。**严禁**对中间的 `11_定稿.md` 净化/导出而漏掉吸收专家意见的 `14_专家修订稿.md`。

## 执行步骤

1. **定稿净化**（正式交付物必做，不可逆）：
   `python ${SUITE_ROOT}/shared/scripts/finalize_draft.py {FINAL_DRAFT}.md -o {FINAL_DRAFT}_clean.md --sources 04_validated_sources.json`
   - 把 `[Sx]→[1]..[n]` 顺序编码、删脚手架标签与图例、删附录A证据缺口清单、清封面占位与 HTML 注释。
   - 净化后运行 `finalize_draft.py --check` 复核（无残留标记、编号连续、无重复 URL）。
   - **证据 provenance**：同步生成 `python ${SUITE_ROOT}/shared/scripts/finalize_draft.py {FINAL_DRAFT}.md -o {FINAL_DRAFT}_clean.md --manifest {FINAL_DRAFT}_manifest.json --sources 04_validated_sources.json`，产出 `[Sx]↔[n]→来源` 可回溯清单（claim 级字段见 `06_evidence_map.json`），与正文交付物并排保留。
   - 净化清单见 `${SUITE_ROOT}/shared/references/finalize_checklist.md`（含脚本无法覆盖的人工检查项，如 GB/T 7714 条目作者卷期页回填）。
   - 只对最终交付文件运行；工作稿保留脚手架。

2. **导出 PDF**（若要求）：
   `python ${SUITE_ROOT}/shared/scripts/export_pdf.py {FINAL_DRAFT}_clean.md -o {FINAL_DRAFT}_clean.pdf`
   - pandoc 优先；缺失自动降级 python-markdown。需 Chrome/Edge 或 weasyprint 之一。

3. **导出 DOCX**（若要求）：
   `python ${SUITE_ROOT}/shared/scripts/export_docx.py {FINAL_DRAFT}_clean.md -o {FINAL_DRAFT}_clean.docx`
   - 中文公文/学位排版：A4、标题黑体三号居中、正文宋体小四+Times 西文、1.5 倍行距、首行缩进 2 字符、表格跨页保护。需 `pip install python-docx`。

4. **视觉抽检**（交付前必做）：
   `python ${SUITE_ROOT}/shared/scripts/visual_qa.py {FINAL_DRAFT}_clean.md -o qa/ --sections "参考文献"`
   - 截图首页 + 参考文献区，人工或视觉模型过目：长 URL 断行、悬挂缩进、表格不溢出。

5. **排版缺陷修复**：若参考文献破损标点/长 URL 溢出 → `build_references.py --body` 重建参考文献节，重跑导出与抽检。

## 交付前自查（机械层面）

- 净化版正文 `[n]` 与参考文献条目完全闭合、编号连续（可用 `check_citations.py --academic` 复核，但最终判决以审核方终审门为准）。
- 无 `[Sx]`/`[Gx]`/`[假设]`/`[待内部确认]`/图例/附录A/封面占位残留。
- 图表无跨页断裂、图号唯一。

## 完成标准

- 交付文件已生成且视觉抽检通过。
- 在交付说明中记录：净化运行日期、导出路径、抽检结论。