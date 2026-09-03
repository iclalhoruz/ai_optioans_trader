FROM python:3.12-slim

WORKDIR /app

COPY contracts/ ./contracts/
COPY services/ai-strategy/requirements.txt ./services/ai-strategy/requirements.txt
RUN pip install --no-cache-dir -r services/ai-strategy/requirements.txt

COPY services/ai-strategy/ ./services/ai-strategy/
# Never COPY .env here - secrets go in at runtime via docker-compose's
# env_file, not baked into the image.

ENV PYTHONPATH=/app
EXPOSE 8002

CMD ["uvicorn", "main:app", "--app-dir", "services/ai-strategy", "--host", "0.0.0.0", "--port", "8002"]
