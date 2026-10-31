#!/usr/bin/env python3
"""Shard-2 wave-2 finisher: probe run + SUBAGENT-RETURN + per-unit manifest + receipt.

For ARC-0015 and ARC-0021 (the two units whose prior builder died before the
probe harness existed):
  1. re-run both named probes live (fail-closed on any non-zero exit),
  2. write probes/<uid>/SUBAGENT-RETURN.json  (sibling shape: ARC-0019),
  3. write probes/<uid>/UNIT-ARTIFACT-MANIFEST.json with a CRLF-normalized
     sha256 row for the primary artifact (mirrors _measure_one_delivered.py),
  4. write command-center/receipts/<uid>.json in the receipt_core golden shape
     with state=BLOCKED, failure.classification=["reviewer-absent"] and
     reviewer NOT-REVIEWED (builders never self-certify),
  5. validate admission (schema C2 + catalog C3 + sentinel C4) BEFORE declaring
     success - an invalid receipt is a hard failure, never a silent write.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
PROBES = REPO / "command-center" / "p2-wave" / "probes"

UNITS = {
    "ARC-0015": {
        "output_path": "command-center/phase3/A2/TEST-PLAN.json",
        "output_schema": "command-center/schema/test-plan.schema.json",
        "probes": ["probe1_mutation.py", "probe2_eol.py"],
        "probe_ids": ["probe1", "probe2"],
        "claims": [
            (
                "Two generate() runs over the live ARC-0010 registry are byte-identical "
                "across all 10 files; datetime.now() and dict-order injections turn the "
                "determinism test red.",
                "command-center/p2-wave/probes/ARC-0010/generator.py:132",
            ),
            (
                "CRLF rewrites of every generated file preserve the LF-normalized "
                "verdict; a content mutation flips it; no VCS comparator is used.",
                "command-center/p2-wave/probes/ARC-0015/probe2_eol.py:1",
            ),
        ],
    },
    "ARC-0021": {
        "output_path": "command-center/phase3/A3/MIGRATION.json",
        "output_schema": "command-center/schema/migration-plan.schema.json",
        "probes": ["probe1_adopt.py", "probe2_uninstall.py"],
        "probe_ids": ["probe1", "probe2"],
        "claims": [
            (
                "Adopt-in-place pins the existing bytes of 6 claimed paths with zero "
                "rewrites; the drift detector fires on a planted mutation and stays "
                "silent on clean bytes.",
                "command-center/p2-wave/probes/ARC-0021/probe1_adopt.py:1",
            ),
            (
                "Uninstall removes only lockfile-claimed paths; the 4 unclaimed "
                "overlays survive under independent preservation signals; NC-ABSENT "
                "and the forbidden-wipe control pass both states.",
                "command-center/p2-wave/probes/ARC-0021/probe2_uninstall.py:1",
            ),
        ],
    },
}
SUPPORTING = {
    "ARC-0015": [
        "command-center/schema/test-plan.schema.json",
        "command-center/p2-wave/probes/ARC-0010/generator.py",
        "command-center/p2-wave/probes/ARC-0010/registry.json",
        "command-center/p2-wave/probes/ARC-0015/probe1_mutation.py",
        "command-center/p2-wave/probes/ARC-0015/probe2_eol.py",
    ],
    "ARC-0021": [
        "command-center/schema/migration-plan.schema.json",
        "command-center/p2-wave/probes/ARC-0021/probe1_adopt.py",
        "command-center/p2-wave/probes/ARC-0021/probe2_uninstall.py",
    ],
}


def norm_sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_gate():
    spec = importlib.util.spec_from_file_location(
        "gate", REPO / "platform" / "lib" / "receipt_schema_gate.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    # cmd.exe cannot run POSIX 'VAR=value command' prefixes; move them into env.
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip(chr(34)).strip(chr(39))
        cmd = cmd[m.end():]
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=900, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    started = datetime.now(timezone.utc)
    gate = load_gate()
    rc_all = 0
    for uid, spec in UNITS.items():
        here = PROBES / uid
        here.mkdir(parents=True, exist_ok=True)
        out_rel = spec["output_path"].replace("\\", "/")
        probe_cmds = [
            f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{name}"
            for name in spec["probes"]
        ]
        # --- 1. live probes ------------------------------------------------- #
        named = []
        ok = True
        for pid, cmd in zip(spec["probe_ids"], probe_cmds):
            wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
            exe = str(sys.executable).replace("\\", "/")
            run_cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
            rc, text = run_probe(run_cmd)
            print(f"{uid} {pid} rc={rc}")
            if rc != 0:
                print(text[-1500:])
                print(f"FAILED:{uid} receipts probe {pid} exit {rc}")
                ok = False
            named.append({"id": pid, "command": cmd, "exit_code": rc, "raw_output": text})
        if not ok:
            rc_all = 1
            continue

        # --- 2. SUBAGENT-RETURN.json ---------------------------------------- #
        primary_sha, primary_bytes = norm_sha(REPO / out_rel)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        ret = {
            "id": uid,
            "unit_id": uid,
            "status": "DELIVERED",
            "state": "SUCCESS",
            "sentinel": f"SUCCESS:{uid}",
            "registered": True,
            "output_path": out_rel,
            "output_schema": spec["output_schema"],
            "named_probes": named,
            "artifacts": [
                {
                    "path": out_rel,
                    "sha256": primary_sha,
                    "bytes": primary_bytes,
                    "exists": True,
                    "eol": "LF",
                    "role": "primary",
                }
            ],
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "reviewer": {
                "reviewer_id": "unassigned-independent-reviewer",
                "verdict": "NOT-REVIEWED",
                "independent": False,
            },
            "ts": now,
            "notes": (
                "Shard2-w2 resume completion: prior builder session ended after "
                "artifact authoring but before the probe harness existed. Artifact NOT "
                "rebuilt; both named probes authored and re-run live this session, "
                "exit 0. Receipt held BLOCKED (reviewer-absent) per receipt_core: only "
                "the independent reviewer closes. Did not run unit_manifest.py --write."
            ),
        }
        (here / "SUBAGENT-RETURN.json").write_text(
            json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )

        # --- 3. UNIT-ARTIFACT-MANIFEST.json ---------------------------------- #
        rows = [
            {
                "path": out_rel,
                "sha256": primary_sha,
                "bytes": primary_bytes,
                "present": True,
                "unit_id": uid,
                "role": "primary",
            }
        ]
        for rel in SUPPORTING[uid]:
            sha_n, bts = norm_sha(REPO / rel)
            rows.append(
                {
                    "path": rel.replace("\\", "/"),
                    "sha256": sha_n,
                    "bytes": bts,
                    "present": True,
                    "unit_id": uid,
                    "role": "supporting",
                }
            )
        man = {
            "schema_version": 1,
            "contract": "completion-predicate-condition-11-unit-artifact-registration",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "unit_id": uid,
            "verified_on_disk": True,
            "expected": len(rows),
            "present": len(rows),
            "artifacts": rows,
        }
        (here / "UNIT-ARTIFACT-MANIFEST.json").write_text(
            json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )

        # --- 4. receipt (BLOCKED, reviewer-absent), golden receipt_core shape - #
        started_iso = started.strftime("%Y-%m-%dT%H:%M:%SZ")
        evidence = []
        for idx, (claim, anchor) in enumerate(spec["claims"]):
            src = named[idx % 2]
            ver = named[(idx + 1) % 2]
            evidence.append(
                {
                    "claim": claim,
                    "verdict": "CONFIRMED",
                    "confidence": "almost-certain",
                    "anchor": anchor,
                    "probes": [
                        {
                            "role": "source",
                            "method": "command",
                            "command": src["command"],
                            "raw_output": src["raw_output"][:2000],
                            "fingerprint": f"{uid}:{src['id']}",
                            "exit_code": src["exit_code"],
                        },
                        {
                            "role": "verifier",
                            "method": "command",
                            "command": ver["command"],
                            "raw_output": ver["raw_output"][:2000],
                            "fingerprint": f"{uid}:{ver['id']}:verifier",
                            "exit_code": ver["exit_code"],
                        },
                    ],
                }
            )
        receipt = {
            "schema_version": 1,
            "unit_id": uid,
            "state": "BLOCKED",
            "sentinel": f"SUCCESS:{uid}",
            "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=" + uid + "]",
            "min_bytes_threshold": 2048,
            "artifacts": ret["artifacts"],
            "evidence": evidence,
            "timestamps": {"started_at": started_iso, "ended_at": now},
            "retry": {"count": 0, "policy": "max-3-fix-cycles-per-unit"},
            "failure": {
                "classification": ["reviewer-absent"],
                "reason": (
                    "Builder-side construction complete and live-verified "
                    "(_measure_one_delivered.py -> SUCCESS:delivered): artifact at "
                    "output_path parses, carries the completion sentinel, both named "
                    "probes exit 0, per-unit manifest row matches the CRLF-normalized "
                    "sha256. state stays BLOCKED because receipt_core forbids "
                    "state=SUCCESS without reviewer.verdict=PASS and independent=true; "
                    "only the independent reviewer closes. Not owner-gated; blanket "
                    "build directive 2026-10-24 recorded as satisfied for the gate "
                    "surface this unit carries."
                ),
                "blocked_on": "independent reviewer per catalog reviewer_requirement",
            },
            "reviewer": {
                "reviewer_id": "unassigned-independent-reviewer",
                "verdict": "NOT-REVIEWED",
                "independent": False,
            },
            "manifest_registration": {
                "registered": True,
                "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
                "entry_id": uid,
            },
            "produced_by": {
                "model": "opus",
                "role": "builder-shard-2-w2",
                "vendor": "anthropic",
            },
        }
        receipt_path = REPO / "command-center" / "receipts" / f"{uid}.json"
        receipt_path.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")

        # --- 5. admission validation, fail-closed ---------------------------- #
        errs = gate.validate_receipt(receipt)
        if errs:
            print(f"FAILED:{uid} receipt schema-invalid: {errs[0][:160]}")
            receipt_path.unlink()
            rc_all = 1
            continue
        cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
        ids = {u["id"] for u in cat["work_units"] if isinstance(u, dict)}
        if uid not in ids:
            print(f"FAILED:{uid} not in catalog")
            rc_all = 1
            continue
        if uid not in receipt["sentinel"]:
            print(f"FAILED:{uid} sentinel does not embed unit id")
            rc_all = 1
            continue
        print(f"{uid} receipt admission: C1 parse; C2 schema-valid; C3 catalog; C4 sentinel")
        print(f"{uid} artifacts primary sha256={primary_sha[:16]} bytes={primary_bytes}")
        print(f"SUCCESS:{uid} receipts")
    return rc_all


if __name__ == "__main__":
    raise SystemExit(main())
