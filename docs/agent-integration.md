# Agent 集成指南（PR-08 骨架 · 2026-11-21）

> evidence-suite 是研究 Agent 的**证据校验层**：上游研究发动机产出草稿/报告，
> 本套件做 claim 级验证、溯源、红队审查。本页回答两个问题：
> ① 主流上游 agent 的输出怎么接进来；② 本套件怎么被宿主 agent / 工具生态调用。
> 外部环境依据见 `landscape-2026-11.md`；优化依据见 `optimization-plan-2026-11.md`。

---

## 一、上游 agent 输出 → 本套件消费入口（对接矩阵）

通用前提：本套件的最小消费契约是 **`claim → evidence → verdict` 结构**
（README「互操作契约」节）。上游只要能给出「论断 + 来源 + 引文位置」三者，
即可进入校验链路；给不出结构化映射时，走 Review Only 的纯文本入口。

| 上游 agent | 输出形态 | 对接方式 | 落点脚本 |
|-----------|---------|---------|---------|
| **NVIDIA AI-Q**（deep-researcher-agent blueprint，开源） | 报告 + 全文级引用归因（工具输出即 evidence） | 转换为其引用列表 → `04_validated_sources.json` + `06_evidence_map.json` 骨架；报告原文走定稿链路 | `finalize_draft.py --manifest` |
| **STORM**（stanford-oval，开源） | 文章 + source→citation 全程映射 | 映射直接喂 claim-centric manifest 的 `evidence[]`（source_id + locator 同构） | `finalize_draft.py --claim-manifest` |
| **GPT-Researcher**（开源） | 报告 + 引用列表（URL 级） | Review Only：报告当草稿、URL 列表当语料，先 `validate_sources.py` 审来源再 `check_citations.py` | `validate_sources.py` → `check_citations.py` |
| **OpenScholar**（allenai，开源） | 答案 + 内联引用（含 self-feedback 修订史） | 取最终答案走 Review Only；self-feedback 轨迹可作 r2 诚实性自评的对照输入 | `check_citations.py` |
| **OpenAI Deep Research**（闭源） | 报告 + inline citations | 导出为 Markdown 后走 Review Only；引用的 URL 手动补进语料（编造风险高，r1 必审） | `validate_sources.py` |
| **Anthropic Citations API** | 结构化引用（**字符级 provenance**：精确引文 + 文档区间） | 与本套件 `locator.quote_hash` 粒度对齐最好——直接映射为 evidence[] 的 locator | `finalize_draft.py --claim-manifest` |
| **任意 LLM 草稿**（无结构化引用） | 纯文本，`[Sx]` 标记可选 | w2 补缺口检索 → w3 语料验证 → w4 证据图谱（Local Corpus First） | 全写作链路 |

> **对接成本排序**（从低到高）：Anthropic Citations ≈ STORM < AI-Q < GPT-Researcher < Deep Research 导出 < 纯文本。
> 共同要求：上游引用必须是**可解析 URL/DOI**，r1 来源审计会按 `source_ranking.yaml` 分级；不可解析的引用一律按编造处理。

## 二、本套件被调用：三种宿主形态

### 1. SKILL.md 宿主（当前主路径）

opencode / Claude Code / Codex 等加载 `evidence-writer/` + `evidence-reviewer/` 两个 skill，
Agent 按 SKILL.md 编排 Bash 调用（脚本白名单见 `SECURITY.md`）。触发词见 README「触发」节。

### 2. 统一 CLI（脚本宿主）

```bash
evidence-suite --list        # 全部子命令
evidence-suite validate <manifest.json>
evidence-suite export pdf <draft.md> --manifest <manifest.json>
```

宿主不需要理解 skill 语义，只需把子命令当**可组合 validator** 用——
清单见 `shared/config/validators.yaml`（输入 / 判定语义 / 退出码 / 0–1–2–3 约定）。

### 3. MCP server（一等集成路径，PR-08 后续）

MCP 2026-07-28 规范起，生态注意力转向验证/provenance（见 landscape-2026-11 第三节）。
映射关系：

| MCP 概念 | 本套件对应 |
|---------|-----------|
| tool | `evidence-suite.py` 子命令（validate / sufficiency / check / export …） |
| resource | `evidence_manifest.json` / `claim_manifest.json` / provenance 五件套 |
| 工具响应附载 | manifest 本身——研究 agent 的每次检索/写作结果可带 manifest 回传，宿主侧留档审计 |

> 实现取舍：本套件脚本为纯标准库 + 可断网设计，MCP server 作为**薄包装**（stdio transport，
> 子命令透传）放在 `shared/scripts/`，不引入新依赖；待 PR-08 批次实现。

## 三、审查独立性提醒（集成时最容易错的一点）

无论哪种宿主形态：**同模型内调用 writer→reviewer = `ai-internal`，不是独立评审**。
跨模型编排（如宿主用模型 A 跑 writer、模型 B 跑 reviewer）须在 manifest 的
`review_independence` 如实记录 `reviewer_model` / `writer_model` / `context_shared`。
详见 README「限制」节与 `THREAT_MODEL.md`。
