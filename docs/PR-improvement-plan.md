# evidence-suite 改进 PR 提纲

> 依据对 evidence-suite 9 维度审查生成，已对照仓库实际代码校准。
> 每个 PR 给出：目标 / 涉及文件 / 关键改动 / 验收标准 / 工作量。
> 建议合并顺序见文末「依赖与排序」。

**审查校准说明（改动前必须读）**：
- `schema_version` 当前是 schema `const`，且 `validate_manifest.py:82` 对版本不匹配**硬报错**；做版本迁移 PR 前需先改为「版本协商 + 告警」，否则旧 manifest 全部无法解析。
- SSRF 逐跳重定向防护**已实现**（`download_reference_files.py:101-107` `redirect_request` 递归校验），P0 网络项不再重复实现，聚焦「域名黑名单 + 审计日志 + 补测试」。
- `suspect_domains` 已有机制（`rules.yaml`），扩展为可域名后缀黑名单即可，无需新配置体系。

---

## P0 · 高收益低工作量

### PR-01 风险披露强化 + 报告携带 review_kind

- **目标**：让「评审类型、套件能力边界」在交付物层面可见，不只藏在 JSON。
- **文件**：`README.md`、`shared/scripts/export_pdf.py`、`shared/scripts/export_docx.py`、`shared/scripts/finalize_draft.py`、`shared/templates/*`
- **改动**：
  1. PDF/DOCX 页眉或脚注输出 `review_kind`（ai-internal / ai-cross-model / human-expert）与 `verification_mode`，阅读者一眼可知评审性质。
  2. README 顶部「能力边界」横幅：套件只校验「拿到的来源文本是否支持论断」，**不检测来源本身造假**；`quote_hash`/页码因 PDF 版本、扫描件、网页改版会失效；反证检索找不到 ≠ 论断正确。
  3. manifest 与导出报告同步落 `boundary_notice` 字段。
- **验收**：导出一份 PDF，首页可见 review_kind；README 增三行边界声明。
- **工作量**：S（~1d）

### PR-02 统一顶层 CLI 入口

- **目标**：把分散脚本封装为 `evidence-suite` 子命令，降低集成门槛。
- **文件**：新增 `pyproject.toml`、`shared/scripts/__main__.py`（或 `evidence_suite/cli.py`）、`README.md`
- **改动**：console script `evidence-suite`，子命令代理现有脚本，不重复实现逻辑：
  ```bash
  evidence-suite review input.md --profile general_tech --manifest out/manifest.json
  evidence-suite sufficiency out/manifest.json --review-mode balanced
  evidence-suite export pdf out/manifest.json --output report.pdf
  evidence-suite export html out/manifest.json        # 依赖 PR-15
  evidence-suite validate out/manifest.json
  evidence-suite probe                              # 代理 probe_capabilities.py
  ```
- **验收**：`pip install -e .` 后各子命令与脚本行为一致；`run_tests.py` 通过。
- **工作量**：M（~2d）

### PR-03 真实端到端示例（L3 全链路）

- **目标**：当前 `examples/quickstart` 仅演示最小闭环，缺真实业务样例。
- **文件**：`examples/e2e/run_e2e.ps1`、`run_e2e.sh`、`examples/e2e/input_draft.md`（模拟技术调研报告草稿）、`examples/e2e/sources.json`、`examples/e2e/expected/`、`README.md`
- **改动**：一份草稿一键跑通「草稿输入 → 提取 Claim → 证据校验 → 红队审查 → 导出 PDF/DOCX + manifest 五件套」，产出与 expected/ 对比。
- **验收**：Windows/Linux 各跑通一次，输出 manifest 过 `validate_manifest.py`。
- **工作量**：M（~2d）

### PR-04 网络层加固（域名黑名单 + 审计日志 + 测试补齐）

- **目标**：SSRF 逐跳防护已有，补域名维度与可追溯日志。
- **文件**：`shared/scripts/download_reference_files.py`、`shared/config/rules.yaml`、`SECURITY.md`、`THREAT_MODEL.md`、`tests/run_tests.py`
- **改动**：
  1. `rules.yaml` 新增 `suspect_domain_suffixes`（如 `.ru`、已知跳转站），`url_allowed()` 在 IP 校验之外再做域名后缀校验。
  2. 新增可选 `--audit-log <path>`：记录全部 HTTP 请求、下载来源、被拒请求（含原因 code），输出 `audit_log.json`。
  3. 补测试：域名黑名单、审计日志字段完整性、302 跳转到私网（现有防护的回归）。
- **验收**：`tests/run_tests.py` 全绿；伪造一个恶意域名能被子命令拒绝并在审计日志留痕。
- **工作量**：S–M（~1.5d）

### PR-05 术语速查表

- **目标**：`claim_class` 等术语分散在 `claim_evidence_layer.md`，新用户学习成本高。
- **文件**：新增 `shared/references/glossary.md`、`README.md`
- **改动**：集中整理 `claim_class`（E/M/N/L/D/C/U/J）、`support_level`、`evidence_status`、`risk`（R0–R4）、`authority`（A1–D2）、`freshness`，每项含含义 / 取值 / 适用场景 / 反例；README「证据模型」处链接。
- **验收**：单页可查全部枚举。
- **工作量**：S（~0.5d）

