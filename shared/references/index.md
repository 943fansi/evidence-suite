# Reference Files Index

> 原单流水线 `SKILL.md` 已停用并拆分为 **evidence-writer**（写作方）与 **evidence-reviewer**（审查方）。两侧的结构化设计（签名原则 / 决策优先级 / 对抗协议 / 判决词表 / 硬性禁止）分别见各自 `SKILL.md`；本索引用于在对应阶段**按需加载**参考指南，控制 token 开销。

## 核心设计（在两侧 SKILL.md）
- 签名原则：来源为锚 · 论断为证 · 图谱为骨 · 留白为诚
- 写作者（evidence-writer）：决策优先级、Topic Card、阶段编译器（0/1/3/4/5/7/9/10）、证据严谨引擎、修订协议、定稿净化
- 审查者（evidence-reviewer）：对抗协议、判决词表、阻断规则、阶段编译器（2/4b/5b/6/8/终审门）、脚本门禁、终审门

## File overview

| File | Lines | 加载阶段（w 写作 / r 审查） | 用途 |
|------|-------|-----------------|------|
| `gap_adjacent_strategy.md` | ~47 | w5 | 核心论断即研究空白时的邻接证据拼接 |
| `domain_routing.md` | ~36 | w1 / w2（r1 复核） | 题目域 → category → 权威源路由表 |
| `source_registry.json` | ~642 | w2（脚本） | 权威来源清单快照；scripts 读取，勿直接进上下文 |
| `significance_writing_guide.md` | ~43 | w5 | 研究意义写作、防空洞 |
| `patent_writing_guide.md` | ~98 | w5（专利类）/ r4 第 16 条 | 专利申请技术交底书七节结构与写法（含 [Sx] 仅限背景技术规则） |
| `gf_report_format.md` | ~34 | w5（GF类）/ r4 第 17 条 | 中国国防科学技术报告页序/排版/引用格式 |
| `impl_plan_format.md` | ~39 | w5（实施方案类）/ r4 第 18 条 | 项目实施方案 11 章结构与编号规范 |
| `journal_paper_format.md` | ~39 | w5（期刊类）/ r4 第 19 条 | 期刊论文结构与 [Sx]→GB/T 7714 对接 |
| `thesis_format.md` | ~35 | w5（学位类）/ r4 第 15 条 | 学位论文双封面/分点摘要/章号图表编号规范 |
| `claim_evidence_layer.md` | ~114 | w4 / w5 / r4 | 论断—证据分层规范（定向修正·图谱错位） |
| `anti_marketing_rules.md` | ~113 | r4 | 反套路/反营销话术（硬性禁止·公式化） |
| `technical_route.md` | ~125 | w5 | Mermaid 技术路线图写法 |
| `finalize_checklist.md` | ~80 | w9 / 终审门 | 定稿净化清单（[Sx]→[1]..[n]、删图例/附录A/封面占位，含人工核查项） |
| `workflow.md` | ~306 | 总体参考 | 整体流程与阶段衔接（历史存档，见头部对照表） |
| `expert_roles/index.md` | ~33 | r5 | 领域专家角色选择 |

## Loading rule

- `index.md` (this file): 始终加载，~33 行
- 单个文件：仅在其对应阶段（w/r）执行时按需加载
- 上下文中并发参考文件上限：3（不含本索引）

## Token Budget

- 本文件 ~33 行，技能激活时始终加载
- 按需文件各 ~40-120 行，仅在其对应阶段执行时加载
- 参考总开销：任意时刻不超过 4 个文件
