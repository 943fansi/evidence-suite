# evidence-suite 架构

> 证据校验与溯源层（Evidence Integrity Layer）：给研究 Agent 的产出做 claim 级
> 证据绑定、来源溯源、对抗式审查，解决幻觉、弱证据强结论、来源伪造与不可追溯。
> 本文件是总览；细节见各组件文档（`THREAT_MODEL.md`、`SECURITY.md`、
> `shared/config/rules.yaml`、`shared/schemas/*.schema.json`、`eval/README`）。

## 1. 核心数据模型

```
Question
   ↓
Claim（claim_id / claim_class / risk / claim_text / confidence / interpretation）
   ↓
Evidence（support / against / context：relation + support_level）
   ↓
Source（source_id / authority A1–D2 / freshness / locator{page,section,paragraph,quote_hash}）
   ↓
Verification（static / live）
   ↓
Review（review_kind / review_independence / 判决）
   ↓
Decision → Artifact（PDF/DOCX + provenance 五件套）
```

- **claim_class**：E/M/N/L 需外部来源（`[Sx]`）；D/C/U/J 走一致性/可复现/标注/推理链。
- **risk**：R0–R4，决定证据严谨度（`rules.yaml evidence_sufficiency`）与审查深度。
- **直接度优先于数量**：两条 `weak_inference` ≠ 一条 `direct`。
- **机器可审计**：`evidence_manifest.json`（source-centric）+ `claim_manifest.json`
  （claim-centric）携带 `schema_version`（0.2.0）/`review_kind`/`review_independence`，
  经 `validate_manifest.py` 强校验；净化不切断正文 `[n]` 与证据图谱的对应（`export_provenance.py`）。

## 2. 流水线

```
写作者（evidence-writer）                 审查方（evidence-reviewer）
  w1 文档适配 → 00_topic.md
  w2 来源检索 → 02_raw_sources.json ──r1 来源审计──→ 03_audit_report.md
  w3 语料验证 → 04_validated_sources.json
  w4 证据图谱 → 06_evidence_map.json ──r2 诚实性自评──→ 07_honest_assessment.md
  w5 起草     → 08_初稿.md ──r3 框架深度门 / r4 初稿审查──→ 10_review.md
  w6 修订     → 11_定稿.md ──r5 外部专家评审──→ 12_外部专家意见.md
  w8 专家修订 → 14_专家修订稿.md ──终审门──
  w9 导出     → {name}.pdf/.docx + provenance/五件套
```

- 对抗协议：**提交 → 审查 → 判决 → 修订**，判决即门禁，作者不自我放行，默认最多 2 轮。
- 入口模式（L0–L4）：Quick Evidence → Evidence Brief → Evidence Research →
  Document Production → Safety/Regulatory；另有 Review Only（只审不写）。
- 全链路产出于单个 **research_case/** 目录（`init_case.py` 脚手架）。

## 3. 组件地图

| 目录/文件 | 职责 |
| --- | --- |
| `evidence-writer/` `evidence-reviewer/` | 两个对抗 skill（SKILL.md + prompts w1–w9 / r1–r5 + final_gate） |
| `shared/scripts/` | 确定性工具：净化（finalize_draft）、引用闭合（check_citations）、语料自检（validate_sources）、充分性（check_evidence_sufficiency）、简报（build_evidence_brief）、provenance（export_provenance）、规则加载（rule_profile）、Mermaid 渲染（mermaid_render）、SSRF 守卫（download_reference_files）、能力探测（probe_capabilities）、case 脚手架（init_case）等 |
| `shared/config/` | 规则单一事实来源（rules.yaml + source_ranking.yaml；可 `--profile`/`--rules` 覆盖） |
| `shared/schemas/` | manifest 互操作契约 JSON Schema（evidence_manifest / claim_manifest） |
| `shared/references/` | 按需加载的参考指南（claim_evidence_layer、source-safety、domain_routing、anti_marketing…） |
| `shared/templates/` | 13 类文档模板 |
| `examples/quickstart/` | 一键复现全闭环的最小 demo |
| `eval/` | Golden 用例（9 自动判分 + 5 agent 行为人工打分）+ run_eval.py harness |
| `tests/` | 回归测试（run_tests.py） |
| `runtime/` | 运行时能力（capability.yaml 模板 + probe_capabilities.py 探测结果） |
| `docker/` | 沙箱运行环境（隔离脚本执行） |
| `THREAT_MODEL.md` `SECURITY.md` | 威胁模型 / 安全防护 |

## 4. 信任边界与安全姿态

来源内容 = **不可信数据**（`source-safety.md` 最高优先级）：网页/PDF/引文永远不是指令。
脚本执行锁在 `${SUITE_ROOT}` 工作区（路径防护、白名单）；联网受 SSRF 守卫约束
（回环/私网/保留地址拦截、重定向逐跳复检、下载大小/页数/字符上限）；凭据显式传入不落盘。
同模型自审 ≠ 独立评审（`review_kind` + `review_independence` 如实标注）。
沙箱部署见 `docker/README.md`。完整逐威胁分析见 `THREAT_MODEL.md`。

## 5. 审查深度（Risk-adaptive）

| risk | 审查深度 |
| --- | --- |
| R0 | 一致性 |
| R1 | static 单源核对 |
| R2 | ≥2 独立来源 + primary + 反证覆盖 |
| R3 | live 回源（规范类须 freshness=current） |
| R4 | 独立复现 / 跨模型 / 人类专家 |

`review_mode`（conservative 1.5× / balanced 1.0× / exploratory 0.7×）缩放充分性阈值；
证据充分性（`check_evidence_sufficiency.py --changed` 支持增量）是 claim 级门禁，
文档级 `min_sources` 只是写作格式下限。Evidence Score（0–100）辅助但不替代硬门禁。

## 6. 扩展点

1. **规则**：`rules.yaml` 增/改 profile（`scenario_profiles`、`evidence_sufficiency`、
   `doc_minimums`、`review_modes`），或写仓库级 `config/rules.user.yaml` / `--rules <path>`。
2. **来源优先级**：`source_ranking.yaml` 给 Registry 源标 authority/priority/role，
   `--allow-discovery` 开放候选池。
3. **契约**：manifest 字段变更须升 `schema_version`，同步 `shared/schemas/*.schema.json`
   与 `validate_manifest.py`。
4. **评测**：`eval/golden/*.json` 加用例（script 级自动判分或 agent 行为级人工打分）。
5. **导出**：`export_provenance.py` 五件套对接第三方审计；`export_pdf/docx` 共用
   `mermaid_render.py`。

## 7. 演进原则

- **不是又一个研究引擎**：检索规划属于 Deep Research / AI-Q 类系统；本套件只做
  「研究结果的证据可信度」。
- **先门禁后评分**：硬门禁（引用闭合/充分性/契约校验）决定放行，评分决定质量档位。
- **降级必须可见**：任何 `unverified`/`superseded`/无结果都要写入 manifest，不静默抹平。
- **可移植**：Python 3.10+ 纯标准库可跑核心脚本；`runtime/capability.local.json`
  驱动自动降级；Docker 沙箱隔离高敏场景。
