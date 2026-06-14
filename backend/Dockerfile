# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Chroma/sqlite/pillow 빌드에 필요한 최소 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libsqlite3-dev \
        libjpeg-dev \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

# 앱 소스 + 규정 데이터 + 룰 yaml 같이 들어감
COPY app ./app
COPY data ./data

# SQLite 체크포인트와 업로드는 볼륨으로 외부에 보관
# (data/uploads, .chroma, .checkpoints.sqlite)
VOLUME ["/app/data/uploads", "/app/.chroma"]

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
