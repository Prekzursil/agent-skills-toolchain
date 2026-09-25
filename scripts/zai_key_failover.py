#!/usr/bin/env python3
"""Z.AI coding-plan dual-key failover (prekzursil1993 <-> realprekzursil).

Both plan keys live as user env vars. ZAI_API_KEY is the active switch for MCP
(${ZAI_API_KEY}). Claude Code stores a literal ANTHROPIC_AUTH_TOKEN for
https://api.z.ai/api/anthropic — this script keeps that in sync on rotate.

Modes:
  (default)         probe both; switch if active exhausted and other healthy
  --status          print last state + current env
  --probe-only      probe both, change nothing
  --on-failure      optimistic rotate to the other key (StopFailure hook);
                    optionally verifies the target with a short probe

NEVER regenerates or revokes keys — selection only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.z.ai/api/coding/paas/v4/chat/completions"
KEYS = {
    "prekzursil1993": "ZAI_API_KEY_prekzursil1993",
    "realprekzursil": "ZAI_API_KEY_realprekzursil",
}
HOME = Path.home()
STATE = HOME / ".agents" / "zai-key-state.json"
SECRETS_ENV = HOME / ".agents" / "secrets" / "zai-coding-plan.env"
ACTIVE_TXT = HOME / ".agents" / "secrets" / "zai-api-key.txt"
CLAUDE_SETTINGS = HOME / ".claude" / "settings.json"
CLAUDE_JSON = HOME / ".claude.json"
EXHAUST_CODES = {429}
EXHAUST_MARKERS = (
    "insufficient",
    "quota",
    "exceeded",
    "balance",
    "rate limit",
    "out of",
    "no credit",
    "billing",
    "usage",
)


def sha8(v: str) -> str:
    return hashlib.sha256(v.encode()).hexdigest()[:8]


def _read_user_env(name: str) -> str:
    """Read USER-scope env (HKCU) so hooks/tasks see registry even if process env is stale."""
    v = os.environ.get(name, "").strip()
    if sys.platform == "win32":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as k:
                reg_v, _ = winreg.QueryValueEx(k, name)
                if isinstance(reg_v, str) and reg_v.strip():
                    return reg_v.strip()
        except OSError:
            pass
    if v:
        return v
    # secrets file fallback
    if SECRETS_ENV.exists():
        for line in SECRETS_ENV.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{name}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _set_user_env(name: str, value: str) -> None:
    if sys.platform == "win32":
        # Prefer registry write (setx can hang / truncate >1024)
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_SET_VALUE
            ) as k:
                winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        except OSError:
            subprocess.run(
                ["setx", name, value], check=False, capture_output=True
            )
        # Broadcast env change (best-effort, short timeout)
        try:
            import ctypes

            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_ulong()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                "Environment",
                SMTO_ABORTIFHUNG,
                1000,
                ctypes.byref(result),
            )
        except Exception:
            pass
    else:
        os.environ[name] = value
    os.environ[name] = value


def probe(key: str, timeout: float = 45.0) -> dict:
    body = json.dumps(
        {
            "model": "glm-4.6",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
            "stream": False,
        }
    ).encode()
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {
                "ok": True,
                "status": r.status,
                "latency_ms": int((time.time() - t0) * 1000),
                "note": "",
            }
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        exhausted = e.code in EXHAUST_CODES or any(
            m in detail.lower() for m in EXHAUST_MARKERS
        )
        return {
            "ok": False,
            "status": e.code,
            "latency_ms": int((time.time() - t0) * 1000),
            "exhausted": exhausted,
            "note": detail[:160],
        }
    except Exception as e:
        return {
            "ok": False,
            "status": 0,
            "exhausted": False,
            "note": f"{type(e).__name__}: {e}",
        }


def which_account(key: str, values: dict[str, str]) -> str:
    for acct, v in values.items():
        if v and v == key:
            return acct
    return "?"


def _patch_claude_token(new_key: str) -> list[str]:
    """Replace ANTHROPIC_AUTH_TOKEN (and any old key literal) in Claude config files."""
    touched: list[str] = []
    for path in (CLAUDE_SETTINGS, CLAUDE_JSON):
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        updated = raw
        # Prefer explicit ANTHROPIC_AUTH_TOKEN field
        updated2, n = re.subn(
            r'("ANTHROPIC_AUTH_TOKEN"\s*:\s*")[^"]*(")',
            rf"\g<1>{new_key}\g<2>",
            updated,
            count=1,
        )
        updated = updated2
        if n == 0 and "api.z.ai" in updated:
            # fallback: replace first z.ai-shaped key near anthropic base url
            updated2, n = re.subn(
                r"[0-9a-fA-F]{16,}\.[A-Za-z0-9]+",
                new_key,
                updated,
                count=1,
            )
            updated = updated2
        if updated != raw:
            bak = path.with_suffix(path.suffix + f".bak-failover-{time.strftime('%Y%m%d-%H%M%S')}")
            try:
                bak.write_text(raw, encoding="utf-8")
            except Exception:
                pass
            path.write_text(updated, encoding="utf-8")
            touched.append(str(path))
    return touched



def _propagate_biomni(key: str) -> None:
    """Best-effort: push the active key into Biomni (.env + CS local-mcp.json),
    restart its daemons, so Biomni A1 / the CS connector never ride an exhausted
    key after a rotate. Fail-open: never blocks the failover itself."""
    import subprocess
    try:
        env = dict(os.environ)
        env["ZAI_API_KEY"] = _read_user_env("ZAI_API_KEY") or key
        env["WSLENV"] = "ZAI_API_KEY/u"
        r = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "/mnt/c/Users/Prekzursil/.agents/scripts/zai_biomni_key_propagate.sh"],
            capture_output=True, text=True, timeout=180, env=env,
        )
        out = (r.stdout or "") + (r.stderr or "")
        ok = "SUCCESS:biomni-key-rotate" in out
        print(f"{'SUCCESS' if ok else 'WARN'}:zai-biomni-propagate {out.strip()[-200:]}")
    except Exception as e:  # noqa: BLE001 - fail-open by design
        print(f"WARN:zai-biomni-propagate skipped ({type(e).__name__}: {e})")

def apply_active(key: str, account: str) -> list[str]:
    _set_user_env("ZAI_API_KEY", key)
    touched = _patch_claude_token(key)
    try:
        ACTIVE_TXT.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_TXT.write_text(key + "\n", encoding="utf-8")
        touched.append(str(ACTIVE_TXT))
    except Exception:
        pass
    _propagate_biomni(key)
    return touched


def load_values() -> dict[str, str]:
    return {a: _read_user_env(v) for a, v in KEYS.items()}


def main() -> int:
    args = set(sys.argv[1:])
    values = load_values()
    missing = [a for a, v in values.items() if not v]
    if missing:
        print(f"FAILED:zai-failover env vars missing for {missing}")
        return 1
    if len(set(values.values())) < 2:
        print(
            "FAILED:zai-failover both account keys are identical — "
            "restore distinct values in ZAI_API_KEY_prekzursil1993 / "
            "ZAI_API_KEY_realprekzursil (see ~/.agents/secrets/zai-coding-plan.env)"
        )
        return 1

    active = _read_user_env("ZAI_API_KEY")
    # If Claude token differs, prefer matching that as "active" for --on-failure
    if CLAUDE_SETTINGS.exists():
        try:
            s = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))
            tok = (s.get("env") or {}).get("ANTHROPIC_AUTH_TOKEN") or ""
            if tok and tok in values.values():
                active = tok
        except Exception:
            pass
    active_acct = which_account(active, values) if active else "?"

    if "--status" in args:
        st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
        print(
            f"active={active_acct} (ZAI_API_KEY sha8={sha8(active) if active else '-'})\n"
            f"last_state={json.dumps(st, indent=1)}"
        )
        return 0

    # --- optimistic rotate for StopFailure (no dual probe) ---
    if "--on-failure" in args:
        other = [a for a in values if a != active_acct] or [
            a for a in values if values[a] != active
        ]
        if not other:
            print("FAILED:zai-failover --on-failure no alternative account")
            return 1
        # Prefer account whose key differs from active
        candidates = [a for a in other if values[a] != active] or other
        target = candidates[0]
        # Quick verify target (short timeout); if clearly exhausted, try any remaining
        pr = probe(values[target], timeout=20.0)
        if not pr.get("ok") and pr.get("exhausted"):
            alt = [a for a in candidates[1:] if a != target]
            if alt:
                target = alt[0]
                pr = probe(values[target], timeout=20.0)
        if not pr.get("ok") and pr.get("exhausted"):
            state = {
                "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "action": "on-failure-no-healthy",
                "active_before": active_acct,
                "target_probe": pr,
            }
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
            print("FAILED:zai-failover --on-failure alternative also exhausted")
            return 1
        # Switch even if probe was network-flaky (ok or non-exhaust fail)
        touched = apply_active(values[target], target)
        state = {
            "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": f"on-failure switched {active_acct} -> {target}",
            "active_before": active_acct,
            "active_after": target,
            "target_probe": pr,
            "touched": touched,
            "sha8s": {a: sha8(v) for a, v in values.items()},
        }
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
        print(f"SUCCESS:zai-failover {state['action']}")
        print("NOTE: restart Claude Code / MCP sessions to pick up the new token.")
        return 0

    results = {a: probe(v) for a, v in values.items()}
    for a, r in results.items():
        print(
            f"{a}: ok={r['ok']} status={r['status']} exhausted={r.get('exhausted')} "
            f"({r.get('note','')[:80]})"
        )

    state = {
        "probed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": results,
        "active_before": active_acct,
        "sha8s": {a: sha8(v) for a, v in values.items()},
    }

    if "--probe-only" in args:
        state["action"] = "probe-only"
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
        return 0

    active_res = results.get(active_acct)
    need_switch = active_acct == "?" or (
        active_res and not active_res["ok"] and active_res.get("exhausted")
    )
    if need_switch:
        other = [a for a in results if a != active_acct]
        healthy = [a for a in other if results[a]["ok"]] or [
            a for a in other if not results[a].get("exhausted")
        ]
        if not healthy:
            state["action"] = "no-healthy-alternative"
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
            print("FAILED:zai-failover active exhausted AND no healthy alternative")
            return 1
        target = healthy[0]
        touched = apply_active(values[target], target)
        state["action"] = f"switched {active_acct} -> {target}"
        state["active_after"] = target
        state["touched"] = touched
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
        print(f"SUCCESS:zai-failover {state['action']}")
        print(
            "NOTE: restart Claude Code / MCP sessions to pick up the new token."
        )
        return 0

    state["action"] = "no-switch-needed"
    state["active_after"] = active_acct
    # Keep Claude token aligned with active even when no switch
    if active and active_acct != "?":
        state["touched"] = apply_active(active, active_acct)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1), encoding="utf-8")
    print(f"SUCCESS:zai-failover active key ({active_acct}) healthy; no switch")
    return 0


if __name__ == "__main__":
    sys.exit(main())
