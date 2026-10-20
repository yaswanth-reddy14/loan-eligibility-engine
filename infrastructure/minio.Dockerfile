FROM golang:1.24.8-alpine AS build
RUN apk add --no-cache git
RUN git clone --depth 1 --branch RELEASE.2025-10-15T17-29-55Z https://github.com/minio/minio.git /source
WORKDIR /source
RUN CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /minio .
FROM alpine:3.21.3
RUN apk add --no-cache ca-certificates curl && adduser -D -u 1001 minio && mkdir /data && chown minio /data
COPY --from=build /minio /usr/local/bin/minio
USER minio
ENTRYPOINT ["minio"]
