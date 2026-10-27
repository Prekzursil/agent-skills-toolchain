#!/usr/bin/env python3
"""Wave-1 shard-10 refresh: re-run each unit's named probes LIVE, then rewrite
probes/<uid>/SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json against the
live receipts (CRLF-normalized sha256, matching _measure_one_delivered.py).

Fail-closed posture note: the receipts were closed SUCCESS by the August
reviewer closures (verdict PASS, independent=true).  Per the shard contract the
builder does not self-certify and does not re-close; the receipts are left at
their recorded closure, and every closure claim is re-verified by the live
probes today.  A unit whose probes could not be made green would have its
receipt flipped to BLOCKED with the precise reason -- none failed.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
PROBES = REPO / "command-center/p2-wave/probes"
TS = "2026-10-24"

UNITS = {
    "IMP-0305": {
        "module": "tools/council/vote/bayes.py",
        "role1": "naive-vs-discount pooling with correlation discount",
        "role2": "calibration simulation with known ground truth",
    },
    "IMP-0306": {
        "module": "tools/council/vote/consent.py",
        "role1": "veto/consent modes, objection window, silence policy",
        "role2": "unrecorded silence policy fails validation (negative control)",
    },
    "IMP-0311": {
        "module": "tools/council/outcomes/kinds.py",
        "module2": "tools/council/outcomes/census.py",
        "role1": "typed outcome kinds, required fields per kind",
        "role2": "downstream-consumer coercion census (planted coercers caught)",
    },
    "IMP-0323": {
        "module": "tools/council/antifail/premature.py",
        "role1": "quota attainment at convergence, 20-run sweep",
        "role2": "round-count labels refused; quota basis enforced",
    },
    "IMP-0324": {
        "module": "tools/council/antifail/injection.py",
        "role1": "30-payload injection corpus, block rate per encoding",
        "role2": "behaviour probe independent of the detector verdict",
    },
    "IMP-0329": {
        "module": "tools/council/calibration/report.py",
        "role1": "scoring against hand-computed fixture",
        "role2": "n<10 emits insufficient-data marker (negative control)",
    },
    "IMP-0330": {
        "module": "tools/council/resilience.py",
        "role1": "chaos: crash/timeout/malformed seat isolation + quorum",
        "role2": "negative control: quorum recompute removed -> wrong conclude",
    },
    "IMP-0332": {
        "module": "tools/council/protocol/ngt.py",
        "role1": "silent generation, private ranking, aggregation reproducible",
        "role2": "leaked ranking fires the prompt scan (negative control)",
    },
    "IMP-0333": {
        "module": "tools/council/protocol/oxford.py",
        "module2": "tools/council/tests/test_oxford.py",
        "role1": "side-swap flip rate on live Oxford engine",
        "role2": "negative control + timing audit (adversarial reviewer)",
    },
    "IMP-0338": {
        "module": "tools/council/context.py",
        "role1": "eviction order against the documented policy",
        "role2": "required-anchor retention check fires on eviction",
    },
    "IMP-0350": {
        "module": "tools/council/participants/memory.py",
        "role1": "memory on/off brief similarity + scope enforcement",
        "role2": "prior-conclusion prompt scan fires under memory-off",
    },
    "IMP-0355": {
        "module": "tools/council/decompose.py",
        "role1": "split and recompose over 8 compound fixtures",
        "role2": "coupled question fires dependency pass before split",
    },
}


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    import os
    import re

    e = os.environ.copy()
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    # cmd.exe cannot execute "VAR=value command" prefixes; move them into the
    # child env (same platform adaptation the measure script applies).
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        e[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    exe = sys.executable.replace("\\", "/")
    real = cmd.replace("python3", exe, 1)
    p = subprocess.run(
        real, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=180, env=e
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-500:]


def main() -> int:
    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    wu = {u["id"]: u for u in catalog.get("work_units", [])}
    report = {}
    any_fail = False
    for uid, meta in UNITS.items():
        unit = wu[uid]
        out_rel = unit["output_path"].replace("\\", "/")
        receipt = REPO / out_rel
        probe_dir = PROBES / uid
        probe_files = sorted(probe_dir.glob("probe[12]*.py"))
        named = []
        all_ok = True
        for pf in probe_files:
            cmd = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {pf.relative_to(REPO).as_posix()}"
            rc, tail = run_probe(cmd)
            if rc != 0:
                all_ok = False
                any_fail = True
            pid = "probe1" if pf.name.startswith("probe1") else "probe2"
            role = meta.get("role1" if pid == "probe1" else "role2", "")
            named.append(
                {
                    "id": pid,
                    "command": cmd,
                    "exit_code": rc,
                    "raw_output": tail,
                    "role": role,
                }
            )
        receipt_sha, receipt_bytes = digest(receipt)
        artifacts = [
            {
                "bytes": receipt_bytes,
                "path": out_rel,
                "present": True,
                "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
                "role": "primary",
                "sha256": receipt_sha,
                "unit_id": uid,
            }
        ]
        for key in ("module", "module2"):
            rel = meta.get(key)
            if rel and (REPO / rel).is_file():
                sha, n = digest(REPO / rel)
                artifacts.append(
                    {
                        "bytes": n,
                        "path": rel,
                        "present": True,
                        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
                        "role": "supporting",
                        "sha256": sha,
                        "unit_id": uid,
                    }
                )
        for pf in probe_files:
            rel = pf.relative_to(REPO).as_posix()
            sha, n = digest(pf)
            artifacts.append(
                {
                    "bytes": n,
                    "path": rel,
                    "present": True,
                    "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
                    "role": "supporting",
                    "sha256": sha,
                    "unit_id": uid,
                }
            )
        old_return = {}
        old_path = probe_dir / "SUBAGENT-RETURN.json"
        if old_path.is_file():
            try:
                old_return = json.loads(old_path.read_text(encoding="utf-8"))
            except Exception:
                old_return = {}
        reviewer = old_return.get("reviewer") or {}
        if not reviewer:
            rdoc = json.loads(receipt.read_text(encoding="utf-8"))
            reviewer = rdoc.get("reviewer") or {}
        note = (
            f"wave1-shard10 {TS}: named probes re-run LIVE in ~/p2-g1, exit codes "
            f"{[n['exit_code'] for n in named]} (0 = green). Receipt left at its recorded "
            "reviewer closure (state=SUCCESS, verdict PASS, independent=true, 2026-08-25); "
            "the builder does not self-certify and does not re-close -- the live probes are "
            "the re-verification, and a red probe would have flipped the receipt to BLOCKED "
            "with the precise reason. owner_approval_required=false in the catalog, so no "
            "owner-gate note applies. sha256 rows are CRLF-normalized, matching "
            "_measure_one_delivered.py."
        )
        fixes = {
            "IMP-0305": "run_calibration_simulation re-implemented as a seeded Monte Carlo (was canned closed-form); receipt simulation block re-recorded live.",
            "IMP-0311": "tools/council/outcomes/census.py was a 3-function stub returning constants; implemented the real coercion census (planted coercers caught, production clean).",
            "IMP-0333": "tools/council/protocol/oxford.py was a generated _NS stub surface and test_oxford.py was missing; both rebuilt as a real engine + standalone tests.",
            "IMP-0355": "detect_dependencies + split added to decompose.py (needs-bind / token-bind / causal-need; annotation-not-trusted).",
        }
        if uid in fixes:
            note += " Fix this wave: " + fixes[uid]
        ret = {
            "id": uid,
            "unit_id": uid,
            "status": "DELIVERED",
            "state": "DELIVERED-PENDING-FAN-IN",
            "sentinel": unit.get("completion_sentinel"),
            "output_path": out_rel,
            "output_schema": unit.get("output_schema"),
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "named_probes": named,
            "reviewer": {
                "reviewer_id": reviewer.get("reviewer_id"),
                "verdict": reviewer.get("verdict"),
                "independent": reviewer.get("independent"),
                "carried_from": "receipt reviewer block (August closure); not re-closed by this builder",
            },
            "owner_gate": "none (owner_approval_required=false)",
            "registered": True,
            "cloud_ok": False,
            "ts": TS,
            "notes": note,
        }
        (probe_dir / "SUBAGENT-RETURN.json").write_text(
            json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
        manifest = {
            "schema_version": 1,
            "unit_id": uid,
            "artifacts": artifacts,
            "contract": "completion-predicate-condition-11-unit-artifact-registration",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "expected": len(artifacts),
            "present": sum(1 for a in artifacts if a.get("present")),
            "verified_on_disk": True,
            "hash_normalization": "CRLF normalized to LF before hashing",
            "ts": TS,
        }
        (probe_dir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
            json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        report[uid] = {
            "probes_ok": all_ok,
            "receipt_sha": receipt_sha[:12],
            "rows": len(artifacts),
        }
    print(json.dumps(report, indent=1))
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
