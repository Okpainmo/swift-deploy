# Swift Deploy

> A lightweight, declarative infrastructure tool that turns a single manifest.yaml into a fully running containerized stack.

`swiftdeploy` is a small declarative deployment tool. You describe the stack once in `manifest.yaml`, then on running the respective CLI commands, it(the CLI) is able to generate `nginx.conf` and `docker-compose.yml` from provided customizable templates, start the respective containers, switch release modes, and also tear the stack down - respectively.

The manifest is the source of truth. Generated files can be deleted and recreated with:

```bash
./swiftdeploy init
```

## Project Layout

```text
manifest.yaml                  # deployment declaration
swiftdeploy                    # executable Python CLI
Dockerfile                     # FastAPI service image
app/main.py                    # API service
app/requirements.txt           # FastAPI runtime dependencies
templates/nginx.conf.tpl       # Nginx config template
templates/docker-compose.yml.tpl # Docker Compose template
```

## Requirements

- Docker
- Modern Docker Compose: `docker compose`
- Python 3.10+ on the host for the `swiftdeploy` CLI

## Setup

Build the local service image referenced by the manifest:

```bash
docker build -t sd-demo-api-1:latest .
```

Generate the config files:

```bash
./swiftdeploy init
```

Run the five pre-flight checks:

```bash
./swiftdeploy validate
```

`validate` checks that:

- `manifest.yaml` exists and parses as YAML
- required fields are present and non-empty
- the service Docker image exists locally
- the configured Nginx host port is free
- generated `nginx.conf` passes `nginx -t`

## Deploy

```bash
./swiftdeploy deploy
```

`deploy` runs `init`, starts the stack with `docker compose up -d`, then waits up
to 60 seconds for `/healthz` to pass through Nginx.

Test the service:

```bash
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/healthz
```

The app service is not exposed directly. All traffic goes through Nginx.

## Promote

Switch to canary:

```bash
./swiftdeploy promote canary
curl -i http://127.0.0.1:8080/healthz
```

Canary responses include:

```text
X-Mode: canary
```

Use the chaos endpoint in canary mode:

```bash
curl -X POST http://127.0.0.1:8080/chaos \
  -H 'Content-Type: application/json' \
  -d '{"mode":"slow","duration":2}'

curl -X POST http://127.0.0.1:8080/chaos \
  -H 'Content-Type: application/json' \
  -d '{"mode":"error","rate":0.5}'

curl -X POST http://127.0.0.1:8080/chaos \
  -H 'Content-Type: application/json' \
  -d '{"mode":"recover"}'
```

Return to stable:

```bash
./swiftdeploy promote stable
curl http://127.0.0.1:8080/healthz
```

`promote` updates `manifest.yaml`, regenerates `docker-compose.yml`, restarts
only the app container, and confirms the active mode through `/healthz`.

## Logs

Nginx writes access logs to container stdout in the required format:

```text
$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request
```

View them with:

```bash
docker compose logs nginx
```

The Compose stack also defines the named volume `swiftdeploy-logs` for deployment
logs.

## Teardown

Remove containers, networks, and volumes:

```bash
./swiftdeploy teardown
```

Remove generated configs too:

```bash
./swiftdeploy teardown --clean
```

## Manifest

Base required fields(image names and port are alterable):

```yaml
services:
  image: swift-deploy-1-node:latest
  port: 3000

nginx:
  image: nginx:latest
  port: 8080

network:
  name: swiftdeploy-net
  driver_type: bridge
```

Additional fields control mode, version, restart policy, proxy timeout, and the
contact shown in Nginx JSON error responses.
