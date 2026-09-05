# Lightweight Python 3.12 slim runtime
FROM python:3.12-slim

# Streamlit and Python runtime configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Layer 1: Copy requirements and install dependencies
COPY frontend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Layer 2: Copy frontend application source and Streamlit settings
COPY frontend/ /app/frontend/
COPY .streamlit/ /app/.streamlit/

# Layer 3: Security - create and switch to unprivileged user
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

# Expose Streamlit dashboard port
EXPOSE 8501

# Healthcheck to verify Streamlit accessibility
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health')" || exit 1

# Start Streamlit application
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
