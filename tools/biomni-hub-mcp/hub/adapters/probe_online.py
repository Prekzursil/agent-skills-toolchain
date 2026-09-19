"""Dry-run + live probe for OnlineBiomniAdapter (reconciled interface).

Part A (offline): monkeypatch the single network seam ``_request`` to record
every (method, path, query) the adapter issues, drive all 10 canonical tools
with fake-but-shaped responses, and assert each maps to the right phylo v2
endpoint and preserves task_id / message_id / result_files / biomni_url. Every
tool now returns a :class:`schema.ToolEnvelope`, so payload assertions read
``env.data`` and ``env.biomni_url`` / ``env.display_instruction``.

Part B (live, best-effort): a read-only ``status()`` against the machine's
active account (broker mode) — expected to show the broker daemon up or down
without consuming any Biomni usage.

Run:  python hub/adapters/probe_online.py
"""
from __future__ import annotations

import json
import os
import sys

# Put the hub/ dir on path so ``adapters.online`` (which imports backends/schema)
# resolves whether this is run as a script or from the package.
_HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HUB not in sys.path:
    sys.path.insert(0, _HUB)

from adapters import online  # noqa: E402
from adapters.online import OnlineBiomniAdapter  # noqa: E402

CALLS: list = []

# Canned responses keyed by (METHOD, path-prefix) — shaped like phylo v2.
FAKE = {
    ("POST", "/v2/projects"): {"id": "proj_abc", "name": "x"},
    ("GET", "/v2/projects"): {"projects": [{"id": "proj_abc", "name": "x"}]},
    # force /auth/me fallback
    ("GET", "/v2/workspaces"): {"error": "not found"},
    ("GET", "/v2/auth/me"): {
        "email": "prek@example.com",
        "organization_id": "org_1",
        "organization_name": "Org One",
    },
    ("POST", "/v2/agent/sessions/create"): {
        "session_id": "sess_123",
        "status": "running",
    },
    ("POST", "/v2/agent/sess_123/user_message"): {"message_id": "msg_9"},
    ("POST", "/v2/agent/sess_123/start_processing"): {"ok": True},
    ("GET", "/v2/agent/sess_123/messages"): {
        "messages": [{"role": "assistant", "text": "hi"}]
    },
    ("GET", "/v2/agent/sess_123"): {"status": "completed"},
    ("GET", "/v2/agent/projects/proj_abc/sessions"): {
        "sessions": [{"session_id": "sess_123"}]
    },
    ("GET", "/v2/files/results"): {
        "results": [
            {
                "name": "plot.png", "size": 2048,
                "session_id": "sess_123", "path": "/s/plot.png",
            },
            {"name": "other.csv", "size": 10, "session_id": "sess_999"},
        ]
    },
}


def fake_request(self, method, path, body=None, query=None, token="", timeout=None):
    CALLS.append((method.upper(), path, query))
    key = (method.upper(), path)
    if key in FAKE:
        return 200, FAKE[key]
    for (m, p), v in FAKE.items():
        if m == method.upper() and path.startswith(p):
            return 200, v
    return 200, {}


