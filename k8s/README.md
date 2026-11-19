# Kubernetes manifests (Phase 5, Part B: local kind cluster)

```powershell
kind create cluster --name punepg
powershell -ExecutionPolicy Bypass -File k8s\make-secret.ps1      # Secret from .env, never committed
kubectl apply -f k8s/                                             # namespace, PostGIS StatefulSet + PVC + Service, client Deployment + Service
docker build -t punepg-client:local client/                       # multi-stage image
kind load docker-image punepg-client:local --name punepg          # hand the local image to the kind node
kubectl -n punepg get pods -w                                     # wait for postgis-0 and client-* to be Running / Ready
kubectl -n punepg port-forward svc/client 8088:80                 # open http://localhost:8088
```

Files

| File | Object(s) | Why |
|---|---|---|
| `00-namespace.yaml` | Namespace `punepg` | one place for everything |
| `10-postgis-secret.example.yaml` | Secret (example values) | the real one comes from `make-secret.ps1` |
| `20-postgis-statefulset.yaml` | headless Service + StatefulSet + PVC template | database with a disk that follows the pod |
| `30-client-deployment.yaml` | Deployment + ClusterIP Service | stateless nginx client |
| `experiments/postgis-emptydir.yaml` | StatefulSet with `emptyDir` | Q11: show what is lost without a PVC |

`kubectl apply -f k8s/` skips the `experiments/` sub-folder (apply is not recursive), which is intended.
