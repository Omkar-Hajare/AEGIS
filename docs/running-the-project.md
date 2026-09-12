# Adaptive Cache System — Project Execution Guide

This guide provides the complete, chronological workflow for running, verifying, testing, and monitoring the Adaptive Cache System across both **Docker Compose** (local multi-container stack) and **Kubernetes** (Minikube cluster with HPA and Prometheus Operator).

---

## 1. Run with Docker Compose

Docker Compose orchestrates all six core services on a unified bridge network (`adaptive-cache-network`).

Execute from the repository root:

```bash
# Build and start all services in detached mode
docker compose up -d --build
```

Compose starts the stack in strict dependency order:
1. `redis` (`redis:7-alpine`) and `postgres` (`postgres:16-alpine`) start and pass health checks.
2. `backend` (`adaptive-backend`, FastAPI) starts once Redis and PostgreSQL report healthy.
3. `frontend` (`adaptive-frontend`, Streamlit) starts once the backend reports healthy.
4. `prometheus` (`adaptive-prometheus`) and `grafana` (`adaptive-grafana`) start with auto-provisioned configurations.

---

## 2. Verify All Compose Services

Verify that all six containers are running and report `healthy`:

```bash
# 1. Check container operational and health status
docker compose ps

# Expected output shows 6 healthy services:
# adaptive-backend     Up (healthy)   0.0.0.0:8000->8000/tcp
# adaptive-frontend    Up (healthy)   0.0.0.0:8501->8501/tcp
# adaptive-grafana     Up (healthy)   0.0.0.0:3000->3000/tcp
# adaptive-postgres    Up (healthy)   0.0.0.0:5432->5432/tcp
# adaptive-prometheus  Up (healthy)   0.0.0.0:9090->9090/tcp
# adaptive-redis       Up (healthy)   0.0.0.0:6379->6379/tcp
```

### Quick Service Liveness Probes

Verify individual service responsiveness via CLI:

```bash
# Verify Backend API
curl -s http://localhost:8000/health
# Output: {"status":"ok","service":"Adaptive Cache System","version":"0.1.0"}

# Verify Backend Prometheus Metrics Exposer
curl -s http://localhost:8000/metrics | grep requests_total

# Verify Streamlit Frontend
curl -I -s http://localhost:8501/_stcore/health | grep "HTTP/1.1 200"

# Verify Redis
docker exec adaptive-redis redis-cli ping
# Output: PONG

# Verify PostgreSQL
docker exec adaptive-postgres pg_isready -U postgres -d adaptive_cache
# Output: adaptive_cache:5432 - accepting connections

# Verify Prometheus Server
curl -s http://localhost:9090/-/healthy
# Output: Prometheus Server is Healthy.

# Verify Grafana
curl -s http://localhost:3000/api/health
# Output: {"commit":"...","database":"ok","version":"11.1.0"}
```

### Inspecting Compose Logs
To follow live logs from any container:

```bash
# Follow all container logs
docker compose logs -f

# Follow a specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f prometheus
```

---

## 3. Create or Start the Minikube Cluster

When deploying to Kubernetes, initiate a Minikube cluster with sufficient compute resources and the **metrics-server** addon enabled (required for HPA autoscaling):

```bash
minikube start \
  --cpus=4 \
  --memory=8192 \
  --driver=docker \
  --addons=metrics-server
```

Validate cluster availability:

```bash
minikube status
kubectl get nodes
kubectl top nodes
```

---

## 4. Build Docker Images

Build the backend and frontend images from the **repository root** so that the shared data contracts (`contracts/`) and UI configurations (`.streamlit/`) are included in the build context:

```bash
# Build Backend image
docker build -t hackathon-backend:latest -f backend/Dockerfile .

# Build Frontend image
docker build -t hackathon-frontend:latest -f frontend/Dockerfile .
```

---

## 5. Load or Build Images Inside Minikube Correctly

### Host Docker vs. Minikube Docker Daemon

When using the `docker` driver for Minikube, Minikube runs inside an isolated container with its own internal Docker daemon. Images built on your host machine are not visible to Minikube by default. If Kubernetes attempts to run a pod pointing to `hackathon-backend:latest` without the image in Minikube's daemon, the pod fails with `ErrImagePull` or `ImagePullBackOff`.

