import json, base64, sys
from pathlib import Path
from datetime import datetime, timezone

auth_path = Path.home() / ".codex" / "auth.json"
out_path = Path(sys.argv[1])

def b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def decode_jwt(token: str):
    parts = token.split(".")
    if len(parts) != 3:
        return {"error": f"not_jwt parts={len(parts)}", "len": len(token)}
    header = json.loads(b64url_decode(parts[0]))
    payload = json.loads(b64url_decode(parts[1]))
    # redact anything sensitive-looking
    redacted = {}
    for k, v in payload.items():
        if k in ("email", "name", "preferred_username", "upn"):
            if isinstance(v, str) and "@" in v:
                local, _, domain = v.partition("@")
                redacted[k] = f"{local[:2]}***@{domain}"
            elif isinstance(v, str):
                redacted[k] = v[:2] + "***" if len(v) > 2 else "***"
            else:
                redacted[k] = v
        elif k in ("sub", "oid", "sid", "jti", "auth_time"):
            redacted[k] = f"present:{type(v).__name__}:len={len(str(v))}"
        elif isinstance(v, (list, dict)):
            redacted[k] = f"complex:{type(v).__name__}"
        else:
            redacted[k] = v
    return {
        "header": {kk: header.get(kk) for kk in ("alg", "typ", "kid") if kk in header},
        "claims_redacted": redacted,
        "exp": payload.get("exp"),
        "iat": payload.get("iat"),
        "nbf": payload.get("nbf"),
        "iss": payload.get("iss"),
        "aud_type": type(payload.get("aud")).__name__ if "aud" in payload else None,
        "token_use": payload.get("token_use") or payload.get("typ") or payload.get("type"),
        "scp_or_scope": payload.get("scp") or payload.get("scope"),
        "https_api_openai_com_auth": {k: payload.get(k) for k in payload if "openai" in k.lower() or k.startswith("https://")},
    }

data = json.loads(auth_path.read_text(encoding="utf-8"))
now = datetime.now(timezone.utc)
report = {
    "audited_at": now.isoformat(),
    "auth_path": str(auth_path),
    "auth_mode": data.get("auth_mode"),
    "last_refresh": data.get("last_refresh"),
    "token_field_lengths": {},
    "id_token": None,
    "access_token": None,
    "refresh_token": {"present": False},
    "agent_identity": {},
    "lifecycle": {},
}

tokens = data.get("tokens") or {}
for k in ("id_token", "access_token", "refresh_token", "account_id"):
    v = tokens.get(k)
    if v is None:
        report["token_field_lengths"][k] = None
    else:
        report["token_field_lengths"][k] = len(str(v))

if tokens.get("id_token"):
    report["id_token"] = decode_jwt(tokens["id_token"])
if tokens.get("access_token"):
    report["access_token"] = decode_jwt(tokens["access_token"])
if tokens.get("refresh_token"):
    rt = tokens["refresh_token"]
    report["refresh_token"] = {
        "present": True,
        "len": len(rt),
        "format": "opaque" if rt.count(".") != 2 else "jwt_like",
        "prefix_class": "starts_with_rt_" if str(rt).startswith("rt_") else "other",
    }

ai = data.get("agent_identity") or {}
report["agent_identity"] = {
    "plan_type": ai.get("plan_type"),
    "task_id": ai.get("task_id"),
    "email_present": bool(ai.get("email")),
    "chatgpt_user_id_present": bool(ai.get("chatgpt_user_id")),
    "account_id_present": bool(ai.get("account_id")),
    "agent_runtime_id_present": bool(ai.get("agent_runtime_id")),
    "agent_private_key_present": bool(ai.get("agent_private_key")),
    "agent_private_key_len": len(ai["agent_private_key"]) if ai.get("agent_private_key") else None,
}

def secs_to_human(s):
    if s is None:
        return None
    s = int(s)
    return f"{s}s ({s/3600:.2f}h)"

def exp_info(decoded):
    if not decoded or not decoded.get("exp"):
        return None
    exp = datetime.fromtimestamp(decoded["exp"], timezone.utc)
    iat = datetime.fromtimestamp(decoded["iat"], timezone.utc) if decoded.get("iat") else None
    return {
        "exp_utc": exp.isoformat(),
        "iat_utc": iat.isoformat() if iat else None,
        "ttl_from_iat": secs_to_human((decoded["exp"] - decoded["iat"]) if decoded.get("iat") else None),
        "seconds_until_exp": int((exp - now).total_seconds()),
        "expired": exp <= now,
    }

report["lifecycle"]["id_token"] = exp_info(report["id_token"])
report["lifecycle"]["access_token"] = exp_info(report["access_token"])
if report.get("last_refresh"):
    try:
        lr = datetime.fromisoformat(report["last_refresh"].replace("Z", "+00:00"))
        report["lifecycle"]["seconds_since_last_refresh"] = int((now - lr).total_seconds())
    except Exception as e:
        report["lifecycle"]["last_refresh_parse_error"] = str(e)

# inferences for concurrent behavior
report["lifecycle"]["assessment"] = {
    "refresh_token_is_jwt": report["refresh_token"].get("format") == "jwt_like",
    "shared_auth_json_risk": "HIGH if multiple processes write after refresh; LOW for concurrent read-only short runs (measured on DBX single-node)",
    "recommended_long_run": "per-process CODEX_HOME seeded from vault for multi-node or runs > expected access TTL",
    "trigger_hypotheses": [
        "Codex refreshes when access_token near expiry or on 401",
        "last_refresh updated on successful refresh write-back to auth.json",
        "agent_identity.agent_private_key is local agent identity material — do not share across untrusted hosts",
    ],
}

out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({
    "auth_mode": report["auth_mode"],
    "last_refresh": report["last_refresh"],
    "id_exp": report["lifecycle"].get("id_token"),
    "access_exp": report["lifecycle"].get("access_token"),
    "refresh": report["refresh_token"],
    "plan_type": report["agent_identity"].get("plan_type"),
    "wrote": str(out_path),
}, indent=2))
print("SUCCESS:auth_audit")
