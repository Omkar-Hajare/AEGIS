# PHASE 1: CONTAINER RUNTIME CONTRACT & DOCKERIZATION SPECIFICATION

## Overview
This document defines the container runtime contracts, build specifications, and operational instructions for containerizing the **Adaptive Cache and Application Scaling System (VH26-Satyagrah)**.

The container architecture guarantees parity across environments:
- Local Development
- Standalone Docker Containers (Phase 1)
- Multi-Container Docker Compose (Phase 2)
- Kubernetes Pods and Deployments (Phase 5+)

Application logic remains unchanged across all runtime targets by externalizing infrastructure configuration via environment variables.

---

## 1. BACKEND RUNTIME CONTRACT

### Specifications
* **Base Runtime Image:** `python:3.12-slim` (Debian Bookworm minimal base)
* **Python Version:** Python 3.12+
* **Working Directory:** `/app`
* **Entry Point / App Object:** `app` located in `backend/app/main.py`
* **Startup Command:**
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```
* **Exposed Port:** `8000` (TCP)
* **Application Security:** Runs as non-root user `appuser` (UID 10001)
* **Health Check Endpoint:** `GET http://127.0.0.1:8000/health`
  * Response: `{"status": "ok", "service": "Adaptive Cache System", "version": "0.1.0"}`

### Environment Variables
Configured via `pydantic-settings` in `backend/app/config.py`:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | string | `Adaptive Cache System` | Application identifier |
| `APP_VERSION` | string | `0.1.0` | API version |
| `CACHE_BACKEND`| string | `inmemory` | Cache store (`inmemory` or `redis`) |
| `REDIS_HOST` | string | `localhost` | Redis server hostname/IP (`redis` in Compose) |
| `REDIS_PORT` | integer| `6379` | Redis port |
| `REDIS_DB` | integer| `0` | Redis logical database index |
| `REDIS_PASSWORD`| string| `""` | Redis auth password (if enabled) |

### External Dependencies
* **In-Memory Mode (`CACHE_BACKEND=inmemory`):** Zero external infrastructure required. Runs completely standalone.
* **Redis Mode (`CACHE_BACKEND=redis`):** Requires network reachability to Redis at `${REDIS_HOST}:${REDIS_PORT}`.
* **PostgreSQL:** Reserved for persistent storage in subsequent phases; currently not required for backend startup.

### Active Endpoints
* `GET /health`: Health status probe
* `GET /data/product/{product_id}`: Read-heavy catalog mock endpoint
* `GET /data/recommendation/{user_id}`: Compute-heavy recommendation mock endpoint
* `GET /telemetry/observation`: Live sliding-window telemetry snapshot
* `GET /telemetry/workload`: Workload classification state
* `GET /telemetry/system`: System cache and memory status
* `POST /telemetry/window/reset`: Window rotation trigger

---

## 2. FRONTEND RUNTIME CONTRACT

### Specifications
* **Base Runtime Image:** `python:3.12-slim`
* **Python Version:** Python 3.12+
* **Working Directory:** `/app`
* **Entry Point:** `frontend/app.py`
* **Startup Command:**
  ```bash
  streamlit run frontend/app.py --server.port=8501 --server.address=0.0.0.0
  ```
* **Exposed Port:** `8501` (TCP)
* **Application Security:** Runs as non-root user `appuser` (UID 10001)
* **Health Check Endpoint:** `GET http://127.0.0.1:8501/_stcore/health`

### Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `BACKEND_URL` | string | `http://localhost:8000` | Target FastAPI API URL (`http://backend:8000` in Compose) |
| `STREAMLIT_SERVER_PORT` | integer | `8501` | Streamlit listening port |
| `STREAMLIT_SERVER_ADDRESS`| string | `0.0.0.0` | Bind address (must be 0.0.0.0 in containers) |
| `STREAMLIT_SERVER_HEADLESS`| boolean | `true` | Suppresses auto-browser launch in container |
| `STREAMLIT_BROWSER_GATHER_USAGE_STATS` | boolean | `false` | Disables telemetry phone-home |

### External Dependencies
* Connects over HTTP to the backend via `${BACKEND_URL}`.
* Uses fallback mock data in `frontend/mocks/data.py` if the backend is not yet populated or offline.

---

## 3. DOCKER BUILD INSTRUCTIONS

Build contexts must be executed from the **repository root** so that the shared data contracts in `contracts/` and Streamlit configuration in `.streamlit/` are available to the build engine:

```bash
# Build Backend Image
docker build -t adaptive-cache-backend -f backend/Dockerfile .

# Build Frontend Image
docker build -t adaptive-cache-frontend -f frontend/Dockerfile .
```

---

## 4. DOCKER RUN INSTRUCTIONS (STANDALONE)

### Running Backend Container
```bash
docker run -d \
  --name adaptive-backend \
  -p 8000:8000 \
  -e CACHE_BACKEND=inmemory \
  adaptive-cache-backend
```

Verify backend:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/data/product/101
curl http://localhost:8000/telemetry/observation
```

### Running Frontend Container
```bash
docker run -d \
  --name adaptive-frontend \
  -p 8501:8501 \
  -e BACKEND_URL=http://host.docker.internal:8000 \
  adaptive-cache-frontend
```

Verify frontend:
Open in browser or check headers:
```bash
curl -I http://localhost:8501/_stcore/health
```

---

## 5. DOCKER NETWORKING & ARCHITECTURAL READINESS

1. **Localhost Isolation:** Inside a Docker container, `localhost` refers strictly to that container. The frontend cannot query `http://localhost:8000` to reach a sibling container.
2. **Phase 1 (Bridge / Host Access):** Containers map host ports (`-p 8000:8000` and `-p 8501:8501`). On Linux/macOS, frontend can reach host-mapped backend via `--net=host` or a shared user-defined Docker bridge network.
3. **Phase 2 (Docker Compose Preparation):** In Compose, service names (`backend` and `frontend`) serve as automatic DNS hosts. The frontend will configure:
   `BACKEND_URL=http://backend:8000`
   and backend will configure:
   `REDIS_HOST=redis`
   with zero code modifications.
