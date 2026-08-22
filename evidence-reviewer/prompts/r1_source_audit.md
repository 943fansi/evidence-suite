# r1: Source Audit（来源审计，审查者侧 · 全局阶段 2）

Use this prompt to instruct an external agent to audit the raw sources JSON.

## Prompt Template

```
请审查刚才输出的"{topic}"资料 JSON（02_raw_sources.json）。

重要要求：
1. 不要新增资料。
2. 不要撰写方案。
3. 只审查 JSON 质量。
4. 找出不可靠来源、过度推断、字段缺失、引用风险和需要补充验证的地方。

审查模式（evidence_verification_mode）：默认 **static**（不联网，只审工件）；涉及监管/安全/财务等 R3/R4 级风险或用户要求时，启用 **live**（联网回源）。static 下第 1、17 条只做"格式/字段"层面的静态检查（URL 格式、标准号写法），不真正访问网络；live 下才真正回源核验可达性/现行性。

请逐条检查（标注 [live] 的仅在 live 模式执行回源，其余 static 模式即可）：
1. [live] URL 是否真实、具体、可访问？
2. 该 URL 是否为原始来源，而不是转载、聚合页或二级加工？
3. source_level 是否合理？
4. is_primary_source 是否判断正确？
5. summary 是否忠实于资料本身？
6. evidence_points 是否有证据支撑？
7. usable_claims 是否超出了资料能证明的范围？
8. claim_limits 是否足够明确？
9. 是否存在把新闻报道、公众号、B2B 平台当作核心依据的问题？
10. 是否存在市场规模口径混杂的问题？
11. 是否存在标准号、论文 DOI、发布机构、年份缺失的问题？
12. 是否存在供应商参数不足但被用于确定选型的问题？
13. 每个 source 的 evidence_points 在 PDF 下载和文字抽取前均为 provisional——经过 Web 搜索验证但未经原文 PDF 文字抽取确认。仅有在 w3 子步骤 3c 执行后标记为 pdf_text_extracted: true 的来源，其证据才被最终确认。审计报告应在"总体评估"中注明当前 evidence_points 的成熟度级别。
14. registry_id 是否完整且正确：命中来源路由清单（${SUITE_ROOT}/shared/scripts/select_sources.py --domain 输出）的来源必须填对应清单 id；清单外补充来源必须填 "supplementary" 并在 credibility_reason 说明理由。缺填视为缺失字段。
15. 是否误用 forbidSources（自媒体/知乎/非官方转载/百科/AI厂商营销博客/教育软文）作为核心依据：命中即列入 suspicious_sources，suggested_action="delete"。
16. allowFullText=false 的来源（EPRI/IEC/ISO/ASTM/ICRP 等付费报告）是否被写了"全文结论"：命中即列入 overclaimed_points，要求降级为"仅引编号/摘要"。
17. [live] 标准类来源：标准号、版本年份是否核对现行有效性（须回 std.samr.gov.cn 或发布机构官网）；废止标准必须剔除或替换。
18. 统计类数据（能源/教育/材料性能）：是否回原始统计机构；智库/媒体图表二次引用是否注明"转引自"。
19. 为每条来源标注 `authority`（A1–D2，见 `${SUITE_ROOT}/shared/references/claim_evidence_layer.md` 的 Source Authority）：法规/监管 A1、国际组织/标准组织 A2、国家/行业标准 A3、官方技术报告 B1、原始实验/工程报告 B2、期刊论文 C1、学位论文 C2、厂商资料 D1、二手资料 D2。缺标注视为缺失字段。

输出 JSON，结构如下：

{
  "topic": "{topic}",
  "review_date": "YYYY-MM-DD",
  "evidence_verification_mode": "static|live",
  "overall_assessment": "",
  "source_quality_summary": {
    "A_count": 0,
    "B_count": 0,
    "C_count": 0,
    "high_risk_count": 0
  },
  "suspicious_sources": [
    {
      "source_id": "",
      "problem": "",
      "suggested_action": "delete/downgrade/verify/replace"
    }
  ],
  "overclaimed_points": [
    {
      "source_id": "",
      "overclaimed_text": "",
      "reason": "",
      "safer_expression": ""
    }
  ],
  "missing_fields": [
    {
      "source_id": "",
      "missing_items": []
    }
  ],
  "weak_evidence": [
    {
      "source_id": "",
      "weakness": "",
      "how_to_improve": ""
    }
  ],
  "sources_to_prioritize": [],
  "sources_to_avoid_as_core_evidence": [],
  "revised_recommendations": []
}

最后请给出"修订后的资料使用建议"：
1. 哪些资料可作为核心依据？
2. 哪些资料只能作为背景？
3. 哪些资料只能作为线索？
4. 哪些结论必须补充调研后才能写入文档正文？
```

## Agent Assignment

| Stage | Agent | File Output |
|-------|-------|-------------|
| 2. Source Audit | External (DeepSeek/GPT) | 审计 JSON（外部输出）→ 当前 assistant 落盘为 `03_audit_report.md` |

## 外部 API 不可用时的回退（重要）

发送给外部 agent 的**就是上面的 prompt 模板本身**。若当前环境**外部生成 API 不可用**，当前 assistant 本地执行本阶段时回退为：

1. 本地读取 `02_raw_sources.json`，按上述 18 条检查项逐条审查（只审不增补）。
2. 以同一 JSON schema 输出审计结果（含 `evidence_verification_mode`，本地回退默认 static），落盘 `03_audit_report.md`（外部审计 JSON 全文 + 总体评估 + 结论）。
3. 若连本地审查也受限（无可读语料），明确告知用户本阶段受阻，**不要**跳过审计直接放行进入 w3 语料构造。

## Post-Audit: 只落盘审计产物，不创建语料

外部审计后，审查者（r1）只负责产出审计结果，**不创建 `04_validated_sources.json`**（创建生产语料属写作者 w3，违反"审查者只做审查、不做生产"边界）：

1. 收集外部 agent 的审计 JSON。
2. **落盘 `03_audit_report.md`（硬门禁产物，勿跳过）**：内容为外部审计 JSON 全文 + 一段"总体评估"（evidence_points 成熟度级别、需补验证项）+ 结论（可进入 w3 / 需退回 w2 补检索）。
3. 把审计结论结构化交接给写作者 w3：
- 每条来源的处置（`suspicious_sources[].suggested_action`：delete / downgrade / verify / replace）、role 建议、需补字段（`missing_fields`）全部保留在 `03_audit_report.md` 的 JSON 结构内。
- w3 依据 `03_audit_report.md` + `02_raw_sources.json` 生成 `04_validated_sources.json`（见 `evidence-writer/prompts/w3_corpus.md`）：删除 `suggested_action="delete"` 来源、按审计建议降级 role、保留 URL、补 `role`/`access_status`/`url_verified`/`registry_id`/`allow_full_text`/`authority` 字段、证据缺口保留为一级条目。
- 若审计结论为"退回补搜"，不进入 w3，写作者回 w2 补检索后重走本门。
