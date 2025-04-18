FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y gcc python3-dev default-libmysqlclient-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# 安装 Celery 依赖 #
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir \
    -r requirements.txt

EXPOSE 5000


COPY . .

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]