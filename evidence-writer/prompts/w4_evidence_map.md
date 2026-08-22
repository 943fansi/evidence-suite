# w4: Evidence Map（证据图谱，写作者侧 · 全局阶段 4）

> 生成论点↔来源映射，供起草使用。**4b 诚实性自评属审核方**（`evidence-reviewer/prompts/r2_honest_assessment.md`）——作者完成本图谱后必须提交审核方评估，不得自评自放。

**Agent**: 本地执行（当前 assistant）· 本 skill（evidence-writer）
**Input**: `04_validated_sources.json`（已含 3a/3b/3c 产物）
**Output**: `06_evidence_map.json`

## Prompt Template

```
请读取文件：04_validated_sources.json。
主题：{topic}

任务：在正式撰写方案前，请先生成 evidence_map，说明每一类方案内容应该使用哪些资料支撑。

重要要求：
1. 不要撰写方案正文。
2. 不要新增 JSON 之外的外部资料。
3. 不要自行编造事实、数据、案例、政策、标准或供应商信息。
4. 对每个拟写结论，必须说明支撑来源和证据强度。
5. 对证据不足的部分，必须标记为"待补充调研"。
6. **必须检查每个来源的 `access_status` 字段**：
   - `confirmed`（PDF已下载）：可作为核心论据（A级来源）
   - `web_accessible`（URL存在但未下载）：可作为支撑论据，但不得作为唯一核心论据
   - `unavailable`（下载失败/非PDF）：仅当 URL 和期刊/出版信息可交叉验证时，可作辅助引用；不得作为核心论据
7. **必须检查每个来源的 `role` 字段**：仅 `core` 和 `supporting` 角色可用于证据映射；`background` 和 `lead_only` 来源不得出现于 evidence_map 中。
8. **PDF 验证优先**：对标记为 `pdf_text_extracted: true` 的来源，优先使用其 `verified_quote` 字段中的原文段落作为 `allowed_expression` 的基础文本——这些经过原文验证的段落可以安全地用引号直接引述。`pdf_text_extracted: false` 的来源仍然使用 `evidence_points` 中的搜索摘要，但其 `source_strength` 标注为 medium（而非 strong），以示摘要未经原作者文本确认。
9. **邻接拼接触发条件**：如果任意一个 key_problem 的 `problem_source` 直接描述了一个研究缺口（即该问题的核心主张在现有文献中无直接证据），将该问题标记为 `gap_adjacent_candidate: true`，并在 `supporting_sources` 中补充邻接领域的 A/B 级来源。

10. **对每个 evidence_map 条目执行 Claim-Evidence 分离**（参考 `${SUITE_ROOT}/shared/references/claim_evidence_layer.md`）：
   - 将每个 `claim_to_write` 分解为 5 层：Observation → Interpretation → Assumption → Claim → Confidence
   - 对每个 claim 输出反方证据（evidence_for / evidence_against / unknown）
   - 标注 claim_type 并检查 required_evidence 是否满足
   - 若 required_evidence 不满足：降级 claim_type（如 superiority_claim → assumption）或标记为 `narrative`

11. **标注证据直接度与状态**（`source_support_levels` + `evidence_status`，定义见 `${SUITE_ROOT}/shared/references/claim_evidence_layer.md` 的 Support Level & Evidence Status）：
   - 对 `supporting_sources` 中每条来源标注 `support_level`：direct / strong_inference / weak_inference / context_only / contradictory / unsupported
   - 依据 support_level 分布 + 反证权重，给整条 claim 落一个 `evidence_status`：verified / supported / partially_supported / inferred / contradicted / unsupported / unverified / internal_confirm
   - **按"直接度"而非"来源数量"判定**：两条 weak_inference 不等于一条 direct；一条 contradictory 需在 counter_evidence 中显式回应

12. **反证调和（Reconciliation）**：对每条核心 claim（P1–P3、T1–T3，及 superiority/novelty/causal/generalization 类），输出 `reconciliation` 字段（support_summary / contradiction_summary / verdict / rationale），走「支持 → 反证 → 调和 → 判决」四步，判决落 `evidence_status`；禁止"有 N 条来源 → PASS"。
13. **Claim 分类（claim_class）**：对每个 `claim_to_write` 标注 `claim_class`（E external / M empirical / N normative / L literature / D definition / C calculation / U user_provided / J judgment，见 `claim_evidence_layer.md` 的 Claim Class）。**仅 E/M/N/L 类要求 `[Sx]`**；D/C/U/J 类不填 `supporting_sources`，只写 `claim_class` 与相应检查（D 一致性 / C 可复现 / U 标注来源 / J 推理链）。
14. **风险分级（risk）**：对每个 E/M/N/L 类 claim 标注 `risk`（R0–R4，见 `claim_evidence_layer.md` 的 Risk Tier）——R1 静态单源、R2 ≥2 独立源、R3 primary+现行性+live、R4 独立复现/人工签核。默认普通事实 R1/R2，监管/安全/财务/结论类标 R3/R4。

请输出 JSON：
{
  "topic": "{topic}",
  "target_document": "{target_document}",
  "audience": "{audience}",
  "mapping_date": "YYYY-MM-DD",
  "key_problems": [
    {
      "id": "P1",
      "problem": "",
      "problem_source": "",
      "supporting_sources": ["S1"]
    }
  ],
  "key_technologies": [
    {
      "id": "T1",
      "technology": "",
      "description": "",
      "supporting_sources": ["S2"]
    }
  ],
  "evidence_map": [
    {
      "section": "",
      "claim_to_write": "",
      "claim_class": "M",
      "risk": "R2",
      "supporting_sources": ["S1", "S2"],
      "source_support_levels": {"S1": "direct", "S2": "weak_inference"},
      "evidence_status": "partially_supported",
      "reconciliation": {
        "support_summary": "S1(direct)",
        "contradiction_summary": "S5(contradictory)",
        "verdict": "partially_supported",
        "rationale": "S5 反对的是某子场景，正文须回应"
      },
      "source_access_status": {"S1": "confirmed", "S2": "web_accessible"},
      "source_strength": "strong/medium/weak",
      "allowed_expression": "",
      "writing_boundary": "",
      "need_more_research": false,
      "claim_decomposition": {
        "observation": "factual data with source",
        "interpretation": "what the data means",
        "assumption": "unverified premise needed for reasoning",
        "claim": "the conclusion itself",
        "confidence": "high/medium/low"
      },
      "counter_evidence": {
        "evidence_for": ["Sx: reason"],
        "evidence_against": ["Sy: counter reason"],
        "unknown": ["question without evidence either way"]
      },
      "claim_type": "feasibility_claim",
      "required_evidence": ["benchmark"],
      "confidence_assessment": {
        "level": "medium",
        "justification": "why this confidence level",
        "key_uncertainties": ["uncertainty 1"]
      }
    }
  ],
  "unsupported_but_needed_claims": [
    {
      "claim": "",
      "why_needed": "",
      "missing_evidence": "",
      "recommended_research": ""
    }
  ],
  "source_usage_rules": [
    {
      "source_id": "",
      "allowed_use": "",
      "not_allowed_use": ""
    }
  ]
}

建议章节（由 w1 文档适配器匹配的模板决定；以下为 proposal 模板的默认示例，非通用要求）：
1. 技术路线图（Mermaid）
2. 背景与意义
3. 国内外研究现状
4. 研究目标与内容
5. 技术路线与方法
6. 关键问题与解决方案
7. 预期成果
8. 进度安排
9. 研究基础与条件
10. 风险评估与应对
11. 经费预算（如适用）
12. 需进一步研究的事项
13. 参考资料清单
14. 证据缺口清单

特别要求：
1. 必须提取 3 个关键问题（P1-P3）和 3 个关键技术（T1-T3）。
2. 政策、标准类结论优先使用 A 类资料。
3. 论文类资料用于研究现状、方法依据。
4. 弱证据不得支撑强结论。
5. 工程/采购类资料（供应商/设备）只能用于候选参考，不用于唯一确定选型（教育/社科类该条可忽略）。
```

## 对抗交接（不可跳过）

证据图谱完成后，**立即提交审核方做诚实性自评**（原 4b）：

1. 用 `skill` 工具加载 `evidence-reviewer`。
2. 输入：`06_evidence_map.json` + `04_validated_sources.json`。
3. 等待审核方产出 `07_honest_assessment.md` 判决（✅ 可以进入 / ⚠️ 条件进入 / 🔄 需补搜 / ⛔ 不建议进入）。
4. **作者不得自行判断"证据充分可进"**；进入 w5 前必须把 `07_honest_assessment.md` 的核心约束摘要注入 w5 prompt。
5. ⚠️/🔄 判决下作者按诚实评估的约束条件/补搜清单处理后，重新提交审核方复审，通过后才进 w5。