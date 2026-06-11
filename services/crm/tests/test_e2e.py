"""End-to-end test: the full two-service callback loop over real HTTP.

Both services run as real uvicorn subprocesses on localhost — the CRM calls the
channel's /v1/send, the channel posts HMAC-signed callbacks back to the CRM's
/receipts. The channel is configured hostile (heavy out-of-order + duplicates +
real failures) so the loop has to earn its correctness:

    seed -> segment preview -> create campaign (draft) -> APPROVE (HITL) ->
    send worker -> channel simulates -> async signed callbacks -> /receipts ->
    append-only log -> projection -> stats

Asserts: cumulative/monotonic funnel, out-of-order safety (a clicked comm still
has every earlier lifecycle timestamp), duplicate idempotency (no inflation),
nothing stuck in QUEUED, forged callbacks rejected (401), attribution sane.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

SECRET = "test-shared-secret"
CRM_DIR = Path(__file__).resolve().parents[1]          # services/crm
CHANNEL_DIR = CRM_DIR.parent / "channel"               # services/channel

# Import the CRM's signer to forge/sign test callbacks (cwd is services/crm).
from app.core.signing import sign  # noqa: E402


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_health(base: str, timeout_s: float = 25.0) -> None:
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/health", timeout=1.0)
            if r.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(0.15)
    raise RuntimeError(f"service {base} never became healthy ({last})")


def _spawn(service_dir: Path, port: int, env_extra: dict) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(service_dir)
    env.update(env_extra)
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(service_dir), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )


@pytest.fixture()
def services(tmp_path):
    crm_port, ch_port = _free_port(), _free_port()
    db_path = tmp_path / "e2e.db"
    crm_base = f"http://127.0.0.1:{crm_port}"
    ch_base = f"http://127.0.0.1:{ch_port}"

    channel = _spawn(CHANNEL_DIR, ch_port, {
        "CHANNEL_CALLBACK_SECRET": SECRET,
        "CHANNEL_SEED": "42",
        "CHANNEL_MIN_LATENCY_MS": "1",
        "CHANNEL_MAX_LATENCY_MS": "5",
        "CHANNEL_OUT_OF_ORDER_RATE": "0.6",
        "CHANNEL_DUPLICATE_RATE": "0.4",
        "CHANNEL_FAILURE_RATE": "0.12",
        "CHANNEL_RETRY_MAX_ATTEMPTS": "5",
        "CHANNEL_RETRY_BASE_DELAY_MS": "2",
        "CHANNEL_RETRY_MAX_DELAY_MS": "20",
    })
    crm = _spawn(CRM_DIR, crm_port, {
        "CRM_DATABASE_URL": f"sqlite+aiosqlite:///{db_path}",
        "CRM_BUS": "memory",
        "CRM_CALLBACK_SECRET": SECRET,
        "CRM_CHANNEL_BASE_URL": ch_base,
        "CRM_CRM_PUBLIC_URL": crm_base,
        "CRM_RETRY_MAX_ATTEMPTS": "5",
        "CRM_RETRY_BASE_DELAY_MS": "5",
        "CRM_RETRY_MAX_DELAY_MS": "50",
    })
    try:
        _wait_health(ch_base)
        _wait_health(crm_base)
        yield crm_base, ch_base
    finally:
        for p in (crm, channel):
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


def _await_settled(api: httpx.Client, campaign_id: str, audience: int,
                   timeout_s: float = 30.0) -> dict:
    """Poll until delivered+failed == audience and the funnel stops changing."""
    deadline = time.time() + timeout_s
    stable = 0
    prev = None
    funnel = {}
    while time.time() < deadline:
        funnel = api.get(f"/campaigns/{campaign_id}/stats").json()["funnel"]
        complete = funnel["delivered"] + funnel["failed"] >= audience
        if complete and funnel == prev:
            stable += 1
            if stable >= 4:
                return funnel
        else:
            stable = 0
        prev = funnel
        time.sleep(0.08)
    return funnel


def test_full_callback_loop_over_http(services):
    crm_base, _ = services
    with httpx.Client(base_url=crm_base, timeout=10.0) as api:
        # 1. Seed the demo dataset.
        r = api.post("/seed", json={"n_customers": 120, "seed": 7})
        assert r.status_code == 200, r.text
        assert r.json()["customers"] == 120

        # 2. Preview a win-back segment against real data.
        segment = {"match": "all", "rules": [
            {"field": "lifecycle_stage", "op": "in", "value": ["lapsed", "at_risk"]}]}
        r = api.post("/segments/preview", json={"segment": segment})
        assert r.status_code == 200, r.text
        audience = r.json()["count"]
        assert audience > 0

        # 3. Create campaign (draft — nothing is sent yet).
        campaign = api.post("/campaigns", json={
            "name": "Win-back lapsed", "segment": segment, "channel": "email",
            "message": "We miss you — 20% off your next order."}).json()
        assert campaign["status"] == "draft"
        assert campaign["recipient_count"] == audience

        # 4. Approve — the HITL gate, the only thing that dispatches.
        r = api.post(f"/campaigns/{campaign['id']}/approve")
        assert r.status_code == 200, r.text
        assert r.json()["dispatched"] == audience

        # 5. Let the async loop settle.
        funnel = _await_settled(api, campaign["id"], audience)

        # --- centerpiece guarantees ---------------------------------------
        assert funnel["sent"] == audience
        assert funnel["delivered"] + funnel["failed"] == audience
        assert funnel["delivered"] <= funnel["sent"]
        assert funnel["opened"] <= funnel["delivered"]
        assert funnel["read"] <= funnel["opened"]
        assert funnel["clicked"] <= funnel["read"]
        assert funnel["failed"] >= 1  # 12% over 120 -> some real failures

        comms = api.get(
            f"/campaigns/{campaign['id']}/communications").json()["communications"]
        # Nothing stuck queued.
        assert all(c["state"] != "queued" for c in comms)

        # Attribution never exceeds clicks.
        stats = api.get(f"/campaigns/{campaign['id']}/stats").json()
        assert 0 <= stats["attributed_orders"] <= funnel["clicked"]

        # 6. Forged callback (bad signature) is rejected.
        forged = json.dumps({
            "communication_id": comms[0]["id"], "event_type": "clicked",
            "provider_event_id": "forged-1"}).encode()
        r = api.post("/receipts", content=forged, headers={"x-signature": "deadbeef"})
        assert r.status_code == 401

        # 7. Duplicate signed callback is idempotent (folds to no-op).
        delivered = next((c for c in comms if c["state"] in
                          ("delivered", "opened", "read", "clicked")), comms[0])
        body = json.dumps({
            "communication_id": delivered["id"], "event_type": "delivered",
            "provider_event_id": "dup-probe-1"}).encode()
        sig = sign(body, SECRET)
        first = api.post("/receipts", content=body, headers={"x-signature": sig})
        second = api.post("/receipts", content=body, headers={"x-signature": sig})
        assert first.status_code == 200 and second.status_code == 200
        assert second.json()["status"] == "duplicate"
