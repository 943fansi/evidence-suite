# Workflow Reference（历史存档）

> ⚠️ **历史存档文件**。本文使用**旧版 Stage 1–12 编号**（含双 Stage 8/9、R2 第二轮体系），与现行 SKILL.md 的 **0–10 整数阶段**无直接对应关系。
>
> **现行编号（权威，见 SKILL.md）**：0 文档适配 → 1 来源检索 → 2 来源审计 → 3 验证语料（含 3a/3b/3c）→ 4 证据图谱（含 4b 诚实性自评）→ 5 起草 → 6 自评 → 7 修订（含 7b humanizer）→ 8 外部评审 → 9 专家修订 → 10 PDF 导出。
>
> 本文仅作**概念/字段参考**（如 evidence_map schema、route diagram 规范、quality heuristics），**不要**据此执行阶段或校验文件名。执行与门禁一律以 SKILL.md 与 `inspect_pipeline.py` 为准。
>
> **路径约定**：文中路径示例以 `${SUITE_ROOT}` 开头，即**套件根目录**（`shared/` 的上一级），由 agent 加载 skill 时解析；脚本以 `Path(__file__).resolve().parents[2]` 自行定位，无需手工替换。
>
> ⚠️ **字段名冲突警示**：本文档 `Stage 4` 的旧 schema 用 `sections[]`（含 `needed_gap` 等字段）；现行权威 schema 见 `${SUITE_ROOT}/evidence-writer/references/w4_evidence_map.md`，用 `evidence_map[]`（含 `claim_decomposition`、`counter_evidence`、`claim_type`、`confidence_assessment`）。**生成/校验 `06_evidence_map.json` 一律以现行 prompt 的字段为准**，勿按本文档写 `sections[]`。

### 旧编号 → 现行编号对照（仅概念参考）

| 本文旧阶段 | 现行阶段 | 说明 |
|-----------|---------|------|
| Stage 1 Source Collection | 1 来源检索 | 概念对应 |
| Stage 2 Source Audit | 2 来源审计 | 概念对应；旧输出 `03_source_audit.md` 现为 `03_audit_report.md` |
| Stage 3 Validated Corpus | 3 验证语料 | 概念对应；旧 `04_validated_sources.json` 不变 |
| Stage 4 Evidence Map | 4 证据图谱 | 概念对应；旧 `06_evidence_map.json` 不变 |
| Stage 5 Route Diagram | 4/5 之间 | 并入阶段 4 图谱流程 |
| Stage 6 Draft | 5 起草 | 旧输出 `08_draft.md` 现为 `08_初稿.md` |
| Stage 7 Self-Review | 6 自评 | 概念对应；旧 `10_review.md` 不变 |
| Stage 8 Targeted Gap Search | —（已废弃） | 旧 R2 第二轮体系，现行单轮 |
| Stage 9–12 Second-Round… | —（已废弃） | 旧 R2 体系 |
| 文末 Stage 8 External Review | 8 外部评审 | 概念对应；旧 `12_external_review.md` 现为 `12_外部专家意见.md` |
| 文末 Stage 9 Expert Revision | 9 专家修订 | 概念对应；旧 `14_expert_revised.md` 现为 `14_专家修订稿.md` |

Use this reference only when the user wants historical field/schema detail. For execution, follow SKILL.md.

## Stage 1: Source Collection

Goal: create `01_source_search_prompt.txt` and `02_raw_sources.json`.

Ask or infer:
- topic
- date
- source scope
- priority source classes
- forbidden source classes

Search prompt (`01_source_search_prompt.txt`) should capture: topic, date, source scope, priority classes, forbidden classes, search queries executed, and expected JSON output fields.

Raw sources JSON (`02_raw_sources.json`):
- `topic`
- `data_collection_date`
- `search_scope[]`
- `sources[]`
- `evidence_gaps[]`
- `recommended_next_searches[]`

Each source: `source_id`, `category`, `type`, `title_or_name`, `url` (prefer direct PDF links), `year`, `publisher_or_source`, `country_or_region`, `source_level` (A/B/C), `is_primary_source`, `access_date`, `summary`, `evidence_points[]`, `usable_claims[]`, `claim_limits[]`, `claim_strength[]` (background/method/requirement/metric/budget/supplier/cannot_support_quantitative_claim), `use_for[]`, `credibility_reason`, `risk_notes[]`.

