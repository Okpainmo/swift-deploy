# Swift Deploy

`swiftdeploy` is a declarative deployment orchestration tool that generates and manages an entire containerized application stack from a single `manifest.yaml` source of truth.

The project combines infrastructure automation, reverse proxy configuration, observability, policy enforcement, and deployment lifecycle management into a unified CLI-driven platform. Rather than manually writing infrastructure files, operators define the desired deployment state in a manifest, while `swiftdeploy` dynamically generates and manages Docker Compose, Nginx, monitoring, and policy configurations automatically.

The platform supports:

- Declarative infrastructure generation

- Automated stack deployment and teardown

- Canary and stable deployment modes

- Health checks and chaos testing

- Prometheus-style metrics instrumentation

- Real-time operational status monitoring

- Open Policy Agent (OPA) powered deployment guardrails

- Policy-gated promotions and deployments

- Audit logging and historical reporting

`swiftdeploy` demonstrates modern DevOps and SRE practices including Infrastructure as Code (IaC), Policy-as-Code, observability, progressive delivery, and operational auditing within a lightweight self-managed platform.

## Overall Architecture

```text
manifest.yaml
      ↓
swiftdeploy
      ↓
generated infrastructure
      ↓
Docker Compose
 ├── App
 ├── Nginx
 └── OPA
      ↓
Metrics + Policies
      ↓
Safe deployment decisions
      ↓
Audit history
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
templates/*.rego.tpl           # OPA policy templates generated into policies/
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

`init` also generates `policies/infrastructure.rego` and
`policies/canary.rego`. Policy thresholds live in `manifest.yaml`; the Rego files
contain only decision logic.

Run the local pre-flight checks:

```bash
./swiftdeploy validate
```

`validate` checks that:

- `manifest.yaml` exists and parses as YAML
- required fields are present and non-empty
- the service Docker image exists locally
- the configured Nginx host port is free
- generated `nginx.conf` passes `nginx -t`

`deploy` goes further than validation: it starts OPA, sends live host stats to the
infrastructure policy, blocks unsafe deploys, starts the public stack, and waits
for `/healthz` to pass through Nginx.

## Deploy

```bash
./swiftdeploy deploy
```

`deploy` runs `init`, starts the OPA policy sidecar, asks the infrastructure
policy whether the host is safe, starts the stack with `docker compose up -d`,
then waits up to 60 seconds for `/healthz` to pass through Nginx.

The CLI surfaces the OPA reason and blocks on violations such as low disk space
or high CPU load.

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

Before promotion, `swiftdeploy` scrapes `/metrics`, calculates error rate and P99
latency, asks OPA's canary policy for a reasoned decision, and blocks unhealthy
canaries.

## Metrics, Status, and Audit

The API exposes Prometheus text metrics at:

```bash
curl http://127.0.0.1:8080/metrics
```

Run the live dashboard:

```bash
./swiftdeploy status
```

Each scrape is appended to `history.jsonl`. Generate the Markdown audit report:

```bash
./swiftdeploy audit
```

OPA is reachable by the CLI at the loopback-bound manifest port, for example
`127.0.0.1:8181`, and is not routed through the public Nginx ingress.

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

Example manifest:

```yaml
services:
  image: 'sd-demo-api-1:latest'
  port: 5000
  mode: stable
  version: 1.0.0
  restart_policy: unless-stopped

nginx:
  image: 'nginx:latest'
  port: 8080
  proxy_timeout: 5s
  contact: ops@swiftdeploy.local

network:
  name: swiftdeploy-net
  driver_type: bridge

opa:
  image: 'openpolicyagent/opa:latest'
  port: 8181

policy_infrastructure:
  min_disk_free_gb: 10
  max_cpu_load: 2.0

policy_canary:
  max_error_rate: 0.01
  max_p99_latency_ms: 500
  window_seconds: 30
```

`services`, `nginx`, `network`, and `opa` define the generated runtime stack.
`policy_infrastructure` controls the pre-deploy gate. `policy_canary` controls
the promotion gate that evaluates error rate and P99 latency from `/metrics`.

## Practical Use Cases

At its heart, SwiftDeploy is:

> **A declarative -> generated -> policy-gated -> observable deployment loop**

That pattern shows up everywhere from Terraform and Helm to internal platform
tools that standardize how teams ship software.

### 1. Ephemeral Dev Environments

#### Problem

Developers need isolated environments for testing features.

#### How SwiftDeploy Solves It

Each developer writes:

```yaml
services:
  image: myapp:feature-xyz
  port: 3000
  mode: stable
