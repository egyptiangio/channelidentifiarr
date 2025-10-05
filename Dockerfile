FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/app.py .

# Copy frontend files
COPY frontend ./frontend

# Create data directory
RUN mkdir -p /data

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9192/api/health || exit 1

# Expose port
EXPOSE 9192

# Run with gunicorn using gevent worker for SSE support
CMD ["gunicorn", "--bind", "0.0.0.0:9192", "--worker-class", "gevent", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--log-level", "info", "app:app"]
