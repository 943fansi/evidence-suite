# Claim-Evidence Separation Layer

## Core Principle

不要生成"有数据的结论"，而要暴露"从证据到主张之间的所有推理层"。

Every claim must expose:
- Which part is **observation** (data)
- Which part is **interpretation** (meaning)
- Which part is **assumption** (unverified premise)
- Which part is **claim** (final assertion)
- What is the **confidence** level

## 5-Layer Decomposition

| Layer | 英文 | 中文 | 定义 | 示例 |
|-------|------|------|------|------|
| 1 | Observation | 观察/数据 | 实际存在的可核实数据点 | 工业AI市场年增长率 23.5% [S3] |
| 2 | Interpretation | 解释 | 数据意味着什么 | 行业需求正在增加 |
| 3 | Assumption | 假设前提 | 使解释能推导至主张所需的前提 | 本领域需求与整体市场同步增长 |
| 4 | Claim | 主张 | 最终想让人接受的结论 | 项目具备产业化潜力 |
| 5 | Confidence | 可信度 | 整个推理链的可靠性评估 | medium（因 Assumption 未经直接验证） |

## Claim Class（证据分类：决定是否需外部来源）

先按"是否需要外部证据"把每个 claim 分成 8 类——**只有前 4 类走来源真实性审查**：

| 代码 | claim_class | 含义 | 需 `[Sx]` | 检查方式 |
|------|-------------|------|:--------:|---------|
| E | external | 外部事实（市场/统计/历史/现实状态） | 必须 | 来源真实性 |
| M | empirical | 实证主张（实验/测量/观测结论） | 必须 | 来源真实性 |
| N | normative | 规范/标准/政策要求 | 必须 | 来源真实性 + 现行性 |
| L | literature | 文献主张（他人研究/观点/结论） | 必须 | 来源真实性 |
| D | definition | 作者定义（对象/符号/术语） | 否 | 前后一致性 |
| C | calculation | 计算/推导（本文计算所得） | 否 | 公式正确 / 可复现 / 输入有据 |
| U | user_provided | 用户提供（前提/参数/数据） | 否 | 仅标注来源 |
| J | judgment | 作者判断（分析/评价/取舍） | 否 | 推理链是否成立 |

**关键**：D/C/U/J **不是不检查**，而是**不走外部来源真实性审查**。绝不给"本文将研究对象定义为……"这类句子强行挂 `[Sx]`。

### 默认审查路径（routing matrix）

| claim_class | `[Sx]` | 静态审查 | 回源（live） | 反证 |
|-------------|:------:|:--------:|:-----------:|:----:|
| E external | ✓ | ✓ | 按风险 | 高风险 |
| M empirical | ✓ | ✓ | 按风险 | 高风险 |
| N normative | ✓ | ✓ | 建议 | 高风险 |
| L literature | ✓ | ✓ | 按风险 | 中/高 |
| D definition | — | — | — | — |
| C calculation | — | 可选 | — | — |
| U user_provided | — | — | — | — |
| J judgment | — | — | — | 必要时 |

现有 `claim_type`（superiority / causal / novelty …）仍保留，但**只在 E/M/N/L 类内**作为"该外部证据需要什么"的细分：`claim_class` 决定"要不要外部证据"，`claim_type` 决定"要哪种外部证据"。

## Risk Tier（风险分级：决定证据严谨度）

对**证据类 claim**（E/M/N/L）按"出错后果"标注 `risk`，风险越高约束越重——**R0/R1 不要求回源、不要求人工签核，只有 R3/R4 才触发最重约束**：

| risk | 含义 | 示例 | 证据要求 |
|------|------|------|---------|
| R0 | stylistic（措辞/格式） | 排版、术语统一 | 无证据（属非证据类 D/C/U/J） |
| R1 | ordinary factual（普通事实） | 一般背景事实 | 静态单源（r1 static） |
| R2 | important factual（重要事实） | 核心论据、方法依据 | ≥2 独立来源交叉 |
| R3 | regulatory/safety/financial | 标准条款、安全限值、预算依据 | primary source + 现行性 + live 回源 |
| R4 | safety-critical/legal/publication-critical | 事故结论、法律声明、投稿关键结论 | 独立复现 / 人工签核 |

### Claim Class × Risk 证据约束矩阵

| claim_class | R1 | R2 | R3 | R4 |
|-------------|----|----|----|----|
| E / M / L | 静态单源 | ≥2 独立源 | primary + 现行性 + live | 独立复现 / 人工签核 |
| N 规范 | 静态单源 | ≥2 独立源 | **primary + 现行版本 + live** | 人工签核 |

