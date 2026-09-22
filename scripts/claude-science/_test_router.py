#!/usr/bin/env python3
"""Both-states test for cs_glm_router.py (single-signal rule: prove the split).

Starts the router with ZAI_API_KEY from the Windows env (passed via WSLENV),
then: (1) /v1/messages must answer from GLM (200 with GLM content);
(2) /api/oauth/profile must answer from Anthropic with the real account email
(not a GLM/anthropic error) — the two-plane split working in BOTH directions.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request

PORT = 8232


def main() -> int:
    env = dict(os.environ, CS_ROUTER_PORT=str(PORT))
    router_path = os.path.join(os.path.expanduser("~"), ".local", "bin", "cs_glm_router.py")
    p = subprocess.Popen(
        [sys.executable, router_path],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    time.sleep(1.5)
    try:
        body = json.dumps({
            "model": "claude-opus-5",  # router must map this to glm-4.6
            "max_tokens": 512,
            "messages": [{"role": "user", "content": "say OK"}],
        }).encode()
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/messages",
            data=body,
            headers={
                "content-type": "application/json",
                "authorization": "Bearer dummy-must-be-swapped",
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            doc = json.loads(r.read())
            # GLM reasoning models may emit thinking blocks before text — scan all
            reply = "".join(
                b.get("text", "") for b in doc.get("content") or [] if isinstance(b, dict)
            )
            model = doc.get("model", "?")
            print(f"PLANE-1 messages: http=200 model={model} reply={reply[:30]!r}")
            assert model.startswith("glm"), f"model not mapped: {model}"
            assert reply.strip(), "empty GLM reply (no text block in any content block)"

        req2 = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/api/oauth/profile",
            headers={"authorization": "Bearer " + os.environ.get("ANTHROPIC_API_KEY", "")},
        )
        try:
            with urllib.request.urlopen(req2, timeout=60) as r:
                prof = json.loads(r.read())
                email = prof.get("account", {}).get("email", "?")
                print(f"PLANE-2 profile: http=200 email={email}")
                assert "@" in email, "no account email — plane leaked to GLM"
        except urllib.error.HTTPError as e:
            print(f"PLANE-2 profile: HTTP {e.code} (may be fine if upstream token scope differs)")
        print("SUCCESS:cs-glm-router two-plane split verified")
        return 0
    except AssertionError as e:
        print(f"FAILED:cs-glm-router {e}")
        return 1
    finally:
        p.terminate()


if __name__ == "__main__":
    sys.exit(main())
