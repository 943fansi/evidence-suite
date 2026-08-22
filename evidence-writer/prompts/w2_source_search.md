# w2: Source Collection（来源检索，写作者侧 · 全局阶段 1）

Use this prompt format to instruct an external agent (e.g., DeepSeek, ChatGPT, Claude) to perform source collection.

## Prompt Template

```
请联网检索"{topic}"相关资料。

重要要求：
你只负责资料检索、证据整理和 JSON 输出，不要撰写文档正文，不要进行自由发挥。

来源路由约束（Source Routing，强制）：
检索前先运行 `python ${SUITE_ROOT}/shared/scripts/select_sources.py --domain <topic_domain>`（topic_domain 见 ${SUITE_ROOT}/shared/references/domain_routing.md），把输出的 `selected_sources[]` 及其 `search_directive` 作为本轮的**指定权威来源清单**注入：
1. 对每个 selected source，按 `search_directive` 执行 `site:<domain> <query>` 定向检索；命中时该来源的 `id` 记入每条 source 的 `registry_id` 字段。
2. `allowFullText: false` 的来源（如 EPRI/IEC/ISO/ASTM 付费报告、ICRP）仅允许取题录/摘要与文档编号，禁止虚构全文内容。
3. `must_verify_standard_current: true` 的来源，检索到的标准必须先到 std.samr.gov.cn 或发布机构官网核对现行有效性，禁止引用废止标准。
4. 清单外的补充来源允许存在，但须在 `sources[].registry_id` 填 `"supplementary"` 并在 `credibility_reason` 中说明补充理由。
5. 禁止使用 registry 中 `forbidden_and_rules` 列出的 forbidSources（自媒体、非官方转载、百科、AI厂商营销、教育软文等）作为正式引用依据。
6. 预印本（arXiv 等）仅作最新进展参考，须标注提交/版本日期，正式结论引同行评审版本。

反证主动搜索（Counter-Evidence Search，强制）：
对每个关键主张（P1–P3、T1–T3 或 topic 核心论断），除检索支持性证据外，**主动检索反证**——高质量证据检索不只问"有什么支持我"，还要问"有什么可能证明我错"：
1. 支持方检索："{claim}"
2. 反证方检索："{claim} criticism" / "{claim} limitation" / "{claim} contradictory" / "{claim} failed" / "{claim} 质疑" / "{claim} 局限" / "{claim} 反例" / "{claim} 争议" / "{claim} 失效"
3. 命中的反证来源同样进入 `sources[]`，并在 `counter_evidence` 字段标注"反对什么主张 + 严重程度 + 摘要"。
4. 某关键主张**检索不到反证**时，在顶层 `counter_evidence_search` 显式记录"未发现反证"（负结果也是结果，供 w4/r2 诚实性评估用）。

检索目标：
1. 近 5 年高质量综述论文、代表性研究论文、实验研究、应用研究论文。
2. 政府政策、行业规划、监管文件、标准规范、技术指南。
3. 国内外典型应用案例、实践案例。
4. 关键技术、核心方法或工具（如适用：设备、平台、方案提供方）。
5. 可用于文档撰写的政策依据、理论依据、实践依据和需求依据。

资料优先级：
A 类资料（核心依据）：
- 上述来源路由选中的权威来源（registry 命中项优先）
- 政府部门官网
- 监管机构官网
- 国际组织官网
- 国家标准、行业标准、IEC/ISO/IEEE/IAEA 等标准或技术文件
- 论文数据库、出版社官网、期刊官网
- 高校、科研院所、国家实验室官网

B 类资料（技术路线/方法选型/案例依据）：
- 企业/机构官网
- 产品白皮书 / 正式技术手册
- 行业/协会报告

C 类资料（仅作线索或背景）：
- 新闻报道
- 公众号文章
- 会议新闻
- 转载文章
- 商业软文

使用原则：
1. A 类资料可作为核心依据。
2. B 类资料可作为技术路线、方法选型、案例说明依据。
3. C 类资料只能作为线索或背景，不能作为关键结论的唯一依据。
4. 如果找不到原始来源，必须标记为"待核验"。
5. 不得把不确定信息改写成确定事实。
6. 不得编造链接、论文、标准、案例或供应商。

请重点关注以下方面：
1. {topic} 的核心概念、主要理论或方法、应用场景。
2. {topic} 的国内外研究现状。
3. {topic} 的关键挑战或瓶颈。
4. {topic} 在特定应用场景中的约束条件与限制。
5. {topic} 相关的评估与验证方法（与主题相关）。
6. {topic} 相关的标准、规范、政策要求。
7. {topic} 相关工具、方法、平台（如适用）。
8. {topic} 的应用前景与实践价值。
9. {topic} 仍需补充调研的内容。

输出格式：
只输出 JSON，不要输出解释性文字。

JSON 顶层结构：
{
  "topic": "{topic}",
  "data_collection_date": "YYYY-MM-DD",
  "search_scope": [],
  "sources": [],
  "counter_evidence_search": [
    {
      "claim": "",
      "supporting_sources": ["Sx"],
      "contradictory_sources": ["Sy"],
      "none_found": false
    }
  ],
  "evidence_gaps": [],
  "recommended_next_searches": []
}

每条 sources 必须包含：
{
  "source_id": "S1",
   "category": "论文/政策/标准/案例/市场/技术报告/其他（工程类可含供应商）",
  "type": "",
  "title_or_name": "",
  "url": "",
  "year": "",
  "publisher_or_source": "",
  "country_or_region": "",
  "source_level": "A/B/C",
  "is_primary_source": true,
  "access_date": "YYYY-MM-DD",
  "registry_id": "",
  "summary": "",
  "evidence_points": [
    {
      "claim": "",
      "evidence": "",
      "confidence": "high/medium/low",
      "can_be_cited_as": ""
    }
  ],
  "usable_claims": [],
  "claim_limits": [],
  "use_for": [],
  "credibility_reason": "",
  "risk_notes": [],
  "counter_evidence": [
    {
      "against_claim": "",
      "severity": "critical/high/medium",
      "summary": ""
    }
  ]
}

如果是工程/设备/产品类资料（教育/社科/政策类可跳过此节），额外包含：
{
  "products": [],
  "core_specs": [],
  "interfaces_protocols": [],
  "environmental_adaptability": [],
  "certifications_or_standards": [],
  "case_references": [],
  "price_info": "",
  "selection_reason": "",
  "unknowns_to_verify": []
}

特别要求：
1. 每个 source_id 必须唯一，格式为 S1、S2、S3。
2. 每条资料至少给出 2 条 evidence_points。
3. 每条资料必须写 claim_limits，说明该资料不能证明什么。
4. 市场规模资料必须保留机构名称、年份、预测周期、统计口径。
5. 标准规范资料必须写清标准号、发布机构、适用范围。
6. 工程/设备类资料必须写清是否有公开参数、是否有应用案例、是否有报价（教育/社科类该条可忽略）。
7. 最后 evidence_gaps 必须列出当前资料不足的地方。
8. 来源数量下限：返回的 sources 数量不得少于 {min_sources}（开题报告/可行性报告≥15，调研报告/综述≥25，本科≥20，硕士≥40，博士≥60，白皮书≥12，GF报告≥12，实施方案≥12，期刊论文≥15，专利交底书/申请草案≥8）。若检索结果不足，扩大数据库、年限、语言或相邻领域关键词后继续检索，不得以低质量/无关资料凑数。
9. 覆盖度检查：每个关键问题（3 个）与每项关键技术（3 个）都至少要有 1 条对应来源；若某问题/技术无来源，必须在 evidence_gaps 中显式记录。
10. 来源多样性：论文类不得全部来自单一作者/单一课题组/单一期刊；至少覆盖 2 个不同国家或机构；综述与研究型论文并重。
11. 每条 source 的 `registry_id` 必须填写：命中来源路由清单的填清单内 id，清单外的填 "supplementary" 并附理由；不得留空。
12. 允许降级但不可跳过路由：若某权威来源无命中结果，必须将该查询与结果记录到 `recommended_next_searches`，并在 `evidence_gaps` 注明"该权威源无结果，原因待核"。
```

