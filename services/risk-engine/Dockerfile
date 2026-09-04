FROM python:3.11-slim

# Setting the working directory inside the container
WORKDIR /app

# Copying dependency list and installing them securely
COPY services/risk-engine/requirements.txt ./services/risk-engine/
RUN pip install --no-cache-dir -r services/risk-engine/requirements.txt

# Copying the actual application code and shared contracts directory
COPY services/risk-engine/ ./services/risk-engine/
COPY contracts/ ./contracts/

# Setting PYTHONPATH so Python can resolve modules from both /app and /app/services/risk-engine
ENV PYTHONPATH="/app:/app/services/risk-engine"

EXPOSE 8004
CMD ["uvicorn", "main:app", "--app-dir", "services/risk-engine", "--host", "0.0.0.0", "--port", "8004"]