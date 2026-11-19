# Multi-stage build for the MapLibre client.
#
# Stage 1 "builder" (node:20, ~1.1 GB): fetches the exact MapLibre GL JS and PMTiles releases from npm and
#   copies the browser bundles next to our HTML/JS, so the page needs no CDN.
# Stage 2 "runtime" (nginx:alpine, ~50 MB): gets ONLY the finished /site folder. Node, npm and node_modules
#   never reach the final image, which is why it is 20x smaller than the single-stage version (see Q10).
#
#   docker build -t punepg-client:local client/
#   docker run --rm -p 8088:80 punepg-client:local      -> http://localhost:8088

FROM node:20 AS builder
WORKDIR /build
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY index.html app.js config.js style.css ./
# optional static data for the GitHub Pages / kind copies (ignored if the folder is empty)
COPY data/ ./data/
RUN mkdir -p site/vendor \
 && cp index.html app.js config.js style.css site/ \
 && cp -r data site/ \
 && cp node_modules/maplibre-gl/dist/maplibre-gl.js  site/vendor/ \
 && cp node_modules/maplibre-gl/dist/maplibre-gl.css site/vendor/ \
 && cp node_modules/pmtiles/dist/pmtiles.js          site/vendor/

FROM nginx:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /build/site /usr/share/nginx/html
EXPOSE 80
