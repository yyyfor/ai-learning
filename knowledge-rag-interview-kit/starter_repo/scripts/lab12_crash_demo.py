#!/usr/bin/env python3
"""Lab 12 definition of done: kill the API right after a side effect, restart,
resume, and prove from the execution ledger that the action was not duplicated.

Starts its own API on --port (default 8010) twice, so it does not touch the one
you use on 8000. Needs Docker services, Ollama, seeded lab examples and the
[agent] extras. Takes a few minutes: each API start syncs indexes.

    python scripts/lab12_crash_demo.py
"""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
GOAL = "Create a follow-up task asking HR to confirm the annual leave policy for full-time employees."


def start_api(port, crash, log):
    env = {**os.environ, "RAG_ENABLED": "true", "AGENT_CHECKPOINT_DB": "var/crash_demo.sqlite"}
    env.pop("AGENT_CRASH_AFTER_WRITE", None)
    if crash:
        env["AGENT_CRASH_AFTER_WRITE"] = "exit"  # os._exit(137): like kill -9, no cleanup
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
                               cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.time() + 600
    while time.time() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"API exited early; see {log.name}")
        try:
            if httpx.get(f"http://127.0.0.1:{port}/agent/v2/runs/none", timeout=2).status_code in (404, 503):
                return process
        except httpx.HTTPError:
            pass
        time.sleep(2)
    process.kill()
    raise SystemExit("API did not start in time")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    base = f"http://127.0.0.1:{args.port}"
    headers = {"Authorization": "Bearer " + os.environ["API_TOKEN"]} if os.getenv("API_TOKEN") else {}
    (ROOT / "var").mkdir(exist_ok=True)
    log = open(ROOT / "var" / "crash_demo.log", "w")
    client = httpx.Client(base_url=base, headers=headers, timeout=600)

    print("1) Starting API with AGENT_CRASH_AFTER_WRITE=exit ...")
    api = start_api(args.port, crash=True, log=log)
    run = client.post("/agent/v2/runs", json={"goal": GOAL}).json()
    print(f"   run {run['id'][:8]} status={run['status']}")
    if run["status"] != "awaiting_approval":
        api.send_signal(signal.SIGTERM)
        raise SystemExit(f"The model did not propose the follow-up (status {run['status']}); run again.")
    before = len(client.get("/agent/followups").json())
    print("2) Approving. The API writes the follow-up, then dies before saving the checkpoint ...")
    try:
        response = client.post(f"/agent/v2/runs/{run['id']}/approval", json={"approved": True})
        print(f"   approval request returned HTTP {response.status_code}")
    except httpx.HTTPError as exc:
        print(f"   approval request lost with the process: {type(exc).__name__}")
    print(f"   API exit code: {api.wait(timeout=30)}")

    print("3) Restarting API normally ...")
    api = start_api(args.port, crash=False, log=log)
    try:
        view = client.get(f"/agent/v2/runs/{run['id']}").json()
        after_crash = len(client.get("/agent/followups").json())
        print(f"   status={view['status']} next={view['next']} follow-ups written so far: {after_crash - before}")
        print("4) Resuming from the checkpoint ...")
        view = client.post(f"/agent/v2/runs/{run['id']}/resume").json()
        final = len(client.get("/agent/followups").json())
        print(f"   status={view['status']} receipt={view['receipt']}")
        print(f"   events: {' -> '.join(e['node'] for e in view['events'])}")
        ok = view["status"] == "completed" and view["receipt"]["reused_existing"] and final - before == 1
        print(f"5) Ledger check: {final - before} follow-up for this run -> {'PASS' if ok else 'FAIL'}")
        raise SystemExit(0 if ok else 1)
    finally:
        api.send_signal(signal.SIGTERM)
        api.wait(timeout=30)


if __name__ == "__main__":
    main()
