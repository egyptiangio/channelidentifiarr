FROM python:3.11-slim

# Build arguments for version info
ARG GIT_BRANCH=unknown
ARG GIT_SHA=unknown

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
COPY backend/settings_manager.py .
COPY backend/config.py .

# Copy frontend files
COPY frontend ./frontend

# Write version files with build-time git info
RUN echo "${GIT_BRANCH}" > /app/.git-branch && \
    echo "${GIT_SHA}" > /app/.git-sha

# Create data directory
RUN mkdir -p /data

# Set environment variables for version info
ENV GIT_BRANCH=${GIT_BRANCH}
ENV GIT_SHA=${GIT_SHA}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9192/api/health || exit 1

# Expose port
EXPOSE 9192

# Run with gunicorn using gevent worker for SSE support
CMD ["gunicorn", "--bind", "0.0.0.0:9192", "--worker-class", "gevent", "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--log-level", "info", "app:app"]