## Agent Assignment

| Stage | Agent | File Output |
|-------|-------|-------------|
| 1. Source Collection | External (DeepSeek/GPT) | `01_{agent}_检索提示词.txt` → `02_raw_sources.json` |

## 外部 API 不可用时的回退（重要）

发送给外部 agent 的**就是上面的 prompt 模板本身**。若当前环境**外部搜索/生成 API 不可用**（无 DeepSeek/GPT 凭据、网络受限），当前 assistant 本地执行本阶段时回退为：

1. 用 **WebSearch + WebFetch**（本地工具）执行上述检索目标与来源路由约束（`registry_id` 命中 / `supplementary` / forbidSources 等规则照常生效）。
2. 检索结果按同一 JSON schema 落盘 `02_raw_sources.json`。
3. 若 WebSearch/WebFetch 也完全不可用，明确告知用户该阶段需要外部 API，**不要**自行编造来源或补齐缺口。

## Usage

1. Read this template
2. Run `python ${SUITE_ROOT}/shared/scripts/select_sources.py --domain <topic_domain>` (from w1 Topic Card) and capture the `selected_sources` + `forbidden_and_rules` blocks
3. Fill `{topic}`, `{min_sources}`, and paste the routing output into the prompt's 来源路由约束 section
4. Send to the chosen external agent
5. Save the agent's output as `02_raw_sources.json`