---

## P1 · 中等工作量

### PR-06 可 pip 安装的 core 包

- **目标**：`pip install evidence-suite-core` 即可集成，不必 clone 仓库。
- **文件**：`pyproject.toml`、`shared/` 打包（`shared/schemas/`、`shared/config/`、`shared/templates/` 作为 package data）、`README.md`、`CHANGELOG.md`
- **改动**：核心脚本 + schema + 规则配置打包；skill 提示、示例作为独立资源包（`evidence-suite-skills`）或仓库内可选目录；完整 git 仓库保留用于二次开发。
- **验收**：干净 venv 中 `pip install .` 后 `evidence-suite --help` 可用；CI 加一步安装验证。
- **工作量**：M（~3d）

### PR-07 Docker Compose 开箱即用

- **目标**：当前仅 `docker/Dockerfile` + README，无开箱 compose。
- **文件**：`docker/docker-compose.yml`、`docker/README.md`、`docker/Dockerfile`
- **改动**：预装 pandoc / chrome / mermaid-cli / pdfplumber；`volumes` 挂载本地工作目录；`--offline` 断网模式（校验脚本不联网）；补充 Windows WSL / PowerShell 已知坑点说明。
- **验收**：`docker compose up` 后能直接跑 PR-03 的 e2e 示例。
- **工作量**：M（~2d）

### PR-08 文档导航 + 配置参考 + Agent 集成指南

- **目标**：docs 缺结构化导航，`rules.yaml` 无字段级文档，SKILL.md 对人不友好。
- **文件**：新增 `docs/index.md`、`docs/configuration.md`、`docs/agent-integration.md`、`docs/human-guide.md`；`README.md` 链接改造
- **改动**：
  1. `docs/index.md` 分栏：快速开始 / 概念术语（→ PR-05）/ 使用模式 L0–L4 / 配置参考 / Agent 集成 / 安全部署 / 评测 / 贡献。
  2. `docs/configuration.md`：为 `rules.yaml` 每个字段写含义、取值、默认值、风险影响、覆盖优先级（1–4 层）。
  3. `docs/agent-integration.md`：以 Claude Code / OpenCode 为例的完整接入步骤（加载 skill、调用 suite 脚本、消费 manifest）。
  4. `docs/human-guide.md`：SKILL.md 的人类可读版，说明 writer/reviewer 角色与 w1–w9 / r1–r5 每步做什么。
- **验收**：新用户按 docs/index.md 可零前置知识走完 L0 demo。
- **工作量**：M（~3d）

### PR-09 Manifest 版本迁移与兼容告警

- **目标**：schema 演进后旧 manifest 仍可解析。
- **文件**：新增 `shared/scripts/migrate_manifest.py`、`shared/scripts/validate_manifest.py`、`shared/schemas/*.schema.json`、`tests/run_tests.py`
- **改动**：
  1. schema `schema_version` 由 `const` 改为 `enum` + `compatibility_notes` 字段，记录兼容的 suite 版本区间与废弃字段表。
  2. `validate_manifest.py`：版本低于当前 → 提示运行迁移脚本；命中废弃字段 → 告警而非硬报错。
  3. `migrate_manifest.py`：旧版本向上迁移，迁移路径可注册（如 0.1.0 → 0.2.0）。
- **验收**：构造 0.1.0 旧 manifest，迁移后新版校验通过；废弃字段只告警不阻断。
- **工作量**：M（~2d）

### PR-10 Locator 健壮性（质量分级 + 归一化哈希）

- **目标**：PDF 版本 / 扫描件 / 排版变化导致 quote_hash 与页码漂移。
- **文件**：`shared/scripts/extract_pdf_text.py`、`shared/scripts/audit_provenance.py`、`shared/scripts/validate_manifest.py`、`shared/schemas/*.schema.json`、`tests/run_tests.py`
- **改动**：
  1. 区分原生可抽取文本 vs 扫描 PDF：扫描件允许 `locator` 降级为章节标题，`quote_hash: null`，并新增 `locator_quality: high/medium/low`。
  2. `quote_hash` 改为对原文片段**归一化后哈希**（折叠空白、统一换行），缓解排版差异导致的失效。
- **验收**：同一原文的不同空白排版得到相同 quote_hash；扫描 PDF 路径不再强制要求页码。
- **工作量**：M（~3d）

### PR-11 eval 输出机器可读 JSON

- **目标**：`eval/run_eval.py` 仅输出 markdown，不便批量实验。
- **文件**：`eval/run_eval.py`、`eval/README.md`、`.github/workflows/ci.yml`
- **改动**：默认追加 `eval/report.json`：每条用例 pass/fail、证据得分、风险、阻断情况、耗时；markdown 报告由 JSON 渲染。
- **验收**：CI 在 report.json 上做最小阈值断言（如 P0 用例零回归）。
- **工作量**：S–M（~1.5d）

### PR-12 用户友好错误 + 依赖矩阵

