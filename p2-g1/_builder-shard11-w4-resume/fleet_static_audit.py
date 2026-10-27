#!/usr/bin/env python3
"""Static G-1 delivered audit over the full catalog (no live probe re-runs).
Mirrors _measure_one_delivered.py checks 1-7 minus the probe re-run."""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None

def digest_file(path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()

def probe_cmds_available(ret: dict | None, probe_dir: Path) -> bool:
    if isinstance(ret, dict):
        n = 0
        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
            if isinstance(item, dict) and isinstance(item.get("command"), str) and item["command"].strip():
                n += 1
        if n >= 1:
            return True
    if any(probe_dir.glob("probe1*.py")) and any(probe_dir.glob("probe2*.py")):
        return True
    return (probe_dir / "run_probes.py").is_file()

def main() -> int:
    data = load_json(CATALOG)
    units = {u.get("id"): u for u in data.get("work_units", []) if isinstance(u, dict) and UID_RE.match(u.get("id") or "")}
    stats = {"catalog": len(units), "delivered_static": 0, "state_success": 0, "state_blocked": 0,
             "receipt_missing": 0, "manifest_mismatch": 0, "return_bad": 0, "probedir_missing": 0,
             "unparseable": 0, "sentinel_absent": 0, "nocmds": 0, "other": 0}
    fails = []
    for uid, unit in sorted(units.items()):
        reason = None
        probe_dir = PROBES / uid
        if not probe_dir.is_dir():
            stats["probedir_missing"] += 1; reason = "predicate:absent(probedir)"
        else:
            out_rel = str(unit.get("output_path") or "").replace("\\", "/")
            out = REPO / out_rel if out_rel else None
            doc = load_json(out) if out else None
            if doc is None:
                stats["receipt_missing"] += 1; reason = "receipt-missing-or-unparseable"
            else:
                st = str(doc.get("state") or "").upper()
                if st == "SUCCESS":
                    stats["state_success"] += 1
                elif st in NOT_DELIVERING:
                    stats["state_blocked"] += 1
                sentinel = str(unit.get("completion_sentinel") or "")
                text = ""
                try: text = out.read_text(encoding="utf-8")
                except OSError: text = ""
                ret = load_json(probe_dir / "SUBAGENT-RETURN.json")
                man = load_json(probe_dir / "UNIT-ARTIFACT-MANIFEST.json")
                if sentinel and sentinel not in text:
                    stats["sentinel_absent"] += 1; reason = "sentinel-absent"
                elif not isinstance(ret, dict):
                    stats["return_bad"] += 1; reason = "return-missing-unparseable"
                elif str(ret.get("status") or ret.get("state") or "").upper() in NOT_DELIVERING:
                    stats["return_bad"] += 1; reason = "return:" + str(ret.get("status") or ret.get("state"))
                elif not probe_cmds_available(ret, probe_dir):
                    stats["nocmds"] += 1; reason = "named-probes-absent"
                elif not isinstance(man, dict):
                    stats["manifest_mismatch"] += 1; reason = "manifest-unparseable"
                else:
                    rows = [a for a in (man.get("artifacts") or []) if isinstance(a, dict) and a.get("unit_id") == uid]
                    live_sha = digest_file(out)
                    if not any(str(a.get("path") or "").replace("\\","/") == out_rel and str(a.get("sha256") or "") == live_sha and a.get("present") is True for a in rows):
                        stats["manifest_mismatch"] += 1; reason = "manifest-sha-mismatch"
                    else:
                        stats["delivered_static"] += 1
        if reason:
            fails.append((uid, reason))
    (REPO / "_builder-shard11-w4-resume" / "fleet_static_audit_out.json").write_text(
        json.dumps({"stats": stats, "fails": fails}, indent=1), encoding="utf-8")
    print(json.dumps(stats, indent=1))
    print(f"FAILED-unit-count={len(fails)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
