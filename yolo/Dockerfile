# 使用Python官方精简镜像
FROM python:3.11-slim

# 安装系统级依赖（关键）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    gcc \
    libffi-dev \
    && apt-get install -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 优先升级pip并指定超时
COPY requirements.txt .
RUN pip install --upgrade pip --default-timeout=1000 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 分步安装依赖（关键修改）
RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=1000 \
    -r requirements.txt

# 复制应用代码
COPY . .

# 启动命令
CMD ["python", "app.py"]