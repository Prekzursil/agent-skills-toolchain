"""Probe sentinel prepare + write-path variants. Local owner-authorized only."""

from __future__ import annotations

import json
import time
import uuid
import urllib.error
import urllib.request
from pathlib import Path

from crcp.bridge import ChatGPTBridge
from crcp.write_path import (
    _browser_headers,
    build_next_body,
    post_conversation,
)


def shape(o, depth=0):
    if depth > 5:
        return "..."
    if isinstance(o, dict):
        return {k: shape(v, depth + 1) for k, v in o.items()}
    if isinstance(o, list):
        return [shape(o[0], depth + 1)] if o else []
    if isinstance(o, str):
        return f"str:{len(o)}"
    if isinstance(o, (int, float, bool)) or o is None:
        return o
    return type(o).__name__


def prepare(
    bridge: ChatGPTBridge, device_id: str, session_id: str, p: str = ""
) -> dict:
    url = f"{bridge.base}/backend-api/sentinel/chat-requirements/prepare"
    body = json.dumps({"p": p}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers=_browser_headers(
            bridge,
            device_id=device_id,
            session_id=session_id,
            originator="Codex Browser",
        ),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    bridge = ChatGPTBridge()
    device_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    out = Path(__file__).resolve().parents[1] / "reports"

    prep = prepare(bridge, device_id, session_id, p="")
    print("persona", prep.get("persona"))
    print("keys", sorted(prep.keys()))
    print("shape", json.dumps(shape(prep), indent=2)[:2500])

    msg = f"CRCP sentinel probe {uuid.uuid4().hex[:8]}"
    chat_body = build_next_body(text=msg, style="desktop_auth", model="gpt-5-5")

    attempts = []

    # A: prepare token only
    r = post_conversation(
        bridge,
        chat_body,
        stream=True,
        device_id=device_id,
        session_id=session_id,
        sentinel_prepare_token=prep.get("prepare_token"),
        originator="Codex Browser",
    )
    attempts.append(
        {
            "name": "prepare_token_only",
            "ok": r.get("ok"),
            "status": r.get("status"),
            "body_prefix": (r.get("body_text") or "")[:300],
        }
    )
    print("A prepare_only", r.get("status"), (r.get("body_text") or "")[:200])

    # B: prepare token as finalize-style chat token header too
    r2 = post_conversation(
        bridge,
        chat_body,
        stream=True,
        device_id=device_id,
        session_id=session_id,
        sentinel_prepare_token=prep.get("prepare_token"),
        sentinel_chat_token=prep.get("token") or prep.get("prepare_token"),
        originator="Codex Browser",
    )
    attempts.append(
        {
            "name": "prepare_as_both_headers",
            "ok": r2.get("ok"),
            "status": r2.get("status"),
            "body_prefix": (r2.get("body_text") or "")[:300],
        }
    )
    print("B both", r2.get("status"), (r2.get("body_text") or "")[:200])

    # C: if proofofwork fields present, try building dummy proof header from seed
    pow_info = prep.get("proofofwork") or prep.get("proof_of_work")
    if isinstance(pow_info, dict):
        print("pow_info_keys", sorted(pow_info.keys()))
        print(
            "pow_info_sample",
            {
                k: (str(v)[:80] if not isinstance(v, (int, float, bool)) else v)
                for k, v in pow_info.items()
            },
        )

    report = {
        "at": time.time(),
        "persona": prep.get("persona"),
        "prepare_keys": sorted(prep.keys()),
        "shape": shape(prep),
        "turnstile_required": (prep.get("turnstile") or {}).get("required")
        if isinstance(prep.get("turnstile"), dict)
        else None,
        "attempts": attempts,
    }
    path = out / "sentinel_prepare_probe.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", path)


if __name__ == "__main__":
    main()
