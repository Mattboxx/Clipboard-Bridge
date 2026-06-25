# Server in un container. Funziona in qualsiasi ambiente Docker.
FROM python:3.12-slim

WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY clipboard_bridge-Server.py .

# I dati (testo/file/cronologia) vivono su un volume persistente.
ENV CLIPBOARD_DATA_DIR=/data \
    CLIPBOARD_MAX_HISTORY=200 \
    PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 5088

CMD ["python", "clipboard_bridge-Server.py"]
