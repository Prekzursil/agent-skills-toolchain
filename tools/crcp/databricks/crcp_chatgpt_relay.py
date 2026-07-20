# CRCP ChatGPT list/fetch relay (portable script).
# Runtime: LOCAL / GitHub (verdict-app style) — see README.md in this folder.
# Databricks is optional and NOT the default deploy path.
#
# Local usage:
#   python databricks/crcp_chatgpt_relay.py          # list_only via ~/.codex/auth.json
#   main(list_only=True) / main(fetch_latest=1)
#
# Prefer always-on: Windows task CRCPChatGPTBridge → python -m crcp chatgpt live
#
# Safety:
#   - token CONSUMER only unless you explicitly enable refresh (default off)
#   - never print tokens

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _b64url_decode(s: str) -> bytes:
    import base64

    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def decode_jwt(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    return json.loads(_b64url_decode(payload))


def load_auth_from_secret(
    scope: str = "codex-harness-prekzursil",
    key: str = "auth_json",
) -> dict[str, Any]:
    """Load auth.json from Databricks secret scope (preferred) or local path."""
    try:
        from pyspark.dbutils import DBUtils  # type: ignore
        from pyspark.sql import SparkSession  # type: ignore

        spark = SparkSession.builder.getOrCreate()
        dbutils = DBUtils(spark)
        raw = dbutils.secrets.get(scope=scope, key=key)
        return json.loads(raw)
    except Exception:
        # local fallback for testing
        p = Path.home() / ".codex" / "auth.json"
        return json.loads(p.read_text(encoding="utf-8"))


def chatgpt_get(access: str, account_id: str, path: str, query: dict | None = None) -> Any:
    q = f"?{urllib.parse.urlencode(query)}" if query else ""
    url = f"https://chatgpt.com{path}{q}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access}",
            "Accept": "application/json",
            "ChatGPT-Account-Id": account_id,
            "User-Agent": "CRCP-databricks-relay/0.1",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main(
    *,
    list_only: bool = False,
    fetch_latest: int = 1,
    dbfs_out: str | None = "/dbfs/FileStore/crcp/chatgpt",
    scope: str = "codex-harness-prekzursil",
    key: str = "auth_json",
) -> dict[str, Any]:
    auth = load_auth_from_secret(scope=scope, key=key)
    access = auth["tokens"]["access_token"]
    claims = decode_jwt(access)
    oa = claims.get("https://api.openai.com/auth") or {}
    account_id = oa.get("chatgpt_account_id") or auth["tokens"].get("account_id") or ""
    exp = claims.get("exp")
    now = datetime.now(timezone.utc).timestamp()
    report: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "access_seconds_until_exp": int(exp - now) if exp else None,
        "plan": oa.get("chatgpt_plan_type"),
        "mode": "list_only" if list_only else f"fetch_latest_{fetch_latest}",
    }

    listing = chatgpt_get(
        access, account_id, "/backend-api/conversations", {"offset": 0, "limit": max(fetch_latest, 5)}
    )
    items = listing.get("items") or []
    report["total"] = listing.get("total")
    report["items"] = [
        {"id": it.get("id"), "title": it.get("title"), "update_time": it.get("update_time")}
        for it in items[:10]
    ]

    if list_only:
        return report

    packs = []
    for it in items[:fetch_latest]:
        cid = it.get("id")
        if not cid:
            continue
        conv = chatgpt_get(access, account_id, f"/backend-api/conversation/{cid}")
        pack = {
            "id": cid,
            "title": conv.get("title") or it.get("title"),
            "mapping_nodes": len(conv.get("mapping") or {}),
            "keys": sorted(conv.keys())[:20],
        }
        packs.append(pack)
        if dbfs_out:
            try:
                out = Path(dbfs_out)
                out.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                path = out / f"conv_{cid}_{stamp}.json"
                path.write_text(json.dumps(conv, indent=2, default=str), encoding="utf-8")
                pack["dbfs_path"] = str(path)
            except Exception as e:
                pack["dbfs_error"] = type(e).__name__
    report["packs"] = packs
    return report


if __name__ == "__main__":
    # Local dry-run using ~/.codex/auth.json
    print(json.dumps(main(list_only=True), indent=2, default=str))