def part_a() -> int:
    online.OnlineBiomniAdapter._request = fake_request  # type: ignore
    # Non-loopback base so broker mode is off; force a static token.
    a = OnlineBiomniAdapter(api_base="https://api.phylo.bio", token="TESTTOKEN")

    # Every tool now returns a ToolEnvelope; ``.data`` holds the payload.
    r = {
        "create_project": a.create_project("x"),
        "list_projects": a.list_projects(),
        "list_workspaces": a.list_workspaces(),
        "switch_workspace": a.switch_workspace("org_1"),
        # ABC order: (project_id, prompt, model_profile)
        "start_new_task": a.start_new_task("proj_abc", "analyse BRCA1"),
        "send_message": a.send_message("sess_123", "continue"),
        "wait_for_next_update": a.wait_for_next_update("sess_123", 0.0, since=0),
        "list_tasks": a.list_tasks("proj_abc"),
        "list_result_files": a.list_result_files("sess_123"),
    }
    d = {k: (v.data if v.data is not None else {}) for k, v in r.items()}

    checks = []

    def check(name, cond, detail=""):
        checks.append((name, bool(cond), detail))

    paths = [c[1] for c in CALLS]
    check(
        "create_project -> POST /v2/projects",
        ("POST", "/v2/projects", None) in CALLS,
    )
    check(
        "create_project preserves project_id",
        d["create_project"].get("project_id") == "proj_abc",
    )
    check("list_projects -> GET /v2/projects", ("GET", "/v2/projects", None) in CALLS)
    check("list_workspaces falls back to /v2/auth/me", "/v2/auth/me" in paths)
    check(
        "list_workspaces derives a workspace",
        d["list_workspaces"]["workspaces"][0]["id"] == "org_1",
    )
    check(
        "start_new_task -> POST /v2/agent/sessions/create",
        "/v2/agent/sessions/create" in paths,
    )
    check(
        "start_new_task task_id == session_id",
        d["start_new_task"].get("task_id") == "sess_123",
    )
    check(
        "start_new_task builds biomni_url",
        "sess_123" in (r["start_new_task"].biomni_url or ""),
    )
    check(
        "start_new_task has display_instruction",
        bool(r["start_new_task"].display_instruction),
    )
    check(
        "send_message -> user_message + start_processing",
        "/v2/agent/sess_123/user_message" in paths
        and any(p.endswith("/start_processing") for p in paths),
    )
    check(
        "send_message preserves message_id",
        d["send_message"].get("message_id") == "msg_9",
    )
    check(
        "start_processing passes message_id as query",
        any(
            c[0] == "POST"
            and c[1].endswith("/start_processing")
            and c[2] == {"message_id": "msg_9"}
            for c in CALLS
        ),
    )
    check(
        "wait_for_next_update polls messages + status",
        "/v2/agent/sess_123/messages" in paths
        and ("GET", "/v2/agent/sess_123", None) in CALLS,
    )
    check(
        "wait_for_next_update reports done + cursor",
        d["wait_for_next_update"].get("done") is True
        and d["wait_for_next_update"].get("cursor") == 1,
    )
    check(
        "wait_for_next_update attaches result_files on done",
        any(
            f["name"] == "plot.png"
            for f in d["wait_for_next_update"].get("result_files", [])
        ),
    )
    check(
        "list_tasks -> GET /v2/agent/projects/{pid}/sessions",
        "/v2/agent/projects/proj_abc/sessions" in paths,
    )
    check(
        "list_result_files -> GET /v2/files/results", "/v2/files/results" in paths
    )
    rows = d["list_result_files"].get("result_files", [])
    check(
        "list_result_files filters by task_id + maps session_id -> task_id",
        len(rows) == 1
        and rows[0]["name"] == "plot.png"
        and rows[0]["size"] == 2048
        and rows[0]["task_id"] == "sess_123",
    )

    print("=== PART A: offline dry-run (canonical tool -> endpoint) ===")
    passed = 0
    for name, ok, detail in checks:
        suffix = (" :: " + detail) if detail else ""
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}{suffix}")
        passed += ok
    print(f"\n  {passed}/{len(checks)} checks passed")
    print("\n  --- endpoints exercised (in order) ---")
    for m, p, q in CALLS:
        print(f"    {m:5} {p}{('?' + str(q)) if q else ''}")
    return 0 if passed == len(checks) else 1


def part_b() -> None:
    print("\n=== PART B: live read-only status() (no usage consumed) ===")
    # Real network seam; uses the machine's active biomni account (broker mode).
    import importlib
    importlib.reload(online)
    a = online.OnlineBiomniAdapter()
    st = a.status()
    print("  " + json.dumps(st, indent=2, default=str).replace("\n", "\n  "))


if __name__ == "__main__":
    rc = part_a()
    try:
        part_b()
    except Exception as e:  # noqa: BLE001
        print(f"  live probe raised (non-fatal): {e!r}")
    sys.exit(rc)
