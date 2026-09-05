# evidence-suite 路线图（Roadmap）

> 版本计划与里程碑。PR 编号对应 `docs/PR-improvement-plan.md` 的改进提纲；
> 已落地项在标题打 ✅。

## 里程碑

| 里程碑 | 目标 | 关键 PR | 状态 |
|--------|------|---------|------|
| M1 交付可信度 | 交付物级风险披露 + 统一 CLI + 真实 e2e | PR-01 / PR-02 / PR-03 / PR-05 / PR-19 / PR-20 | ✅ 部分完成（PR-01/02/05/19/20 已落地，PR-03 e2e 待补） |
| M2 工程骨架 | pip 可安装、Docker 开箱即用、文档导航 | PR-06 / PR-07 / PR-08 / PR-12 | 待启动 |
| M3 契约与安全 | manifest 版本兼容、locator 健壮性、网络加固、评测可机器读 | PR-04 / PR-09 / PR-10 / PR-11 | ✅ 部分完成（PR-04/09/10/11 已落地） |
| M4 反证与复现 | 反证落地、网页快照、来源缓存、HTML 导出 | PR-13 / PR-14 / PR-15 / PR-16 | 待启动 |
| M5 生态与基准 | 公开 benchmark、多语言适配 | PR-17 / PR-18 | 待启动 |

## 已完成

- ✅ **PR-01 风险披露强化**（M1）：`evidence_boundary.py` 集中能力边界声明；manifest 落
  `boundary_notice`；`export_pdf.py --manifest` 页脚 / `export_docx.py --manifest` 文末
  标注 `review_kind` 与边界声明；README 顶部「能力边界」横幅。
- ✅ **PR-02 统一 CLI**（M1）：`shared/scripts/evidence_suite.py` 子命令封装全部脚本；
  `pyproject.toml` 注册 console script（`evidence-suite`）。
- ✅ **PR-04 网络加固**（M3）：`download_reference_files.py` 域名后缀黑名单
  （`rules.yaml suspect_domain_suffixes`，DNS 前匹配）+ `--audit-log` 机器可读审计日志。
- ✅ **PR-05 术语速查**（M1）：`shared/references/glossary.md` 集中枚举取值，README 链接。
- ✅ **PR-09 manifest 版本兼容**（M3）：`validate_manifest.py` 旧版本仅告警 +
  `migrate_manifest.py` 注册式幂等迁移（0.1.0→0.2.0 派生 relation + 默认 review_independence）。
- ✅ **PR-10 locator 健壮性**（M3）：`locator_quality: high/medium/low` 枚举校验；
  `evidence_boundary.py` 提供 `normalize_quote` / `quote_sha256`（排版漂移不影响哈希）；
  schema 允许 `quote_hash: null`（扫描件降级章节级定位）。
- ✅ **PR-11 eval 机器可读**（M3）：`eval/run_eval.py` 输出 `eval/report.json`。
- ✅ **PR-19 贡献模板**（M1）：`.github/PULL_REQUEST_TEMPLATE.md` + issue 三类模板。
- ✅ **PR-20 Roadmap 独立文件**（M1）：本文档。

## 待办（按优先级）

### P1 · 中等工作量

- [ ] **PR-03 真实端到端示例**：模拟技术调研报告草稿 → L3 全链路一键脚本 → PDF/DOCX + provenance 五件套。
- [ ] **PR-06 可 pip 安装 core 包**：`pip install evidence-suite-core`；skill/示例作为可选资源包。
- [ ] **PR-07 Docker Compose 开箱即用**：预装 pandoc/chrome/mermaid-cli，挂载工作目录，断网模式。
- [ ] **PR-08 文档导航 + 配置参考 + Agent 集成指南**：`docs/index.md` / `configuration.md` / `agent-integration.md` / SKILL 人类可读版。
- [ ] **PR-12 用户友好错误 + 依赖矩阵**：错误分类与排错提示、`--debug` 堆栈、最小/完整依赖表。

### P2 · 中长期

- [ ] **PR-13 反证阶段落地**：R3/R4 默认强制反证检索；「未找到反证」告警/阻断可配置。
- [ ] **PR-14 网页快照归档 + 来源缓存**：wayback 快照链接入 manifest；来源下载/解析缓存。
- [ ] **PR-15 HTML 导出器**：内嵌证据元数据，正文 `[Sx]` 点击查看证据详情。
- [ ] **PR-16 并行 Claim 校验**：`--parallel N` 并发校验独立 claim。
- [ ] **PR-17 公开 benchmark 数据集 + 基线指标**：开源部分 golden 用例，标注人工评审项。
- [ ] **PR-18 多语言与海外标准适配**：英文 locator/DOI、authority 海外标准分级。

## 版本迭代计划

- **0.2.x**：契约/安全/工程骨架（M1–M3 收尾，含 PR-03/06/07/08/12）
- **0.3.x**：反证与复现（M4：PR-13/14/15/16）
- **0.4.x**：生态与基准（M5：PR-17/18）
