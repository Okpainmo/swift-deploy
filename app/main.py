import os
import random
import time
import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field


STARTED_AT = time.monotonic()
MODE = os.environ.get("MODE", "stable") or "stable"
APP_VERSION = os.environ.get("APP_VERSION", "1.0.0") or "1.0.0"

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
    if MODE == "canary" and request.url.path != "/chaos":
        if CHAOS["mode"] == "slow":
            await asyncio.sleep(float(CHAOS["duration"]))
        elif CHAOS["mode"] == "error" and random.random() < float(CHAOS["rate"]):
            response = Response(
                content='{"error":"chaos error","mode":"canary"}',
                media_type="application/json",
                status_code=500,
            )
            response.headers["X-Mode"] = "canary"
            return response

    response = await call_next(request)
    if MODE == "canary":
        response.headers["X-Mode"] = "canary"
    return response


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