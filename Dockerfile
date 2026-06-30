
FROM python:3.12-slim

WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY clipboard_bridge-Server.py .


ENV CLIPBOARD_DATA_DIR=/data \
    CLIPBOARD_MAX_HISTORY=200 \
    PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 5088

CMD ["python", "clipboard_bridge-Server.py"]
