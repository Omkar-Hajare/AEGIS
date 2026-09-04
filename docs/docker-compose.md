# Docker Compose Quickstart (Phase 2)

## Overview
The Docker Compose environment orchestrates all six core services of the Adaptive Cache System over a unified bridge network (`adaptive-cache-network`).

```
Streamlit (8501)
     ↓
FastAPI (8000) ──→ Redis (6379)
     │         ──→ PostgreSQL (5432)
     ↓
Prometheus (9090)
     ↓
Grafana (3000)
```

---

## 1. Services and Ports

| Service | Container Name | Image / Build | Port Mapping | Internal DNS Target |
| :--- | :--- | :--- | :--- | :--- |
| **backend** | `adaptive-backend` | `backend/Dockerfile` | `8000:8000` | `backend:8000` |
| **frontend** | `adaptive-frontend` | `frontend/Dockerfile` | `8501:8501` | `frontend:8501` |
| **redis** | `adaptive-redis` | `redis:7-alpine` | `6379:6379` | `redis:6379` |
| **postgres** | `adaptive-postgres` | `postgres:16-alpine` | `5432:5432` | `postgres:5432` |
| **prometheus** | `adaptive-prometheus` | `prom/prometheus:v2.54.1`| `9090:9090` | `prometheus:9090` |
| **grafana** | `adaptive-grafana` | `grafana/grafana:11.1.0` | `3000:3000` | `grafana:3000` |

---

## 2. Operational Commands

### Start the Stack
```bash
docker compose up -d --build
```

### Check Status & Health
```bash
docker compose ps
```

### View Logs
```bash
# Follow all services
docker compose logs -f

# Follow specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f prometheus
```

### Stop the Stack
```bash
# Stop containers (preserves volumes)
docker compose down

# Stop and remove volumes (clean reset)
docker compose down -v
```

---

## 3. Health & Endpoint Verification

* **FastAPI Backend:**
  ```bash
  curl http://localhost:8000/health
  curl http://localhost:8000/data/product/101
  ```
* **Streamlit Frontend:**
  ```bash
  curl -I http://localhost:8501/_stcore/health
  # Browser: http://localhost:8501
  ```
* **Prometheus:**
  ```bash
  curl http://localhost:9090/-/healthy
  # Browser: http://localhost:9090
  ```
* **Grafana:**
  ```bash
  curl http://localhost:3000/api/health
  # Browser: http://localhost:3000 (User: admin / Pass: admin)
  ```

---

## 4. Current Limitations & Roadmap

* **Prometheus `/metrics`:** Prometheus is running and scraping `backend:8000/metrics`. Since the backend metrics endpoint is not yet implemented, Prometheus records HTTP 404. This will be wired in **Phase 3**.
* **PostgreSQL Persistence:** PostgreSQL is running, healthy, and accessible at `postgres:5432` with a persistent volume (`postgres_data`). Active database entity models and migration logic are scheduled for future persistence sprints.
* **Grafana Dashboards:** Prometheus is auto-provisioned as the default datasource. Custom metric dashboards will be configured in **Phase 4**.
