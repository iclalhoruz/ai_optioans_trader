# Runs workflow/scheduler.py - the autonomous watchlist loop. No exposed
# port, this isn't an HTTP service; it just calls broker-gateway's API on
# an interval for as long as the container is up.
FROM python:3.12-slim

WORKDIR /app

COPY workflow/requirements.txt ./workflow/requirements.txt
RUN pip install --no-cache-dir -r workflow/requirements.txt

COPY workflow/ ./workflow/
# Never COPY .env here - secrets go in at runtime via docker-compose's
# env_file, not baked into the image.

ENV PYTHONPATH=/app

CMD ["python", "workflow/scheduler.py"]
