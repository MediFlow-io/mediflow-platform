FROM golang:1.22-alpine AS build
WORKDIR /app
COPY go.mod ./

COPY . .
RUN go build -o gateway .
FROM alpine:latest
WORKDIR /app
COPY --from=build /app/gateway .
EXPOSE 8080
CMD ["./gateway"]