You can make images available to Minikube using either of the following two approaches:

### Option A: Build Directly Inside Minikube (Recommended & Fastest)
Point your shell's Docker client to Minikube's internal Docker daemon:

```bash
# Direct shell to use Minikube's Docker daemon
eval $(minikube docker-env)

# Build images directly into Minikube's image store
docker build -t hackathon-backend:latest -f backend/Dockerfile .
docker build -t hackathon-frontend:latest -f frontend/Dockerfile .

# Revert shell back to host Docker when finished
eval $(minikube docker-env -u)
```

### Option B: Load Host Images into Minikube
If you already built the images on your host Docker engine:

```bash
minikube image load hackathon-backend:latest
minikube image load hackathon-frontend:latest
```

### Verify Images Inside Minikube
Verify that Minikube has access to both application images:

```bash
minikube image ls | grep hackathon
# Output must show:
# docker.io/library/hackathon-backend:latest
# docker.io/library/hackathon-frontend:latest
```

---

## 6. Deploy the Application to Kubernetes

You can deploy the application tier using either the raw Kubernetes manifests (`k8s/`) or the parameterized Helm chart (`helm/adaptive-cache/`).

### Approach A: Deploy via Raw Kubernetes Manifests (`k8s/`)

Deploy resources in topological dependency order:

```bash
# 1. Deploy PostgreSQL (Secret, PVC, Deployment, Service)
kubectl apply -f k8s/postgres/secret.yaml
kubectl apply -f k8s/postgres/pvc.yaml
kubectl apply -f k8s/postgres/deployment.yaml
kubectl apply -f k8s/postgres/service.yaml

# 2. Deploy Redis (Deployment, Service)
kubectl apply -f k8s/redis/deployment.yaml
kubectl apply -f k8s/redis/service.yaml

# Wait for databases to become ready
kubectl rollout status deployment/postgres --timeout=90s
kubectl rollout status deployment/redis --timeout=60s

# 3. Deploy Backend (ConfigMap, Deployment, Service, HPA)
kubectl apply -f k8s/backend/configmap.yaml
kubectl apply -f k8s/backend/deployment.yaml
kubectl apply -f k8s/backend/service.yaml
kubectl apply -f k8s/backend/hpa.yaml

# Wait for backend pods to become ready
kubectl rollout status deployment/backend --timeout=90s

# 4. Deploy Frontend (ConfigMap, Deployment, Service)
kubectl apply -f k8s/frontend/configmap.yaml
kubectl apply -f k8s/frontend/deployment.yaml
kubectl apply -f k8s/frontend/service.yaml

# Wait for frontend pod to become ready
kubectl rollout status deployment/frontend --timeout=90s
```

### Approach B: Deploy via Helm Chart (`helm/adaptive-cache/`)

Alternatively, deploy the complete application stack with one Helm command:

```bash
helm upgrade --install adaptive-cache helm/adaptive-cache \
  --set backend.image.pullPolicy=Never \
  --set frontend.image.pullPolicy=Never
```

---

## 7. Deploy or Update the Helm Monitoring Stack

Deploy the Prometheus Operator and Grafana monitoring stack via `kube-prometheus-stack` into the `monitoring` namespace:

```bash
# 1. Add and update Prometheus community chart repository
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 2. Create the monitoring namespace
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# 3. Install or upgrade kube-prometheus-stack
helm upgrade --install adaptive-monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --set grafana.sidecar.dashboards.enabled=true \
  --set grafana.sidecar.dashboards.searchNamespace=ALL \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false

# 4. Apply the pre-built Grafana Dashboard ConfigMap (auto-imported by sidecar)
kubectl apply -f k8s/monitoring/dashboard-configmap.yaml

# 5. Apply the ServiceMonitor to scrape backend /metrics every 5 seconds
kubectl apply -f k8s/monitoring/service-monitor.yaml
```

Wait for the monitoring stack to become fully ready:

```bash
kubectl rollout status deployment/adaptive-monitoring-grafana -n monitoring --timeout=120s
```

---

## 8. Verify All Kubernetes Pods and Services

Confirm that all application and monitoring components are running cleanly:

