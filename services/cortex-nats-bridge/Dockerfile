FROM golang:1.22.3-alpine AS builder
WORKDIR /src
COPY go.mod ./
COPY . .
RUN go mod tidy
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/cortex-nats-bridge .

FROM alpine:3.20
WORKDIR /app
COPY --from=builder /out/cortex-nats-bridge /usr/local/bin/cortex-nats-bridge
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/cortex-nats-bridge"]