（D/C/U/J 非证据类不适用本表，按一致性 / 可复现 / 标注 / 推理链检查。）

**原则**：Risk Tier 把"一律有罪推定"**缩小适用域**——默认普通事实为 R1/R2，仅安全/监管/财务/结论类上 R3/R4。

## Source Authority（来源权威分级）

对**来源本身**标注 `authority`（A1–D2），区分"标准 + 技术报告 + 工程案例 + 论文 + 法规"混合证据的**证据地位**——这是来源的属性（存于 `04_validated_sources.json` 的 `authority` 字段），与 `source_level`（A/B/C 质量档，用于 C 级过度使用告警）是**两个不同轴**：

| authority | 类型 | 例 |
|-----------|------|-----|
| A1 | 法规/监管机构 | NRC Regulatory Guide、国家核安全局法规、IAEA Safety Standards |
| A2 | 国际组织/标准组织 | IEEE Std、IEC、ISO、IAEA TECDOC |
| A3 | 国家/行业标准 | GB、国军标、行业标准 |
| B1 | 官方技术报告 | EPRI 报告、NUREG、国家实验室报告 |
| B2 | 原始实验/工程报告 | 结题报告、实测数据报告 |
| C1 | 同行评审论文 | 期刊论文 |
| C2 | 学位论文 | 硕博论文 |
| D1 | 厂商资料 | 设备手册、供应商技术资料 |
| D2 | 二手资料 | 转载/聚合/百科/新闻 |

### Risk → Authority 要求

| claim risk | 来源 authority 要求 |
|-----------|---------------------|
| R1 | 任意（不强制高权威） |
| R2 | 建议 ≥ B1 |
| R3（监管/安全/财务） | **≥ A2**（标准/监管来源，且现行 + live） |
| R4 | ≥ A1/A2 + 独立复现 / 人工签核 |

D1/D2（厂商/二手）作 R3/R4 依据即标记 high。

## Claim Type Taxonomy

### Claim Types

| claim_type | 含义 | required_evidence | threshold_confidence |
|------------|------|-------------------|---------------------|
| `superiority_claim` | 技术/方案比现有方案更优 | benchmark数据 + competitor对比 + 第三方引用 | high |
| `causal_claim` | X导致Y | 机制证据 + 统计关联 + 排除混杂变量 | high |
| `generalization_claim` | 某发现可推广到其他场景 | 多场景数据 + 边界条件分析 + 失效条件说明 | medium+ |
| `market_potential_claim` | 市场/产业有潜力 | 市场数据(含来源机构/年份/范围) + 领域关联论证 | medium |
| `novelty_claim` | 创新性/填补空白 | 文献综述证据 + 明确界定"空白"的边界 | high (宣称空白需高证据) |
| `feasibility_claim` | 技术或方案可实施 | 已有案例/实验数据 + 资源评估 | medium |
| `impact_claim` | 预期影响/效益 | 因果链 + 对照基线 + 规模约束 | medium |
| `narrative` | 叙事/愿景而非事实 | 无事实性要求，但必须标注为 narrative | N/A (标记即可) |

### Unsupported Claims Blocking Rule

If a claim's `claim_type` requires evidence that is not present:
- Decompose into lower-confidence layers
- OR downgrade to `narrative` type with explicit marking
- OR remove the claim

**Example violation**:
> 本技术国际领先

```
claim_type: superiority_claim
required_evidence: [benchmark, competitor_comparison, citation]
actual_evidence: [citation_only]  ← insufficient
→ 自动触发: 降级或禁止输出
```

## Support Level & Evidence Status

### support_level（证据直接度，逐来源判定）

每条 `supporting_sources` 中的来源必须标注它**能否直接证明**这条 claim，而不只是"是否被引用"：

| support_level | 含义 | 判定问题 |
|---------------|------|---------|
| `direct` | 原文直接陈述/支持该 claim | 原文是否直接说了这句话？ |
| `strong_inference` | 由原文经极简推理即可推出 | 一步推理能否推出？ |
| `weak_inference` | 需显著推理/桥接才能推出 | 是否需要多步假设才成立？ |
| `context_only` | 仅提供背景/语境，不直接支撑 | 是否只是相关背景？ |
| `contradictory` | 原文与该 claim 相反 | 原文是否反驳该 claim？ |
| `unsupported` | 无来源可支撑 | 该 claim 是否无任何来源？ |

