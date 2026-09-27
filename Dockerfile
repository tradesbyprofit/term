# J.A.R.V.I.S. Quantitative Pinnacle Trading Terminal - Production Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python quantitative & production web stack
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY pinnacle_core.py .
COPY real_pinnacle_ingest.py .
COPY wsgi_application.py .

# Expose port (Render/Fly/Railway/Heroku inject PORT via env)
ENV PORT=8000
EXPOSE 8000

# Run with Gunicorn WSGI multi-worker server
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8000} --workers 2 --threads 4 wsgi_application:application"]
