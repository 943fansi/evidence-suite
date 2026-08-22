# Evidence-Driven Proposal Writer Pro (Shared Asset Library)

> **路径常量（SUITE_ROOT）**：本库与两侧 skill（evidence-writer / evidence-reviewer）的脚本、参考指南、模板引用统一以 `${SUITE_ROOT}` 开头。`${SUITE_ROOT}` 即**套件根目录**（本 `shared/` 的上一级），由 agent 加载 skill 时解析，**不要写死为绝对路径**；`shared/scripts/` 内的脚本也以 `Path(__file__).resolve().parents[2]` 自行定位套件根，无需手工替换。

> ⚠️ **本目录现为共享资产库**：原单流水线 `SKILL.md` 已停用，按「编写 / 审核」职责拆分为两个**相互对抗**的 skill——**`${SUITE_ROOT}/evidence-writer`**（生产：适配/检索/语料/图谱/起草/修订/导出）与 **`${SUITE_ROOT}/evidence-reviewer`**（审查：来源审计/诚实性自评/框架深度门/初稿审查/外部评审/终审门）。本目录仅保留 `scripts/`、`references/`、`templates/` 供两侧按绝对路径调用。下方 Pipeline 概览为历史快照，执行以两个新 skill 的 SKILL.md 为准。

Multi-agent evidence-driven pipeline for drafting, reviewing, and revising source-grounded technical documents — from topic to PDF.

## Pipeline Overview

11-stage pipeline using specialized agents at each stage (sub-steps 3a/3b/3c/4b/7b are folded into their parent stage row, not separate stages):

| Stage | Agent | Output |
|-------|-------|--------|
| 0. Document Adapter | opencode | Selected template + topic_domain |
| 1. Source Collection | External (DeepSeek/GPT) | `02_raw_sources.json` |
| 2. Source Audit | External (DeepSeek/GPT) | Audit report |
| 3. Validated Corpus | opencode | `04_validated_sources.json` + mandatory sub-steps 3a (PDF download → `reference_files/*.pdf`), 3b (access_status validation), 3c (text extraction → `pdf_text/*.txt`) |
| 4. Evidence Map | opencode | `06_evidence_map.json` + mandatory sub-step 4b (Honest Assessment → `07_honest_assessment.md`) |
| 5. Draft | opencode | `08_初稿.md` |
| 6. Self-Review | opencode | `10_review.md` |
| 7. Revision | opencode | `11_定稿.md` + optional sub-step 7b (humanizer prose polish) |
| 8. External Expert Review | External (≥2 parallel) | `12_外部专家意见.md` |
| 9. Expert-Response Revision | opencode | `14_专家修订稿.md` |
| 10. PDF Export | opencode — Bash | `{filename}.pdf` |

## Key Features

- **Multi-Agent Pipeline**: External agents for search/audit/review, opencode for mapping/drafting/revision. Automatic fallback to internal tools when external agents are unavailable.
- **Evidence-Backed Writing**: All claims traceable to specific sources via `[Sx]` markers. PDF text extraction (Stage 3 sub-step 3c) upgrades evidence from search-agent summaries to verified original text.
- **Mermaid Route Diagram First**: Technical route diagram serves as the structural blueprint — 3 key problems + 3 key technologies + 3 structural levels.
- **Proof-Level Markers**: `[Sx]`, `[Gx]`, `[假设]`, `[待内部确认]` with document header legend.
- **Gap-Adjacent Strategy**: When core claims are themselves the research gap, adjacent-domain evidence splicing with transparent claims mapping.
- **Anti-Formulaic Writing**: Problem-driven narrative structure, theory-selection rationales, and forbidden boilerplate detection built into quality heuristics.
- **PDF Export**: Mermaid 图默认 local-first（mermaid-cli `mmdc`），无本地渲染器时回退 mermaid.ink（远程，图内容发送第三方）；`--mermaid-engine local` 可禁止联网。Markdown → PDF via pandoc + Chrome headless with A4-optimized CJK typography.
- **Statistical Charts**: Optional matplotlib chart generation from evidence data (effect sizes, trends, comparisons).
- **Parallel External Reviews**: Run multiple external agents (ChatGPT, 豆包, etc.) for comprehensive expert review.
- **Research-Depth Minimums**: Per-document-type minimum reference counts (proposal ≥15 … PhD ≥60) enforced via `check_citations.py --min-sources`, plus P/T coverage and review-section density checks.
- **Source Routing**: Stage 1 searches are constrained to a curated authoritative-source registry (`references/source_registry.json`, override with a user-maintained master list via `select_sources.py --registry <path>`). `select_sources.py` maps `topic_domain` → categories → per-source `site:` search directives, honors `allowFullText` (metadata-only vs full text), enforces standard-validity checks, and bans `forbidSources` — every validated source carries a `registry_id` for traceability.

## Structure

> 本结构树描述当前**共享库 `shared/`** 的布局（`templates/`、`references/`、`scripts/`）。现行已拆分为 `evidence-writer` / `evidence-reviewer` 两个 skill（各含自己的 `prompts/`），执行以各 skill 的 SKILL.md 为准。

