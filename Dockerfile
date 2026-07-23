# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ARG VERSION=dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="Clipboard Bridge Server" \
      org.opencontainers.image.description="Local-network clipboard bridge for Windows and iPhone" \
      org.opencontainers.image.url="https://github.com/mattbox03/Clipboard-Bridge" \
      org.opencontainers.image.source="https://github.com/mattbox03/Clipboard-Bridge" \
      org.opencontainers.image.documentation="https://github.com/mattbox03/Clipboard-Bridge/blob/main/GUIDE.md" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY clipboard_bridge-Server.py .

ENV CLIPBOARD_DATA_DIR=/data \
    CLIPBOARD_MAX_HISTORY=200 \
    PYTHONUNBUFFERED=1

VOLUME ["/data"]
EXPOSE 5088

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5088/health', timeout=3).read()"]

CMD ["python", "clipboard_bridge-Server.py"]
