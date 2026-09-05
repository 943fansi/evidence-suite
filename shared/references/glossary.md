# evidence-suite 术语速查表（Glossary）

> 本表是 `claim_evidence_layer.md` / `rules.yaml` / `source_ranking.yaml` 的公开速查版，
> 供新用户快速定位枚举取值。完整语义与判定规则以 `claim_evidence_layer.md` 为准。
> 规则权威取值以 `shared/config/rules.yaml` 为准。

## 1. Claim Class（证据分类：决定是否需外部来源）

只前 4 类走**来源真实性审查**；D/C/U/J 仍要检查，但不挂 `[Sx]`。

| 代码 | 名称 | 含义 | 需 `[Sx]` | 检查方式 |
|------|------|------|:--------:|---------|
| E | external | 外部事实（市场/统计/历史/现实状态） | ✅ | 来源真实性 |
| M | empirical | 实证主张（实验/测量/观测结论） | ✅ | 来源真实性 |
| N | normative | 规范/标准/政策要求 | ✅ | 来源真实性 + 现行性 |
| L | literature | 文献主张（他人研究/观点/结论） | ✅ | 来源真实性 |
| D | definition | 作者定义（对象/符号/术语） | ❌ | 前后一致性 |
| C | calculation | 计算/推导（本文计算所得） | ❌ | 公式正确/可复现/输入有据 |
| U | user_provided | 用户提供（前提/参数/数据） | ❌ | 仅标注来源 |
| J | judgment | 作者判断（分析/评价/取舍） | ❌ | 推理链是否成立 |

## 2. Support Level（证据直接度，逐来源判定）

| 取值 | 含义 | 判定问题 |
|------|------|---------|
| direct | 原文直接陈述/支持该 claim | 原文是否直接说了这句话？ |
| strong_inference | 原文经极简推理即可推出 | 一步推理能否推出？ |
| weak_inference | 需显著推理/桥接才能推出 | 是否需多步假设才成立？ |
| context_only | 仅提供背景/语境 | 是否只是相关背景？ |
| contradictory | 原文与该 claim 相反 | 原文是否反驳该 claim？ |
| unsupported | 无来源可支撑 | 该 claim 是否无任何来源？ |

**原则**：两条 `weak_inference` ≠ 一条 `direct`。

## 3. Evidence Status（证据状态，逐 claim 判定）

| 取值 | 含义 |
|------|------|
| verified | 已对照原文核验（pdf_text_extracted + verified_quote） |
| supported | ≥1 条 `direct` 支撑且无反证 |
| partially_supported | 仅 `weak_inference` 支撑，或存在需回应的反证 |
| inferred | 全靠推断/假设链，无直接来源 |
| contradicted | 反证权重大于支持 |
| unsupported | 无充分证据 |
| unverified | 来源为摘要，尚未对照原文 |
| internal_confirm | 依赖内部信息（参数/数据），需作者确认 |

## 4. Risk Tier（风险分级：决定证据严谨度）

| risk | 含义 | 证据要求 |
|------|------|---------|
| R0 | stylistic（措辞/格式） | 无证据（属非证据类 D/C/U/J） |
| R1 | ordinary factual（普通事实） | 静态单源（r1 static） |
| R2 | important factual（重要事实） | ≥2 独立来源交叉 |
| R3 | regulatory/safety/financial | primary source + 现行性 + live 回源 |
| R4 | safety-critical/legal/publication-critical | 独立复现 / 人工签核 |

## 5. Source Authority（来源权威 A1–D2）

| authority | 类型 | 例 |
|-----------|------|-----|
| A1 | 法规/监管机构 | NRC Regulatory Guide、IAEA Safety Standards |
| A2 | 国际组织/标准组织 | IEEE Std、IEC、ISO |
| A3 | 国家/行业标准 | GB、国军标 |
| B1 | 官方技术报告 | EPRI、NUREG、国家实验室报告 |
| B2 | 原始实验/工程报告 | 结题报告、实测数据报告 |
| C1 | 同行评审论文 | 期刊论文 |
| C2 | 学位论文 | 硕博论文 |
| D1 | 厂商资料 | 设备手册、供应商技术资料 |
| D2 | 二手资料 | 转载/聚合/百科/新闻 |

**Risk → Authority**：R1 任意；R2 建议 ≥B1；R3 ≥A2（且现行 + live）；R4 ≥A1/A2 + 独立复现/人工签核。D1/D2 作 R3/R4 依据即标记 high。

## 6. Evidence Freshness（证据新鲜度）

| freshness | 含义 |
|-----------|------|
| current | 当前有效（最新版本/近 2–3 年） |
| recent | 近期（3–10 年内文献/数据） |
| historical | 历史（仅作史实/背景） |
| superseded | 已被替代/废止 |
| unknown | 无法判定 |

**原则**：`superseded` 不得支撑 R3/R4 现行性主张；政策/标准类 R3/R4 必须 `current`。

## 7. Relation / Confidence / Locator（V2 证据模型）

| 字段 | 取值 | 含义 |
|------|------|------|
| relation | supports / contradicts / context_only | 来源对 claim 的方向性关系 |
| confidence | high / medium / low | claim 级可信度 |
| locator | page / section / paragraph / quote_hash | 原文定位；`quote_hash` 建议 `sha256(归一化片段)` |
| locator_quality | high / medium / low | 定位精度；扫描件降级为 `low`（可仅章节级，`quote_hash` 置 null） |

## 8. 其他枚举

| 字段 | 取值 |
|------|------|
| review_kind | ai-internal（同模型内部红队）/ ai-cross-model / human-expert |
| verification_mode | static / live |
| schema_version | 当前 `0.2.0`（旧版由 `migrate_manifest.py` 向上迁移） |
