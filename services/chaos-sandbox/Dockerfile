FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app
COPY services/chaos-sandbox/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system chaos \
    && useradd --system --gid chaos --no-create-home chaos

COPY contracts/ ./contracts/
COPY services/chaos-sandbox/chaos_sandbox/ ./chaos_sandbox/

USER chaos
EXPOSE 8003
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8003/health', timeout=2).close()"]
CMD ["uvicorn", "chaos_sandbox.main:app", "--host", "0.0.0.0", "--port", "8003"]
