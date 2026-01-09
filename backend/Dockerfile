# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy source and install
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Run uvicorn
CMD ["uvicorn", "oya.main:app", "--host", "0.0.0.0", "--port", "8000"]