```bash
# Check default namespace application pods
kubectl get pods -o wide

# Expected pods:
# backend-xxxx-xxxx     Running (2/2 replicas)
# backend-xxxx-yyyy     Running
# frontend-xxxx-xxxx    Running (1/1 replica)
# postgres-xxxx-xxxx    Running (1/1 replica)
# redis-xxxx-xxxx       Running (1/1 replica)

# Check monitoring pods
kubectl get pods -n monitoring

# Check services
kubectl get services
kubectl get services -n monitoring

# Check Horizontal Pod Autoscaler status
kubectl get hpa backend
# Output should show: TARGETS: 0%/50% (or current CPU), MINPODS: 2, MAXPODS: 6
```

### Kubernetes Service Liveness Checks

```bash
# Check backend pod logs
kubectl logs deployment/backend -c backend --tail=20

# Check frontend pod logs
kubectl logs deployment/frontend -c frontend --tail=20

# Test Redis via pod execution
kubectl exec deployment/redis -c redis -- redis-cli ping
# Output: PONG

# Test PostgreSQL via pod execution
kubectl exec deployment/postgres -c postgres -- pg_isready -U postgres -d adaptive_cache
# Output: adaptive_cache:5432 - accepting connections
```

---

## 9. Port-Forward Services

To access Kubernetes services from your local browser and CLI, open port-forward tunnels in separate terminal tabs (or in the background):

```bash
# 1. Port-forward FastAPI Backend (Port 8000)
kubectl port-forward svc/backend 8000:8000

# 2. Port-forward Streamlit Frontend (Port 8501)
kubectl port-forward svc/frontend 8501:8501

# 3. Port-forward Prometheus Server (Port 9090)
kubectl port-forward -n monitoring svc/adaptive-monitoring-kube-p-prometheus 9090:9090

# 4. Port-forward Grafana (Port 3000)
kubectl port-forward -n monitoring svc/adaptive-monitoring-grafana 3000:80
```

> **Note**: For Docker Compose, port-forwarding is not required because ports `8000`, `8501`, `9090`, and `3000` are already bound to `0.0.0.0` on the host.

---

## 10. Test Health Endpoints

Verify connectivity to the running backend:

```bash
# Root API discovery endpoint
curl -s http://localhost:8000/ | python3 -m json.tool

# Health probe endpoint
curl -s http://localhost:8000/health
# Output: {"status":"ok","service":"Adaptive Cache System","version":"0.1.0"}

# Prometheus metrics exposition
curl -s http://localhost:8000/metrics | head -n 30
```

---

## 11. Test Product and Recommendation Endpoints

Generate traffic and observe cache HIT vs. MISS dynamics:

### Product Endpoint (`/data/product/{id}`)
Simulates read-heavy catalog items.

```bash
# First request: Cache MISS -> retrieves from origin (~30ms) -> stores in cache
curl -i -s http://localhost:8000/data/product/101

# Second request: Cache HIT -> served instantly from cache (0ms origin time)
curl -i -s http://localhost:8000/data/product/101
```

### Recommendation Endpoint (`/data/recommendation/{id}`)
Simulates compute-heavy personalized payloads with high origin latency (~600ms).

```bash
# First request: Cache MISS -> heavy origin computation (~600ms)
curl -i -s http://localhost:8000/data/recommendation/user42

# Second request: Cache HIT -> returns immediately from cache
curl -i -s http://localhost:8000/data/recommendation/user42
```

### Cache Inspection & Invalidation Endpoints
```bash
# List all resident cache objects, access counts, and sizes
curl -s http://localhost:8000/cache/objects | python3 -m json.tool

# Invalidate a specific product key
curl -X DELETE -s http://localhost:8000/data/product/101

# Trigger live adaptive decision evaluation
curl -s http://localhost:8000/adaptive/runtime-decision | python3 -m json.tool

# View decision history
curl -s http://localhost:8000/adaptive/decisions | python3 -m json.tool
```

---

## 12. Run k6 Workload Scenarios

Run k6 performance and adaptive tests against `http://localhost:8000` (works against both Docker Compose and port-forwarded Kubernetes):

### 12.1 Steady State Traffic
Validates baseline sustained throughput (10 Virtual Users):

