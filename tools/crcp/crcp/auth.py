"""Auth vault — status only, never print secrets."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _b64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def decode_jwt_claims(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        return json.loads(_b64url(parts[1]))
    except Exception:
        return None


def _exp_info(claims: dict[str, Any] | None, now: datetime) -> dict[str, Any] | None:
    if not claims or "exp" not in claims:
        return None
    exp = datetime.fromtimestamp(int(claims["exp"]), timezone.utc)
    iat = (
        datetime.fromtimestamp(int(claims["iat"]), timezone.utc)
        if claims.get("iat")
        else None
    )
    return {
        "exp_utc": exp.isoformat(),
        "iat_utc": iat.isoformat() if iat else None,
        "ttl_hours_from_iat": round((claims["exp"] - claims["iat"]) / 3600, 2)
        if claims.get("iat")
        else None,
        "seconds_until_exp": int((exp - now).total_seconds()),
        "expired": exp <= now,
        "within_5min_of_exp": (exp - now).total_seconds() <= 300,
    }


def codex_auth_status(codex_home: Path | None = None) -> dict[str, Any]:
    """Two-signal Codex auth: file present + JWT validity (no token values)."""
    now = datetime.now(timezone.utc)
    home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth_path = home / "auth.json"
    out: dict[str, Any] = {
        "rail": "codex",
        "auth_path": str(auth_path),
        "file_present": auth_path.is_file(),
        "status": "MISSING",
        "signals": [],
    }
    if not auth_path.is_file():
        out["signals"].append("file_absent")
        return out

    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception as e:
        out["status"] = "UNKNOWN"
        out["signals"].append(f"parse_error:{type(e).__name__}")
        return out

    st = auth_path.stat()
    out["file_mtime_utc"] = datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()
    out["file_bytes"] = st.st_size
    out["auth_mode"] = data.get("auth_mode")
    out["last_refresh"] = data.get("last_refresh")
    out["signals"].append("file_present")

    tokens = data.get("tokens") or {}
    out["token_fields"] = {
        "id_token": bool(tokens.get("id_token")),
        "access_token": bool(tokens.get("access_token")),
        "refresh_token": bool(tokens.get("refresh_token")),
        "account_id": bool(tokens.get("account_id")),
        "id_token_len": len(tokens["id_token"]) if tokens.get("id_token") else 0,
        "access_token_len": len(tokens["access_token"]) if tokens.get("access_token") else 0,
        "refresh_token_len": len(tokens["refresh_token"]) if tokens.get("refresh_token") else 0,
    }

    access_claims = decode_jwt_claims(tokens["access_token"]) if tokens.get("access_token") else None
    id_claims = decode_jwt_claims(tokens["id_token"]) if tokens.get("id_token") else None
    out["access_token"] = _exp_info(access_claims, now)
    out["id_token"] = _exp_info(id_claims, now)

    if access_claims:
        oa = access_claims.get("https://api.openai.com/auth") or {}
        out["claims_summary"] = {
            "iss": access_claims.get("iss"),
            "client_id": access_claims.get("client_id"),
            "scp": access_claims.get("scp"),
            "chatgpt_plan_type": oa.get("chatgpt_plan_type"),
            "chatgpt_account_id_present": bool(oa.get("chatgpt_account_id")),
            "chatgpt_user_id_present": bool(oa.get("chatgpt_user_id")),
            "sso_connection_id_present": bool(oa.get("sso_connection_id")),
        }
        out["signals"].append("access_jwt_decoded")

    # proactive refresh heuristics (from Codex source)
    last_refresh = data.get("last_refresh")
    out["refresh_policy"] = {
        "proactive_if_last_refresh_older_than_days": 8,
        "proactive_if_access_within_minutes": 5,
        "endpoint": "https://auth.openai.com/oauth/token",
        "refresh_token_single_use": True,
    }
    if last_refresh:
        try:
            lr = datetime.fromisoformat(str(last_refresh).replace("Z", "+00:00"))
            age_days = (now - lr).total_seconds() / 86400
            out["last_refresh_age_days"] = round(age_days, 3)
            out["would_proactive_refresh_by_age"] = age_days > 8
        except Exception:
            out["last_refresh_age_days"] = None

    access_ok = bool(out.get("access_token") and not out["access_token"]["expired"])
    if access_ok:
        out["status"] = "LOGGED_IN"
        out["signals"].append("access_token_valid")
        if out["access_token"].get("within_5min_of_exp"):
            out["status"] = "EXPIRING_SOON"
            out["signals"].append("within_5min_of_exp")
    elif tokens.get("refresh_token"):
        out["status"] = "EXPIRED_NEEDS_REFRESH"
        out["signals"].append("access_expired_refresh_present")
    else:
        out["status"] = "EXPIRED"
        out["signals"].append("access_expired_no_refresh")

    ai = data.get("agent_identity") or {}
    out["agent_identity"] = {
        "plan_type": ai.get("plan_type"),
        "agent_runtime_id_present": bool(ai.get("agent_runtime_id")),
        "agent_private_key_present": bool(ai.get("agent_private_key")),
        "chatgpt_user_id_present": bool(ai.get("chatgpt_user_id")),
        "account_id_present": bool(ai.get("account_id")),
    }
    return out


def databricks_auth_status(timeout_sec: int = 20) -> dict[str, Any]:
    """Two-signal Databricks: config file + CLI whoami (no token print)."""
    cfg = Path.home() / ".databrickscfg"
    out: dict[str, Any] = {
        "rail": "databricks",
        "profile": "DEFAULT",
        "config_path": str(cfg),
        "config_present": cfg.is_file(),
        "status": "MISSING",
        "signals": [],
    }
    if not cfg.is_file():
        out["signals"].append("config_absent")
        return out
    out["signals"].append("config_present")
    try:
        proc = subprocess.run(
            ["databricks", "auth", "describe", "--profile", "DEFAULT"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        out["cli_exit"] = proc.returncode
        # redact token lines
        safe_lines = []
        for line in text.splitlines():
            if "token" in line.lower() and "****" not in line and "✓" in line:
                safe_lines.append(line.split(":")[0] + ": ********")
            else:
                safe_lines.append(line)
        out["describe_preview"] = "\n".join(safe_lines[:25])
        if proc.returncode == 0 and "bolt-datascience" in text:
            out["status"] = "LOGGED_IN"
            out["workspace_hint"] = "bolt-datascience"
            out["signals"].append("cli_describe_ok")
        elif proc.returncode == 0:
            out["status"] = "LOGGED_IN"
            out["signals"].append("cli_describe_ok")
        else:
            out["status"] = "UNKNOWN"
            out["signals"].append("cli_describe_failed")
    except FileNotFoundError:
        out["status"] = "UNKNOWN"
        out["signals"].append("databricks_cli_missing")
    except subprocess.TimeoutExpired:
        out["status"] = "UNKNOWN"
        out["signals"].append("cli_timeout")
    except Exception as e:
        out["status"] = "UNKNOWN"
        out["signals"].append(f"error:{type(e).__name__}")
    return out


def agent_mail_status(base: str = "http://127.0.0.1:8812", timeout_sec: int = 5) -> dict[str, Any]:
    out: dict[str, Any] = {
        "rail": "agent_mail",
        "health_url": f"{base}/api/health",
        "mcp_url": f"{base}/mcp",
        "status": "DOWN",
        "signals": [],
    }
    try:
        # Always hit loopback direct — system proxy (Fiddler) returns 502 on 127.0.0.1.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(f"{base}/api/health", method="GET")
        with opener.open(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", "replace")
            data = json.loads(body)
            out["http_status"] = resp.status
            out["health"] = data
            if data.get("status") == "ok":
                out["status"] = "LOGGED_IN"  # bus up (no user login)
                out["signals"].append("health_ok")
            else:
                out["status"] = "UNKNOWN"
                out["signals"].append("health_unexpected")
    except Exception as e:
        out["status"] = "DOWN"
        out["signals"].append(f"error:{type(e).__name__}")
    return out


def chatgpt_bridge_status(codex_home: Path | None = None) -> dict[str, Any]:
    """Can we call backend-api with current access_token? (consumer probe)."""
    now = datetime.now(timezone.utc)
    base = codex_auth_status(codex_home)
    out: dict[str, Any] = {
        "rail": "chatgpt_live_bridge",
        "status": "MISSING",
        "depends_on": "codex_auth",
        "signals": list(base.get("signals") or []),
        "codex_status": base.get("status"),
    }
    if base.get("status") not in ("LOGGED_IN", "EXPIRING_SOON"):
        out["status"] = "EXPIRED" if base.get("status", "").startswith("EXPIRED") else "MISSING"
        return out

    home = codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    auth = json.loads((home / "auth.json").read_text(encoding="utf-8"))
    access = auth["tokens"]["access_token"]
    claims = decode_jwt_claims(access) or {}
    oa = claims.get("https://api.openai.com/auth") or {}
    account_id = oa.get("chatgpt_account_id") or auth["tokens"].get("account_id") or ""

    url = "https://chatgpt.com/backend-api/me"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access}",
            "Accept": "application/json",
            "ChatGPT-Account-Id": account_id,
            "User-Agent": "CRCP-auth-vault/0.1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(500)
            out["http_status"] = resp.status
            out["signals"].append("backend_api_me_ok")
            out["status"] = "LOGGED_IN"
            # do not parse email into output
            try:
                j = json.loads(body.decode("utf-8", "replace"))
                out["me_keys"] = sorted(j.keys())[:20] if isinstance(j, dict) else None
                out["object"] = j.get("object") if isinstance(j, dict) else None
            except Exception:
                pass
    except urllib.error.HTTPError as e:
        out["http_status"] = e.code
        out["status"] = "EXPIRED" if e.code in (401, 403) else "UNKNOWN"
        out["signals"].append(f"backend_api_http_{e.code}")
    except Exception as e:
        out["status"] = "UNKNOWN"
        out["signals"].append(f"error:{type(e).__name__}")
    out["probed_at"] = now.isoformat()
    return out


def full_auth_status() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    rails = {
        "codex": codex_auth_status(),
        "databricks": databricks_auth_status(),
        "agent_mail": agent_mail_status(),
        "chatgpt_live_bridge": chatgpt_bridge_status(),
    }
    # overall: green if codex + agent_mail + (dbx optional for local)
    critical = ["codex", "agent_mail", "chatgpt_live_bridge"]
    green = all(rails[r].get("status") in ("LOGGED_IN", "EXPIRING_SOON") for r in critical)
    return {
        "probed_at": now,
        "overall": "GREEN" if green else "DEGRADED",
        "rails": rails,
        "policy": {
            "never_print_secrets": True,
            "chatgpt_bridge_is_token_consumer": True,
            "single_refresh_writer": "primary CODEX_HOME only",
        },
    }
