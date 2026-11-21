# 优化提案（2026-11-21）：同类 skill / 项目对标

> 渐进式推导：现状自评 → 同类项目对照 → 逐项借鉴 → 分级提案。
> 本页是**方案文档**（未实施），落地时按 P0 → P1 → P2 逐批进 roadmap。
> 对照项目的资料性质全部为官方仓库/论文/官方文档，第三方评测已标注。

---

## 一、现状自评（先亮家底）

**强项（保持，不动）：**

| 能力 | 依据 |
|---|---|
| 对抗协议（提交→审查→判决→修订） | `SKILL.md` ×2 + final_gate；同模型自审如实标注 `review_kind` |
| 风险分层 R0–R4 与审查深度自适应 | `rules.yaml evidence_sufficiency` + `--review-mode` |
| 「直接度 > 数量」判定哲学 | `support_level` / `check_evidence_sufficiency.py` |
| 确定性脚本做门禁、LLM 只做判断 | 25 个 CLI + 85 回归用例 + eval 15 自动判分 |
| manifest 互操作契约 + provenance 五件套 | `schemas/*.schema.json`、`export_provenance.py` |
| 安全姿态 | source-safety / SSRF 守卫 / THREAT_MODEL |
| 中文期刊纵深（journal_top + GB/T 7714 + 双语） | `check_journal_style.py` S1–S17 |

**短板（本轮对标的靶子）：**

| # | 短板 | 证据 |
|---|---|---|
| G1 | **claim 分解无质量门**：w4 的 claim 划分靠 agent 自由发挥，没有"原子性"操作标准 | w4/w5 无原子性检查项；RAGChecker/FActScore 均把 claim 级拆解当作评测第一环 |
| G2 | 反证检索无系统策略（PR-13 待办） | r1 反证词表是静态的，无搜索式验证流程 |
| G3 | 评测指标未对齐学术口径 | eval 只有 pass/fail；无 citation recall/precision、factual precision 口径 |
| G4 | 上游 agent 对接未产品化：只接受"已有文档"，STORM/AI-Q/GPT-Researcher 的结构化输出要人工搬 | README 定位图无对接矩阵；PR-03/PR-08 待办 |
| G5 | skill 工程未对照渐进披露规范自审 | writer 357 行 / reviewer 276 行（未超 500 行红线，但"何时加载哪个 reference"的时机指引可更明确） |
| G6 | 分发短板：非 pip、Docker 非开箱即用 | PR-06/PR-07 待办（本轮不动，列 blocker 关系） |

---

## 二、同类项目对照表

| 项目 | 定位 | 与本套件关系 | 一句话借鉴 |
|---|---|---|---|
| **anthropics/skills 官方指南** | Agent Skill 工程规范 | 工程规范 | 渐进披露三级（metadata→body→linked refs）+ 500 行红线 + SKILL.md 当目录 |
| **FActScore**（EMNLP 2023，被引 2400+） | 长文本事实性评测 | 方法论上游 | 原子事实分解 → 逐条对照知识源验证 → 聚合 factual precision |
| **SAFE**（Google DeepMind） | 搜索增强事实性评测 | 方法论上游 | 用搜索引擎自动化"逐原子验证"，替代人工知识源——PR-13 反证的现成打法 |
| **VeriScore / DecMetrics** | 通用 claim 分解/分解质量 | 方法论上游 | 分解本身要打分（DecMetrics）——G1 的直接依据 |
| **OpenScholar**（AI2，开源） | 4500 万论文科学 QA agent | 上游 agent | self-feedback 循环**结构化**（批评检查单而非自由反思）降低幻觉引用 |
| **STORM**（Stanford，开源） | 多视角 Wikipedia 式文章生成 | 上游 agent | source-to-citation 映射全程保留（与本套件 source-map.json 同构，直接消费） |
| **GPT-Researcher**（开源） | 自主 research + 引用报告 | 上游 agent | 上游输出样本来源；用户基数大，对接价值高 |
| **RAGChecker**（NeurIPS 2024 D&B） | RAG 细粒度诊断 | 评测参照 | claim 级 entailment 指标体系 + 检索/生成两侧细分——PR-17 指标设计参照 |
| **Cleanlab TLM / Guardrails AI** | 信任分/护栏框架 | 工程形态参照 | validator 可独立组合、逐条输出 trust score——check_* 脚本的包装形态 |
| **Vectara HHEM** | 幻觉检测模型 | 工具参照 | 自动初筛用专用模型，LLM-as-judge 只做补充（landscape-2026-11 已证） |

> 定位澄清：以上 agent 类项目做"研究发动机"，本套件做"证据变速箱 + 刹车"——**全部是上游/互补，无竞品**。竞品类（Deep Research 闭源系统的引用功能）见 `landscape-2026-11.md` 第三节。

---

## 三、逐项借鉴 → 渐进提案

### P0 · 低成本高确定性（每项 ≤1 天，纯规则/文档/eval 口径，不动核心代码）

**P0-1 ✅ 已落地（2026-11-21）claim 原子性规范 + 审查检查项（补 G1）**
- `claim_evidence_layer.md` 增补「原子性操作定义」：一个 claim = 一个可独立验证的断言；
  复合断言（"A 且 B"、"A 因此 B"、"A 比 B 更 X"）必须拆分为可分别挂 `[Sx]` 的子 claim；
  分解产物在 `06_evidence_map.json` 以 `parent_claim` 字段保留层级。