- **目标**：脚本报错面向内部调试，缺使用者排错指引。
- **文件**：`shared/scripts/*.py`（错误出口收敛）、`shared/scripts/probe_capabilities.py`、`README.md`
- **改动**：错误分类（配置错误 / 输入文档错误 / 来源下载失败 / schema 校验失败），每类给简短排错提示并指向文档章节，`--debug` 才输出完整堆栈；README 增最小/完整依赖矩阵表。
- **验收**：对每种错误类制造一次故障，均得到人类可读提示。
- **工作量**：M（~2d）

---

## P2 · 中长期

### PR-13 反证阶段落地（可配置开关）

- **目标**：反证从路线图变为可配置能力。
- **文件**：`shared/config/rules.yaml`、新增 `shared/scripts/check_counter_evidence.py`、`shared/scripts/check_evidence_sufficiency.py`、`evidence-writer/SKILL.md`、`evidence-reviewer/SKILL.md`
- **改动**：R3/R4 默认强制反证检索；配置项控制「未找到反证时告警 / 阻断」；manifest 增 `counter_evidence` 区块。
- **验收**：一条无公开反证的高险论断按配置产出告警或阻断。
- **工作量**：L（~1w）

### PR-14 网页快照归档 + 来源缓存

- **目标**：网页改版/链接失效后证据不可复现；重复运行重复下载。
- **文件**：`shared/scripts/download_reference_files.py`、`shared/schemas/*.schema.json`、`shared/config/rules.yaml`
- **改动**：可选集成网页归档（如 wayback），manifest 保存 `archive_snapshot_url`；来源缓存目录（按 URL+内容哈希），重复运行命中缓存。
- **工作量**：L（~1w）

### PR-15 HTML 导出器

- **目标**：当前仅 PDF/DOCX 排版导出，Web 场景受限。
- **文件**：新增 `shared/scripts/export_html.py`、`shared/templates/`、CLI（PR-02 挂子命令）
- **改动**：HTML 内嵌证据元数据，正文 `[Sx]` 可点击查看证据详情 / locator / confidence。
- **工作量**：M–L（~4d）

### PR-16 并行 Claim 校验

- **目标**：长文档上百条 Claim 串行慢。
- **文件**：`shared/scripts/check_evidence_sufficiency.py`
- **改动**：`--parallel N` 并发校验独立 Claim，保持增量校验语义。
- **工作量**：M（~2d）

### PR-17 公开 benchmark 数据集 + 基线指标

- **目标**：`eval/golden` 无法被外部对比复现。
- **文件**：`eval/golden/*` 公开子集、新增 `benchmarks/README.md`、`eval/README.md`
- **改动**：开源部分 golden 用例（标注哪些需人工/第二模型评审）；配合 PR-11 给出基线指标（如「L3 下 reviewer 拦截幻觉 Claim 的比例」）。
- **工作量**：L（~1w+）

### PR-18 多语言与海外标准适配

- **目标**：当前面向中文技术文档，英文/海外标准适配不足。
- **文件**：`shared/references/claim_evidence_layer.md`、`shared/config/source_ranking.yaml`、locator/引用解析脚本
- **改动**：locator 支持英文引用习惯（DOI/页码/URL），authority A1–D2 增加海外标准分级说明。
- **工作量**：L（~1w+）

---

## 开源治理

### PR-19 CONTRIBUTING 增强 + 模板

- **目标**：PR/issue 流程化。
- **文件**：新增 `.github/PULL_REQUEST_TEMPLATE.md`、`.github/ISSUE_TEMPLATE/{bug,feature,eval-case}.yml`；`CONTRIBUTING.md`
- **改动**：PR 清单自动勾选回归测试、manifest schema 校验、changelog 更新；issue 三类模板。
- **工作量**：S（~0.5d）

### PR-20 Roadmap 独立文件

- **目标**：迭代计划从 README 底部移到 `docs/roadmap.md`。
- **文件**：新增 `docs/roadmap.md`、`README.md`
- **改动**：里程碑 + 版本计划表，标注本提纲各 PR 归属里程碑。
- **工作量**：S（~0.5d）

---

## 依赖与建议合并顺序

| 批次 | PR 集合 | 理由 |
|------|---------|------|
| 第一批（独立、快赢） | PR-01 / PR-05 / PR-19 / PR-20 | 纯文档 + 交付物标注，零冲突 |
| 第二批（工程骨架） | PR-02 / PR-03 / PR-12 | CLI 是后续所有集成的底座，e2e 是验证口径 |
| 第三批（安全与兼容） | PR-04 / PR-09 / PR-10 / PR-11 | 网络/契约/校验侧，可并行 |
| 第四批（可分发） | PR-06 / PR-07 / PR-08 | 依赖 PR-02 的 CLI 定义 |
| 第五批（长期） | PR-13 → PR-18（按序） | 反证优先，其余彼此独立 |

**关键前置**：PR-09 必须先改 `schema_version` 的 `const` 语义；PR-06 依赖 PR-02 的入口定义；PR-15 依赖 PR-02 的 `export html` 子命令占位。
