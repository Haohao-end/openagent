# 使用 Debian12 的 Python3.11 版本作为基础镜像
FROM python:3.11-slim-bookworm AS base

# 设置 shell 为 bash（可选）
SHELL ["/bin/bash", "-c"]

# 设置工作目录
WORKDIR /app/api

# 安装系统依赖（包括 curl，用于下载 tiktoken 文件）
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 curl tzdata && rm -rf /var/lib/apt/lists/*

# 预下载 tiktoken 编码文件到缓存目录
RUN mkdir -p /root/.cache/tiktoken && \
    curl -o /root/.cache/tiktoken/cl100k_base.tiktoken \
    https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken

# 复制 requirements 并安装依赖
COPY requirements.txt .
RUN pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    rm -rf /root/.cache


# 复制代码文件
COPY . .

# 设置镜像级固定环境变量（业务配置通过 env_file/.env 注入）
ENV FLASK_APP=app/http/app.py \
    NLTK_DATA=/app/api/internal/core/unstructured/nltk_data \
    TZ=Asia/Shanghai

RUN ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone

# 启动脚本
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5001

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
