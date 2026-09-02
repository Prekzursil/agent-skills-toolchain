#!/usr/bin/env python3
"""Probe 2: a token stored where an agent can write must fail.

Negative control: the identical HMAC-valid token that passes via env/fd is
rejected when presented from /tmp or the worktree. The owner secret channel
is an inherited read-only memfd (write errno EBADF); an agent-writable
secret file cannot configure the gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.lib import owner_approval as G  # noqa: E402

ART = REPO / "command-center/receipts/TST-0226.json"
SENTINEL = "SUCCESS:TST-0226"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0226-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    report = G.run_required_controls()
    fails = G.control_failures(report)
    if fails:
        return fail("; ".join(fails))

    contrast = report["same_token_env_vs_file"]
    if not contrast.get("contrast"):
        return fail(f"contrast {contrast}")
    file_tmp = report["file_tmp"]
    file_repo = report["file_repo"]
    if file_tmp["reason"] != "agent-writable-channel" or file_tmp["accepted"]:
        return fail(f"file_tmp {file_tmp}")
    if file_repo["reason"] != "agent-writable-channel" or file_repo["accepted"]:
        return fail(f"file_repo {file_repo}")
    if not report["agent_secret_file_refused"]["raised"]:
        return fail("agent secret file configured the gate")
    prov = report["secret_provenance"]
    if prov.get("channel") != "inherited-fd":
        return fail(f"secret channel {prov}")
    if not prov.get("write_blocked"):
        return fail(f"owner fd writable {prov}")
    if not report["stolen_tmp_classified_agent_writable"]:
        return fail("tmp path not agent-writable")
    if not report["stolen_repo_classified_agent_writable"]:
        return fail("repo path not agent-writable")

    live = doc.get("live_controls") or {}
    if not (live.get("same_token_env_vs_file") or {}).get("contrast"):
        return fail("receipt missing env-vs-file contrast")
    if (live.get("secret_provenance") or {}).get("channel") != "inherited-fd":
        return fail("receipt secret provenance missing inherited-fd")

    payload = {
        "probe": "probe2-agent-writable",
        "unit_id": "TST-0226",
        "pass": True,
        "env_accepted": contrast["env_accepted"],
        "file_tmp_accepted": contrast["file_tmp_accepted"],
        "file_repo_accepted": contrast["file_repo_accepted"],
        "file_tmp_reason": file_tmp["reason"],
        "file_repo_reason": file_repo["reason"],
        "secret_channel": prov.get("channel"),
        "owner_fd_write_blocked": report["owner_fd_write_blocked"],
        "owner_fd_write_errno": report["owner_fd_write_errno"],
        "agent_secret_file_refused": True,
        "receipt_matches_live": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"env_ok file_tmp={file_tmp['reason']} file_repo={file_repo['reason']} "
        f"secret_channel={prov.get('channel')} write_errno={report['owner_fd_write_errno']}"
    )
    print("SUCCESS:TST-0226-probe2 agent-writable token presentation is rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