For suppliers also: `products[]`, `core_specs[]`, `interfaces_protocols[]`, `environmental_adaptability[]`, `certifications_or_standards[]`, `case_references[]`, `price_info`, `selection_reason`, `unknowns_to_verify[]`.

## Stage 2: Source Audit

Output: `03_source_audit.md`.

Review only the corpus. Do not add sources.

Check:
- URL specificity, primary-source status, and reliability (third-party hosting = `needs_verification`)
- Source level correctness
- Unsupported summaries or usable claims
- Missing DOI, standard number, publisher, year, certification, or quote scope
- News, social posts, B2B pages, and marketing material used as core evidence
- Market data without original report scope
- Supplier parameters used without formal specs or third-party validation

Default source-role decisions:
- Official regulations, standards texts, IAEA publications, peer-reviewed full-text papers → can be core
- Third-party standards pages → `needs_verification` until official text obtained
- News, press releases, brochures, social posts, copied slide decks → `lead_only`
- Supplier pages → `lead_only` for candidate capabilities only
- Abstract-only papers → may support research existence, not detailed methods or results
- Patents → conceptual direction only, not validated technology
- Reports >20 years old with evolved materials/practices → `context_only`

Output:
- Overall assessment
- Source quality summary table
- Individual source audit with assessment and action
- Sources requiring action (downgrade role, downgrade level, URL reliability issues)
- Overclaimed points with safer expression
- Missing fields
- Weak evidence with mitigation
- Sources to prioritize (highest evidentiary value)
- Sources to avoid as core evidence
- Revised recommendations

## Stage 3: Validated Corpus

Output: `04_validated_sources.json`.

Rules:
- Remove unusable or duplicate sources
- Downgrade weak sources (role: core/supporting/context_only/lead_only/needs_verification)
- Preserve uncertainty explicitly
- Keep evidence gaps as first-class items
- Keep source IDs stable
- Preserve the `url` field from raw sources
- Add per-source: `role`, `access_status` (confirmed/web_accessible/unavailable), `url_verified`, `use_for[]`, `claim_strength[]`

> `access_status` 词表以 `${SUITE_ROOT}/evidence-writer/references/w3_corpus.md` 为准（证据用途取向）：`confirmed`（PDF 已下载）/ `web_accessible`（URL 存在未下载）/ `unavailable`（下载失败或非 PDF）。旧语料中可能出现的 `full_text/abstract_only/landing_page_only`、`open_full_text/open_page/metadata_only/transcription` 等值为历史遗留，新产出一律使用三值词表。
- Add top-level: `validated_source_count`, `sources_by_role` summary

## Stage 4: Evidence Map

Output: `06_evidence_map.json`. Create BEFORE drafting.

Top-level fields:
- `topic`, `target_document`, `audience`, `mapping_date`
- `sections[]` — per section: `section`, `claim_to_write`, `supporting_sources[]`, `source_strength` (strong/medium/weak), `allowed_expression`, `writing_boundary`, `need_more_research`
- `key_problems[]` — each: problem statement, `supporting_sources[]`. Exactly 3.
- `key_technologies[]` — each: technology name, `supporting_sources[]`. Exactly 3.
- `unsupported_but_needed_claims[]` — each: `claim`, `needed_gap`, `action`
- `source_usage_rules[]` — per-rule: source ID range, usage constraint

### Route-Driven Evidence Map

When a technical route diagram will be included in the final draft:

1. Create a preliminary evidence map first (identify claims, sources, tentative sections).
2. Derive the route diagram (key problems + key technologies + layer structure) from the evidence map, following `references/technical_route.md`.
3. Restructure the evidence map sections to align with the route layers. Bidirectional refinement — route is evidence-grounded, evidence map becomes route-structured.
4. Map each route layer to document sections (see technical_route.md Layer-Section Mapping).
5. Use route's key problem labels as the document's primary problem identifiers. Do not add extra "key problems" in the evidence map not in the route.
6. Use route's key technology labels as the document's primary methodology identifiers.
7. Each key_problem and key_technology entry must have supporting source IDs.

