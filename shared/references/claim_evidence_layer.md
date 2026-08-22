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

## JSON Schema Extensions

### For evidence_map.json (Stage 4)

Each entry in `evidence_map[]` extends with:

```json
{
  "section": "...",
  "claim_to_write": "...",
  "supporting_sources": ["S1"],
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
