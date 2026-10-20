FROM golang:1.26-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY cmd ./cmd
COPY internal ./internal
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/patient-flow ./cmd/patient-flow

FROM alpine:3.20
# CA certificates: needed for https calls (JWKS, Django) and TLS to managed databases like Neon.
RUN apk add --no-cache ca-certificates tzdata
RUN adduser -D -H flow
COPY --from=build /out/patient-flow /usr/local/bin/patient-flow
USER flow
EXPOSE 8090
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 CMD wget -qO- http://127.0.0.1:8090/healthz || exit 1
ENTRYPOINT ["patient-flow"]
