#!/usr/bin/env python3
"""AUD-0059 NAMED PROBE 1: search hook logs / event ledgers for per-hook fire records.

Catalog evidence_requirement Probe 1:
  search the hook logs and event ledger for per-hook fire records.

Registered is not the same as firing. This probe enumerates registered hooks
(from the AUD-0013 dispatch manifest + agent-self settings) and searches live
ledgers plus any on-disk fire logs. A planted known-fire fixture must be found
by the searcher — an empty hit set against the planted log means the instrument
is broken, not that nothing ever fired.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe1-fire-log-search.json"
RAW = PROBE / "probe1-fire-log-search.raw.txt"
PLANTED_LOG = PROBE / "fixtures" / "planted_fire_log.jsonl"
MANIFEST = REPO / "hooks" / "_dispatch" / "manifest.json"
SETTINGS = REPO / "agent-self" / "config" / "settings.json"
H4 = REPO / "command-center" / "hook-audit" / "H4-TIMING-live.json"

MARKER = "AUD-0059-KNOWN-FIRE"


def _norm_name(s: str) -> str:
    s = s.replace("\\", "/").strip()
    # strip common prefixes / suffixes to a stable hook id
    for prefix in (
        "python ",
        "python3 ",
        "pwsh ",
        "node ",
        "bash ",
    ):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :]
    s = s.strip().strip('"').strip("'")
    # keep last two path components when absolute
    parts = [p for p in s.replace("\\", "/").split("/") if p]
    if len(parts) >= 2 and parts[-1].endswith((".py", ".ps1", ".js", ".sh")):
        return f"{parts[-2]}/{parts[-1]}"
    if parts:
        return parts[-1]
    return s


def load_registered() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()

    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for event, body in (man.get("events") or {}).items():
            for chk in body.get("checks") or []:
                script = str(chk.get("script") or "")
                name = str(chk.get("name") or script)
                key = f"dispatch:{name}"
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": name,
                        "script": script,
                        "source": "hooks/_dispatch/manifest.json",
                        "event": event,
                        "plane": "dispatcher",
                    }
                )

    if SETTINGS.is_file():
        doc = json.loads(SETTINGS.read_text(encoding="utf-8"))
        for event, groups in (doc.get("hooks") or {}).items():
            for grp in groups or []:
                matcher = grp.get("matcher") if isinstance(grp, dict) else None
                for h in (grp.get("hooks") or []) if isinstance(grp, dict) else []:
                    cmd = str(h.get("command") or "")
                    nid = _norm_name(cmd)
                    key = f"settings:{event}:{nid}:{matcher}"
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "id": nid,
                            "script": cmd,
                            "source": "agent-self/config/settings.json",
                            "event": event,
                            "matcher": matcher,
                            "plane": "settings",
                        }
                    )
    return rows


def ledger_roots() -> list[Path]:
    home = Path.home()
    return [
        home / ".claude" / "event-ledger",
        home / ".claude" / "stub-ledger",
        Path("/tmp") / "claude-claim-ledger",
        REPO / ".claude" / "event-ledger",
        REPO / ".claude" / "stub-ledger",
    ]


def collect_log_blobs() -> list[dict]:
    """Gather searchable text blobs from live ledgers + planted fixture + optional audit."""
    blobs: list[dict] = []

    # Planted known-fire control (must hit)
    if PLANTED_LOG.is_file():
        blobs.append(
            {
                "path": str(PLANTED_LOG.relative_to(REPO)).replace("\\", "/"),
                "kind": "planted-control",
                "text": PLANTED_LOG.read_text(encoding="utf-8", errors="replace"),
                "exists": True,
                "bytes": PLANTED_LOG.stat().st_size,
            }
        )

    for root in ledger_roots():
        if not root.exists():
            blobs.append(
                {
                    "path": str(root),
                    "kind": "live-ledger-root",
                    "text": "",
                    "exists": False,
                    "bytes": 0,
                }
            )
            continue
        files = [
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.suffix.lower() in {".jsonl", ".ndjson", ".json", ".log", ".txt"}
        ]
        if not files:
            blobs.append(
                {
                    "path": str(root),
                    "kind": "live-ledger-root-empty",
                    "text": "",
                    "exists": True,
                    "bytes": 0,
                }
            )
        for p in files[:200]:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = ""
            blobs.append(
                {
                    "path": str(p),
                    "kind": "live-ledger-file",
                    "text": text[:500_000],
                    "exists": True,
                    "bytes": p.stat().st_size,
                }
            )

    # Committed audit fire-timing is NOT a real-turn ledger; record separately.
    if H4.is_file():
        blobs.append(
            {
                "path": "command-center/hook-audit/H4-TIMING-live.json",
                "kind": "audit-controlled-fire",
                "text": H4.read_text(encoding="utf-8", errors="replace")[:500_000],
                "exists": True,
                "bytes": H4.stat().st_size,
            }
        )
    return blobs


def search_hook(hook_id: str, script: str, blobs: list[dict]) -> dict:
    needles = []
    for cand in (hook_id, script, Path(script).name if script else ""):
        c = str(cand).strip()
        if c and len(c) >= 3:
            needles.append(c)
    needles = list(dict.fromkeys(needles))

    hits = []
    for b in blobs:
        text = b.get("text") or ""
        if not text:
            continue
        for n in needles:
            if n in text:
                # classify
                if b["kind"] == "planted-control":
                    cls = "planted-control"
                elif b["kind"] == "audit-controlled-fire":
                    cls = "audit-controlled-fire"
                else:
                    cls = "live-ledger"
                hits.append({"path": b["path"], "kind": cls, "needle": n})
                break
    live = [h for h in hits if h["kind"] == "live-ledger"]
    audit = [h for h in hits if h["kind"] == "audit-controlled-fire"]
    planted = [h for h in hits if h["kind"] == "planted-control"]
    return {
        "live_turn_fire_evidence": bool(live),
        "audit_controlled_fire_evidence": bool(audit),
        "planted_fixture_hit": bool(planted),
        "hits": hits[:20],
    }


def planted_control_ok(blobs: list[dict]) -> dict:
    """Searcher must find MARKER in the planted log — otherwise the instrument is broken."""
    planted = next((b for b in blobs if b["kind"] == "planted-control"), None)
    if planted is None:
        return {
            "ok": False,
            "reason": "planted fire log missing",
            "marker_found": False,
        }
    found = MARKER in (planted.get("text") or "")
    # Also require the searcher path finds it via a synthetic hook id
    syn = search_hook("planted/known-fire-record", "planted/known-fire-record", blobs)
    ok = found and syn["planted_fixture_hit"]
    return {
        "ok": ok,
        "marker_found": found,
        "searcher_hit": syn["planted_fixture_hit"],
        "description": (
            "Planted known-fire fixture must be found by the same searcher used "
            "for live ledgers; empty hits against the planted log = broken instrument."
        ),
    }


def main() -> int:
    registered = load_registered()
    blobs = collect_log_blobs()
    control = planted_control_ok(blobs)

    per_hook = []
    live_count = 0
    audit_count = 0
    none_count = 0
    for row in registered:
        ev = search_hook(row["id"], row.get("script") or "", blobs)
        if ev["live_turn_fire_evidence"]:
            live_count += 1
            status = "live-fire-evidence"
        elif ev["audit_controlled_fire_evidence"]:
            audit_count += 1
            status = "audit-controlled-fire-only"
        else:
            none_count += 1
            status = "no-fire-evidence"
        per_hook.append({**row, "fire_status": status, "evidence": ev})

    live_roots = [
        {
            "path": b["path"],
            "exists": b["exists"],
            "bytes": b["bytes"],
            "kind": b["kind"],
        }
        for b in blobs
        if b["kind"].startswith("live-ledger")
    ]
    live_present = any(b["exists"] and b["bytes"] > 0 for b in live_roots)

    result = {
        "ok": control["ok"],
        "unit": "AUD-0059",
        "probe": 1,
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "registered_count": len(registered),
        "with_live_turn_fire_evidence": live_count,
        "with_audit_controlled_fire_only": audit_count,
        "with_no_fire_evidence": none_count,
        "live_ledger_present": live_present,
        "live_ledger_roots": live_roots,
        "planted_control": control,
        "per_hook": per_hook,
        "notes": (
            "Live event-ledger / stub-ledger absence means Probe 1 cannot attest "
            "real-turn firing for registered hooks; audit H4 timing is controlled "
            "fire during a prior audit, not a real turn. Planted fixture validates "
            "the searcher."
        ),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0059 NAMED PROBE 1: per-hook fire-log / ledger search",
        "unit=AUD-0059",
        f"registered_count={len(registered)}",
        f"live_turn_fire_evidence={live_count}",
        f"audit_controlled_fire_only={audit_count}",
        f"no_fire_evidence={none_count}",
        f"live_ledger_present={live_present}",
        f"planted_control_ok={control['ok']} marker_found={control.get('marker_found')}",
    ]
    for root in live_roots:
        lines.append(
            f"LEDGER_ROOT\texists={root['exists']}\tbytes={root['bytes']}\t"
            f"kind={root['kind']}\tpath={root['path']}"
        )
    for row in per_hook[:40]:
        lines.append(
            f"HOOK\t{row['fire_status']}\tplane={row['plane']}\tevent={row['event']}\tid={row['id']}"
        )
    if len(per_hook) > 40:
        lines.append(f"... +{len(per_hook) - 40} more hooks")
    lines.append(
        "SUCCESS:AUD-0059-probe1" if control["ok"] else "FAILED:AUD-0059-probe1"
    )
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if control["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
