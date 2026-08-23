# Docker 沙箱运行指引

用容器隔离 evidence-suite 的本地脚本执行与联网能力——满足「不要在高敏感生产环境直接运行未做沙箱隔离版本」的安全要求（见 `SECURITY.md` / `THREAT_MODEL.md`）。

## 构建

```bash
docker build -t evidence-suite -f docker/Dockerfile .
```

镜像包含：Python 3.12 + `shared/requirements.txt` 依赖 + pandoc + 中文 CJK 字体 + curl。**不含 mermaid-cli（mmdc）**——容器内 Mermaid 走 `mermaid.ink` 远程渲染，或用 `--mermaid-engine remote`；需要本地渲染时自行在镜像中安装 node + @mermaid-js/mermaid-cli。

## 运行

套件以只读挂载、工作区以可写挂载（Windows PowerShell 用 `${PWD}`）：

```bash
# 校验类脚本（建议断网：--network none）
docker run --rm --network none \
  -v ${PWD}:/workspace \
  -v ${PWD}/shared:/opt/evidence-suite/shared:ro \
  evidence-suite \
  python /opt/evidence-suite/shared/scripts/check_citations.py /workspace/11_定稿.md --sources /workspace/04_validated_sources.json --min-sources 15

# 能力探测
docker run --rm -v ${PWD}:/workspace evidence-suite
```

- **断网隔离**：`--network none` 时 `download_reference_files.py`/`fetch_nsfc_report.py` 无法联网（SSRF 之外的物理断网兜底）；`--mermaid-engine local` 在容器内需先装 mmdc。
- **文件系统隔离**：脚本只能写 `-v` 挂载的目录，容器内无宿主文件；不要挂载 `~/.ssh`、`.env` 等敏感目录。
- **输出目录**：容器内 `/workspace` 即宿主当前目录，`research_case/`、`figures/`、`qa/` 都落在其中（已 gitignore）。

## 局限

- 容器内无 Chrome/Edge，`export_pdf.py` 的 Chrome headless 引擎不可用；有 weasyprint（已装）时走 weasyprint。
- easyocr（NSFC `--ocr`）较重未装，需要时自行 `pip install easyocr`（拉 torch）。
- 联网场景（下载/回源）才需要带网运行，并遵守 `SECURITY.md` 的 SSRF 与下载上限约束。
