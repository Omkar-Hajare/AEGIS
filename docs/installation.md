# Adaptive Cache System — Installation & Prerequisites Guide

This document defines all system assumptions, external software prerequisites, Python dependencies, container image builds, Kubernetes cluster setup, and configuration steps required before running the Adaptive Cache System.

---

## 1. Supported Environment Assumptions

The platform is designed to run across local development workstations, containerized environments, and local or cloud Kubernetes clusters.

- **Supported Operating Systems**:
  - Linux (Ubuntu 22.04 / 24.04 LTS, Debian 12, Fedora 39+, Arch Linux)
  - macOS (Apple Silicon M1/M2/M3 or Intel x86_64, macOS 13+)
  - Windows 10/11 via **WSL2** (Ubuntu distribution recommended)
- **Minimum Hardware Requirements**:
  - **CPU**: 4 physical or virtual cores (6+ cores recommended for running Minikube, metrics-server, and k6 load tests simultaneously).
  - **RAM**: 8 GB minimum (16 GB recommended to prevent OOM when running the full Docker Compose stack alongside Kubernetes and Prometheus TSDB).
  - **Disk Space**: 20 GB free disk space for Docker image layers, PostgreSQL volumes, and Minikube virtual machine/container disks.
- **Shell Environment**:
  - POSIX-compliant shell (`bash` or `zsh`) with standard CLI utilities (`curl`, `tar`, `grep`, `lsof`, `git`).

---

## 2. Required Software Installation

Install the following software packages before attempting to build or run the project.

### 2.1 Git
Required for repository version control and subresource management.

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y git

# macOS (Homebrew)
brew install git

# Verification
git --version  # Minimum v2.30+
```

### 2.2 Python 3.12+
The backend and frontend containers run `python:3.12-slim`. Local Python development requires Python 3.10+ (Python 3.12 recommended for runtime parity).

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv python3-dev

# macOS (Homebrew)
brew install python@3.12

# Verification
python3 --version  # Output: Python 3.12.x
pip3 --version
```

### 2.3 Docker Engine & Docker Compose
Docker is required for container builds, standalone execution, and Docker Compose orchestration.

```bash
# Ubuntu/Debian (Official Docker Engine)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# macOS
# Install Docker Desktop for Mac or OrbStack

# Verification
docker --version          # Minimum v24.0+
docker compose version   # Minimum v2.20+ (Compose v2 plugin)
```

### 2.4 kubectl
The Kubernetes command-line tool for cluster management.

```bash
# Linux (AMD64)
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
rm kubectl

# macOS (Homebrew)
brew install kubectl

# Verification
kubectl version --client --output=yaml
```

### 2.5 Minikube
Local single-node Kubernetes cluster emulator.

```bash
# Linux (AMD64)
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
rm minikube-linux-amd64

# macOS (Homebrew)
brew install minikube

# Verification
minikube version  # Minimum v1.32+
```

### 2.6 Helm
Package manager for Kubernetes, used to deploy both the application chart (`helm/adaptive-cache`) and the monitoring stack.

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# macOS (Homebrew alternative)
brew install helm

# Verification
helm version  # Minimum v3.12+
```

### 2.7 k6 Load Testing Engine
Used for high-concurrency performance benchmarking and Kubernetes HPA autoscaling validation.

```bash
# Ubuntu/Debian
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D34E8889
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update && sudo apt-get install -y k6

# macOS (Homebrew)
brew install k6

