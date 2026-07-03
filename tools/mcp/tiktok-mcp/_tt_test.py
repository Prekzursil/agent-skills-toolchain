"""E2E smoke test for the TikTok MCP — proves the library + environment work end-to-end
and validates the server's trimmers against REAL API payloads. Read-only; no secrets logged.

Run:  .venv\\Scripts\\python.exe _tt_test.py
With an ms_token:  set TIKTOK_MS_TOKEN=... then run (recommended — keyless often 403s).
"""
from __future__ import annotations

import asyncio
import json
import os

from TikTokApi import TikTokApi

import server  # reuse _open / _trim_video / _trim_user from the real server


async def main() -> int:
    have_token = bool(os.environ.get("TIKTOK_MS_TOKEN"))
    have_proxy = bool(os.environ.get("TIKTOK_PROXY"))
    print(f"[cfg] ms_token={'set' if have_token else 'absent'} proxy={'set' if have_proxy else 'absent'}")

    ok = {}
    try:
        async with TikTokApi() as api:
            await server._open(api)

            # 1) trending
            try:
                vids = [server._trim_video(v.as_dict) async for v in api.trending.videos(count=3)]
                ok["trending"] = len(vids)
                if vids:
                    print("[trending] sample:", json.dumps(vids[0], ensure_ascii=False)[:400])
            except Exception as exc:  # noqa: BLE001
                ok["trending"] = f"ERR {type(exc).__name__}: {str(exc)[:160]}"

            # 2) a known public creator
            try:
                info = await api.user(username="tiktok").info()
                u = server._trim_user(info)
                ok["user_info"] = u.get("uniqueId") or "no-uniqueId"
                print("[user_info] tiktok ->", json.dumps(u, ensure_ascii=False)[:300])
            except Exception as exc:  # noqa: BLE001
                ok["user_info"] = f"ERR {type(exc).__name__}: {str(exc)[:160]}"

            # 3) a hashtag
            try:
                hv = [server._trim_video(v.as_dict) async for v in api.hashtag(name="news").videos(count=2)]
                ok["hashtag"] = len(hv)
            except Exception as exc:  # noqa: BLE001
                ok["hashtag"] = f"ERR {type(exc).__name__}: {str(exc)[:160]}"

    except Exception as exc:  # noqa: BLE001 - session creation itself failed
        print(f"[session] FAILED to create: {type(exc).__name__}: {str(exc)[:200]}")
        print(json.dumps(ok, indent=2))
        return 2

    print("\n=== RESULT ===")
    print(json.dumps(ok, indent=2, ensure_ascii=False))
    passed = any(isinstance(v, int) and v > 0 for v in ok.values())
    print("VERDICT:", "PASS (at least one live call returned data)" if passed else "FAIL (all calls empty/blocked)")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
