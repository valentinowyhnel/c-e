FROM golang:1.22.3 AS build
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/cortex-graph ./main.go

FROM gcr.io/distroless/base-debian12
COPY --from=build /out/cortex-graph /cortex-graph
EXPOSE 8080
ENTRYPOINT ["/cortex-graph"]