## Stage 5: Route Diagram Generation

Derive from `06_evidence_map.json`. Read `references/technical_route.md` for full instructions.

Default: 3 key problems, 3 key technologies, 3 structural levels, `flowchart TD`, subgraph for each level.

Route diagram is NOT optional when the document type expects a route diagram or when key_problems/key_technologies exist in the evidence map. It is the structural blueprint.

## Stage 6: Draft

Output: `08_draft.md`. Draft from `04_validated_sources.json` and `06_evidence_map.json` only.

**Structure**: Route diagram FIRST (with post-diagram explanation), then document body.

**Header**: Include evidence-use legend explaining `[S1]`, `[G1]`, `[假设]`, `[待内部确认]`.

**Body sections** (document-type-dependent; defaulting to proposal template):
// 章节结构由 Stage 0 从 templates/ 按 {target_document} 匹配。
// 以下为 proposal 模板的默认章节列表，实际执行时以选定的模板文件为准。
1. §技术路线图 — Mermaid diagram + post-diagram source/gap mapping
2. §1 背景与意义 — policy context, real-world needs, existing method limitations, key problems
3. §2 国内外研究现状 — key mechanisms, current methods, standards framework, domestic gaps
4. §3 研究目标与内容 — overall objective + 4-5 content areas
5. §4 技术路线与方法 — detailed methods; reference route diagram
6. §5 关键问题与解决方案 — table: P1-P3 + auxiliary problems
7. §6 预期成果 — deliverables + metric table
8. §7 进度安排 — timeline table with phases, tasks, milestones
9. §8 研究基础与条件 — team, resources, materials request list
10. §9 风险评估与应对 — risk table
11. §10 经费预算 — cost drivers only (education/social-science docs may skip)
12. §11 需进一步研究的事项 — research gaps
13. 参考文献 — full reference list with [Sx] IDs
14. 附录A：证据缺口清单 — gap table

**Non-proposal templates**: thesis, survey, feasibility, whitepaper templates in `templates/` directory. Stage 0 selects the appropriate one.

**Evidence markers**: `[S1]` for citations, `[G1]` for gaps, `[假设]` for assumptions, `[待内部确认]` for items needing user input.

**Avoid**: generic "public information shows" without citations; hard commitments from single papers; exact budget/timeline/test values without source or user-provided assumptions.

**Route-Body Consistency** (see `references/technical_route.md` for details):
- Terminology lock: route node labels = body headings
- Count lock: N key problems + M technologies in route = same in body §5
- Layer-section lock: each route layer → corresponding body section
- Gap visibility: `待补证`/`待验证` in route → gap entry in body + internal materials list
- Citation locality: citations in body prose, not in route nodes

## Stage 7: Self-Review (+ Revised Self-Review Gate)

Output: `10_review.md`.

Check:
- Citation closure: all [Sx] in body found in reference list, all references cited in body
- Unsupported facts without citations
- Weak evidence supporting strong conclusions
- Case data copied as project commitment
- Supplier selected too early
- Budget without quotes
- Metrics without verification method
- Safety-critical claims phrased absolutely
- Gaps not added to Appendix A
- **Route-body consistency**:
  - Route node labels match body headings exactly
  - Key problem count matches between route and body
  - Key technology count matches between route and body
  - Every `待补证`/`待验证` in route has gap entry in body
  - No body section introduces a "key" problem/technology absent from route

Also check (revised review gate):
- Second-round sources (if any) used within allowed roles
- Lead-only and needs-verification sources excluded from core claims
- New tables contain no unsupported metrics
- Remaining gaps visible and actionable
- Document matches intended genre and audience

Recommend one of: can finalize / minor revision then finalize / targeted gap search required / major revision then re-review.

## Stage 8: Targeted Gap Search

When self-review exposes hard gaps blocking credible revision. Do not repeat broad discovery.

Output: `11_second_round_source_search_prompt.txt` → `12_round2_raw_sources.json`.

Focus the prompt on:
- Exact unsupported claims or weak sections
- Priority source classes
- Forbidden or limited source classes
- Specific geographic, regulatory, standards, time, or technology boundaries

