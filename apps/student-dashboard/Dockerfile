# Builds the student dashboard and serves it with Nginx, which also proxies the APIs.
# Build context: apps/student-dashboard. Vite 8 needs Node 20.19+ / 22.12+.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js eslint.config.js ./
COPY public ./public
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine
# Rendered to /etc/nginx/conf.d/default.conf at start, with the backend addresses below (Docker defaults).
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV API_URL=http://api:8000 GATEWAY_URL=http://gateway:8080 FLOW_URL=http://patient-flow:8090 \
    NOTIFY_URL=http://notifications:8095 PROXY_TIMEOUT=15s
COPY --from=build /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/healthz || exit 1
