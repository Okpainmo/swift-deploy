# Swift Deploy

> A lightweight, declarative infrastructure tool that turns a single manifest.yaml into a fully running containerized stack.

`swiftdeploy` is a small declarative deployment tool. You describe the stack once in `manifest.yaml`, then on running the respective CLI commands, it(the CLI) is able to generate `nginx.conf` and `docker-compose.yml` from provided customizable templates, start the respective containers, switch release modes, and also tear the stack down - respectively.

The manifest is the source of truth. Generated files can be recreated with:

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

## Practical Use Cases.

At its heart, SwiftDeploy is:

> **A declarative → generated → reproducible deployment system**

That pattern shows up everywhere - from **Terraform** to internal platform tools at big companies.

### 1. Ephemeral Dev Environments(Per Feature Branch)

#### Problem

Developers need isolated environments for testing features.

#### How SwiftDeploy Solves It

Each developer writes:

```yaml
services:
  image: myapp:feature-xyz
  port: 3000

mode: canary
```

Then runs:

```bash
./swiftdeploy init
```

```bash
./swiftdeploy deploy
```

#### Result

* Spin up **isolated environments instantly**
* No manual Nginx/Docker setup
* Easy teardown after testing

This is how companies simulate **preview environments**.

### 2. Canary Deployments Without Kubernetes

#### Problem

You want safe rollouts but don’t have Kubernetes.

#### How SwiftDeploy Solves It

```bash
./swiftdeploy promote canary
```

#### Real usage

* Deploy new version in **canary mode**
* Introduce failures with `/chaos`
* Observe logs + behavior
* Roll back:

```bash
./swiftdeploy promote stable
```

This mimics production patterns used in:

* load balancers
* service meshes

### 3. Internal Platform Tooling (Platform Engineering)

#### Problem

Teams keep rewriting:

* Docker Compose configs
* Nginx configs
* deployment scripts

#### SwiftDeploy becomes:

> A **company-wide deployment standard**

Instead of:

> “Hey DevOps, how do I deploy this?”

They do:

```yaml
manifest.yaml
```

Then:

```bash
./swiftdeploy init
```

```bash
./swiftdeploy deploy
```

This is exactly what internal tools at companies replace:

* raw Docker usage
* inconsistent setups

### 4. Onboarding New Engineers

#### Problem

New devs struggle to set up local infra.

#### With SwiftDeploy:

```bash
git clone repo

./swiftdeploy init

./swiftdeploy deploy
```

Done.

No need to explain:

* Nginx configs
* ports
* Docker networking

This reduces onboarding time drastically.

### 5. Chaos Testing & Resilience Validation

SwiftDeploy's demo API contains:

```http
POST /chaos
```

#### Real-world use

Simulate:

* slow services
* random failures

Test:

* retry logic
* timeouts
* monitoring alerts

This is similar to tools like:

* Chaos Monkey(Netflix)

### 6. Standardized Logging & Observability Entry Point

SwiftDeploy Nginx enforces:

```txt
$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request
```

#### Why this matters

In real systems:

* logs are inconsistent
* debugging is painful

SwiftDeploy enforces:

* uniform logs
* traceable requests

This becomes the foundation for:

* monitoring pipelines
* log aggregation (ELK, Loki)

### 7. Reproducible Infrastructure (No Config Drift)

#### Problem

Manual config changes break environments.

#### SwiftDeploy approach:

```txt
manifest.yaml → always regenerates everything
```

#### Result

* Delete configs → regenerate → same system
* No “it works on my machine” issues

This is **exactly** why Terraform exists.

### 8. CI/CD Integration (Next Level)

You can plug this into CI:

```bash
./swiftdeploy validate
./swiftdeploy deploy
```

#### Use case

* Run integration tests in CI
* Spin up full stack temporarily
* Tear it down after

Lightweight alternative to full cloud environments.

### 9. Microservice Sandbox

If you extend your manifest:

```yaml
services:
  - auth
  - payments
  - analytics
```

You now have:

> A **mini orchestrator for microservices**

Useful for:

* local testing
* architecture experiments
* demos

### 10. Foundation for Bigger Tools

SwiftDeploy is basically like a **proto version** of:

* Helm(templating configs)
* Docker Compose(service orchestration)
* Terraform(declarative infra)

## Where this shines (and where it doesn’t)

### Great for:

* Local environments
* Small teams
* Internal tools
* POCs
* Learning infra design

### Not enough for:

* large-scale production
* auto-scaling
* distributed systems
* multi-region deployments

## Leveling Up.

You might wish to extend SwiftDeploy into a tool for:

* remote deployment (SSH)
* secrets management
* multi-service orchestration
* CI/CD integration
* monitoring hooks (Prometheus)

**Contributions and welcomed.**

Cheers!!!
