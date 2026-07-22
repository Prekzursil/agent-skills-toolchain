"""Solve PoW then attempt authenticated conversation POST with sentinel headers."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from crcp.bridge import ChatGPTBridge
from crcp.sentinel import acquire_sentinel_tokens, try_finalize
from crcp.write_path import build_next_body, post_conversation


def main() -> None:
    bridge = ChatGPTBridge()
    tokens = acquire_sentinel_tokens(bridge)
    print(
        "acquired",
        {
            "persona": tokens.get("persona"),
            "pow": tokens.get("pow"),
            "turnstile_required": tokens.get("turnstile_required"),
            "blocker": tokens.get("blocker"),
            "prepare_len": len(tokens.get("prepare_token") or ""),
            "proof_len": len(tokens.get("proof_token") or ""),
        },
    )

    msg = f"CRCP pow probe {uuid.uuid4().hex[:8]} — reply OK"
    body = build_next_body(text=msg, style="desktop_auth", model="gpt-5-5")
    did = tokens["device_id"]
    sid = tokens["session_id"]
    attempts = []

    def attempt(name: str, **kw):
        r = post_conversation(
            bridge,
            body,
            stream=True,
            device_id=did,
            session_id=sid,
            originator="Codex Browser",
            **kw,
        )
        row = {
            "name": name,
            "ok": r.get("ok"),
            "status": r.get("status"),
            "body_prefix": (r.get("body_text") or "")[:350],
            "content_type": r.get("content_type"),
        }
        attempts.append(row)
        print(name, row["status"], row["body_prefix"][:180])
        return r

    # 1) Desktop-style: prepare + proof, no turnstile
    attempt(
        "prepare+proof",
        sentinel_prepare_token=tokens.get("prepare_token"),
        sentinel_proof_token=tokens.get("proof_token"),
    )
    # 2) + empty turnstile
    attempt(
        "prepare+proof+empty_ts",
        sentinel_prepare_token=tokens.get("prepare_token"),
        sentinel_proof_token=tokens.get("proof_token"),
        sentinel_turnstile_token="",
    )
    # 3) finalize path if we can get a dummy turnstile — skip without real ts
    # try finalize with empty turnstile
    fin = try_finalize(
        bridge,
        prepare_token=tokens["prepare_token"],
        proof_token=tokens["proof_token"],
        turnstile_token="",
        device_id=did,
        session_id=sid,
    )
    attempts.append(
        {
            "name": "finalize_empty_ts",
            "ok": fin.get("ok"),
            "status": fin.get("status"),
            "body_prefix": (fin.get("body_text") or str(fin.get("body")))[:350],
        }
    )
    print("finalize", fin.get("status"), (fin.get("body_text") or "")[:180])

    if fin.get("ok") and isinstance(fin.get("body"), dict) and fin["body"].get("token"):
        chat_tok = fin["body"]["token"]
        attempt(
            "finalize_chat_token",
            sentinel_chat_token=chat_tok,
            sentinel_proof_token=tokens.get("proof_token"),
            sentinel_prepare_token=tokens.get("prepare_token"),
        )

    report = {
        "persona": tokens.get("persona"),
        "pow": tokens.get("pow"),
        "turnstile_required": tokens.get("turnstile_required"),
        "attempts": attempts,
        "success": any(a.get("ok") for a in attempts),
    }
    path = (
        Path(__file__).resolve().parents[1] / "reports" / "sentinel_pow_send_probe.json"
    )
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("wrote", path, "success=", report["success"])


if __name__ == "__main__":
    main()
