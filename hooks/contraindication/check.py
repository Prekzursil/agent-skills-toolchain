#!/usr/bin/env python3
r"""contraindication/check.py — PreToolUse hook: tool/action contraindication registry.

Loads contraindications.json (same directory) and matches the pending tool call against
each row's tool_pattern + input_pattern (+ optional bg-registry activity gate). On any
hit this hook INJECTS (exit 0 + additionalContext) the documented harm and safe_alternative.

NEVER blocks — inject-only. FAIL-OPEN: any exception -> exit 0. Pure stdlib.
Opt-out: set env CONTRAINDICATION=off (or "0"/"false") OR create a .disabled file here.

Adding a row: every "X + Y broke Z" becomes a row in contraindications.json. The format
is the entire point — the hook stays frozen; only the data file grows.

Settings.json wire spec (PreToolUse):
  Matcher:       Edit|Write|Bash|PowerShell|mcp__.*
  Command:       python C:/Users/Prekzursil/.claude/hooks/contraindication/check.py
  Timeout:       5000
  StatusMessage: Contraindication registry check
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

THIS = Path(__file__).resolve().parent
DISABLED = THIS / ".disabled"
REGISTRY = THIS / "contraindications.json"

# ---------------------------------------------------------------------------
# Calibrated-silence path setup (fail-open import)
# ---------------------------------------------------------------------------
_CAL_SIL_DIR = str(THIS.parent / "calibrated-silence")
if _CAL_SIL_DIR not in sys.path:
    sys.path.insert(0, _CAL_SIL_DIR)

# bg-registry dir: populated by bg-registry/register.py on Task spawns.
_BG_DIR = Path(os.environ.get("BG_REGISTRY_DIR",
                               str(Path.home() / ".claude" / "bg-registry")))
# Only consider bg-registry records created in the last N seconds as "active".
_BG_MAX_AGE_SEC = int(os.environ.get("CONTRAINDICATION_BG_MAX_AGE", str(4 * 3600)))

# Per-session "already surfaced" state. A contraindication is a tool-combo HARM
# warning (DDI-style): a NEW/distinct one must ALWAYS surface, but an exact REPEAT
# in the same session may be deduplicated by calibrated-silence. We track which
# contraindication ids were already surfaced this session in a small JSON file,
# auto-cleared after _SEEN_TTL_HOURS. Env-overridable so tests stay hermetic.
_SEEN_DIR = Path(os.environ.get(
    "CONTRAINDICATION_SEEN_DIR",
    str(Path.home() / ".claude" / "contraindication"),
))
_SEEN_TTL_HOURS = float(os.environ.get("CONTRAINDICATION_SEEN_TTL_HOURS", "4"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _disabled() -> bool:
    return (DISABLED.exists()
            or os.environ.get("CONTRAINDICATION", "").lower() in ("off", "0", "false"))


def _emit(msg: str) -> None:
    """Inject additionalContext — the only output this hook ever produces."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": msg,
        }
    }))


def _cs_allow(itype: str, context: dict) -> bool:
    """Gate through calibrated-silence. Fail-open = True if module unavailable."""
    try:
        import calibrated_silence  # noqa: PLC0415
        ctx = dict(context)
        ledger = os.environ.get("CALSIL_LEDGER_PATH")
        if ledger:
            ctx["ledger_path"] = ledger
        allow, _ = calibrated_silence.should_interject(itype, ctx)
        return bool(allow)
    except Exception:
        return True  # fail-open


def _seen_path(session_id: str) -> Path:
    """Per-session state file path (sha1 of the session id, like iatrogenics)."""
    try:
        h = hashlib.sha1(session_id.encode("utf-8", "replace")).hexdigest()[:24]
        return _SEEN_DIR / f"{h}.json"
    except Exception:
        return _SEEN_DIR / "default.json"


def _load_seen(session_id: str) -> dict:
    """Load the per-session {contraindication_id: surfaced_count} map.

    Returns {} if absent, corrupt, or older than the TTL (auto-clear). Fail-open.
    """
    p = _seen_path(session_id)
    try:
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {}
        ts = float(data.get("_ts", 0))
        if time.time() - ts > _SEEN_TTL_HOURS * 3600:
            return {}  # stale -> treat every finding as distinct again
        return data
    except Exception:
        return {}