Second-round source IDs: `R2-S1`, gap IDs: `R2-G1`.
Each second-round source: `evidence_role` (core/supporting/context_only/lead_only/needs_verification), `access_status`, `relevance` flags, `usable_claims[]`, `limitations[]`, `recommended_use_in_revision[]`.

## Stage 9: Second-Round Audit and Validation

Output: `14_round2_source_audit.md` → `15_round2_validated_sources.json`.

Decide for each: keep_core / keep_supporting / context_only / lead_only / needs_verification / downgrade / drop.
Also: gap closure assessment, sources to promote/downgrade, revision rules, high-risk sources, remaining gaps.

## Stage 10: Revision Plan

Output: `16_revision_plan.md`.

Include: revision objective, evidence use rules, section-by-section plan, new tables/artifacts needed, expressions to downgrade, remaining gaps.

Common improvements: add terminology/scope/boundary section; add/revise route diagram; add user/internal materials request list; replace vague goals with deliverable metrics; replace precise budget with cost-driver logic; replace "prediction model" with "candidate model and validation framework"; separate prototype from production system.

## Stage 11: Revision

Output: `17_revised_draft.md`.

Actions: delete unsupported claims; downgrade to cautious phrasing; move evidence-poor content into research gaps; split targets into benchmark/proposed/validation-needed; add closure notes when reviewer comments cannot be satisfied without new evidence; preserve citation closure; add revision change summary.

## Stage 12: Revised Self-Review Gate

Output: `18_revised_review.md` (if major revision).

Check: second-round sources used within allowed roles; lead-only/needs-verification sources out of core; new tables without unsupported metrics; remaining gaps visible and actionable; document matches genre and audience.

## Stage 8: External Expert Review

Output: `12_外部专家意见.md`.

Multiple reviewer lenses: domain technical expert, engineering application expert, standards/compliance expert, project management expert, budget/equipment expert.

Output: decision and score table, main strengths, main problems with severity, chapter-by-chapter comments, evidence-chain review, quantitative metrics review, equipment and budget review, top risks and fallback routes, must-supplement materials, safer project positioning, final expert opinion.

## Stage 9: Expert-Response Revision

Output: `14_专家修订稿.md`.

Revise within evidence boundaries. Add Expert Response Table:

| Reviewer Comment Type | Comment Summary | Handling | Location Changed | Note |
|----------------------|----------------|----------|-----------------|------|

Handling values: modified / downgraded wording / moved to supplementary research list / insufficient evidence, not added to body / retained with reason.

## Reference File Archive

When user asks to preserve cited public resources:

```bash
python scripts/download_reference_files.py <workspace>/04_validated_sources.json -o <workspace>/reference_files --timeout 30 --sleep 1
```

Rules:
- Download only public PDFs confirmed by URL or response content
- Name files with citation IDs: `S1_Title.pdf`, `R2-S1_Title.pdf`
- Generate `manifest.json` and `manifest.csv`
- Skip landing pages, paywalled pages, standards pages without downloadable PDFs
- Keep supplier, news, and `lead_only` sources out of archive unless `--include-all`
- Never bypass access controls, paywalls, robots, or license restrictions

## Technical Route Diagram

Use `references/technical_route.md` when user asks for: 技术路线图, 项目技术路线, Mermaid 流程图, implementation route, technology roadmap.

Default constraints: 3 key problems, 3 key technologies, maximum 3 structural levels, `flowchart TD`, subgraphs for layers, short implementable node labels, evidence gaps as `待补证`/`待验证`.

Do not draw a route that promises unsupported metrics, mature products, certifications, procurement choices, or regulatory compliance.

## Quality Heuristics

A strong output usually has:
- Few or no lead_only/context_only sources in core claims
- Clear claim limits for each source
- Evidence gaps visible in the final document (Appendix A)
- Separated mature and exploratory scenarios
- No precise procurement or certification claims without formal documents
- A response table after expert revision
- An internal/user materials request list when local data is necessary
- Visible downgrade from unsupported certainty to candidate/prototype/validation-needed
- A revision plan before major rewrites
- Route diagram at document top with post-diagram evidence mapping
- Consistent terminology between route diagram and body
- All evidence markers explained in header legend
