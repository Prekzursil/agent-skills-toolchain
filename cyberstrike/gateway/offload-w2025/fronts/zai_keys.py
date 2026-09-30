"""zai-keys front — dual Z.AI coding-plan key rotation, call-time lazy.

Improvement over home's zai_key_failover.py (which is demand-probe +
StopFailure-hook driven):
- rotation happens AT CALL TIME: every gateway invoke of this backend can
  request `active` — the front returns the currently-healthy key, rotating
  first (registry write + ZAI_API_KEY env) when the active one is exhausted
  (429/quota markers). No hooks, no scheduled probes, no daemon.
- state lives in ~/.agents/zai-key-state.json (same file, same format) so the
  home script and this front stay interoperable.
- NEVER regenerates or revokes keys — selection only (estate rule).

Tools (via run(tool, args)):
  status           -> both sha8s + which is active/healthy
  active           -> sha8 + health of the healthy key (rotates if needed);
                      NEVER returns the plaintext key
  rotate           -> force-switch to the other key if it's healthy; returns
                      sha8/probe only, NEVER the plaintext key (the rotated
                      value lands in ZAI_API_KEY + the shared state file)
  probe            -> probe both keys, return raw results
  invoke           -> {"model","messages",...} chat completion on the healthy key
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
SECRETS_ENV = HOME / ".agents" / "secrets" / "zai-coding-plan.env"
STATE = HOME / ".agents" / "zai-key-state.json"
ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
KEY_NAMES = ("ZAI_API_KEY_prekzursil1993", "ZAI_API_KEY_realprekzursil")
ACTIVE_ENV = "ZAI_API_KEY"

EXHAUST_MARKERS = ("insufficient", "quota", "exceeded", "balance", "rate limit",
                   "out of", "no credit", "billing")

_CACHE: dict = {"probe": {}, "ts": 0.0}
PROBE_TTL = 300.0


def _sha8(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:8]


def _read_user_env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if v and not v.startswith("${"):
        return v
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
                reg_v, _ = winreg.QueryValueEx(k, name)
                if isinstance(reg_v, str) and reg_v.strip() and not reg_v.startswith("${"):
                    return reg_v.strip()
        except OSError:
            pass
    if SECRETS_ENV.exists():
        for line in SECRETS_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val and not val.startswith("${"):
                    return val
    return ""


def _set_user_env(name: str, value: str) -> None:
    os.environ[name] = value
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE) as k:
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        except OSError:
            pass


def _probe(key: str, timeout: float = 30.0) -> dict:
    now = time.time()
    cached = _CACHE["probe"].get(_sha8(key))
    if cached and now - _CACHE["ts"] < PROBE_TTL:
        return cached
    body = json.dumps({"model": "glm-4.6", "messages": [{"role": "user", "content": "hi"}],
                       "max_tokens": 1, "stream": False}).encode()
    req = urllib.request.Request(ENDPOINT, data=body,
                                 headers={"Authorization": f"Bearer {key}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            out = {"ok": True, "status": r.status, "exhausted": False}
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:300].lower()
        except Exception:
            detail = ""
        out = {"ok": False, "status": e.code,
               "exhausted": e.code == 429 or any(m in detail for m in EXHAUST_MARKERS),
               "note": detail[:120]}
    except Exception as e:  # noqa: BLE001
        out = {"ok": False, "status": 0, "exhausted": False, "note": f"{type(e).__name__}"}
    _CACHE["probe"][_sha8(key)] = out
    _CACHE["ts"] = now
    return out


def _keys() -> dict[str, str]:
    out = {}
    for name in KEY_NAMES:
        v = _read_user_env(name)
        if v:
            out[name] = v
    return out


def _active(keys: dict[str, str]) -> str | None:
    act = _read_user_env(ACTIVE_ENV)
    if act and act in keys.values():
        return act
    return next(iter(keys.values()), None)


def _select(force_rotate: bool = False) -> dict:
    keys = _keys()
    if len(keys) < 2:
        return {"error": f"need both keys configured (found {len(keys)}); "
                         f"source: {SECRETS_ENV}", "sha8s": {k: _sha8(v) for k, v in keys.items()}}
    act = _active(keys)
    act_res = _probe(act)
    if act_res.get("ok") and not force_rotate:
        return {"key": act, "sha8": _sha8(act), "rotated": False,
                "probe": {"ok": True, "status": act_res.get("status")}}
    # rotate: find healthy alternative
    for v in keys.values():
        if v == act:
            continue
        res = _probe(v)
        if res.get("ok") or not res.get("exhausted"):
            _set_user_env(ACTIVE_ENV, v)
            _write_state({"action": "gateway-rotated", "active_sha8": _sha8(v),
                          "probe": res, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            return {"key": v, "sha8": _sha8(v), "rotated": True, "probe": res}
    return {"error": "all Z.AI keys exhausted", "probes": {_sha8(v): _probe(v) for v in keys.values()}}


def _write_state(state: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    except OSError:
        pass


def _chat(payload: dict) -> str:
    sel = _select()
    if "error" in sel:
        return json.dumps(sel)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(ENDPOINT, data=body,
                                 headers={"Authorization": f"Bearer {sel['key']}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.dumps({"ok": True, "used_sha8": sel["sha8"], "rotated": sel["rotated"],
                               "response": json.loads(r.read().decode())})
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        # if exhausted mid-call, rotate once and retry
        if e.code == 429 or any(m in detail.lower() for m in EXHAUST_MARKERS):
            _CACHE["probe"].pop(sel["sha8"], None)
            _CACHE["ts"] = 0.0
            sel2 = _select(force_rotate=True)
            if "error" not in sel2:
                req2 = urllib.request.Request(ENDPOINT, data=body,
                                              headers={"Authorization": f"Bearer {sel2['key']}",
                                                       "Content-Type": "application/json"})
                try:
                    with urllib.request.urlopen(req2, timeout=120) as r2:
                        return json.dumps({"ok": True, "used_sha8": sel2["sha8"], "rotated": True,
                                           "response": json.loads(r2.read().decode())})
                except Exception:  # noqa: BLE001
                    pass
        return json.dumps({"ok": False, "status": e.code, "error": detail})


def run(tool: str, args: dict) -> str:
    if tool == "status":
        keys = _keys()
        act = _active(keys)
        return json.dumps({"keys": {k: _sha8(v) for k, v in keys.items()},
                           "active_sha8": _sha8(act) if act else None,
                           "env_var": ACTIVE_ENV,
                           "state_file": str(STATE)}, indent=2)
    if tool == "active":
        sel = _select()
        return json.dumps({k: v for k, v in sel.items() if k != "key"} | {"sha8": sel.get("sha8")})
    if tool == "rotate":
        # same surface rule as 'active': never return the plaintext key over
        # the gateway — sha8 only. The rotated key lands in ZAI_API_KEY and
        # the shared state file, where local callers already read it.
        sel = _select(force_rotate=True)
        return json.dumps({k: v for k, v in sel.items() if k != "key"} | {"sha8": sel.get("sha8")})
    if tool == "probe":
        return json.dumps({_sha8(v): _probe(v) for v in _keys().values()}, indent=2)
    if tool == "invoke":
        return _chat(args.get("payload") or args)
    return json.dumps({"error": f"unknown tool '{tool}'",
                       "tools": ["status", "active", "rotate", "probe", "invoke"]})
