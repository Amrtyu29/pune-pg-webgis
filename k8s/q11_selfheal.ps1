# Q11 experiment: delete the PostGIS pod and time its return; check whether data survives.
#   powershell -ExecutionPolicy Bypass -File k8s\q11_selfheal.ps1 -Label pvc
#   powershell -ExecutionPolicy Bypass -File k8s\q11_selfheal.ps1 -Label emptydir
# Writes docs/outputs/q11_<label>.txt with every "kubectl get pods -w" line prefixed by a wall-clock timestamp.
param([string]$Label = "pvc")
$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
$out = Join-Path $root "docs\outputs\q11_$Label.txt"
$ns = "punepg"

function Stamp($s) { "$(Get-Date -Format 'HH:mm:ss.fff')  $s" }

$log = @()
$log += Stamp "== Q11 run '$Label' =="
$log += Stamp "waiting for postgis-0 to be Ready"
kubectl -n $ns wait --for=condition=ready pod/postgis-0 --timeout=300s | Out-Null

# 1. write a marker row BEFORE the deletion (the thing that should survive)
$log += Stamp "writing marker table q11_marker"
kubectl -n $ns exec postgis-0 -- sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE TABLE IF NOT EXISTS q11_marker(created timestamptz DEFAULT now(), note text); INSERT INTO q11_marker(note) VALUES (''written before pod deletion'');"' | Out-Null
$before = kubectl -n $ns exec postgis-0 -- sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT count(*) FROM q11_marker"'
$log += Stamp "rows in q11_marker before deletion: $before"
$uidBefore = kubectl -n $ns get pod postgis-0 -o jsonpath='{.metadata.uid}'
$log += Stamp "pod uid before: $uidBefore"

# 2. start the watcher (kubectl get pods -w) in a background job that stamps every line
$job = Start-Job -ScriptBlock {
    param($ns)
    kubectl -n $ns get pods -w --no-headers -l app=postgis | ForEach-Object { "$(Get-Date -Format 'HH:mm:ss.fff')  $_" }
} -ArgumentList $ns
Start-Sleep 2

# 3. delete the pod and time until it is Running and Ready again
$t0 = Get-Date
$log += Stamp "kubectl delete pod postgis-0"
kubectl -n $ns delete pod postgis-0 | Out-Null
$log += Stamp "delete command returned"
kubectl -n $ns wait --for=condition=ready pod/postgis-0 --timeout=300s | Out-Null
$t1 = Get-Date
$log += Stamp ("postgis-0 Ready again after {0:N1} s" -f ($t1 - $t0).TotalSeconds)
Start-Sleep 3
Stop-Job $job | Out-Null
$watch = Receive-Job $job
Remove-Job $job | Out-Null

# 4. did the data survive?
$uidAfter = kubectl -n $ns get pod postgis-0 -o jsonpath='{.metadata.uid}'
$after = kubectl -n $ns exec postgis-0 -- sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "SELECT count(*) FROM q11_marker" 2>&1'
$log += Stamp "pod uid after:  $uidAfter  (new pod object: $($uidBefore -ne $uidAfter))"
$log += Stamp "rows in q11_marker after recreation: $after"
$log += ""
$log += "---- kubectl get pods -w (timestamped) ----"
$log += $watch
$log += ""
$log += "---- volumes of the pod ----"
$log += (kubectl -n $ns get pod postgis-0 -o jsonpath='{.spec.volumes}')
$log += ""
$log += (kubectl -n $ns get pvc 2>&1)
$log | Out-File -FilePath $out -Encoding utf8
$log
"saved -> $out"