### evidence_status（证据状态，逐 claim 判定）

每个 claim 必须落一个整体状态：

| evidence_status | 含义 |
|-----------------|------|
| `verified` | 已对照原文核验（pdf_text_extracted + verified_quote） |
| `supported` | 至少一条 `direct` 支撑且无反证 |
| `partially_supported` | 仅 `weak_inference` 支撑，或存在需回应的反证 |
| `inferred` | 全靠推断/假设链，无直接来源 |
| `contradicted` | 反证权重大于支持 |
| `unsupported` | 无充分证据 |
| `unverified` | 来源为摘要，尚未对照原文 |
| `internal_confirm` | 依赖内部信息（参数/数据），需作者确认 |

**判定原则**：`evidence_status` 由 `support_level` 的分布 + 反证权重决定，**不是由来源数量决定**。两条 `weak_inference` 不等于一条 `direct`；一条 `contradictory` 会压制多条支持。

## Reconciliation（反证调和）

对每条**核心 claim**（P1–P3、T1–T3，以及 `claim_type ∈ {superiority_claim, novelty_claim, causal_claim, generalization_claim}`），必须显式走「支持 → 反证 → 调和 → 判决」四步，**禁止"有 N 条来源 → PASS"**：

1. **支持侧**：列出 `source_support_levels ∈ {direct, strong_inference}` 的来源。
2. **反证侧**：列出 `source_support_levels = contradictory` 的来源 + `counter_evidence.evidence_against`。
3. **调和**：判断反证是"可回应"（弱来源 / 仅背景，可在正文回应）还是"关键"（direct 反证且无法否定，压制支持）。
4. **判决**：落 `evidence_status`。

| 判决 | 条件 |
|------|------|
| `supported` | ≥1 条 `direct` 支持 且 无反证 |
| `partially_supported` | 仅 `weak_inference` 支持，或存在可回应的反证 |
| `contradicted` | 反证权重大于支持（direct 反证且无法否定） |
| `unsupported` | 无充分支持 |

每条核心 claim 需落盘 `reconciliation` 字段：

```json
{
  "support_summary": "S1(direct), S4(strong_inference)",
  "contradiction_summary": "S9(contradictory)",
  "verdict": "partially_supported",
  "rationale": "S9 反对的是某子场景，不否定主结论，正文须回应"
}
```

## JSON Schema Extensions

### For evidence_map.json (Stage 4)

Each entry in `evidence_map[]` extends with:

```json
{
  "section": "...",
  "claim_to_write": "...",
  "claim_class": "M",
  "risk": "R2",
  "supporting_sources": ["S1"],
  "source_support_levels": {"S1": "direct"},
  "evidence_status": "supported",
  "reconciliation": {
    "support_summary": "S1(direct)",
    "contradiction_summary": "",
    "verdict": "supported",
    "rationale": ""
  },
  "claim_decomposition": {
    "observation": "factual data point with source",
    "interpretation": "what the data means",
    "assumption": "unverified premise required for this reasoning chain",
    "claim": "the conclusion itself",
    "confidence": "high | medium | low"
  },
  "counter_evidence": {
    "evidence_for": ["S1: reason", "S2: reason"],
    "evidence_against": ["S5: counter reason"],
    "unknown": ["question without evidence either way"]
  },
  "claim_type": "superiority_claim",
  "required_evidence": ["benchmark", "competitor_comparison", "citation"],
  "confidence_assessment": {
    "level": "medium",
    "justification": "why this confidence level",
    "key_uncertainties": ["uncertainty 1"]
  }
}
```

## Marker Convention

In draft text, key claims should make reasoning layers visible. Two approaches:

### Option A: Inline marker (recommended for key P/T claims)

```
[O: 市场数据S3] 工业AI市场增长 → [I: 需求增加] → [A: 本领域同步]
→ [C: 项目具备产业潜力] [Confidence: medium]
```

### Option B: Paragraph-level annotation

```
项目具备产业化潜力。[S3]

> 推理链: Observation(S3:市场增长率23.5%) → Interpretation(需求增长)
> → Assumption(本领域同步) → Claim(产业化潜力)
> Confidence: medium | Counter-evidence: 本领域技术门槛高[S5]
```

Option A is preferred for inline正文, Option B for附录/提案正文的 margin annotations.

## Token Budget

This file (~114 lines) is loaded on demand in Stage 4 (evidence map), Stage 5 (draft), and Stage 6 (self-review).
