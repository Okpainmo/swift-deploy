import os
import random
import time
import asyncio
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field


STARTED_AT = time.monotonic()
MODE = os.environ.get("MODE", "stable") or "stable"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0") or "1.0.0"
HISTOGRAM_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)
REQUEST_TOTALS = defaultdict(int)
REQUEST_DURATION_BUCKETS = defaultdict(int)
REQUEST_DURATION_SUMS = defaultdict(float)
REQUEST_DURATION_COUNTS = defaultdict(int)

CHAOS = {
    "mode": "recover",
    "duration": 0.0,
    "rate": 0.0,
}

app = FastAPI(title="swiftdeploy API", version=APP_VERSION)


class ChaosRequest(BaseModel):
    mode: str
    duration: float | None = Field(default=None, ge=0)
    rate: float | None = Field(default=None, ge=0, le=1)


@app.middleware("http")
async def canary_headers_and_chaos(request: Request, call_next):
    started = time.monotonic()
    status_code = 500
    path = request.url.path
    try:
        if MODE == "canary" and path != "/chaos":
            if CHAOS["mode"] == "slow":
                await asyncio.sleep(float(CHAOS["duration"]))
            elif CHAOS["mode"] == "error" and random.random() < float(CHAOS["rate"]):
                response = Response(
                    content='{"error":"chaos error","mode":"canary"}',
                    media_type="application/json",
                    status_code=500,
                )
                response.headers["X-Mode"] = "canary"
                status_code = response.status_code
                return response

        response = await call_next(request)
        status_code = response.status_code
        if MODE == "canary":
            response.headers["X-Mode"] = "canary"
        return response
    finally:
        observe_request(request.method, path, status_code, time.monotonic() - started)


def observe_request(method, path, status_code, duration):
    key = (method, path, str(status_code))
    REQUEST_TOTALS[key] += 1
    REQUEST_DURATION_SUMS[key] += duration
    REQUEST_DURATION_COUNTS[key] += 1
    for bucket in HISTOGRAM_BUCKETS:
        if duration <= bucket:
            REQUEST_DURATION_BUCKETS[key + (bucket,)] += 1
    REQUEST_DURATION_BUCKETS[key + ("+Inf",)] += 1


def prometheus_labels(labels):
    return ",".join(f'{key}="{value}"' for key, value in labels.items())


def metric_lines():
    lines = [
        "# HELP http_requests_total Total HTTP requests by method, path, and status code.",
        "# TYPE http_requests_total counter",
    ]
    for (method, path, status_code), count in sorted(REQUEST_TOTALS.items()):
        labels = prometheus_labels(
            {"method": method, "path": path, "status_code": status_code}
        )
        lines.append(f"http_requests_total{{{labels}}} {count}")

    lines.extend(
        [
            "# HELP http_request_duration_seconds HTTP request latency in seconds.",
            "# TYPE http_request_duration_seconds histogram",
        ]
    )
    for method, path, status_code in sorted(REQUEST_DURATION_COUNTS):
        base = {"method": method, "path": path, "status_code": status_code}
        for bucket in HISTOGRAM_BUCKETS:
            labels = prometheus_labels({**base, "le": str(bucket)})
            count = REQUEST_DURATION_BUCKETS[(method, path, status_code, bucket)]
            lines.append(f"http_request_duration_seconds_bucket{{{labels}}} {count}")
        labels = prometheus_labels({**base, "le": "+Inf"})
        count = REQUEST_DURATION_BUCKETS[(method, path, status_code, "+Inf")]
        lines.append(f"http_request_duration_seconds_bucket{{{labels}}} {count}")
        labels = prometheus_labels(base)
        lines.append(
            f"http_request_duration_seconds_sum{{{labels}}} "
            f"{REQUEST_DURATION_SUMS[(method, path, status_code)]:.6f}"
        )
        lines.append(
            f"http_request_duration_seconds_count{{{labels}}} "
            f"{REQUEST_DURATION_COUNTS[(method, path, status_code)]}"
        )

    mode_value = 1 if MODE == "canary" else 0
    chaos_value = {"recover": 0, "slow": 1, "error": 2}.get(CHAOS["mode"], 0)
    lines.extend(
        [
            "# HELP app_uptime_seconds Process uptime in seconds.",
            "# TYPE app_uptime_seconds gauge",
            f"app_uptime_seconds {time.monotonic() - STARTED_AT:.3f}",
            "# HELP app_mode Active deployment mode. 0=stable, 1=canary.",
            "# TYPE app_mode gauge",
            f"app_mode {mode_value}",
            "# HELP chaos_active Active chaos mode. 0=none, 1=slow, 2=error.",
            "# TYPE chaos_active gauge",
            f"chaos_active {chaos_value}",
        ]
    )
    return lines


@app.get("/")
def root():
    return {
        "message": f"Welcome to swiftdeploy running in {MODE} mode",
        "mode": MODE,
        "version": APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "mode": MODE,
        "version": APP_VERSION,
        "uptime_seconds": round(time.monotonic() - STARTED_AT, 3),
    }


@app.get("/metrics")
def metrics():
    return Response("\n".join(metric_lines()) + "\n", media_type="text/plain")


@app.post("/chaos")
def chaos(payload: ChaosRequest):
    if MODE != "canary":
        raise HTTPException(
            status_code=403,
            detail="chaos endpoint is only active in canary mode",
        )

    if payload.mode == "slow":
        if payload.duration is None:
            raise HTTPException(status_code=400, detail="duration is required")
        CHAOS.update({"mode": "slow", "duration": payload.duration, "rate": 0.0})
    elif payload.mode == "error":
        if payload.rate is None:
            raise HTTPException(status_code=400, detail="rate is required")
        CHAOS.update({"mode": "error", "duration": 0.0, "rate": payload.rate})
    elif payload.mode == "recover":
        CHAOS.update({"mode": "recover", "duration": 0.0, "rate": 0.0})
    else:
        raise HTTPException(status_code=400, detail="mode must be slow, error, or recover")

    return {"status": "ok", "chaos": CHAOS}

# There’s no uvicorn.run(...) inside app/main.py

# That is intentional. The FastAPI app is defined above as:

# app = FastAPI(title="swiftdeploy API", version=APP_VERSION)

# Then the server is started by the Docker container command in the Dockerfile:

# CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${APP_PORT:-3000}"]

# So the flow is:

# Docker starts container
# → Dockerfile CMD runs uvicorn
# → uvicorn imports app/main.py
# → uvicorn finds main:app
# → FastAPI server starts on APP_PORT
