FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY UI/ ./UI/

# Set Python path to include the project directory
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Expose FastAPI/Gradio port
EXPOSE 80

# Start Unified UI app
CMD ["python", "UI/main.py"]