```
shared/
├── README.md                        # This file
├── requirements.txt                 # Python 依赖（按需安装）
│
├── schemas/                          # Manifest 互操作契约 JSON Schema（finalize_draft.py 产出物校验基准）
│   ├── evidence_manifest.schema.json # source-centric（--manifest）契约：schema_version / review_kind / mapping[]
│   └── claim_manifest.schema.json    # claim-centric（--claim-manifest）契约：schema_version / review_kind / claims[]
│
├── templates/                       # 12 document-type templates + index selector
│   ├── index.md                     # Template selector
│   ├── proposal.md
│   ├── thesis_ug.md
│   ├── thesis_ms.md
│   ├── thesis_phd.md
│   ├── report_survey.md
│   ├── report_feasibility.md
│   ├── report_gf.md                 # 中国国防科学技术报告（GF报告）
│   ├── plan_implementation.md      # 项目实施方案（11章工程执行格式）
│   ├── paper_journal.md           # 期刊论文（0引言+GB/T 7714 引用）
│   ├── patent_disclosure.md         # 专利申请技术交底书（发明/实用新型）
│   ├── patent_application.md        # 发明专利申请草案四件套（权利要求书/说明书/摘要）
│   └── whitepaper.md
│
├── references/                      # On-demand reference guides
│   ├── index.md                     # Reference loader index (token budget)
│   ├── anti_marketing_rules.md      # Anti-boilerplate & narrative detection
│   ├── claim_evidence_layer.md      # Claim-evidence separation (5-layer)
│   ├── domain_routing.md            # topic_domain → category → authoritative sources
│   ├── source_registry.json         # Authoritative source list snapshot (select_sources.py reads it)
│   ├── gap_adjacent_strategy.md     # Adjacent-domain evidence splicing
│   ├── significance_writing_guide.md
│   ├── gf_report_format.md        # GF 报告页序/排版/引用格式
│   ├── impl_plan_format.md        # 项目实施方案 11 章结构
│   ├── journal_paper_format.md    # 期刊论文结构与 GB/T 7714 对接
│   ├── thesis_format.md           # 学位论文双封面/分点摘要/章号编号规范
│   ├── patent_writing_guide.md      # 专利交底书七节结构与写法（[Sx] 仅限背景技术）
│   ├── technical_route.md
│   ├── finalize_checklist.md        # 定稿净化清单（[Sx]→[1]..[n]、删图例/附录A/封面占位）
│   ├── workflow.md                  # 历史存档（整体流程与阶段衔接，见头部对照表）
│   └── expert_roles/                # 5 domain-specific expert role definitions
│       ├── index.md
│       ├── ai.md
│       ├── education.md
│       ├── engineering.md
│       ├── medical.md
│       └── social_science.md
│
├── scripts/                         # 14 Python utilities (bash-executed, never loaded)
│   ├── build_references.py          # 机械生成参考文献节（year 空值省略、URL 逐字、--body 原位回填、--style gbt 类型感知 GB/T 条目、title/title_or_name 双字段兼容）
│   ├── finalize_draft.py            # 定稿净化（[Sx]→[1]..[n] 顺序编码、[Gx]→研究局限、删脚手架/附录A/封面占位/内部路径、--check 校验、--style gbt 骨架+映射表）
│   ├── validate_sources.py          # 语料自检（重复 URL/缺字段/可疑域名 bjjcyjy-antpedia-stm-publishing/access_status 空/中文期刊配额）
│   ├── check_framework_depth.py     # 框架深度门（每实质章目标/方法/输入输出/标准依据四要素+篇幅达标）
│   ├── check_citations.py           # Citation closure + URL/title check + --min-sources/--min-chars gates + --academic 数字引文模式
│   ├── select_sources.py            # Stage 1 source routing selector (registry → search directives)
│   ├── fetch_nsfc_report.py         # NSFC 结题报告 fetch (search/decrypt/paged download → PDF/OCR)
│   ├── sample_chart_data.json       # generate_charts.py 示例数据（换题请 --data 提供自己的）
│   ├── download_reference_files.py  # Stage 3 sub-step 3a PDF download
│   ├── extract_pdf_text.py          # Stage 3 sub-step 3c text extraction
│   ├── export_pdf.py                # Stage 10 Mermaid→SVG + MD→PDF（pandoc 缺失时自动降级 python-markdown；学位打印 CSS + URL 断行 + 悬挂缩进）
│   ├── export_docx.py               # Stage 10 MD→DOCX（A4 中文公文/学位排版：黑体标题/宋体小四/1.5 倍行距/首行缩进 2 字符/表格跨页保护）
│   ├── visual_qa.py                 # Stage 10 视觉抽检（Chrome 截图首页/指定章节，交付前目检）
│   ├── generate_charts.py           # Optional: statistical chart generation
│   └── inspect_pipeline.py          # Pipeline diagnostics
```

## Prerequisites

- **本地执行 agent**（当前 assistant）for local pipeline stages
- **External AI agent** (DeepSeek/GPT/Claude) for Stages 1, 2, and 8 (auto-fallback to 本地执行 agent if unavailable)
- **Python 3** with standard library for pipeline scripts
- **Python deps**: `pip install -r requirements.txt`（按需安装；`easyocr`/`PyMuPDF` 较重，见文件内注释）
- **Optional** (Stage 10 PDF export): `pandoc`（Windows: `winget install pandoc` / macOS: `brew install pandoc` / Linux: `apt install pandoc`）+ Chrome/Edge headless。**pandoc 不可用时自动降级 python-markdown**（`pip install markdown`），两条路径共用同一学位打印 CSS（A4、参考文献悬挂缩进、URL 断行）。导出后用 `scripts/visual_qa.py` 截图目检再交付。
- **Optional** (Stage 10 DOCX export): `pip install python-docx`——`scripts/export_docx.py` 输出中文公文/学位排版 Word 文档（标题黑体居中、正文宋体小四+Times 西文、1.5 倍行距、首行缩进 2 字符、表格跨页保护）。
- **NSFC 结题报告** (`fetch_nsfc_report.py`)：⚠️ 逆向门户 API，密钥来自公开浏览器扩展、仅解密公开数据；使用前请确认符合 NSFC 门户条款，接口/密钥可能随时失效。

## License

MIT（见仓库根 `LICENSE`）。
