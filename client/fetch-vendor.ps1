# Local development without Docker: copy the MapLibre / PMTiles browser bundles into client/vendor
# (the Dockerfile and the GitHub Action do the same with npm). Then open the folder with any static server:
#   powershell -ExecutionPolicy Bypass -File client\fetch-vendor.ps1
#   ..\.venv\Scripts\python.exe -m http.server 8088 --directory client
$here = $PSScriptRoot
Push-Location $here
npm install --no-audit --no-fund
New-Item -ItemType Directory -Force vendor | Out-Null
Copy-Item node_modules\maplibre-gl\dist\maplibre-gl.js  vendor\
Copy-Item node_modules\maplibre-gl\dist\maplibre-gl.css vendor\
Copy-Item node_modules\pmtiles\dist\pmtiles.js          vendor\
Pop-Location
Get-ChildItem (Join-Path $here vendor)
