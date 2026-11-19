# Creates (or replaces) the postgis-secret in the punepg namespace from the repo's .env file,
# so the password is never written into a committed manifest.
#   powershell -ExecutionPolicy Bypass -File k8s\make-secret.ps1
$root = Split-Path $PSScriptRoot -Parent
$env_ = @{}
Get-Content (Join-Path $root ".env") | ForEach-Object {
    if ($_ -match '^\s*([A-Z_]+)\s*=\s*(.*)\s*$') { $env_[$matches[1]] = $matches[2].Trim('"').Trim("'") }
}
kubectl create namespace punepg --dry-run=client -o yaml | kubectl apply -f -
kubectl -n punepg create secret generic postgis-secret `
    --from-literal=POSTGRES_USER=$($env_['POSTGRES_USER']) `
    --from-literal=POSTGRES_PASSWORD=$($env_['POSTGRES_PASSWORD']) `
    --from-literal=POSTGRES_DB=$($env_['POSTGRES_DB']) `
    --dry-run=client -o yaml | kubectl apply -f -
kubectl -n punepg get secret postgis-secret
