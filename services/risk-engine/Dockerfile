FROM python:3.11-slim

# Setting the working directory inside the container
WORKDIR /app

# Copying dependency list and installing them securely
COPY services/risk-engine/requirements.txt ./services/risk-engine/
RUN pip install --no-cache-dir -r services/risk-engine/requirements.txt

# Copying the actual application code (rules.py, schemas.py, main.py)
COPY services/risk-engine/ ./services/risk-engine/

# (Optional for later) Copying the contracts folder when it will be needed
# COPY contracts/ ./contracts/

WORKDIR /app/services/risk-engine

EXPOSE 8004
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]