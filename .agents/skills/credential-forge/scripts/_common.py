"""_common.py -- shared machinery for the credential-forge scripts.

DISCIPLINE (non-negotiable):
- Secret VALUES live in process memory only. This module never prints, logs,
  or writes a value. Prints carry NAMES, paths, counts, lengths, and 4-char
  masks only (mask standard: 1password-ops/SKILL.md "mask to 4 chars").
- Parsing reads store bytes straight into memory; no intermediate temp files.

Grounding:
- shape() walker adapted from Temp/authmap/shape_json.py:3-21
  (strings -> string(len=N), numbers -> 'number', never values).
- winreg env-persist recipe from out/grok-lane-wire.py:50-58
  (SetValueEx, User scope by default; Machine scope is opt-in).
- OP_CONNECT_* inline-strip from the 1password-ops estate gotcha
  (the op-personal bash wrapper is not exec-able from Windows python).
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import pathlib
import re
import winreg

HOME = pathlib.Path(os.environ.get("USERPROFILE", str(pathlib.Path.home())))
STATE_DIR = HOME / ".agents" / "state" / "credential-forge"
SKILL_DIR = HOME / ".agents" / "skills" / "credential-forge"
AUDIT_SCRIPT = HOME / ".agents" / "scripts" / "audit_secret_artifacts.py"

# Stores larger than this are probed (size/mtime) but not parsed by default.
MAX_PARSE_BYTES = 200 * 1024 * 1024

HKCU_ENV = r"Environment"
HKLM_ENV = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"

def _p(*parts: str) -> pathlib.Path:
    out = pathlib.Path(parts[0])
    for part in parts[1:]:
        out = out / part
    return out

APPDATA = os.environ.get("APPDATA", str(HOME / "AppData" / "Roaming"))
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", str(HOME / "AppData" / "Local"))

# ---------------------------------------------------------------------------
# Store registry (references/store-map.md is the human-readable twin).
# design_status = status recorded by the stores research as of 2026-10-22
# (carried from the credential-forge design); observed_* fields are refreshed
# at runtime by probing mtime/size.
STORES: dict[str, dict] = {
    "grok": {
        "label": "grok CLI (.grok/auth.json, issuer-keyed OAuth)",
        "paths": [HOME / ".grok" / "auth.json"],
        "parser": "grok-issuer-map",
        "refresh_owner": "grok CLI (rewrites its own file)",
        "refreshable_by_cli": True,
        "design_status": "LIVE",
    },
    "gemini": {
        "label": "gemini-cli (.gemini/oauth_creds.json, standard OIDC pair)",
        "paths": [HOME / ".gemini" / "oauth_creds.json"],
        "sibling_account_file": HOME / ".gemini" / "google_accounts.json",
        "parser": "gemini-oauth",
        "refresh_owner": "gemini CLI (rewrites its own file)",
        "refreshable_by_cli": True,
        "design_status": "LIVE",
    },
    "claude": {
        "label": "claude code (.claude/.credentials.json)",
        "paths": [HOME / ".claude" / ".credentials.json"],
        "parser": "token-dict-walk",
        "refresh_owner": "claude CLI (rewrites its own file)",
        "refreshable_by_cli": True,
        "design_status": "designOauth LIVE / claudeAiOauth EMPTY",
    },
    "zcode": {
        "label": "zcode (.zcode/v2/credentials.json, flat KV)",
        "paths": [HOME / ".zcode" / "v2" / "credentials.json"],
        "parser": "flat-kv",
        "refresh_owner": "zcode runtime",
        "refreshable_by_cli": True,
        "design_status": "LIVE",
    },
    "codex": {
        "label": "codex (.codex -- env-key only, no auth file expected)",
        "paths": [HOME / ".codex" / "auth.json"],
        "parser": "token-dict-walk",
        "refresh_owner": "codex CLI",
        "refreshable_by_cli": True,
        "design_status": "env-key only (no auth file)",
    },
    "cursor": {
        "label": "cursor desktop state.vscdb (huge SQLite; names-only probing)",
        "paths": [pathlib.Path(APPDATA) / "Cursor" / "User" / "globalStorage" / "state.vscdb"],
        "parser": "sqlite-names",
        "refresh_owner": "cursor desktop app",
        "refreshable_by_cli": False,
        "design_status": "LIVE desktop / STALE cli",
    },
    "cursor-agent": {
        "label": "cursor-agent auth (cli side; design recorded STALE 2026-09-02)",
        "paths": [HOME / ".cursor-agent" / "auth.json",
                  HOME / ".cursor" / "cli-config.json",
                  HOME / ".cursor" / "agent-cli-state.json"],
        "parser": "token-dict-walk",
        "refresh_owner": "none on this box",
        "refreshable_by_cli": False,
        "design_status": "STALE 2026-09-02",
    },
    "opencode": {
        "label": "opencode auth.json (design recorded STALE 2026-04-27)",
        "paths": [HOME / ".local" / "share" / "opencode" / "auth.json",
                  pathlib.Path(LOCALAPPDATA) / "opencode" / "auth.json"],
        "parser": "token-dict-walk",
        "refresh_owner": "none on this box",
        "refreshable_by_cli": False,
        "design_status": "STALE 2026-04-27",
    },
    "gcloud": {
        "label": "gcloud dbs (Windows Cloud SDK roaming dir; account names only)",
        "paths": [pathlib.Path(APPDATA) / "gcloud" / "application_default_credentials.json"],
        "dbs": [pathlib.Path(APPDATA) / "gcloud" / "credentials.db",
                pathlib.Path(APPDATA) / "gcloud" / "access_tokens.db"],
        "legacy_dir": pathlib.Path(APPDATA) / "gcloud" / "legacy_credentials",
        "parser": "token-dict-walk+sqlite-names",
        "refresh_owner": "gcloud CLI",
        "refreshable_by_cli": True,
        "design_status": "6 accounts LIVE",
    },
    "aws": {
        "label": "aws sso cache (~/.aws/sso/cache/*.json, expiresAt)",
        "paths": [],  # globbed at runtime
        "glob": HOME / ".aws" / "sso" / "cache" / "*.json",
        "parser": "aws-sso-cache",
        "refresh_owner": "aws sso login",
        "refreshable_by_cli": True,
        "design_status": "SSO cache present",
    },
    "gh": {
        "label": "gh hosts.yml (env-token lane; presence flags only)",
        "paths": [pathlib.Path(APPDATA) / "GitHub CLI" / "hosts.yml",
                  HOME / ".config" / "gh" / "hosts.yml"],
        "parser": "gh-hosts",
        "refresh_owner": "gh CLI",
        "refreshable_by_cli": True,
        "design_status": "env-token",
    },
    "scw": {
        "label": "scaleway config.yaml (key names only)",
        "paths": [HOME / ".config" / "scw" / "config.yaml"],
        "parser": "yaml-names",
        "refresh_owner": "scw CLI",
        "refreshable_by_cli": True,
        "design_status": "present",
    },
    "op": {
        "label": "1password op CLI config (absent = vault lane degraded, not an error)",
        "paths": [HOME / ".op" / "config"],
        "parser": "json-names",
        "refresh_owner": "op CLI",
        "refreshable_by_cli": True,
        "design_status": "absent on this box",
    },
}

# ---------------------------------------------------------------------------
# shape walker -- names/types/lengths only (Temp/authmap/shape_json.py:3-21)

def shape(obj, depth: int = 0, maxdepth: int = 8):
    if isinstance(obj, dict):
        if depth >= maxdepth:
            return "<dict:depth-cut>"
        return {str(k): shape(v, depth + 1, maxdepth) for k, v in obj.items()}
    if isinstance(obj, list):
        return {"__list__": len(obj), "elem0": shape(obj[0], depth + 1, maxdepth) if obj else None}
    if isinstance(obj, bool):
        return "bool"
    if isinstance(obj, (int, float)):
        return "number"
    if isinstance(obj, str):
        return "string(len=%d)" % len(obj)
    if obj is None:
        return "null"
    return type(obj).__name__

# ---------------------------------------------------------------------------
# offline JWT decode (base64 payload split, zero network)

_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")

def jwt_payload(token: str) -> dict | None:
    """Return the decoded payload dict of a JWT-looking string, or None.
    Pure offline base64 split; never validated against a network key."""
    if not isinstance(token, str):
        return None
    parts = token.split(".")
    if len(parts) != 3 or not _B64URL.match(parts[1] or ""):
        return None
    pad = "=" * (-len(parts[1]) % 4)
    try:
        raw = base64.urlsafe_b64decode(parts[1] + pad)
        data = json.loads(raw.decode("utf-8", "replace"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None

def jwt_exp_iso(token: str) -> str | None:
    payload = jwt_payload(token)
    if not payload:
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp > 0:
        return _dt.datetime.fromtimestamp(exp, _dt.timezone.utc).isoformat(timespec="seconds")
    return None

def jwt_issuer(token: str) -> str | None:
    payload = jwt_payload(token)
    if not payload:
        return None
    iss = payload.get("iss")
    return iss if isinstance(iss, str) and len(iss) < 200 else None

# ---------------------------------------------------------------------------
# expiry helpers

def iso_from_unix_ms(ms) -> str | None:
    if not isinstance(ms, (int, float)) or ms <= 0:
        return None
    return _dt.datetime.fromtimestamp(ms / 1000.0, _dt.timezone.utc).isoformat(timespec="seconds")

def iso_from_unix_s(s) -> str | None:
    if not isinstance(s, (int, float)) or s <= 0:
        return None
    return _dt.datetime.fromtimestamp(s, _dt.timezone.utc).isoformat(timespec="seconds")

def parse_iso(text):
    if not isinstance(text, str) or not text:
        return None
    try:
        return _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

def days_to(expiry_iso: str | None, now=None) -> float | None:
    dt = parse_iso(expiry_iso)
    if dt is None:
        return None
    if now is None:
        now = _dt.datetime.now(_dt.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return round((dt - now).total_seconds() / 86400.0, 2)

# ---------------------------------------------------------------------------
# mtime / liveness

def probe(path: pathlib.Path) -> dict | None:
    try:
        st = path.stat()
    except OSError:
        return None
    mtime = _dt.datetime.fromtimestamp(st.st_mtime, _dt.timezone.utc)
    age_days = round((_dt.datetime.now(_dt.timezone.utc) - mtime).total_seconds() / 86400.0, 2)
    return {"path": str(path), "size": st.st_size, "mtime": mtime.isoformat(timespec="seconds"),
            "mtime_age_days": age_days}

def mtime_verdict(info: dict | None) -> str:
    """recent = rewritten in the last 45 days (LIVE evidence heuristic).
    Authoritative per-store statuses live in references/store-map.md."""
    if info is None:
        return "absent"
    return "recent-mtime" if info["mtime_age_days"] <= 45 else "stale-mtime"

# ---------------------------------------------------------------------------
# token-dict discovery (generic OAuth/file walking; values never leave memory)

_ACCESS_KEYS = ("access_token", "accessToken", "key", "oauth_token", "apiKey", "api_key")
_REFRESH_KEYS = ("refresh_token", "refreshToken")
_EXPIRY_KEYS = ("expires_at", "expiry_date", "expiresAt", "refreshTokenExpiresAt",
                "accessTokenExpiresAt", "expiry", "expired_at")

def find_token_dicts(obj, trail="", depth=0, out=None):
    """Yield (trail, dict) for every dict that carries an access-ish key."""
    if out is None:
        out = []
    if depth > 8:
        return out
    if isinstance(obj, dict):
        if any(k in obj for k in _ACCESS_KEYS) or any(k in obj for k in _REFRESH_KEYS):
            out.append((trail or "<root>", obj))
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                find_token_dicts(v, "%s.%s" % (trail, k), depth + 1, out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, (dict, list)):
                find_token_dicts(v, "%s[%d]" % (trail, i), depth + 1, out)
    return out

def normalize_token_dict(trail: str, d: dict) -> dict:
    access = next((d[k] for k in _ACCESS_KEYS if isinstance(d.get(k), str) and d.get(k)), None)
    refresh = next((d[k] for k in _REFRESH_KEYS if isinstance(d.get(k), str) and d.get(k)), None)
    expires_at = None
    for k in _EXPIRY_KEYS:
        v = d.get(k)
        if isinstance(v, str) and parse_iso(v):
            expires_at = parse_iso(v).astimezone(_dt.timezone.utc).isoformat(timespec="seconds")
            break
        if isinstance(v, (int, float)) and v > 10 ** 12:
            expires_at = iso_from_unix_ms(v)
            break
        if isinstance(v, (int, float)) and 10 ** 9 < v < 10 ** 11:
            expires_at = iso_from_unix_s(v)
            break
    if expires_at is None and access:
        expires_at = jwt_exp_iso(access)
    kind = "oauth-pair" if refresh else ("password-shaped" if "password" in trail.lower() else "api-key")
    if access and access.count(".") == 2 and jwt_payload(access):
        kind = "oauth-pair" if refresh else "jwt-access"
    return {
        "account": trail,
        "kind": kind,
        "access_len": len(access) if access else 0,
        "refresh_len": len(refresh) if refresh else 0,
        "expires_at": expires_at,
        "issuer": jwt_issuer(access) if access else None,
    }

# ---------------------------------------------------------------------------
# state io (atomic; state dir holds names/shapes/expiries ONLY -- never values)

def atomic_json_write(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=True, sort_keys=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)

def load_json(path: pathlib.Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

# ---------------------------------------------------------------------------
# winreg env helpers (names only on read; grok-lane-wire.py:50-58 pattern on write)

def env_scope_names(machine: bool) -> list[str]:
    root, sub = (winreg.HKEY_LOCAL_MACHINE, HKLM_ENV) if machine else (winreg.HKEY_CURRENT_USER, HKCU_ENV)
    names = []
    try:
        with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as k:
            index = 0
            while True:
                try:
                    name, _value, _typ = winreg.EnumValue(k, index)
                except OSError:
                    break
                names.append(name)
                index += 1
    except OSError:
        pass
    return names

def env_names_both_scopes() -> list[str]:
    seen: dict[str, list[str]] = {}
    for machine in (False, True):
        for name in env_scope_names(machine):
            seen.setdefault(name, []).append("Machine" if machine else "User")
    return sorted(seen.keys()), seen

def env_get_value(name: str, machine: bool = False) -> str | None:
    """Value goes straight into caller memory; never print it."""
    root, sub = (winreg.HKEY_LOCAL_MACHINE, HKLM_ENV) if machine else (winreg.HKEY_CURRENT_USER, HKCU_ENV)
    try:
        with winreg.OpenKey(root, sub, 0, winreg.KEY_READ) as k:
            value, _typ = winreg.QueryValueEx(k, name)
            return value if isinstance(value, str) else None
    except OSError:
        return None

def env_set_value(name: str, value: str, machine: bool = False) -> bool:
    """grok-lane-wire.py:50-55 recipe: SetValueEx, no shell, no echo.
    Machine scope is opt-in and reserved for named client keys
    (GROK_LANE_KEY precedent); do NOT blanket-replicate machine-scope writes."""
    root, sub = (winreg.HKEY_LOCAL_MACHINE, HKLM_ENV) if machine else (winreg.HKEY_CURRENT_USER, HKCU_ENV)
    try:
        with winreg.OpenKey(root, sub, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        return True
    except OSError:
        return False

# ---------------------------------------------------------------------------
# op (1Password) helpers -- Connect-mode bypass is an inline env strip

def op_base_env() -> dict:
    """Child env for op with OP_CONNECT_* stripped inline (the estate gotcha:
    the op-personal bash wrapper cannot be exec'd from Windows python, so the
    strip happens here in the env dict instead)."""
    return {k: v for k, v in os.environ.items() if not k.startswith("OP_CONNECT_")}

def find_op() -> pathlib.Path | None:
    for candidate in (HOME / ".local" / "bin" / "op" / ".exe",
                      HOME / ".local" / "bin" / "op.exe",
                      HOME / ".local" / "bin" / "op"):
        if candidate.exists():
            return candidate
    for dirn in os.environ.get("PATH", "").split(os.pathsep):
        p = pathlib.Path(dirn) / "op.exe"
        if p.exists():
            return p
    return None

# ---------------------------------------------------------------------------
# printing helpers -- NAMES/paths/counts/lengths only

def entry_line(provider: str, e: dict) -> str:
    bits = ["%s:%s" % (provider, e.get("account") or "<root>"),
            "kind=%s" % e.get("kind"),
            "access_len=%s" % e.get("access_len", 0),
            "refresh_len=%s" % e.get("refresh_len", 0)]
    if e.get("expires_at"):
        d = days_to(e["expires_at"])
        bits.append("exp=%s" % e["expires_at"])
        bits.append("days_to_expiry=%s" % d)
    if e.get("issuer"):
        bits.append("issuer=%s" % e["issuer"])
    return " ".join(bits)

def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
