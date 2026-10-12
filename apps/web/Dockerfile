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
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO- http://127.0.0.1/healthz || exit 1
