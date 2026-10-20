# Builds the React client and serves it with Nginx, which also reverse-proxies the APIs.
# Build context: apps/web.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.js ./
COPY src ./src
# Empty = same origin: the browser calls /api/... on this Nginx.
ARG VITE_GATEWAY_URL=""
ENV VITE_GATEWAY_URL=$VITE_GATEWAY_URL
# Where students are sent after signing in (the student dashboard container).
ARG VITE_STUDENT_DASHBOARD_URL=""
ENV VITE_STUDENT_DASHBOARD_URL=$VITE_STUDENT_DASHBOARD_URL
RUN npm run build

FROM nginx:1.27-alpine
# Rendered to /etc/nginx/conf.d/default.conf at start, with the backend addresses below (Docker defaults).
COPY nginx.conf /etc/nginx/templates/default.conf.template
ENV API_URL=http://api:8000 GATEWAY_URL=http://gateway:8080 FLOW_URL=http://patient-flow:8090 \
    NOTIFY_URL=http://notifications:8095 PROXY_TIMEOUT=15s
COPY --from=build /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/healthz || exit 1