- `r4_draft_review.md` 增检查项：「复合断言未拆分」与「拆分后子 claim 无来源」；
- 借鉴依据：FActScore（原子化是逐条验证的前提）、DecMetrics（分解质量本身需检查）、RAGChecker（claim 级 entailment）。
- 成本：约 30 行规则文本；风险：无（新增检查项走 r4 人工/审查路径）。

**P0-2 ✅ 已落地（2026-11-21，审计结论：符合）SKILL.md 渐进披露自审（补 G5）**
- 对照官方三级披露做一次审计：frontmatter `description` 是否含全部触发场景与不适用场景；
  body 是否只保留"流程骨架 + 分支判断"，细则全部下沉 references；
  每个 reference 的**加载时机**在 body 中显式写出（"当出现 X 时读 `references/y.md`"）。
- 依据：anthropics/skills 500 行规则 + 渐进披露原则。现状 357/276 行未越线，属"体检"而非重写。

**P0-3 ✅ 已落地（2026-11-21）eval 指标口径对齐（补 G3 的地基）**
- `eval/README.md` 与 `benchmarks/README.md` 增加**指标定义节**：citation recall / citation precision（ALCE 定义）、
  factual precision（FActScore 定义）、claim-level entailment（RAGChecker 定义）——先对齐口径，PR-17 发布时直接复用。
- 成本：文档节 + golden 用例的 expected 字段补齐指标数值。

### P1 · 中等工作量（并入 roadmap 对应 PR）

**P1-1 → PR-13 反证阶段：采用 SAFE 式搜索验证**
- 反证检索升级为模板化流程：`"<claim> criticism / limitation / contradictory / failed"` + 领域词（复用 domain_routing）；
  每条 R2+ claim 记录「反证查询 × 结果 × 判定」三元组，落入 manifest 新增可选字段（schema 0.3.0）；
  「未找到反证」按现有 Stop Rule 处理，如实标注。
- 依据：SAFE 用搜索自动化逐原子验证，已被验证为可行范式。

**P1-2 → PR-03 真实 e2e：上游报告直接进 Review Only**
- 输入样本：STORM / GPT-Researcher / AI-Q(deep-researcher-agent) 的开源报告输出各 1 份；
  走 L3 全链路产出 PDF/DOCX + provenance 五件套，作为 `examples/e2e/`。
- 价值：同时验证 G4（对接成本）与 G6（导出链路），并给 PR-17 提供真实基线。

**P1-3 → PR-08 Agent 集成指南：上游对接矩阵**
- 新增「上游 agent 输出形态 → 本套件消费入口」表：STORM（source→citation 映射 JSON）/
  GPT-Researcher（报告 + 引用列表）/ AI-Q blueprint（evidence 引用）→ 各自的转换要点；
  加 MCP server 一等路径（见 landscape-2026-11 第四节）。
- OpenScholar 的结构化 self-feedback 检查单可反哺 r2 诚实性自评模板（结构化 > 自由反思）。

**P1-4 → PR-06 前置：check_* 包装为可组合 validator**
- 借鉴 Guardrails AI 形态：每个校验脚本声明「输入 schema / 判定语义 / 退出码」，形成 validator 清单文件；
  pip 包（PR-06）把 validator 层与 skill 层分离发布。

### P2 · 生态与基准（维持 roadmap 原规划，吸收本轮口径）

- **PR-17 公开 benchmark**：指标采用 P0-3 的三口径（citation R/P + factual precision + entailment）；
  参照 RAGChecker 的检索/生成两侧细分发布诊断指标；基线数据来自 P1-2 的 e2e。
- **PR-18 多语言**：原子性规范双语版（英文 claim 拆分规则与中文不同：英文长句嵌套更深）。
- **可选工具位**：HHEM 类专用检测模型作为反证初筛的可插拔后端（`--detector hhem`），不内置、只留接口。

---

## 四、落地顺序建议

```
本轮已完成：landscape-2026-11（外部环境）+ 本页（对标与提案）
   ↓
P0-1 / P0-2 / P0-3（各 ≤1 天，互不阻塞，可并行）
   ↓
PR-13（用 SAFE 打法）⇄ PR-03（用开源上游样本）⇄ PR-08（对接矩阵 + MCP）
   ↓
PR-06（validator 分层后 pip 化）→ PR-07（Docker Compose）→ PR-17（三口径 benchmark）
```

## 五、来源索引

- Agent Skill 官方指南（渐进披露 / 500 行）：anthropic 官方 docs（agent skills best practices）
- FActScore：https://arxiv.org/abs/2305.14251 （代码 github.com/shmsw25/FActScore）
- SAFE / LongFact：Google DeepMind 技术报告（搜索式逐原子验证）
- VeriScore / DecMetrics：通用 claim 分解与分解质量评测（arXiv）
- OpenScholar：https://github.com/allenai/openscholar （论文 "Synthesizing Scientific Literature with Retrieval-augmented LMs"）
- STORM：https://github.com/stanford-oval/storm
- GPT-Researcher：github.com/assafelovic/gpt-researcher
- RAGChecker：https://arxiv.org/abs/2408.08067 （NeurIPS 2024 Datasets & Benchmarks）
- Guardrails AI：github.com/guardrails-ai/guardrails ；Cleanlab TLM：cleanlab.ai
