# evidence-suite 沙箱运行环境（Docker）
#
# 构建：docker build -t evidence-suite -f docker/Dockerfile .
# 运行：见 docker/README.md —— 套件只读挂载、工作区可写、可断网运行校验脚本。

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    SUITE_ROOT=/opt/evidence-suite

# 系统工具：pandoc（PDF 导出主路径）、CJK 字体（中文渲染）、curl（下载回退）
RUN apt-get update && apt-get install -y --no-install-recommends \
        pandoc \
        fonts-noto-cjk \
        fonts-noto-cjk-extra \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（按需安装，体积可控；重件见 requirements.txt 注释）
COPY shared/requirements.txt /opt/evidence-suite/shared/requirements.txt
RUN pip install --no-cache-dir -r /opt/evidence-suite/shared/requirements.txt

# 套件本体（只读使用；workspace 由运行时挂载）
COPY . /opt/evidence-suite

WORKDIR /workspace
CMD ["python", "/opt/evidence-suite/shared/scripts/probe_capabilities.py", "--human"]
