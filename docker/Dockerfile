FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set Python path to include the app directory
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Start Celery worker
CMD ["celery", "-A", "src.user_orchestrator", "worker", "-Q", "managers", "--concurrency=1", "-P", "solo", "--loglevel=info"]
