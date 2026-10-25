FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose port (Render automatically routes traffic to $PORT)
EXPOSE 8000

# Use shell form so $PORT expands properly at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
