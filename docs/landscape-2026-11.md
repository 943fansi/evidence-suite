# 领域动态（2026-11-21 搜集）：证据校验与溯源的外部环境

> 本页是**文献调研，不是实测**——梳理与 evidence-suite 直接相关的标准、监管、评测研究与对标系统动态，
> 全部标注来源性质（官方一手 / 第三方）。结论性判断映射到 `docs/roadmap.md` 的待办项。
> 引用本页的论断时，按套件自身规则回溯源头；本页不替代任何一手规范文本。

---

## 一、监管与标准层：AI 生成内容的可追溯性正在被"强制化"

这是对本套件最重要的外部变化：**"AI 产出必须可追溯、可披露"已从最佳实践变成法定义务。**

| 事项 | 状态 | 对本套件的含义 |
|---|---|---|
| **EU AI Act 第 50 条** | **2026-08-02 生效**（Art.113 时间表）：生成式 AI 提供者必须以**机器可读格式**标记 AI 生成内容；深伪与面向公众的 AI 文本须披露。2026-08 欧委会发布透明度义务指南，**2026-10 发布《AI 生成内容透明度实践守则》** | 本套件的 `evidence_manifest.json` + PDF/DOCX 页脚 `review_kind` 标注与"机器可读标记"方向一致；`review_kind`（ai-internal/cross-model/human-expert）正是 Art.50(4) 类披露的结构化雏形 |
| **中国《人工智能生成合成内容标识办法》** | 2025-03-07 发布、**2025-09-01 施行**（网信办等四部门）；配套**强制国标 GB 45438-2025《网络安全技术 人工智能生成合成内容标识方法》同日施行**。显式标识（可见）+ 隐式标识（文件元数据）双轨，恶意删改标识被明令禁止 | 隐式标识 = 元数据层溯源，与本套件 `export_provenance.py` 的"机器审计档案"思路同源；journal_top 场景产出若含 AI 生成物，投稿与交付都要考虑标识合规 |
| **C2PA / Content Credentials** | 2026-07 发布**新实施指南**（聚焦 AI 生成/修改内容标注）；规范支持 **durable credentials**（凭证跨转换持久化） | PR-14（网页快照归档）可借鉴 durable 思路：manifest 中的来源快照凭证应在文档转换后仍可验 |
| **学术出版界** | COPE 立场（AI 不可署名）持续有效；**ICMJE 2025-04 更新**：投稿须显式披露 AI 用途——写作辅助入致谢、数据分析入 Methods，须写明工具名与用途；Springer Nature 有跨生命周期 AI 政策框架 | 与本套件 `review_kind` / `review_independence` 披露字段同构；journal_top 模板可考虑增加"AI 工具使用披露"节（合规成本约 3 行，收益是投稿合规） |

来源性质：EU 条款与实践守则为官方一手（digital-strategy.ec.europa.eu）；中国标识办法为 CAC 官方一手；C2PA 为联盟官方；COPE/ICMJE 为机构官方立场文件。

---

## 二、评测与研究层：引用归因已有成熟的公共评测框架

**对本套件方法论的两个直接支撑：**

1. **确定性/专用检测优于 LLM-as-judge**：2026-04 对比研究显示，以 LLM 作裁判的 RAGAS faithfulness 仅约 62% 准确率（逐句验证路线的局限）；而 Vectara HHEM 专用模型家族（开源 HHEM-2.1 → 商业 HHEM-2.3 显著更强）在幻觉检测上更稳。这印证本套件"**确定性脚本做门禁、LLM 只做需要判断的部分**"的分工不是保守，而是当前最优实践。
2. **引用评测三步法已是行业共识**：FutureAGI 2026-05 总结的三段评价——①模型是否发出引用 → ②引用能否解析 → ③来源是否真的支撑该论断——与本套件「引用闭合 → locator 落位 → support_level 判定」三层一一对应；第三步（真支撑）恰是 ALCE/AIS 框架公认最难、也是本套件对抗审查的差异化所在。

| 框架/基准 | 定位 | 与本套件的关系 |
|---|---|---|
| **ALCE**（citation recall / precision） | 生成带引用文本的自动评测 | PR-17（公开 benchmark）的指标定义可直接采用 recall/precision 口径 |
| **AIS**（Attributable to Identified Sources） | 把"归因"定义为**人可核验**——与"引用了 ≠ 支撑了"同一立场 | 本套件 `support_level` 判定哲学的学术版；manifest 设计目标即"human verifiable" |
| **CiteRAG**（2026-01） | 首个学术引用预测 RAG 基准 | 学术场景 golden 用例可参考其引用预测任务设计 |
| **FineRef / OpenReview 2026-10 人工评测** | 6 种 context attribution 方法 × 7 LLM × 4 数据集 | 佐证"自动归因方法差异大"，人工回填打分环节（本套件 eval 已有）不可省 |
| **HHEM / FaithBench / RAGAS** | 幻觉/忠实度检测 | 若 PR-13（反证阶段）引入自动初筛，专用检测模型优于 judge 式调用 |

