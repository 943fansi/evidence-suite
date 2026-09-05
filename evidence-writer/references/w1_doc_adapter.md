# w1: Document Type Adapter（文档适配，写作者侧 · 全局阶段 0）

**Agent**: 本地执行（当前 assistant）
**Input**: `{target_document}`, `{topic}`, `{audience}`
**Output**: `00_topic.md`（Topic Card）+ Selected template → passed to w5

## Execution Steps

1. Read `${SUITE_ROOT}/shared/templates/index.md`
2. Match `{target_document}` keywords to template file
3. Read the selected template file
4. If `{target_document}` contains thesis variant keywords (本科/硕士/博士/ug/master/phd), also note `{research_type}` (理论/实证/混合) for section weighting
5. **写入 `00_topic.md`（Topic Card，硬门禁产物，勿跳过）**，至少包含：
   - **核心问题（1–2 个）**：本文档要解决什么
   - **文档类型与硬约束**：开题 / 本 / 硕 / 博 / 调研 / 可行性 / 白皮书 / GF报告 / 实施方案 / 期刊论文 / 专利交底书 / 专利申请草案；字数、格式、评审标准
   - **已知来源基调**：领域、奠基文献、方法谱系、主要争议点
   - **topic_domain**：从 `nuclear / materials / energy / education / ai / funding / engineering / general` 中选定一个（供 w2 `select_sources.py --domain` 使用；跨域时选主域）
   - **论证骨架（Mermaid）**：3 个关键问题 + 3 项关键技术 + 3 个结构层次
   - **证据缺口预期**：哪些论点大概率缺来源 → 预先埋 `[Gx]`
   - **语义最小集**：最少需要哪几个来源，核心论点才站得住
6. Output: the selected template's section structure with `{topic}` implanted as document title
7. Pass to w5: instruct "Use this template's section structure for the draft"

## Decision Logic

```
# 决策优先级（从上到下，首个命中即生效；关键词做子串匹配，逐词判断）
if contains_any(target_document, ["国防科技报告", "GF报告", "GF 报告", "GF Report", "科技报告"]):
    template = "report_gf.md"  # 中国国防科学技术报告（格式见 ${SUITE_ROOT}/shared/references/gf_report_format.md）

elif contains_any(target_document, ["实施方案", "implementation plan"]):
    template = "plan_implementation.md"  # 项目实施方案（11章工程执行格式，见 ${SUITE_ROOT}/shared/references/impl_plan_format.md；区别于开题 proposal）

elif contains_any(target_document, ["期刊论文", "期刊", "投稿", "修回稿", "journal"]):
    template = "paper_journal.md"  # 期刊论文（0 引言编号+GB/T 7714 引用，见 ${SUITE_ROOT}/shared/references/journal_paper_format.md）

elif contains_any(target_document, ["专利", "交底书", "发明创造", "实用新型", "patent"]):
    if contains_any(target_document, ["申请草案", "权利要求书", "说明书摘要", "claims"]):
        template = "patent_application.md"  # 发明专利申请草案四件套（写法见 ${SUITE_ROOT}/shared/references/patent_writing_guide.md §五）
    else:
        template = "patent_disclosure.md"  # 专利申请技术交底书（写法见 ${SUITE_ROOT}/shared/references/patent_writing_guide.md）

elif contains_any(target_document, ["白皮书", "技术报告", "技术白皮书", "whitepaper"]):
    template = "whitepaper.md"

elif contains_any(target_document, ["调研", "综述", "现状", "survey", "review"]):
    template = "report_survey.md"

elif contains_any(target_document, ["可行", "可研", "论证", "可行性", "feasibility"]):
    template = "report_feasibility.md"

elif contains_any(target_document, ["方案", "立项", "申报", "项目", "proposal"]):
    template = "proposal.md"

elif contains_any(target_document, ["论文", "学位", "thesis", "ug", "master", "phd", "本科", "硕士", "博士", "学士"]):
    if contains_any(target_document, ["博士", "phd"]):
        template = "thesis_phd.md"
    elif contains_any(target_document, ["硕士", "master"]):
        template = "thesis_ms.md"
    elif contains_any(target_document, ["本科", "学士", "ug", "undergraduate"]):
        template = "thesis_ug.md"
    else:
        template = "thesis_ug.md"  # 论文类但未指明层级 → 默认本科，见 ${SUITE_ROOT}/shared/templates/index.md 注释

else:
    template = "proposal.md"  # default to proposal

# 研究类型标注（仅论文类需要）
if template.startswith("thesis_"):
    if contains_any(target_document, ["理论"]):
        research_type = "理论"   # weight理论框架章 heavier, downweight策略/应用章
    elif contains_any(target_document, ["实证", "实验", "调查"]):
        research_type = "实证"   # weight方法章 heavier, add结果与讨论章
    else:
        research_type = "混合"

# 辅助函数约定（LLM 执行时按语义展开，勿字面拼接）
# contains_any(s, keys) := 任一 key 是 s 的子串（或 s 包含该 key 的等价中文表达）
```

> **路由注意事项**：
> - 条件判断必须逐词用 `in` 语义判断，**禁止**写成 `if "本科" or "学士" or "ug":` 这种恒真形式。
> - "论文"一词本身（未指明本/硕/博）按 `${SUITE_ROOT}/shared/templates/index.md` 的默认路由处理——见「裸"论文"路由」约定。
> - 若多个类型关键词冲突（如"调研报告"同时含"调研"和"报告"），按决策优先级从上到下首个命中生效。

## Token Note
This adapter loads index.md (~17 lines) + selected template (~15-19 lines).
Total overhead: ~32-36 lines. Do NOT load all templates.