# Verification
k6 version  # Minimum v0.48+
```

---

## 3. Project Dependency Installation

The repository provides three modular `requirements.txt` targets depending on the development scope.

### 3.1 Python Virtual Environment Setup

Always create an isolated virtual environment from the repository root:

```bash
# Navigate to repository root
cd /path/to/VH26-Satyagrah

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Upgrade packaging tools
pip install --upgrade pip setuptools wheel
```

### 3.2 Full Monorepo Development (`requirements.txt`)
Installs backend, frontend, testing, database drivers, and simulation tools:

```bash
pip install -r requirements.txt
```

Key packages installed:
- **API & Core**: `fastapi>=0.100.0`, `uvicorn[standard]>=0.23.0`, `pydantic>=2.0.0`, `pydantic-settings>=2.0.0`, `python-dotenv>=1.0.0`
- **Data & Caching**: `redis>=5.0.0`, `SQLAlchemy>=2.0.0`, `psycopg[binary]>=3.1.0`
- **Dashboard UI**: `streamlit>=1.30.0`, `pandas>=2.0.0`, `plotly>=5.18.0`, `requests>=2.31.0`
- **Testing & Quality**: `pytest>=8.0.0`, `pytest-asyncio>=0.21.0`, `httpx>=0.25.0`, `ruff>=0.1.0`

### 3.3 Component-Specific Installations (Optional)

If running or containerizing only a specific tier:

- **Backend Tier Only** (`backend/requirements.txt`):
  ```bash
  pip install -r backend/requirements.txt
  ```
  *Installs: `fastapi`, `uvicorn[standard]`, `pydantic-settings`, `redis>=5.0.0`, `SQLAlchemy>=2.0.0`, `psycopg[binary]>=3.1.0`, `prometheus_client>=0.20.0`.*

- **Frontend Tier Only** (`frontend/requirements.txt`):
  ```bash
  pip install -r frontend/requirements.txt
  ```
  *Installs: `streamlit>=1.30.0`, `pandas>=2.0.0`, `plotly>=5.18.0`, `requests>=2.31.0`, `prometheus-client`.*

### 3.4 Verification of Python Dependencies

Run this inline validation command:

```bash
python3 -c "
import fastapi
import streamlit
import redis
import sqlalchemy
import psycopg
import prometheus_client
import pydantic
print('All critical Python packages imported successfully.')
"
```

---

## 4. Docker Verification & Image Builds

### 4.1 Docker Daemon Verification
Ensure the Docker daemon is running and responsive:

```bash
docker info > /dev/null && echo "Docker daemon is active" || echo "Docker daemon is not running"
```

### 4.2 Building Application Container Images
Build commands must be executed from the **repository root** so that the shared schemas in `contracts/` and UI configurations in `.streamlit/` are within the Docker build context.

```bash
# Build Backend Image
docker build -t hackathon-backend:latest -f backend/Dockerfile .

# Build Frontend Image
docker build -t hackathon-frontend:latest -f frontend/Dockerfile .
```

Verify that the images exist in your local registry:

```bash
docker images | grep hackathon
# Expected output:
# hackathon-backend    latest   ...   ~180MB
# hackathon-frontend   latest   ...   ~350MB
```

---

## 5. Minikube Installation and Verification

A local Kubernetes cluster is required to test the Kubernetes manifests (`k8s/`), Helm chart (`helm/adaptive-cache/`), and Horizontal Pod Autoscaling (HPA).

### 5.1 Starting the Minikube Cluster
Start Minikube with sufficient resources and the **metrics-server** addon enabled (critical for HPA):

```bash
minikube start \
  --cpus=4 \
  --memory=8192 \
  --driver=docker \
  --addons=metrics-server
```

> **IMPORTANT**: The `--addons=metrics-server` flag is required. Without `metrics-server`, the Kubernetes HPA controller cannot observe container CPU utilization, causing HPA status to show `<unknown>/50%`.

### 5.2 Verifying Cluster Health

```bash
# Check cluster responsiveness
minikube status

# Verify nodes
kubectl get nodes

# Verify metrics-server is collecting resource data
kubectl top nodes
```

### 5.3 Pointing Docker CLI to Minikube (Local Image Sharing)
To allow Minikube to use locally built images without pushing to an external registry (Docker Hub / GHCR):

```bash
# Configure current shell to use Minikube's Docker daemon
eval $(minikube docker-env)

