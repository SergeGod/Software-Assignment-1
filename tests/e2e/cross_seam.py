"""End-to-end test across the seam, against the real compose stack.

    python tests/e2e/cross_seam.py flow          # both services up
    docker compose stop ledger
    python tests/e2e/cross_seam.py ledger-down   # settlement degrades, stays healthy

Standard library only, so CI runs it without installing anything. Uses the
same URLs as the browser: ledger on :8001, settlement on :8002.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

LEDGER = os.environ.get("LEDGER_URL", "http://localhost:8001")
SETTLEMENT = os.environ.get("SETTLEMENT_URL", "http://localhost:8002")
STATE_FILE = os.environ.get("E2E_STATE_FILE", "/tmp/tabby-e2e.json")


def request(method: str, url: str, body: dict | None = None, token: str | None = None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def expect(status: int, wanted: int, what: str) -> None:
    if status != wanted:
        sys.exit(f"FAIL {what}: expected {wanted}, got {status}")
    print(f"ok   {what} ({status})")


def wait_healthy(url: str) -> None:
    for _ in range(90):
        try:
            if request("GET", f"{url}/health")[0] == 200:
                return
        except OSError:
            pass
        time.sleep(2)
    sys.exit(f"FAIL {url}/health never returned 200")


def flow() -> None:
    wait_healthy(LEDGER)
    wait_healthy(SETTLEMENT)
    suffix = uuid.uuid4().hex[:6]
    sessions = {}
    for name in ("alice", "bob"):
        status, body = request(
            "POST",
            f"{LEDGER}/api/signup",
            {"username": f"{name}_{suffix}", "display_name": name.title(), "password": "secret123"},
        )
        expect(status, 201, f"sign up {name} on ledger")
        sessions[name] = body
    alice, bob = sessions["alice"], sessions["bob"]
    a, b = alice["user"]["id"], bob["user"]["id"]

    status, _ = request("POST", f"{LEDGER}/api/friends", {"username": bob["user"]["username"]}, alice["token"])
    expect(status, 201, "alice adds bob as a friend")
    status, group = request("POST", f"{LEDGER}/api/groups", {"name": "E2E flat", "member_ids": [b]}, alice["token"])
    expect(status, 201, "alice creates a group with bob")
    expense = {
        "description": "Groceries",
        "amount_cents": 3000,
        "payer_id": a,
        "split_type": "equal",
        "category_id": 1,
        "participants": [{"user_id": a}, {"user_id": b}],
    }
    status, _ = request("POST", f"{LEDGER}/api/groups/{group['id']}/expenses", expense, alice["token"])
    expect(status, 201, "alice adds a 30.00 expense split equally")

    # The cross-seam call: settlement asks ledger for the group's ledger.
    status, settlement = request("GET", f"{SETTLEMENT}/api/groups/{group['id']}/settlement", token=bob["token"])
    expect(status, 200, "settlement computes balances from ledger data")
    wanted = [{"from_user_id": b, "to_user_id": a, "amount_cents": 1500}]
    if settlement["transfers"] != wanted:
        sys.exit(f"FAIL transfers: {settlement['transfers']} != {wanted}")
    print("ok   bob owes alice 15.00")

    status, _ = request(
        "POST", f"{SETTLEMENT}/api/groups/{group['id']}/payments", {"to_user_id": a, "amount_cents": 1500}, bob["token"]
    )
    expect(status, 201, "bob records the payment on settlement")
    status, settlement = request("GET", f"{SETTLEMENT}/api/groups/{group['id']}/settlement", token=alice["token"])
    expect(status, 200, "settlement after the payment")
    if settlement["transfers"]:
        sys.exit("FAIL the group should be settled")
    print("ok   the group is settled")

    with open(STATE_FILE, "w") as f:
        json.dump({"group_id": group["id"], "token": bob["token"]}, f)


def ledger_down() -> None:
    with open(STATE_FILE) as f:
        saved = json.load(f)
    started = time.monotonic()
    status, body = request("GET", f"{SETTLEMENT}/api/groups/{saved['group_id']}/settlement", token=saved["token"])
    elapsed = time.monotonic() - started
    expect(status, 503, "with ledger stopped, settlement answers 503")
    print(f"     detail: {body['detail']!r} after {elapsed:.1f}s")
    if "ledger" not in body["detail"]:
        sys.exit("FAIL the 503 should say the ledger service is unavailable")
    status, health = request("GET", f"{SETTLEMENT}/health")
    expect(status, 200, "settlement /health stays 200 (it reports only its own state)")
    print(f"     health: {health}")


if __name__ == "__main__":
    {"flow": flow, "ledger-down": ledger_down}[sys.argv[1]]()
