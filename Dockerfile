FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    TZ=UTC \
    HME_DATA_DIR=/data/state \
    HME_EXPORT_DIR=/data/export

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY hme_core.py main.py server.py cookies.txt.template ./
COPY web ./web

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/state /data/export \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

CMD ["python", "server.py"]
