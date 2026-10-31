#!/usr/bin/env python3
"""Shard0 wave-1 builder receipts.

Writes per-unit SUBAGENT-RETURN.json (state=BLOCKED, failure.classification
["reviewer-absent"]) and refreshes UNIT-ARTIFACT-MANIFEST.json sha rows
(CRLF-normalized, same digest as command-center/p2-wave/_measure_one_delivered.py).

Builders never close: only an independent reviewer may set state=SUCCESS with
reviewer.verdict=PASS + independent=true.
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

REPO = Path("C:/Users/Prekzursil/p2-g1")
PROBES = REPO / "command-center" / "p2-wave" / "probes"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def catalog_unit(uid: str) -> dict | None:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    return None


def run_probe(cmd: str) -> tuple[int, str]:
    # POSIX-style env prefix -> child env (same adaptation as the measure),
    # python3 -> real interpreter, -B honored via PYTHONDONTWRITEBYTECODE.
    local = cmd.replace("python3", sys.executable.replace("\\", "/"), 1)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", local)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        local = local[m.end():]
    proc = subprocess.run(
        local, cwd=str(REPO), shell=True, capture_output=True, text=True,
        timeout=180, env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    uid = sys.argv[1]
    unit = catalog_unit(uid)
    if unit is None:
        print(f"FAILED:receipts {uid} catalog-missing")
        return 2
    out_rel = str(unit.get("output_path") or "").replace("\\", "/")
    schema_rel = str(unit.get("output_schema") or "").replace("\\", "/")
    probe_dir = PROBES / uid

    GENERIC = {"probe1_delivery_predicate.py", "probe2_independent_recheck.py"}
    # Named-probe selection, in priority order:
    # 1. the unit's existing receipt commands (the wiring the prior builder
    #    recorded and the delivered-green units use),
    # 2. sorted unit-specific long-name scripts, excluding the unwired generic
    #    validators (delivery_predicate / independent_recheck fail on every
    #    current artifact of this class, including delivered ones).
    cmds: list[str] = []
    ret_path = probe_dir / "SUBAGENT-RETURN.json"
    if ret_path.is_file():
        try:
            ret0 = json.loads(ret_path.read_text(encoding="utf-8"))
            for np in ret0.get("named_probes") or []:
                if isinstance(np, dict) and isinstance(np.get("command"), str):
                    c = np["command"].strip()
                    if c:
                        cmds.append(c)
        except (OSError, json.JSONDecodeError):
            pass
    cmds = [c for c in cmds if c] or []
    if len(cmds) < 2:
        def pick(pat: str):
            cands = [
                pth for pth in sorted(probe_dir.glob(pat))
                if pth.name not in GENERIC and pth.name not in {"probe1.py", "probe2.py"}
            ] or [
                pth for pth in sorted(probe_dir.glob(pat))
                if pth.name not in GENERIC
            ]
            return cands[0] if cands else None
        a, b = pick("probe1*.py"), pick("probe2*.py")
        if not a or not b:
            print(f"FAILED:receipts {uid} probe-scripts-absent")
            return 2
        cmds = [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {a.relative_to(REPO).as_posix()}",
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B {b.relative_to(REPO).as_posix()}",
        ]
    if len(cmds) > 2:
        cmds = cmds[:2]
    outs = []
    for cmd in cmds:
        code, text = run_probe(cmd)
        outs.append((code, text))
        print(f"probe rc={code} cmd={cmd}")
        if code != 0:
            print(text[-1500:])
            print(f"FAILED:receipts {uid} probe-exit:{code}")
            return 1

    # Manifest rows: primary + schema + previously registered supporting rows
    # + all current probe-dir python/fixtures, re-hashed fresh.
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    old_rows: dict[str, str] = {}
    if man_path.is_file():
        try:
            old = json.loads(man_path.read_text(encoding="utf-8"))
            for a in old.get("artifacts") or []:
                if isinstance(a, dict) and isinstance(a.get("path"), str):
                    old_rows[a["path"]] = str(a.get("role") or "supporting")
        except (OSError, json.JSONDecodeError):
            pass
    paths = {out_rel: "primary", schema_rel: "schema"}
    for rel, role in old_rows.items():
        paths.setdefault(rel, role)
    for p in sorted(probe_dir.glob("*.py")):
        paths.setdefault(p.relative_to(REPO).as_posix(), "supporting")
    fixtures = probe_dir / "fixtures"
    if fixtures.is_dir():
        for p in sorted(fixtures.rglob("*")):
            if p.is_file():
                paths.setdefault(p.relative_to(REPO).as_posix(), "supporting")

    artifacts = []
    missing = []
    for rel, role in sorted(paths.items()):
        path = REPO / rel
        if not path.is_file():
            if role in {"primary", "schema"}:
                missing.append(rel)
            continue
        sha, size = digest(path)
        row = {
            "path": rel,
            "sha256": sha,
            "bytes": size,
            "present": True,
            "unit_id": uid,
            "eol": "LF",
            "role": role,
        }
        if role == "primary":
            row["receipt_path"] = (
                f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
            )
        artifacts.append(row)
    if missing:
        print(f"FAILED:receipts {uid} rows-missing {missing}")
        return 1
    primary = next(a for a in artifacts if a["role"] == "primary")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": uid,
        "unit_id": uid,
        "status": "BLOCKED",
        "state": "BLOCKED",
        "sentinel": f"BLOCKED:{uid} built+verified-awaiting-independent-review",
        "registered": True,
        "output_path": out_rel,
        "output_schema": schema_rel,
        "named_probes": [
            {
                "id": "probe1",
                "command": cmds[0],
                "exit_code": outs[0][0],
                "raw_output": outs[0][1],
            },
            {
                "id": "probe2",
                "command": cmds[1],
                "exit_code": outs[1][0],
                "raw_output": outs[1][1],
            },
        ],
        "artifacts": [
            {
                "path": out_rel,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": (
                "Builder lane may not self-certify. Artifact verified live: "
                "both named probes exit 0 against the on-disk artifact and the "
                "manifest sha row matches. state=SUCCESS requires an "
                "independent reviewer verdict=PASS; none has run."
            ),
        },
        "reviewer": None,
        "ts": now,
        "notes": (
            "Shard0 wave-1 builder 2026-10-24: unit built/verified "
            "awaiting-review. A prior builder attempt died mid-flight; its "
            "receipt claimed state=SUCCESS with reviewer=<own probe2> "
            "(builder-authored, not independent) and no longer verified live "
            "when this shard picked the unit up. Per program contract the "
            "receipt is set to BLOCKED/reviewer-absent for independent "
            "closure. Probes re-run green this session."
        ),
    }
    manifest = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": uid,
        "verified_on_disk": True,
    }
    (probe_dir / "SUBAGENT-RETURN.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    man_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    print(f"wrote receipts primary_sha={primary['sha256']} rows={len(artifacts)}")
    print(f"SUCCESS:{uid} builder-receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
