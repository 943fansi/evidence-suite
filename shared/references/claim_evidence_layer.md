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