# Build images directly into Minikube's daemon
docker build -t hackathon-backend:latest -f backend/Dockerfile .
docker build -t hackathon-frontend:latest -f frontend/Dockerfile .

# Verify images are inside Minikube
minikube image ls | grep hackathon
```

---

## 6. Helm Installation and Verification

Verify that Helm 3 can communicate with your active Kubernetes context and validate the project chart.

### 6.1 Linting the Local Helm Chart
Run `helm lint` against the provided chart in `helm/adaptive-cache`:

```bash
helm lint helm/adaptive-cache
# Output: 1 chart(s) linted, 0 chart(s) failed
```

### 6.2 Rendering Chart Templates
Perform a dry-run template rendering to ensure all manifests compile cleanly:

```bash
helm template test-release helm/adaptive-cache -f helm/adaptive-cache/values.yaml > /dev/null && echo "Helm templates rendered successfully"
```

---

## 7. Kubernetes Monitoring Installation (`kube-prometheus-stack`)

The Kubernetes deployment utilizes the Prometheus Operator pattern to automatically discover and scrape backend `/metrics` via `ServiceMonitor` resources.

### 7.1 Adding Prometheus Community Helm Repository

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

### 7.2 Deploying `kube-prometheus-stack`
Deploy the Prometheus Operator, Prometheus Server, Grafana, and dashboard discovery sidecars into a dedicated `monitoring` namespace:

```bash
# 1. Create monitoring namespace
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# 2. Install kube-prometheus-stack matching the release label expected by helm/adaptive-cache
helm install adaptive-monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.sidecar.dashboards.enabled=true \
  --set grafana.sidecar.dashboards.searchNamespace=ALL \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

### 7.3 Applying the Pre-Configured Grafana Dashboard ConfigMap
The repository includes a ready-to-use Grafana dashboard definition labeled for automatic discovery by Grafana's sidecar:

```bash
kubectl apply -f k8s/monitoring/dashboard-configmap.yaml
```

Verify that the dashboard ConfigMap is installed:

```bash
kubectl get configmap adaptive-cache-dashboard -n monitoring --show-labels
# Labels must include: grafana_dashboard=1
```

### 7.4 Verifying Monitoring Pods

```bash
kubectl get pods -n monitoring
# All pods (prometheus, grafana, operator, node-exporter) should reach Running status
```

---

## 8. Required Ports & Port Availability

Ensure the following ports are open and not blocked by local host services before launching Docker Compose or Kubernetes port-forwards.

| Host Port | Protocol | Target Service | Purpose |
| :--- | :--- | :--- | :--- |
| **8000** | TCP | FastAPI Backend (`adaptive-backend`) | REST API, documentation (`/docs`), health check (`/health`), and `/metrics` |
| **8501** | TCP | Streamlit UI (`adaptive-frontend`) | Adaptive Cache Control Center dashboard |
| **6379** | TCP | Redis (`adaptive-redis`) | High-speed key-value cache store |
| **5432** | TCP | PostgreSQL (`adaptive-postgres`) | Cache metadata & telemetry snapshot database |
| **9090** | TCP | Prometheus Server | Time-series scraper and PromQL query console |
| **3000** | TCP | Grafana Dashboard | Visual monitoring UI with pre-provisioned panels |

### Checking for Port Conflicts (Linux / macOS)

```bash
lsof -i :8000,8501,6379,5432,9090,3000
```

If ports are in use by local standalone services (e.g. system PostgreSQL or Redis), stop them temporarily:

```bash
# Linux systemd examples:
sudo systemctl stop postgresql
sudo systemctl stop redis-server
```

---

## 9. Environment Variables and Secrets

Configuration is managed via `pydantic-settings` in `backend/app/config.py`. Values are loaded from environment variables or a local `.env` file.

### 9.1 Local Configuration (`.env`)
Initialize your local configuration by copying the template:

```bash
cp .env.example .env
```

### 9.2 Configuration Reference Matrix

