# evidence-suite · 证据驱动写作 / 审查对抗套件

让 AI 写出的技术 / 学术文档**每一条论断都能追溯到来源**：写作方（evidence-writer）负责生产，审查方（evidence-reviewer）有罪推定、只找失败、严重即阻断，两者形成「提交 → 审查 → 判决 → 修订」的对抗循环。

## 为什么需要它

普通 LLM 直接写技术 / 学术文档有 5 个典型问题：

1. **编造来源**：文献、数据、标准编号靠训练记忆臆造。
2. **弱证据撑强结论**：「国际领先」「填补空白」没有来源。
3. **自我放行**：写完即宣称完成，没有独立审查。
4. **证据与结论脱节**：有引用，但引用并不支撑结论。
5. **证据不可追溯**：说不清某句话来自哪篇、哪页。

本套件把「事实性论断必须挂 `[Sx]` 来源标记」作为硬约束，并用独立红队审查强制闭合。

## 它做什么

```
证据检索 → 语料验证 → 证据图谱 → 起草 → 红队审查 → 判决 → 修订 →（终审门）→ 导出
```

- **写作者（evidence-writer）**：w1 文档适配 → w2 来源检索 → w3 验证语料（下载 / 校验 / 抽原文）→ w4 证据图谱 → w5 起草 → w6 修订 → w8 专家修订 → w9 导出。
- **审查者（evidence-reviewer）**：r1 来源审计 → r2 诚实性自评 → r3 框架深度门 → r4 初稿审查 → r5 外部专家评审 → 终审门。

## 运行模式

按用户意图选择，**不所有任务都走完整流水线**：

| 模式 | 做什么 | 是否进对抗循环 |
|------|--------|--------------|
| Quick Evidence | 单个事实 / 标准条款 → 检索 + 核验 → 直接结论 | 否 |
| Evidence Research | 技术调研 / 综述 → 证据图谱 → research memo | 否 |
| Document Production | 完整交付物（默认）→ 全链路 + 红队审查 | 是 |
| Review Only | 已有文档 → 只审不写 → 判决 | 是（仅审查方） |

## 证据模型

- 标记：`[Sx]` 已审计来源、`[Gx]` 研究空白、`[假设]` / `[待内部确认]` 显式留白。
- `support_level`（direct / strong_inference / weak_inference / context_only / contradictory / unsupported）：**证据能多大程度直接证明该结论**。
- `evidence_status`（verified / supported / partially_supported / inferred / contradicted / unsupported / unverified / internal_confirm）：**该结论最终处于什么状态**。
- `claim_class`（E/M/N/L 需 `[Sx]`；D 定义 / C 计算 / U 用户提供 / J 判断 不走来源真实性审查）——见 `claim_evidence_layer.md`。
- `risk`（R0–R4）：R1 单源 / R2 独立交叉 / R3 primary+现行性+live / R4 独立复现/人工签核——把"一律有罪推定"缩小到真正高险的论断。
- `authority`（来源权威 A1–D2）：法规 A1 / 标准 A2 / 国标行标 A3 / 官方报告 B1 / 原始实验 B2 / 期刊 C1 / 学位 C2 / 厂商 D1 / 二手 D2；R3/R4 要求来源 ≥ A2。
- `freshness`（证据新鲜度 current / recent / historical / superseded / unknown）：政策/标准类 R3/R4 须 `current`，`superseded` 不得作现行依据。
- 判定按「直接度」而非「来源数量」：两条 `weak_inference` ≠ 一条 `direct`。
- 交付时 `finalize_draft.py --manifest` 产出 `evidence_manifest.json`（`[n]→来源` 可回溯），保留证据 provenance。

详见 `shared/references/claim_evidence_layer.md`。

## 目录结构

```
evidence-suite/
├── evidence-writer/     # 写作方 SKILL.md + prompts/w1–w9
├── evidence-reviewer/   # 审查方 SKILL.md + prompts/r1–r5 + final_gate
├── shared/
│   ├── scripts/         # 14 个确定性工具（Bash 执行）
│   ├── references/      # 按需加载的参考指南
│   └── templates/       # 13 类文档模板
├── README.md
├── SECURITY.md
└── LICENSE
```

## 安装与使用

1. 克隆仓库，让支持 `SKILL.md` 的 Agent 加载两个 skill（`evidence-writer`、`evidence-reviewer`）。
2. 依赖：Python 3；`pip install -r shared/requirements.txt`（按需）；可选 pandoc / Chrome 用于 PDF 导出。
3. 写文档 → 触发写作方；审文档 → 触发审查方。

路径约定：所有共享资产以 `${SUITE_ROOT}`（套件根目录）开头，由 agent 加载 skill 时解析，无需写死绝对路径。

## 触发（何时激活）

- **写作方**高置信：`evidence-driven`、`source-grounded`、`证据驱动写作`、`学术写作流水线`、`需逐条核验引用的技术/学术文档`。
- **审查方**高置信：`证据审计`、`来源审计`、`source audit`、`draft review`、`红队审查`。
- **不触发**：纯润色、拼写检查、普通摘要、简单改写、非事实性创作、PPT 文案。

## 支持哪些 Agent

凡能加载 `SKILL.md` 并执行本地脚本 / 联网的 Agent（如 opencode、Claude Code、Codex 等）。注意：本仓库是**多 Skill + 共享资产仓库（Suite）**，不是单一可一键安装的 Skill 包——需要路径解析、Python 环境与工作区，详见 `shared/README.md`。

## 安全

本套件会让 Agent 获得本地脚本执行与联网能力（来源检索、PDF 下载、NSFC 抓取）。凭据与边界见 `SECURITY.md`。

## 测试

```bash
python tests/run_tests.py
```

覆盖 `check_citations.py`（引用闭合 / 缺失 URL / 来源数下限 / 正文深度下限 / 数字引文闭合）与 `validate_sources.py`（重复 URL / 可疑域名），仅用 Python 标准库。

## 限制

- 单一 Agent 内「写作者 / 审查者」是同模型角色隔离，属**内部红队**；真正的独立审查需不同模型或人类专家（审查方会自动标注评审类型，不伪造专家）。
- 来源数量下限是「地板」不是目标；防 citation padding 靠审查方的闭合检查与「直接度」判定。

## 路线图

- [x] 去除路径硬编码、收紧触发词
- [x] 引入 `support_level` / `evidence_status` 证据语义
- [x] Claim Class 八类 + Risk Tier R0–R4 分级（缩小规则适用域）
- [x] Source Authority 分级（A1–D2，R3/R4 要求来源 ≥A2）
- [x] Evidence Freshness 字段（current/recent/historical/superseded/unknown）
- [x] 反证主动搜索（criticism/limitation/contradictory/failed + 质疑/局限/反例）
- [x] Evidence Stop Rule（覆盖/反证/多样性达标即停止，边际收益衰减不凑数）
- [x] 审查独立性标注（Independent AI Review vs External Expert Review）
- [x] 运行模式（Quick / Research / Document / Review）
- [x] 反证 reconciliation 正式阶段
- [x] 最小回归测试套件（`tests/run_tests.py`）
- [x] 评测基准用例定义（`benchmarks/`，打分需实跑 agent）

## 许可

MIT（见 `LICENSE`）。
