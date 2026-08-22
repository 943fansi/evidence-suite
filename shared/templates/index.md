# Template Selector

Choose the closest match to `{target_document}` and keep the section order stable.

## Mapping

| Keyword hints | Template |
|---|---|
| 国防科技报告 / GF报告 / 科技报告 / GF Report | `report_gf.md` |
| 实施方案 / 项目实施方案 / implementation plan | `plan_implementation.md` |
| 期刊论文 / 期刊 / 投稿 / 修回稿 / journal | `paper_journal.md` |
| 专利 / 交底书 / 发明创造 / 实用新型 / patent | `patent_disclosure.md` |
| 申请草案 / 权利要求书 / 说明书摘要 / claims | `patent_application.md` |
| 立项 / 申报 / 项目 / 方案 / proposal | `proposal.md` |
| 本科 / 学士 / ug / undergraduate | `thesis_ug.md` |
| 硕士 / master | `thesis_ms.md` |
| 博士 / phd | `thesis_phd.md` |
| 调研 / 综述 / 现状 / survey / review | `report_survey.md` |
| 可行 / 可行性 / 可研 / 论证 / feasibility | `report_feasibility.md` |
| 白皮书 / 技术白皮书 / 技术报告 / whitepaper | `whitepaper.md` |

> **裸"论文"路由约定**：`{target_document}` 含"论文/学位论文/学位/thesis"但**未指明层级**（无 本科/学士/硕士/博士/ug/master/phd）时，视为**学位论文**，默认落到 `thesis_ug.md`（本科）；若上下文明确是"开题/立项申报等方案类文档"，落到 `proposal.md`。两个默认值不冲突——`proposal.md` 只在既非论文类也非其余类型时兜底。关键词集合与 `${SUITE_ROOT}/evidence-writer/prompts/w1_doc_adapter.md` 保持一致。