| Variable Name | Default Value | Valid Options | Purpose |
| :--- | :--- | :--- | :--- |
| `APP_NAME` | `Adaptive Cache System` | string | Application identifier |
| `APP_VERSION` | `0.1.0` | string | API semantic version |
| `CACHE_BACKEND` | `inmemory` | `inmemory`, `redis` | Active cache store implementation |
| `DATA_BACKEND` | `simulated` | `simulated`, `amazon_like` | Upstream origin adapter implementation |
| `REDIS_HOST` | `localhost` | hostname / IP | Redis server host (`redis` in Docker Compose) |
| `REDIS_PORT` | `6379` | integer | Redis port |
| `REDIS_DB` | `0` | integer (0–15) | Redis logical database index |
| `REDIS_PASSWORD` | `""` | string | Optional Redis authentication token |
| `DATABASE_HOST` | `localhost` | hostname / IP | PostgreSQL host (`postgres` in Docker Compose) |
| `DATABASE_PORT` | `5432` | integer | PostgreSQL port |
| `DATABASE_NAME` | `adaptive_cache` | string | PostgreSQL database name |
| `DATABASE_USER` | `adaptive` | string | Database username (`postgres` in Compose/K8s) |
| `DATABASE_PASSWORD`| `adaptive` | string | Database password (`postgres` in Compose/K8s) |
| `DATABASE_URL` | `""` | URI string | Full SQLAlchemy database connection string |
| `BACKEND_URL` | `http://localhost:8000` | URL string | FastAPI target URL used by Streamlit frontend |

### 9.3 Kubernetes ConfigMap & Secret Equivalents

In Kubernetes, configuration is decoupled into:

- **`k8s/backend/configmap.yaml`**: Injects `CACHE_BACKEND=redis`, `REDIS_HOST=redis`, `POSTGRES_HOST=postgres`, and application settings into the backend pods.
- **`k8s/postgres/secret.yaml`**: Stores sensitive database credentials (`POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=adaptive_cache`).

---

## 10. Common Installation Problems & Troubleshooting

### Problem 1: Docker Build Fails with `ModuleNotFoundError: No module named 'contracts'`
- **Cause**: Building from inside `backend/` instead of the root directory.
- **Solution**: Always execute `docker build` from the repository root:
  ```bash
  docker build -t hackathon-backend:latest -f backend/Dockerfile .
  ```

### Problem 2: Minikube HPA Displays `<unknown>/50%` CPU Utilization
- **Cause**: `metrics-server` is either disabled, or backend pods lack resource requests.
- **Solution**:
  1. Enable metrics server: `minikube addons enable metrics-server`.
  2. Verify pod requests: Ensure `k8s/backend/deployment.yaml` specifies `resources.requests.cpu: 100m`.
  3. Wait 60 seconds for metrics-server to aggregate initial readings, then run `kubectl top pods`.

### Problem 3: Port Collision on Port 5432 or 6379
- **Cause**: A local PostgreSQL or Redis daemon is already listening on the host.
- **Solution**: Stop local services via `sudo systemctl stop postgresql redis-server` or change host ports in `docker-compose.yml` (`- "5433:5432"`).

### Problem 4: Grafana Dashboard Does Not Appear in Kubernetes
- **Cause**: The ConfigMap lacks the required sidecar annotation or was deployed to the wrong namespace.
- **Solution**: Ensure `k8s/monitoring/dashboard-configmap.yaml` has `metadata.namespace: monitoring` and `metadata.labels.grafana_dashboard: '1'`. Then restart the Grafana deployment:
  ```bash
  kubectl rollout restart deployment adaptive-monitoring-grafana -n monitoring
  ```

### Problem 5: `psycopg` Build Failure During `pip install`
- **Cause**: Missing C compiler or `libpq` header files on the host system.
- **Solution**: Ensure you install `psycopg[binary]>=3.1.0` (as specified in `requirements.txt`), which uses pre-compiled wheels and avoids local compilation.
