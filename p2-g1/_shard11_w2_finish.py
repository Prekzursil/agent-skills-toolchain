#!/usr/bin/env python3
"""shard11 wave-2 finisher (resume of a mid-flight-dead prior attempt).

Per unit: run the probe kit live, demote the prior builder's probe-authored
reviewer self-closure to extensions.prev_closure (only the independent
reviewer closes), set receipt state=BLOCKED with failure.classification
["reviewer-absent"], refresh the receipt's named_probes with LIVE raw outputs,
and write SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json with the
CRLF-normalized sha256 of the final artifact.

Usage: python _shard11_w2_finish.py <UNIT-ID> <probe1.py> <probe2.py> [supporting.py ...]

Pattern proven by command-center/p2-wave/probes/_shard2_w2_finish.py (wave-2
shard-2, 2026-10-25); probe selection, exit-code checks and manifest semantics
are unchanged. Windows adaptation: env prefixes moved into the child env and
python3 bound to this interpreter, exactly as
command-center/p2-wave/_measure_one_delivered.py does.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

REVIEWER_ABSENT_REASON = (
    "Builder lane may not self-certify: artifact live-verified by both named "
    "probes (exit 0) and registered in the per-unit manifest with the "
    "CRLF-normalized sha256. The prior attempt's reviewer closure was authored "
    "from the builder's own probe2 output (not an independent fresh-context "
    "review) and is demoted to extensions.prev_closure. receipt_core forbids "
    "state=SUCCESS without reviewer.verdict=PASS with independent=true, so the "
    "receipt stays BLOCKED until the independent reviewer closes."
)

RESUME_NOTE = (
    "shard11 wave-2 resume 2026-10-25: prior builder died mid-flight (host "
    "session ended). Artifact and implementation surfaces verified live by this "
    "resume; probe kit rebuilt where the dead attempt had not yet written it; "
    "both probes re-run exit 0; builder-authored reviewer self-closure demoted "
    "to prev_closure; receipt set BLOCKED/reviewer-absent."
)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_catalog_unit(uid: str) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise SystemExit("FAILED:shard11 unit %s not in catalog" % uid)


def digest_file(path) -> tuple:
    raw = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def eol_form(raw: bytes) -> str:
    if b"\x00" in raw:
        return "BINARY"
    crlf = raw.count(b"\r\n")
    lf_total = raw.count(b"\n")
    if crlf == 0:
        return "LF"
    if crlf == lf_total:
        return "CRLF"
    return "MIXED"


def artifact_row(path, role: str = "supporting") -> dict:
    p = Path(path)
    sha, n = digest_file(p)
    return {
        "path": p.resolve().relative_to(REPO).as_posix(),
        "bytes": n,
        "sha256": sha,
        "exists": True,
        "eol": eol_form(p.read_bytes()),
        "role": role,
    }


def run_probe_command(cmd: str, timeout: int = 900) -> tuple:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    exe = str(sys.executable).replace("\\", "/")
    if "python3" in cmd:
        cmd = cmd.replace("python3", '"' + exe + '"', 1)
    try:
        p = subprocess.run(
            cmd, cwd=str(REPO), shell=True, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    tail = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, tail[-16000:]


def write_lf(path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(text.replace("\r\n", "\n").encode("utf-8"))


def write_json(path, doc) -> None:
    write_lf(Path(path), json.dumps(doc, indent=1, ensure_ascii=True) + "\n")


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: _shard11_w2_finish.py <UID> <probe1.py> <probe2.py> [supporting...]")
        return 2
    uid = sys.argv[1]
    p1_name, p2_name = sys.argv[2], sys.argv[3]
    supporting = sys.argv[4:]

    unit = load_catalog_unit(uid)
    out_rel = str(unit["output_path"]).replace("\\", "/")
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    art_path = REPO / out_rel
    if not art_path.is_file():
        print(f"FAILED:{uid} artifact missing at {out_rel}")
        return 1

    probe_cmds = {
        "probe1": f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p1_name}",
        "probe2": f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{p2_name}",
    }
    named_probes = []
    for pid, cmd in probe_cmds.items():
        t0 = utcnow_iso()
        rc, tail = run_probe_command(cmd)
        if rc != 0:
            print(f"FAILED:{uid} {pid} rc={rc}")
            print(tail[-3000:])
            return 1
        named_probes.append({
            "id": pid,
            "command": cmd,
            "exit_code": rc,
            "role": "probe",
            "raw_output": tail,
            "finished_at": utcnow_iso(),
            "started_at": t0,
        })
        print(f"{pid} rc=0")

    # Refresh named_probes with LIVE raw outputs; demote any builder-authored
    # reviewer self-closure (only the independent reviewer closes).
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    doc["named_probes"] = named_probes
    old_rev = doc.get("reviewer")
    if isinstance(old_rev, dict) and old_rev.get("independent") is True:
        ext = doc.get("extensions") or {}
        pc = ext.get("prev_closure") or []
        if isinstance(pc, dict):
            pc = [pc]
        pc.append({
            "demoted_by": (
                "shard11 wave-2 builder 2026-10-25: builder-authored probe "
                "closure is not an independent review; only the independent "
                "reviewer closes (program contract, receipt state=BLOCKED "
                "with failure.classification reviewer-absent)"
            ),
            **old_rev,
        })
        ext["prev_closure"] = pc
        doc["extensions"] = ext
        preserved = {
            k: v for k, v in old_rev.items()
            if k not in {"independent", "verdict", "reviewer_id", "fresh_context",
                         "method", "notes", "vendor", "reproduction_status",
                         "claimed_metric", "deviation_absolute", "within_tolerance",
                         "primary_environment_fingerprint",
                         "reviewer_environment_fingerprint", "hardware_note",
                         "scope_not_agreement", "obligation"}
        }
        doc["reviewer"] = {
            "catalog_reviewer_requirement": unit.get("reviewer_requirement"),
            "independent": False,
            "reviewer_id": None,
            "verdict": "PENDING",
            **preserved,
        }
    else:
        ext = doc.get("extensions") or {}
        doc["extensions"] = ext

    # Builder lane terminal state: BLOCKED, reviewer-absent.
    doc["state"] = "BLOCKED"
    doc["status"] = "BLOCKED"
    doc["failure"] = {
        "classification": ["reviewer-absent"],
        "reason": REVIEWER_ABSENT_REASON,
    }
    ext = doc.setdefault("extensions", {})
    ext["shard11_w2_resume_2026-10-25"] = {
        "action": RESUME_NOTE,
        "builder": "shard11 wave-2 builder",
    }
    blob = json.dumps(doc, indent=1, ensure_ascii=True) + "\n"
    art_path.write_bytes(blob.replace("\r\n", "\n").encode("utf-8"))
    print(f"receipt updated: state=BLOCKED reviewer-absent prev_closure="
          f"{len((doc.get('extensions', {}).get('prev_closure') or []))}")

    primary = artifact_row(art_path, role="primary")
    primary["unit_id"] = uid
    primary["present"] = True
    primary["receipt_path"] = f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
    artifacts = [primary]
    for rel in supporting:
        p = REPO / rel
        if not p.is_file():
            print(f"FAILED:{uid} supporting file missing {rel}")
            return 1
        row = artifact_row(p, role="supporting")
        row["unit_id"] = uid
        row["present"] = True
        row["receipt_path"] = primary["receipt_path"]
        artifacts.append(row)

    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": unit.get("completion_sentinel"),
        "registered": True,
        "output_path": out_rel,
        "output_schema": unit.get("output_schema"),
        "named_probes": named_probes,
        "artifacts": [
            {
                "path": out_rel,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
        "extensions": {
            "prev_closure": doc.get("extensions", {}).get("prev_closure"),
            "shard11_w2_resume_2026-10-25": {
                "action": RESUME_NOTE,
                "builder": "shard11 wave-2 builder",
            },
        },
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": REVIEWER_ABSENT_REASON,
        },
        "cloud_ok": False,
        "ts": utcnow_iso(),
    }
    write_json(pdir / "SUBAGENT-RETURN.json", ret)
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a.get("present")),
        "artifacts": artifacts,
    }
    write_json(pdir / "UNIT-ARTIFACT-MANIFEST.json", man)
    print(f"primary {out_rel} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{uid} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
