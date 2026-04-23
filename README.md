# On-Demand Session Manager

A platform for spinning up isolated, per-user application sessions on an existing GKE cluster. Users create sessions through a web UI; behind the scenes, `kubectl` launches a pod from a preconfigured image and creates a unique subdomain URL for access. Users can only see and manage their own sessions. Sessions are fully stateless and automatically terminate after 12 hours.

## Architecture

```
Browser
  │
  ▼
NGINX Ingress Controller (existing LB)
  ├── pcs.lab.twistlock.com/*         → Platform (frontend + API)
  ├── session1.pcs.lab.twistlock.com  → session-{id} Service → Pod
  └── session2.pcs.lab.twistlock.com  → session-{id} Service → Pod

FastAPI Backend
  ├── gcloud get-credentials  → Authenticates to GKE cluster
  ├── kubectl apply           → Creates Pod + Service + Ingress per session
  └── Redis                   → Stores session metadata
```

### Routing

Each session gets its own subdomain. When a user named `alice` launches a session:

1. A Pod, ClusterIP Service, and dedicated Ingress resource are created via `kubectl apply`
2. The Ingress routes `alice.pcs.lab.twistlock.com` to the session's Service
3. The user clicks the URL to access their running application

This requires a **wildcard DNS record** `*.pcs.lab.twistlock.com` pointing to your cluster's ingress load balancer IP.

### Key Design Decisions

| Decision | Implementation |
|---|---|
| **gcloud + kubectl** | Backend shells out to `gcloud container clusters get-credentials` then `kubectl apply/delete` -- no Python K8s client library. |
| **Subdomain routing** | Each session gets `{session_name}.pcs.lab.twistlock.com` via a per-session Ingress resource with a host rule. |
| **No custom images** | Only the server-configured image (`ONDEMAND_SESSION_IMAGE`) is launched. Users cannot override it. |
| **Stateless pods** | `emptyDir` volumes for `/tmp` and `/workspace`. No persistent state survives termination. |
| **12-hour TTL** | `activeDeadlineSeconds=43200` on each pod. Kubernetes kills them automatically. |
| **Session name ownership** | A device cookie (auto-generated UUID) proves identity. Session names are unique and bound to the creating device. |

## Project Structure

```
├── deployment.yaml          Single-file K8s deployment (namespaces, RBAC, platform services)
├── docker-compose.yaml      Local dev: frontend + backend + Redis
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI entrypoint
│   │   ├── config.py             Settings (GCP project, cluster, domain, etc.)
│   │   ├── routers/
│   │   │   ├── auth.py           Session name claim endpoint
│   │   │   └── sessions.py       Session CRUD endpoints
│   │   ├── services/
│   │   │   ├── k8s_manager.py    gcloud/kubectl subprocess calls
│   │   │   └── session_store.py  Redis session storage
│   │   └── models/
│   │       └── session.py        Pydantic models
│   ├── requirements.txt
│   └── Dockerfile              Python 3.12 + gcloud CLI + kubectl
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/sessions.ts
│   │   └── components/
│   ├── nginx.conf
│   ├── package.json
│   └── Dockerfile
└── README.md
```

## Prerequisites

- An existing GKE cluster with an NGINX Ingress controller and load balancer
- Wildcard DNS: `*.pcs.lab.twistlock.com` pointing to the ingress LB IP
- [kubectl](https://kubernetes.io/docs/tasks/tools/) configured to talk to your cluster
- [Docker](https://docs.docker.com/get-docker/) for building images
- A container registry your cluster can pull from (e.g., Artifact Registry)

## Deployment

### 1. Build and Push Container Images

```bash
REPO=us-central1-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPO

docker build -t $REPO/session-backend:latest ./backend
docker push $REPO/session-backend:latest

docker build -t $REPO/session-frontend:latest ./frontend
docker push $REPO/session-frontend:latest
```

### 2. Configure deployment.yaml

Edit the backend environment variables in `deployment.yaml`:

```yaml
env:
  - name: ONDEMAND_GCP_PROJECT
    value: your-gcp-project-id
  - name: ONDEMAND_GCP_CLUSTER
    value: your-gke-cluster-name
  - name: ONDEMAND_GCP_ZONE
    value: us-central1-a
  - name: ONDEMAND_SESSION_DOMAIN
    value: pcs.lab.twistlock.com
  - name: ONDEMAND_SESSION_IMAGE
    value: your-app-image:tag
```

Replace the image placeholders:

```bash
sed -i "s|BACKEND_IMAGE_PLACEHOLDER|$REPO/session-backend:latest|g" deployment.yaml
sed -i "s|FRONTEND_IMAGE_PLACEHOLDER|$REPO/session-frontend:latest|g" deployment.yaml
```

### 3. Deploy

```bash
kubectl apply -f deployment.yaml
```

### 4. Verify

```bash
kubectl get pods -n ondemand-platform
kubectl get ingress -n ondemand-platform
```

## Local Development

```bash
# Edit docker-compose.yaml with your GCP project/cluster/zone
docker compose up --build
```

Opens at `http://localhost:3000`. Requires `~/.config/gcloud` and `~/.kube` for cluster access.

## API Reference

All session endpoints require `X-Device-Id` and `X-Session-Name` headers.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/claim` | Claim a session name (body: `{"session_name": "..."}`) |
| `POST` | `/api/sessions` | Launch a new session pod |
| `GET` | `/api/sessions` | List sessions for the current user |
| `GET` | `/api/sessions/{id}` | Get session status + access URL |
| `DELETE` | `/api/sessions/{id}` | Terminate session (deletes pod, service, ingress) |
| `GET` | `/healthz` | Health check |

## Configuration

Environment variables (prefixed with `ONDEMAND_`):

| Variable | Default | Description |
|---|---|---|
| `ONDEMAND_GCP_PROJECT` | (required) | GCP project ID |
| `ONDEMAND_GCP_CLUSTER` | (required) | GKE cluster name |
| `ONDEMAND_GCP_ZONE` | (required) | GKE cluster zone |
| `ONDEMAND_SESSION_DOMAIN` | `pcs.lab.twistlock.com` | Base domain for subdomain routing |
| `ONDEMAND_SESSION_IMAGE` | `nginx:latest` | Container image for session pods |
| `ONDEMAND_SESSION_PORT` | `80` | Port the session container listens on |
| `ONDEMAND_SESSION_TTL_HOURS` | `12` | Hours before auto-termination |
| `ONDEMAND_SESSION_NAMESPACE` | `user-sessions` | K8s namespace for session pods |
| `ONDEMAND_REDIS_HOST` | `redis` | Redis hostname |
| `ONDEMAND_REDIS_PORT` | `6379` | Redis port |

## What Happens Under the Hood

When a user clicks "Launch New Session":

```
1. POST /api/sessions
   ↓
2. gcloud container clusters get-credentials (once per process)
   ↓
3. kubectl apply -f - << Pod YAML
   (stateless pod with emptyDir, activeDeadlineSeconds=43200)
   ↓
4. kubectl apply -f - << Service YAML
   (ClusterIP service targeting the pod)
   ↓
5. kubectl apply -f - << Ingress YAML
   (host: alice.pcs.lab.twistlock.com → service)
   ↓
6. User gets URL: https://alice.pcs.lab.twistlock.com
```

When the user clicks "Terminate" or the 12h TTL expires:

```
kubectl delete pod,service,ingress session-{id} -n user-sessions
```
