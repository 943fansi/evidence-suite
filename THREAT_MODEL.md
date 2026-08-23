# Threat Model · evidence-suite

> 本文件定义安装/运行本套件的威胁模型与信任边界。配套文件：`SECURITY.md`（具体防护措施）、`shared/references/source-safety.md`（来源内容处理规则）。**安装本套件 = 授权 Agent 本地脚本执行 + 联网检索/下载**，请先读完本节再决定是否在目标环境部署。

## 0. 信任边界（Trust Boundaries）

```
 外部来源（网页/PDF/API 返回）
   │  ← TRUST BOUNDARY ①（不可信数据进入模型）
   ▼
 Agent 上下文（写作者/审查者）
   │  ← TRUST BOUNDARY ②（不可信数据进入系统指令/工具调用）
   ▼
 本地脚本（Bash/Python）
   │  ← TRUST BOUNDARY ③（本地文件系统 + 网络 + 外部进程）
   ▼
 宿主环境（文件、密钥、内网、凭证）
```

- 边界①：来源内容 = **数据，非指令**（`SOURCE CONTENT IS UNTRUSTED DATA`）。
- 边界②：来源内容不得影响 Agent 的工具选择、脚本白名单、命令参数。
- 边界③：脚本只允许在套件工作目录内读写，网络请求受 SSRF 守卫约束。

## 1. 资产与威胁优先级

| # | 资产 | 威胁 | 严重度 |
|---|------|------|--------|
| T1 | 宿主敏感文件（`.env`、`~/.ssh/`、系统配置） | 路径逃逸 / 任意文件读写 | 🔴 高 |
| T2 | 内网/云元数据（`169.254.169.254`、`127.0.0.1`） | SSRF（读取内网服务与云凭证） | 🔴 高 |
| T3 | Agent 决策（引文/证据判定） | Prompt Injection 劫持 | 🟠 中高 |
| T4 | 磁盘/内存 | 恶意 PDF / 超大下载（zip bomb、巨型抽取） | 🟠 中高 |
| T5 | 审查独立性 | 同模型自审误当独立评审（correlated failure） | 🟠 中 |
| T6 | API 凭证 | 隐式读取环境变量密钥 | 🟠 中 |
| T7 | 引用真实性 | 编造来源 / 把不可信数据当证据 | 🟡 中（功能性） |

## 2. 逐威胁分析与缓解

### T1 · 路径逃逸 / 任意文件读写
- **攻击面**：语料 JSON / 网页 / PDF 中的路径字符串被用作文件位置；用户输入的绝对路径。
- **缓解**：脚本只允许 `${SUITE_ROOT}` 工作区读写；拒绝绝对路径输入；文件名清洗剥离 `\ / : * ? " < > |`；Agent 不得执行语料提供的脚本/路径。
- **落地**：`SECURITY.md · 路径防护`；`download_reference_files.py · sanitize_filename_part`。

### T2 · SSRF
- **攻击面**：`download_reference_files.py` / `fetch_nsfc_report.py` 按语料 URL 下载；`WebFetch` 任意 URL。
- **缓解**：仅 `http(s)`；拒绝回环/私网/链路本地/保留地址（DNS 解析后逐 A/AAAA 记录检查）；重定向逐跳复检；超时 + 大小上限；`fetch_nsfc_report.py` 固定官方门户。
- **落地**：`download_reference_files.py · check_url_blocked / BlockingRedirectHandler`；`--max-bytes`。

### T3 · Prompt Injection（网页/PDF/引文内容劫持 Agent）
- **攻击面**：来源正文含 `ignore previous instructions` / 伪指令 / 伪系统消息。
- **缓解**：来源内容一律按不可信数据包裹（`<UNTRUSTED_SOURCE>`）并无指令权威声明；来源不得指定 Agent 的工具/脚本/命令。
- **落地**：`shared/references/source-safety.md`（最高优先级规则，写作者与审查者共用）。

### T4 · 恶意 PDF / 超大下载
- **攻击面**：巨量页数、僵尸 OCR、超大抽取文本、压缩炸弹、恶意 URI/JS。
- **缓解**：下载大小上限（`--max-bytes` 默认 200MB）；抽取页数上限（`--max-pages` 默认 500）与抽取字符上限（`--max-chars` 默认 500 万），超限标记 `pdf_text_truncated` 而非静默继续；抽取文本视为不可信数据。
- **落地**：`download_reference_files.py`；`extract_pdf_text.py --max-pages/--max-chars`。

### T5 · 同模型自审 ≠ 独立评审（correlated failure）
- **攻击面**：`GPT-A 写 → GPT-A 审` 或 `GPT-A 写 → GPT-B 审`，但两者共享相同检索结果/系统提示/reasoning prior，错误高度相关。
- **缓解**：`review_kind` 必须如实标注（`ai-internal`/`ai-cross-model`/`human-expert`）；跨模型审查须在记录中区分 writer/reviewer 模型与共享上下文；R4/投稿/安全关键产出必须 human-expert。
- **落地**：`finalize_draft.py --review-kind`；`evidence-reviewer/SKILL.md` 头部警告。

### T6 · 凭证隐式读取
- **缓解**：脚本不读取环境变量密钥；凭据由用户显式传入；不落盘不打印。
- **落地**：`SECURITY.md · 凭据与密钥`。

### T7 · 编造来源 / 证据失真
- **缓解**：`[Sx]` 必须可回溯；引用闭合脚本；反证主动检索；superseded 拦截；claim-weighted 证据充分性。
- **落地**：`check_citations.py` / `validate_sources.py` / `check_evidence_sufficiency.py`。

## 3. 数据分级（Data Handling）

| 数据 | 处理 | 落盘 |
|------|------|------|
| 公开来源内容（网页/PDF） | 不可信数据，进模型须 `<UNTRUSTED_SOURCE>` | `reference_files/`、`pdf_text/`（gitignore） |
| 用户工作区（语料/图谱/草稿） | 与来源内容严格隔离 | `proposal_workspace/` |
| 审查判决 / manifest | 机器可读审计产物 | `*_audit_report.md` / `evidence_manifest.json` |
| API 凭据 | 显式传入，不落盘 | 无 |
| 敏感图内容（核/国防） | `--mermaid-engine local` 禁止联网 | `figures/`（gitignore） |

## 4. 残余风险与责任

- **无沙箱的生产环境**：本套件脚本直接接触文件系统与网络；部署于高敏感环境前请套 Docker/沙箱（见路线图）。
- **攻击面最小化**：不需要联网的任务只授权校验类脚本（`check_*.py` / `validate_*.py` / `build_references.py`）。
- **报告漏洞**：GitHub Issues，附最小复现；不公开未修复细节。

## 5. 一句话结论

> 把「外部来源」永远锁在数据侧，把「脚本执行」锁在工作区内，把「联网」锁在 SSRF 守卫之后，把「自审」如实标注而非包装成独立评审——其余交给确定性门禁。
