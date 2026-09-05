# Multi-stage / lightweight Python 3.12 slim runtime
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered streaming logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app"

WORKDIR /app

# Layer 1: Copy requirements and install dependencies with cache optimization
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Layer 2: Copy contracts and backend application source code
COPY contracts/ /app/contracts/
COPY backend/ /app/

# Create symlink so that 'import backend.xyz' resolves correctly alongside flat imports
RUN ln -s /app /app/backend

# Layer 3: Security - create and switch to unprivileged user
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

# Expose backend API port
EXPOSE 8000

# Healthcheck to verify container health
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Start FastAPI application via uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
