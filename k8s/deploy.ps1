# One-shot: build the client image, create the kind cluster if needed, load the image, apply the manifests.
#   powershell -ExecutionPolicy Bypass -File k8s\deploy.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

if (-not (kind get clusters 2>$null | Select-String -Quiet '^punepg$')) {
    kind create cluster --name punepg --wait 120s
}
kubectl config use-context kind-punepg | Out-Null

docker build -t punepg-client:local client/
kind load docker-image punepg-client:local --name punepg

powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "make-secret.ps1")
kubectl apply -f (Join-Path $root "k8s")
kubectl -n punepg rollout status statefulset/postgis --timeout=300s
kubectl -n punepg rollout status deployment/client --timeout=300s
kubectl -n punepg get all,pvc,secret
"open the client with:  kubectl -n punepg port-forward svc/client 8089:80   ->  http://localhost:8089"