def _save_seen(session_id: str, seen: dict) -> None:
    """Persist the per-session seen map (best-effort, fail-open)."""
    try:
        _SEEN_DIR.mkdir(parents=True, exist_ok=True)
        seen["_ts"] = time.time()
        _seen_path(session_id).write_text(json.dumps(seen), encoding="utf-8")
    except Exception:
        pass


def _load_registry() -> list[dict]:
    """Return the list of contraindication rows; empty list on any error."""
    try:
        raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            rows = raw.get("rows")
            return rows if isinstance(rows, list) else []
        return []
    except Exception:
        return []


def _bg_has_running_async() -> bool:
    """True if bg-registry contains any running, async sub-agent task started recently.

    This is the cheap signal for PARA-GIT-ADD: parallel subagents are active, so a
    broad 'git add -A' could sweep their in-progress files into the wrong commit.
    """
    try:
        cutoff = time.time() - _BG_MAX_AGE_SEC
        for ndjson_path in _BG_DIR.glob("*.ndjson"):
            try:
                effective: dict = {}
                text = ndjson_path.read_text(encoding="utf-8", errors="replace")
                for line in text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    rid = rec.get("id")
                    if not rid:
                        continue
                    # fold: last write wins per key
                    if rid in effective:
                        effective[rid].update(rec)
                    else:
                        effective[rid] = dict(rec)
                for rec in effective.values():
                    if (rec.get("status") == "running"
                            and not rec.get("sync", True)
                            and float(rec.get("started_ts") or 0) >= cutoff):
                        return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _check_row(row: dict, tool_name: str, input_str: str) -> bool:
    """Return True if the row fires for the pending tool call."""
    try:
        # 1. tool_name must match tool_pattern (if given)
        tp = row.get("tool_pattern")
        if tp and not re.search(tp, tool_name, re.IGNORECASE):
            return False
        # 2. serialised input must match input_pattern (if given)
        ip = row.get("input_pattern")
        if ip and not re.search(ip, input_str, re.IGNORECASE):
            return False
        # 3. optional: only fire when bg-registry has active async tasks
        if row.get("require_bg_active"):
            if not _bg_has_running_async():
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    try:
        if _disabled():
            return 0

        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except Exception:
            return 0  # malformed stdin -> fail-open

        tool_name = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input") or {}
        session_id = str(payload.get("session_id") or payload.get("cwd") or "default")
        input_str = json.dumps(tool_input)

        rows = _load_registry()
        hits: list[dict] = []
        for row in rows:
            if _check_row(row, tool_name, input_str):
                hits.append(row)

        if not hits:
            return 0

        # Distinct-vs-repeat partition (per session). A contraindication is a
        # tool-combo HARM warning (DDI-style); a NEW/distinct one must NEVER be
        # silenced just because the session is long or noisy. Calibrated-silence
        # is allowed to DEDUP an exact repeat, never to gag a new safety alert.
        seen = _load_seen(session_id)
        hit_ids = [str(row.get("id", "UNKNOWN")) for row in hits]
        all_repeats = bool(hit_ids) and all(hid in seen for hid in hit_ids)
        if all_repeats:
            # Every matched contraindication was already surfaced this session ->
            # a pure repeat: let calibrated-silence dedup it (fail-open = allow).
            if not _cs_allow("gem", {"session_id": session_id}):
                return 0
        # else: at least one NEW harm warning in this call -> bypass CS, always surface.

        # Record every surfaced id so a later identical call counts as a repeat.
        for hid in hit_ids:
            seen[hid] = int(seen.get(hid, 0) or 0) + 1
        _save_seen(session_id, seen)

        parts: list[str] = []
        for row in hits:
            rid = row.get("id", "UNKNOWN")
            harm = row.get("harm", "(harm not documented)")
            alt = row.get("safe_alternative", "(no alternative documented)")
            parts.append(
                f"[{rid}]\n"
                f"  HARM: {harm}\n"
                f"  SAFE ALTERNATIVE: {alt}"
            )

        msg = (
            "CONTRAINDICATION REGISTRY — known dangerous tool/action combination detected:\n\n"
            + "\n\n".join(parts)
            + "\n\nThis is an advisory only. Proceed if you have verified this does not apply."
        )
        _emit(msg)

    except Exception:
        pass  # fail-open: never surface an internal error as a hook failure

    return 0


if __name__ == "__main__":
    sys.exit(main())
