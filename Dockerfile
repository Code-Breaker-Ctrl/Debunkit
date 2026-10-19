# Google Cloud Run optimized Dockerfile for DEBUNK.IT
FROM python:3.12-slim

# Allow statements and log messages to immediately appear in the Cloud Run logs
ENV PYTHONUNBUFFERED=True \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_ENV=production \
    PORT=8080

# Install system dependencies (C-compiler for packages if needed, libpq for Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install production dependencies first (utilizes Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the web service on container startup using Gunicorn
# Google Cloud Run injects the PORT environment variable into the container.
# Using 1 worker with 8 threads is Google's recommended concurrency model for Flask.
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 debunkit_app:app