来源性质：ALCE/AIS/CiteRAG 为同行评审论文或 arXiv（预印本须标注）；RAGAS/HHEM 对比为第三方研究；HHEM 系 Vectara 官方（厂商口径需交叉验证）。

---

## 三、对标系统层：README 引用的对象已全部开源

- **NVIDIA AI-Q**（README「定位」一节的对标对象）：2026-05-20 **开源为 deep-researcher-agent blueprint**（GitHub `NVIDIA-AI-Blueprints/deep-researcher-agent`），2026-03 拿下 DeepResearch Bench 第一，2026-07 官方文档给出规模化指南。其核心机制正是本套件消费的形态：**工具输出被当作 evidence 引用、报告带全文级引用归因**。
  → **影响**：README 的定位图不再是对闭源系统的抽象，而是可直接对接的开源 blueprint——PR-03（真实端到端示例）可用 AI-Q 的报告输出作为输入样本之一。
- **Anthropic Citations API**（2025-01 起）：响应中返回**字符级 provenance**（精确引文 + 文档区间）。API 层原生归因的存在说明：本套件 `locator.quote_hash` 的粒度（页/节/段/引文哈希）与行业最强实践粒度相当，且保持了工具无关性（Citations API 绑定单一厂商）。
- **OpenAI deep research**：报告带 inline citations；2026-05 已有论文专门对比两类系统的归因输出——"解析 deep research 引用"本身成了研究方向。
- **MCP 2026-07-28 规范**：MCP 发布以来最大修订（无状态重写、四语言 SDK 更新），生态注意力转向安全/验证/provenance。
  → **影响**：`evidence_manifest.json` 是天然的 MCP 工具响应附载物（resource/attachment）；PR-08（Agent 集成指南）应把"MCP server 暴露 manifest"列为一等集成路径。

---

## 四、对路线图的具体映射

| roadmap 待办 | 本页发现带来的修正 |
|---|---|
| PR-03 真实端到端 | 输入样本增加 AI-Q 开源 blueprint 的报告输出（开源、可复现） |
| PR-08 Agent 集成指南 | 增加 MCP server 暴露 manifest 的一等路径（MCP 2026-07-28 已稳定） |
| PR-13 反证阶段 | 自动初筛优先专用检测模型（HHEM 类），LLM-as-judge 仅作补充 |
| PR-14 快照归档 | 快照凭证设计参考 C2PA durable credentials（转换后仍可验） |
| PR-17 公开 benchmark | 指标采用 ALCE citation recall/precision + AIS "人可核验"口径 |
| PR-18 多语言/海外标准 | 监管映射表（EU Art.50 / 中国标识办法）写入适配指南；期刊模板评估增加 AI 披露节 |
| journal_top 场景 | 投稿合规：ICMJE 式"工具名+用途"披露，本套件可从 manifest 自动生成该段落草稿 |

## 五、来源注册表同步

本批次同步扩充 `shared/references/source_registry.json`（+7 条，均落在 ai/期刊写作常用域）：
`cac`（中国网信办，A1）、《标识办法》与 GB 45438-2025 的核查入口；
`eu_ai_act`（EUR-Lex 官方法规文本，B1）；`c2pa`（B1，联盟规范非正式国际标准，已显式降级）；
`w3c_prov`（W3C PROV，A2 正式推荐标准）；`mcp_spec`（B1，联盟规范）；
`cope` / `icmje`（出版伦理与投稿披露政策，B1）。`select_sources.py --domain ai` 的 ROUTING 相应补 `china_regulator`。

## 六、来源索引

- EU AI Act Art.50 透明度义务与实践守则：https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content ；导则 https://artificialintelligenceact.eu/transparency-rules-article-50 （第三方追踪站，法规原文以 EUR-Lex 为准）
- 中国《人工智能生成合成内容标识办法》：https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm （CAC 官方）；GB 45438-2025 经国家标准全文公开系统核查
- C2PA 实施指南（2026-07）：https://c2pa.org/a-new-implementation-guide-for-content-credentials
- COPE Authorship and AI Tools：https://publicationethics.org/guidance/cope-position/authorship-and-ai-tools ；ICMJE AI 披露：https://www.icmje.org/recommendations/browse/artificial-intelligence/ai-use-by-authors.html
- ALCE / AIS 对比讨论与 CiteRAG（2026-01）：https://arxiv.org/html/2601.14949v2 ；RAG 引用方法人工评测（2026-10）：https://openreview.net/forum?id=2QItZn0ENm
- FutureAGI 三步评价法（2026-05）：https://futureagi.com/blog/evaluating-llm-citation-attribution-2026 （第三方）
- HHEM 家族与榜单：https://github.com/vectara/hallucination-leaderboard ；arXiv 2505.04847（厂商论文，注意立场）
- NVIDIA AI-Q blueprint：https://github.com/NVIDIA-AI-Blueprints/deep-researcher-agent ；官方文档 docs.nvidia.com（AI-Q Research Agent Blueprint）
- Anthropic Citations API：https://www.anthropic.com/news/introducing-citations-api ；平台文档 platform.claude.com
- MCP 2026-07-28 规范 RC：https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate ；Cloudflare 解读 https://blog.cloudflare.com/mcp-v2 （第三方）