```

Then runs:

```bash
./swiftdeploy init
```

```bash
./swiftdeploy deploy
```

#### Result

- Spin up isolated environments quickly
- Avoid manual Nginx and Docker networking setup
- Tear everything down after testing

This is how companies simulate **preview environments**.

### 2. Canary Deployments Without Kubernetes

#### Problem

You want safe rollouts but don’t have Kubernetes.

#### How SwiftDeploy Solves It

```bash
./swiftdeploy promote canary
```

#### Real usage

- Promote the app into canary mode
- Inject slow responses or random failures with `/chaos`
- Watch metrics, policy status, and Nginx logs
- Return to stable:

```bash
./swiftdeploy promote stable
```

This mimics rollout patterns commonly handled by load balancers, service meshes,
or platform release tooling.

### 3. Internal Platform Tooling (Platform Engineering)

#### Problem

Teams keep rewriting:

- Docker Compose configs
- Nginx configs
- deployment scripts

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

SwiftDeploy gives those teams a single command surface instead of raw Docker
usage, hand-written proxy configs, and inconsistent setup notes.

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

No need to explain Nginx configs, container ports, Docker networking, policy
files, or health checks before someone can see the system running.

This reduces onboarding time and gives new engineers a concrete model of the
deployment flow.

### 5. Chaos Testing & Resilience Validation

SwiftDeploy's demo API contains:

```http
POST /chaos
```

#### Real-world use

Simulate:

- slow services
- random failures

Test:

- retry logic
- timeouts
- monitoring alerts

This is the same family of thinking as resilience tools like Netflix's Chaos
Monkey, scaled down into a small local demo.

### 6. Standardized Logging & Observability Entry Point

SwiftDeploy Nginx enforces:

```txt
$time_iso8601 | $status | ${request_time}s | $upstream_addr | $request
```

#### Why this matters

In real systems:

- logs are inconsistent
- debugging is painful

SwiftDeploy enforces:

- uniform logs
- traceable requests

This becomes the foundation for:

- monitoring pipelines
- log aggregation (ELK, Loki)

### 7. Reproducible Infrastructure (No Config Drift)

#### Problem

Manual config changes break environments.

#### SwiftDeploy approach:

```txt
manifest.yaml → always regenerates everything
```

#### Result

- Delete generated configs, regenerate them, and get the same system back
- Keep the manifest as the reviewable source of truth
- Reduce "it works on my machine" drift

This is the same core reason tools like Terraform and Helm exist: the desired
state should be declared once and regenerated consistently.

### 8. CI/CD Integration

You can plug this into CI:

```bash
./swiftdeploy validate
./swiftdeploy deploy
```

#### Use case

- Run integration tests in CI
- Spin up full stack temporarily
- Tear it down after

It can be a lightweight alternative to full cloud environments for integration
tests, demos, and policy checks.

### 9. Microservice Sandbox Direction

The current manifest models one app behind Nginx, but the same design can grow
into multi-service orchestration. A future manifest could describe:

```yaml
services:
  - auth
  - payments
  - analytics
```

That would turn SwiftDeploy into a mini orchestrator for local microservice
sandboxes.

Useful for:

- local testing
- architecture experiments
- demos

### 10. Foundation for Bigger Tools

SwiftDeploy is a compact prototype of ideas from:

- Helm for templating runtime config
- Docker Compose for service orchestration
- Terraform for declarative infrastructure thinking
- OPA for policy-as-code gates
- Prometheus-style metrics for deploy decisions

## Where this shines (and where it doesn’t)

### Great for:

- Local environments
- Small teams
- Internal tools
- POCs
- Learning infrastructure design
- Demonstrating policy-gated deployment and canary workflows

### Not enough for:

- large-scale production
- auto-scaling
- distributed scheduling
- multi-region deployments
- secrets rotation

## Leveling Up

You might wish to extend SwiftDeploy into a tool for:

- remote deployment over SSH
- secrets management
- multi-service orchestration
- CI/CD integration
- Prometheus scraping and alert hooks
- rollback semantics that bypass unhealthy canary gates

**Contributions are welcome.**

Cheers!!!
