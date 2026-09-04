FROM python:3.12-slim

WORKDIR /app

# alpaca_client.py talks to Alpaca via the official CLI (alpacahq/cli), not
# a Python SDK - the hackathon requires the project to genuinely utilize
# either Alpaca's MCP server or its CLI, and the MCP server's own docs
# describe it as built for AI chat clients, not a plain backend like this
# one. Pinned to the same version verified locally against a real account.
ARG ALPACA_CLI_VERSION=0.0.14
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL "https://github.com/alpacahq/cli/releases/download/v${ALPACA_CLI_VERSION}/cli_${ALPACA_CLI_VERSION}_linux_amd64.tar.gz" \
       | tar -xz -C /usr/local/bin alpaca \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY contracts/ ./contracts/
COPY workflow/ ./workflow/
COPY services/broker-gateway/requirements.txt ./services/broker-gateway/requirements.txt
RUN pip install --no-cache-dir -r services/broker-gateway/requirements.txt

COPY services/broker-gateway/ ./services/broker-gateway/
# Never COPY .env here - secrets go in at runtime via docker-compose's
# env_file, not baked into the image where they'd sit in every layer.

ENV PYTHONPATH=/app
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:8001/health', timeout=2).close()"]

CMD ["uvicorn", "main:app", "--app-dir", "services/broker-gateway", "--host", "0.0.0.0", "--port", "8001"]
