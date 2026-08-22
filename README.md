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
- 判定按「直接度」而非「来源数量」：两条 `weak_inference` ≠ 一条 `direct`。

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

## 限制

- 单一 Agent 内「写作者 / 审查者」是同模型角色隔离，属**内部红队**；真正的独立审查需不同模型或人类专家（审查方会自动标注评审类型，不伪造专家）。
- 来源数量下限是「地板」不是目标；防 citation padding 靠审查方的闭合检查与「直接度」判定。

## 路线图

- [x] 去除路径硬编码、收紧触发词
- [x] 引入 `support_level` / `evidence_status` 证据语义
- [x] 审查独立性标注（Independent AI Review vs External Expert Review）
- [x] 运行模式（Quick / Research / Document / Review）
- [ ] 反证 reconciliation 正式阶段
- [ ] 最小回归测试套件
- [ ] 证据质量评测基准

## 许可

MIT（见 `LICENSE`）。