```bash
k6 run -e BASE_URL=http://localhost:8000 k6/scenarios/steady.js
```

### 12.2 Popularity Shift Traffic
Simulates shifting popularity between disjoint sets of keys (`PRODUCTS_A` vs `PRODUCTS_B`), exercising the closed-loop eviction and adaptive scoring engine:

```bash
k6 run -e BASE_URL=http://localhost:8000 k6/scenarios/popularity-shift.js
```

### 12.3 Traffic Surge (Triggers Kubernetes HPA Autoscaling)
Drives heavy concurrency (80 Virtual Users) to generate CPU pressure and force HPA scale-up:

```bash
k6 run --vus 80 --duration 45s \
  -e BASE_URL=http://localhost:8000 \
  -e TARGET_PATH=/data/product/1 \
  -e SLEEP_SECONDS=0.005 \
  k6/scenarios/spike.js
```

---

## 13. Watch HPA and Pod Resource Usage

While the spike load test runs, observe Kubernetes Horizontal Pod Autoscaler and pod metrics in real time:

```bash
# Watch HPA replica and CPU target status
kubectl get hpa backend --watch

# In another terminal, watch pod resource utilization
watch kubectl top pods -l app=backend
```

### Observed Lifecycle Output

```text
# Initial state (idle):
NAME      REFERENCE            TARGETS   MINPODS   MAXPODS   REPLICAS   AGE
backend   Deployment/backend   5%/50%    2         6         2          10m

# Spike test starts -> CPU spikes past 50%:
backend   Deployment/backend   148%/50%  2         6         4          11m
backend   Deployment/backend   152%/50%  2         6         6          12m

# Spike test completes -> CPU drops below target:
backend   Deployment/backend   4%/50%    2         6         6          13m

# 60s stabilization window completes -> HPA scales down:
backend   Deployment/backend   4%/50%    2         6         3          14m
backend   Deployment/backend   4%/50%    2         6         2          15m
```

---

## 14. Open Dashboards

Access the web interfaces in your browser:

| Dashboard | URL | Default Credentials | Description |
| :--- | :--- | :--- | :--- |
| **Streamlit Control Center** | `http://localhost:8501` | None | Interactive cache monitor, traffic simulator, and decision viewer |
| **FastAPI Swagger Docs** | `http://localhost:8000/docs` | None | Interactive OpenAPI specification and test console |
| **Prometheus Web Console** | `http://localhost:9090` | None | Raw PromQL metric graphs and scrape target status |
| **Grafana Monitoring** | `http://localhost:3000` | `admin` / `admin` | Auto-provisioned "Adaptive Cache System" 4-row dashboard |

### Viewing the Pre-Provisioned Grafana Dashboard
1. Open `http://localhost:3000` in your browser.
2. Log in with Username `admin` and Password `admin` (skip password change if prompted).
3. Navigate to **Dashboards** $\to$ select **"Adaptive Cache System"** (`adaptive-cache-dashboard`).
4. Observe real-time panels across:
   - **APPLICATION**: Request rates, P95 latencies, error percentages, backend origin latency.
   - **CACHE**: Live hit ratio gauge (red/yellow/green), hit/miss rates, memory footprint, evictions.
   - **ADAPTIVE CONTROLLER**: Decision rates, origin pressure, prevented backend calls.
   - **KUBERNETES SCALING**: Running backend pod count, aggregated CPU %, memory usage, and HPA desired vs. available replicas.

---

## 15. Stop and Clean Up the Environment

### Stopping Docker Compose
```bash
# Stop containers while preserving persistent volumes
docker compose down

# Stop containers and wipe database/grafana volumes (clean reset)
docker compose down -v
```

### Stopping Kubernetes Deployment
```bash
# Delete application resources
kubectl delete -f k8s/frontend/
kubectl delete -f k8s/backend/
kubectl delete -f k8s/redis/
kubectl delete -f k8s/postgres/

# Or delete via Helm if deployed with Helm:
helm uninstall adaptive-cache

# Delete monitoring stack and namespace
helm uninstall adaptive-monitoring -n monitoring
kubectl delete namespace monitoring

# Stop Minikube cluster
minikube stop

# (Optional) Completely delete Minikube cluster VM
minikube delete
```
