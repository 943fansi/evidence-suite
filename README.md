# evidence-suite · 研究 Agent 的证据校验与溯源层（Evidence Integrity Layer）

[![CI](https://github.com/943fansi/evidence-suite/actions/workflows/ci.yml/badge.svg)](https://github.com/943fansi/evidence-suite/actions/workflows/ci.yml)

让研究 Agent（含 Deep Research / NVIDIA AI-Q 类系统）产出的技术 / 学术文档**每一条论断都能追溯到来源、并验证是否真能支撑该结论**：写作方（evidence-writer）负责生产，审查方（evidence-reviewer）有罪推定、只找失败、严重即阻断，两者形成「提交 → 审查 → 判决 → 修订」的对抗循环。

## 为什么需要它

普通 LLM 直接写技术 / 学术文档有 5 个典型问题：

1. **编造来源**：文献、数据、标准编号靠训练记忆臆造。
2. **弱证据撑强结论**：「国际领先」「填补空白」没有来源。
3. **自我放行**：写完即宣称完成，没有独立审查。
4. **证据与结论脱节**：有引用，但引用并不支撑结论。
5. **证据不可追溯**：说不清某句话来自哪篇、哪页。

本套件把「证据类论断（E/M/N/L）必须挂 `[Sx]` 来源标记」作为硬约束，并用独立红队审查强制闭合。

## 它做什么

```
证据检索 → 语料验证 → 证据图谱 → 起草 → 红队审查 → 判决 → 修订 →（终审门）→ 导出
```

- **写作者（evidence-writer）**：w1 文档适配 → w2 来源检索 → w3 验证语料（下载 / 校验 / 抽原文）→ w4 证据图谱 → w5 起草 → w6 修订 → w8 专家修订 → w9 导出。
- **审查者（evidence-reviewer）**：r1 来源审计 → r2 诚实性自评 → r3 框架深度门 → r4 初稿审查 → r5 外部专家评审 → 终审门。

## 定位：不是又一个研究引擎

本套件**不负责研究检索规划**——那是 Deep Research / NVIDIA AI-Q 类系统（Intent / Planner / 并行 Researcher / RAG）的事。本套件负责**研究结果的证据可信度**：

```
研究 Agent（AI-Q / Deep Research）
        ↓ 研究产物（报告 / 草稿）
evidence-suite —— Claim 提取 → 分类 → 证据映射 → static/live 验证 → 反证 → 溯源
        ↓
交付物 + Evidence Manifest
```

- **AI-Q / Deep Research = 研究发动机**：尽可能高效地找、组织、综合信息。
- **evidence-suite = 证据变速箱 + 刹车**：判断哪些信息真能支撑哪些 Claim，结果能否追溯回证据。

入口是「给一份已有研究产物做 claim 级验证」，**不重复造 Planner / Researcher / Runtime**。

## 运行模式

按用户意图选择，**不所有任务都走完整流水线**：

| 模式 | 做什么 | 是否进对抗循环 |
|------|--------|--------------|
| Quick Evidence（L0 Answer） | 单个事实 / 标准条款 → 检索 + 核验 → 直接结论 | 否 |
| Evidence Brief（L1） | 5–20 claims → claim→evidence→平衡 表格 + 充分性（`build_evidence_brief.py`） | 否 |
| Evidence Research（L2） | 技术调研 / 综述 → 证据图谱 → research memo | 否 |
| Document Production（L3） | 完整交付物（默认）→ 全链路 + 红队审查 | 是 |
| Safety/Regulatory（L4） | 核安全/法规产出 → `--review-mode conservative` + 跨模型/人类评审 | 是 |
| Review Only | 已有文档 → 只审不写 → 判决 | 是（仅审查方） |

## 证据模型

- 标记：`[Sx]` 已审计来源、`[Gx]` 研究空白、`[假设]` / `[待内部确认]` 显式留白。
- `support_level`（direct / strong_inference / weak_inference / context_only / contradictory / unsupported）：**证据能多大程度直接证明该结论**。
- `relation`（supports / contradicts / context_only）：证据对 claim 的方向性关系；`locator`（page/section/paragraph/quote_hash）把引用落到原文位置；claim 级 `confidence`（high/medium/low）与 `interpretation`——构成 **Claim→Evidence→Source→Locator→Relation→Confidence** 双向可审计图。
- `evidence_status`（verified / supported / partially_supported / inferred / contradicted / unsupported / unverified / internal_confirm）：**该结论最终处于什么状态**。
- `claim_class`（E/M/N/L 需 `[Sx]`；D 定义 / C 计算 / U 用户提供 / J 判断 不走来源真实性审查）——见 `claim_evidence_layer.md`。
- `risk`（R0–R4）：R1 单源 / R2 独立交叉 / R3 primary+现行性+live / R4 独立复现/人工签核——把"一律有罪推定"缩小到真正高险的论断。
- `authority`（来源权威 A1–D2）：法规 A1 / 标准 A2 / 国标行标 A3 / 官方报告 B1 / 原始实验 B2 / 期刊 C1 / 学位 C2 / 厂商 D1 / 二手 D2；R3/R4 要求来源 ≥ A2。
- `freshness`（证据新鲜度 current / recent / historical / superseded / unknown）：政策/标准类 R3/R4 须 `current`，`superseded` 不得作现行依据。
- **判定按「直接度」而非「来源数量」**：两条 `weak_inference` ≠ 一条 `direct`；**claim 级证据充分性**由 `check_evidence_sufficiency.py` 按 risk tier 判定（primary/独立来源/现行性/反证覆盖），文档级 `min_sources` 只是写作格式下限。
- **审查模式（Risk-adaptive）**：`rules.yaml` 的 `review_mode` 控制证据充分性阈值乘数与默认立场——`conservative`（1.5×，核安全/法规）/ `balanced`（1.0×，默认）/ `exploratory`（0.7×）；`check_evidence_sufficiency.py --review-mode` 生效。
- **增量校验**：大文档迭代时 `check_evidence_sufficiency.py --changed C-001,C-003` 只重审变更 claim，跳过未变部分，不必重跑全量；`--score` 可同时输出每条 claim 的 Evidence Score 与等级。
- **方法论**：设计原理（直接度>数量、对抗协议、留白为诚、反证调和、停止规则、评分不替代门禁）见 `docs/methodology.md`。
- **来源优先级清单**：`source_ranking.yaml` 给 Registry 来源标注 `authority/priority/role`，`select_sources.py --allow-discovery` 开放候选池（`source_origin` 四类来源可进入），Registry 是优先级清单而非白名单。
- 交付时 `finalize_draft.py --manifest` 产出 `evidence_manifest.json`（`[n]→来源` 可回溯），保留证据 provenance。

详见 `shared/references/claim_evidence_layer.md`。

## 互操作契约（Evidence Manifest）

`finalize_draft.py --manifest` 产出 `evidence_manifest.json`，是 evidence-suite 与研究 Agent 之间的接口——研究产物进，验证后的 provenance 出。manifest 携带 `schema_version`（`shared/schemas/*.schema.json`，经 `validate_manifest.py` 强制校验）与 `review_kind`。

- **source-centric**（当前 `--manifest` 输出）：`[Sx] → [n] → source_id / title / url + claims[]`。
- **claim-centric**（接口契约，可由 `06_evidence_map.json` 聚合导出）：

```json
{
  "schema_version": "0.2.0",
  "review_kind": "ai-internal",
  "claim_id": "C-017",
  "claim_class": "N",
  "risk": "R3",
  "claim_text": "……",
  "confidence": "high",
  "interpretation": "……",
  "evidence": [
    { "source_id": "S-04", "authority": "A2", "freshness": "current",
      "support_level": "direct", "relation": "supports",
      "locator": {"page": 37, "section": "5.2.3", "quote_hash": "sha256…"} }
  ],
  "verification_mode": "live",
  "verdict": "supported"
}
```

`review_kind` 取值：`ai-internal`（同模型角色隔离，内部红队）/ `ai-cross-model`（不同模型独立审查）/ `human-expert`（人类专家）。**默认 `ai-internal`，不等同独立评审。** 附加 `review_independence` 字段记录审查独立性细节（`reviewer_model` / `writer_model` / `context_shared` / `evidence_shared` / `human_involvement`）——**跨模型 ≠ 独立**：若审查与写作共享相同上下文/证据，错误仍高度相关。`ai-internal` 默认如实标记 `{human_involvement: none, context_shared: true, evidence_shared: true}`。

研究 Agent 只需产出 `claim → evidence → verdict` 结构即可被 Reviewer / 终审门消费；反之本套件产出的 verified manifest 也可回喂给研究 Agent 的 writer。

**Provenance 五件套（`export_provenance.py`）**：终审门通过后，把交付物与其审计档案一起落地到 `research_case/provenance/`——`report.claims.json` / `report.evidence.json` / `report.source-map.json`（正文 `[n]` 引文 → source_id + locator 对账表）/ `report.review.json`（各阶段判决 + `review_kind`）。**PDF/DOCX 给人看，evidence JSON 给机器审计**，正文引文与证据图谱不再因净化而失去对应关系。

## 目录结构

```
evidence-suite/
├── evidence-writer/     # 写作方 SKILL.md + prompts/w1–w9
├── evidence-reviewer/   # 审查方 SKILL.md + prompts/r1–r5 + final_gate
├── shared/
│   ├── scripts/         # 16 个确定性工具（Bash 执行）
│   ├── schemas/         # manifest 互操作契约 JSON Schema（evidence_manifest / claim_manifest）
│   ├── config/          # 规则配置（rules.yaml：risk_tiers / evidence_sufficiency / doc_minimums / …）
│   ├── references/      # 按需加载的参考指南
│   └── templates/       # 13 类文档模板
├── examples/            # 最小示例（quickstart：净化→manifest→充分性→Brief→Provenance→校验 一键复现）
├── eval/                # Eval/Golden 套件（run_eval.py 自动判分 + golden 用例）
├── runtime/             # 运行时能力配置（capability.yaml 模板 + probe_capabilities.py 探测结果）
├── docker/              # Docker 沙箱（隔离脚本执行，可断网）
├── docs/                # 架构与方法论文档（architecture.md / methodology.md）
├── tests/               # 回归测试（run_tests.py，66 用例）
├── README.md
├── SECURITY.md
├── THREAT_MODEL.md      # 威胁模型与信任边界
└── LICENSE
```

## 导出能力（PDF / DOCX）

两个导出器共享同一套 Mermaid 渲染管线（`shared/scripts/mermaid_render.py`，本地 mermaid-cli 优先、mermaid.ink 回退、失败显式占位），正文排版能力对等：

| 能力 | PDF（`export_pdf.py`） | DOCX（`export_docx.py`） |
|------|----------------------|--------------------------|
| 段落首行缩进 2 字符 | ✅ 有（`--no-indent` 关闭） | ✅ 有（`--no-indent` 关闭） |
| Mermaid 路线图显示 | ✅ 有（SVG） | ✅ 有（PNG 嵌入） |
| A4 中文排版（宋体/黑体/楷体、1.5 倍行距） | ✅ | ✅ |
| Markdown 表格 | ✅ | ✅（Word 原生表格，跨页防断） |
| 参考文献悬挂缩进 | ✅ | ✅（普通段落） |

- PDF：pandoc/python-markdown → HTML → weasyprint / Chrome headless；Mermaid 渲染为 SVG 后内嵌。
- DOCX：python-docx 直接排版；Mermaid 渲染为 PNG 后以图片嵌入正文，渲染失败时落可见占位说明。
- 两者均支持 `--mermaid-engine local`（禁止联网渲染，敏感内容断网使用）。

## 规则配置（Rules）

证据严谨度、文档下限、可疑域名、停止规则等参数集中在 `shared/config/rules.yaml`（单一事实来源），支持按业务场景覆盖：

- **场景档**：`--profile medical`（提高权威要求：R2≥A2、R3≥A1，收紧来源下限）/ `--profile general_tech`（放宽 R3 至 B1、下调下限）等，deep-merge 生效。
- **覆盖层**（优先级递增）：默认档 → `config/rules.user.yaml`（仓库级，自动加载）→ `--rules <path>` → `--profile <scenario>`。
- **消费方**：`validate_sources.py --profile`（可疑域名 + 场景追加）、`check_citations.py --doc-type/--profile`（自动套用文档来源/深度下限）、Agent 规则引用（SKILL.md / `claim_evidence_layer.md`）。
- 解析器 `shared/scripts/rule_profile.py` 优先用 PyYAML，缺失时用内置最小 YAML 子集解析器（core 脚本保持纯标准库）。

## 安装与使用

1. 克隆仓库，让支持 `SKILL.md` 的 Agent 加载两个 skill（`evidence-writer`、`evidence-reviewer`）。
2. 依赖：Python 3；`pip install -r shared/requirements.txt`（按需）；可选 pandoc / Chrome 用于 PDF 导出。
3. **能力探测**：`python shared/scripts/probe_capabilities.py --human` 生成 `runtime/capability.local.json`，Agent 据此自动选择最佳路径（pandoc 缺失→python-markdown 回退、mmdc 缺失→mermaid.ink 远程、pdfplumber 缺失→告警而非静默失败）。
4. 写文档 → 触发写作方；审文档 → 触发审查方。
5. **沙箱**（可选）：`docker build -t evidence-suite -f docker/Dockerfile .`，容器内断网跑校验脚本（见 `docker/README.md`）。

路径约定：所有共享资产以 `${SUITE_ROOT}`（套件根目录）开头，由 agent 加载 skill 时解析，无需写死绝对路径。

## 触发（何时激活）

- **写作方**高置信：`evidence-driven`、`source-grounded`、`证据驱动写作`、`学术写作流水线`、`需逐条核验引用的技术/学术文档`。
- **审查方**高置信：`证据审计`、`来源审计`、`source audit`、`draft review`、`红队审查`。
- **不触发**：纯润色、拼写检查、普通摘要、简单改写、非事实性创作、PPT 文案。

## 支持哪些 Agent

凡能加载 `SKILL.md` 并执行本地脚本 / 联网的 Agent（如 opencode、Claude Code、Codex 等）。注意：本仓库是**多 Skill + 共享资产仓库（Suite）**，不是单一可一键安装的 Skill 包——需要路径解析、Python 环境与工作区，详见 `shared/README.md`。

## 安全

本套件会让 Agent 获得本地脚本执行与联网能力（来源检索、PDF 下载、NSFC 抓取）。威胁模型与信任边界见 **`THREAT_MODEL.md`**，具体防护措施见 `SECURITY.md`（SSRF 拦截、路径约束、脚本白名单、恶意 PDF 上限、凭据隔离、风险声明）。

## 测试与评测

```bash
python tests/run_tests.py      # 回归：50 用例，仅 Python 标准库
python eval/run_eval.py        # Eval/Golden：自动判分 + 人工打分表
```

- **回归**（`tests/run_tests.py`）：引用闭合 / 缺 URL / 来源与深度下限 / 数字引文 / 语料自检（含 authority/freshness/superseded）/ manifest 契约校验 / SSRF 守卫 / 规则配置 / 证据充分性 / DOCX 排版与 Mermaid 嵌入 / PDF CSS。
- **Eval/Golden**（`eval/`）：20 个 golden 用例，15 个 script 级**自动判分**（引用闭合含学术模式、缺 URL、可疑域名、source_origin、废止标准、契约非法枚举、证据充分性、机器可审计性、SSRF 拦截），5 个 agent 行为级（prompt injection、摘要≠原文、矛盾处理、论断对齐、幻觉）需真实 agent 运行 + 人工/第二模型回填打分；结果写入 `eval/report.md`。
- 脚本层覆盖明细见 `benchmarks/README.md`（18 个 agent 行为场景定义 + 量化指标）。

## 最小演示（Quickstart）

无需联网、无第三方依赖，一行复现「定稿净化 → manifest 产出 → 契约校验」闭环：

```bash
# Windows
examples/quickstart/run_demo.ps1
# macOS / Linux
examples/quickstart/run_demo.sh
```

输入两条带 `[Sx]` 的论断 → 产出 `output/evidence_manifest.json`（source-centric）与 `output/claim_manifest.json`（claim-centric），并校验通过；期望输出见 `examples/quickstart/expected/`。

## 限制

> ⚠️ **同模型自审 ≠ 独立评审（先读）**：单一 Agent 内「写作者 / 审查者」是同模型角色隔离，属**内部红队**。**模型幻觉会自我包庇**，同模型内红队只能作为第一道过滤——高可信度产出（R4 / 终审门通过 / 投稿或安全关键结论）**必须切换不同模型做 review 或接入人类专家**。所有审查结论在 `evidence_manifest.json` 的 `review_kind` 字段明确标记（`ai-internal` / `ai-cross-model` / `human-expert`），**禁止把 `ai-internal` 包装成独立专家评审**。

- 来源数量下限是「地板」不是目标；防 citation padding 靠审查方的闭合检查与「直接度」判定。
- 安全边界与脚本权限见 `SECURITY.md`；网络类脚本内置 SSRF 拦截（拒绝回环/私网/保留地址）与下载大小上限。

## 路线图

- [x] 去除路径硬编码、收紧触发词
- [x] 引入 `support_level` / `evidence_status` 证据语义
- [x] Claim Class 八类 + Risk Tier R0–R4 分级（缩小规则适用域）
- [x] Source Authority 分级（A1–D2，R3/R4 要求来源 ≥A2）
- [x] Evidence Freshness 字段（current/recent/historical/superseded/unknown）
- [x] 反证主动搜索（criticism/limitation/contradictory/failed + 质疑/局限/反例）
- [x] Evidence Stop Rule（覆盖/反证/多样性达标即停止，边际收益衰减不凑数）
- [x] 本地 Mermaid 渲染默认化（`--mermaid-engine local/auto/remote`）
- [x] 审查独立性标注（Independent AI Review vs External Expert Review）
- [x] 运行模式（Quick / Research / Document / Review）
- [x] 反证 reconciliation 正式阶段
- [x] 最小回归测试套件（`tests/run_tests.py`）
- [x] 评测基准用例定义（`benchmarks/`，打分需实跑 agent）

## 许可

MIT（见 `LICENSE`）。

## 贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)——如何加规则 / 契约 / golden 用例 / 脚本，提交规范与 PR 检查清单。
