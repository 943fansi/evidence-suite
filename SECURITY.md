# Security Policy

## 概述

本仓库是一套**证据驱动写作 / 审查 Agent Skill**（非独立应用）。安装它，意味着运行该 skill 的 Agent 会获得一组**本地脚本执行能力**与**联网能力**（来源检索、PDF 下载等）。请按需授权，不要在不受信任的环境中无审查地运行。

## 脚本能力与边界

脚本位于 `shared/scripts/`，需 Python 3 运行，依赖见 `shared/requirements.txt`（按需安装，非全部必需）。

| 脚本 | 联网 | 文件写入 | 外部 API | 说明 |
|------|------|---------|---------|------|
| `select_sources.py` | 否 | 否 | 否 | 本地路由选源 |
| `download_reference_files.py` | 是（下载公开 PDF） | 是（`reference_files/`） | 否 | 按语料 URL 下载 |
| `fetch_nsfc_report.py` | 是 | 是（输出目录） | 是（逆向 NSFC 门户 API） | 见下方专项说明 |
| `extract_pdf_text.py` | 否 | 是（`pdf_text/`） | 否 | 本地 PDF 抽文本 |
| `build_references.py` / `check_citations.py` / `validate_sources.py` / `check_framework_depth.py` / `finalize_draft.py` / `inspect_pipeline.py` | 否 | 可选写 | 否 | 确定性校验 / 生成 |
| `export_pdf.py` / `export_docx.py` | 部分（mermaid 图远程渲染时，默认 local-first） | 是（导出物） | 是（mermaid.ink 回退） | 导出 PDF/DOCX；`--mermaid-engine local` 禁止联网 |
| `visual_qa.py` | 否 | 是（`qa/`） | 否 | 本地浏览器截图 |

## 凭据与密钥

- 本仓库**不存储任何 API key / token / 密码**，脚本也不读取环境变量中的密钥。
- `fetch_nsfc_report.py` 中的 `KEY = b"IFROMC86"` 是从开源浏览器扩展 `NsfcReportExport` 反解出的**响应混淆常量，不是凭据**，不授予任何鉴权；仅用于解密 NSFC 门户公开返回的结题报告数据。

## NSFC 结题报告抓取（专项提示）

`fetch_nsfc_report.py` 逆向 NSFC 知识门户（kd.nsfc.cn）的浏览器扩展 API，下载**公开可见**的结题报告。使用前请确认符合 NSFC 门户服务条款；接口 / 密钥 / 签名 URL 可能随时失效。请保持低请求频率（脚本已内置 sleep + backoff）。

## 建议

- 在受限环境（沙箱 / CI）中，仅授予最小权限，或只运行不联网的校验类脚本（`check_*.py`、`validate_sources.py`、`build_references.py` 等）。
- 下载与导出的输出目录（`reference_files/`、`pdf_text/`、`proposal_workspace/`、导出物、`figures/`、`qa/`）均已加入 `.gitignore`，不会误提交。
- 报告漏洞请通过 GitHub Issues 联系维护者。
