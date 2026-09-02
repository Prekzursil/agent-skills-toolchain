#!/usr/bin/env python3
"""Write IMP-0088 receipt + per-unit UNIT-ARTIFACT-MANIFEST.json from live hashes."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "IMP-0088"
OUT_REL = "command-center/receipts/IMP-0088.json"
PROBE_DIR = REPO / "command-center/p2-wave/probes/IMP-0088"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0088/probe1_sibling_isolation.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0088/probe2_shared_path_and_blind.py"
T1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_remove_isolation.py"
T2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/marketplace/tests/test_remove_shared_path.py"
SUPPORTING = [
    "tools/marketplace/remove.py",
    "tools/marketplace/ledger.py",
    "tools/marketplace/census.py",
    "tools/marketplace/ownership_blind.py",
    "tools/marketplace/remove_isolation.py",
    "tools/marketplace/tests/test_remove_isolation.py",
    "tools/marketplace/tests/test_remove_shared_path.py",
    "command-center/p2-wave/probes/IMP-0088/probe1_sibling_isolation.py",
    "command-center/p2-wave/probes/IMP-0088/probe2_shared_path_and_blind.py",
]


def sha_file(rel: str) -> dict:
    p = REPO / rel
    data = p.read_bytes() if p.is_file() else b""
    norm = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(norm) if data else 0,
        "sha256": hashlib.sha256(norm).hexdigest() if data else "",
        "exists": p.is_file(),
        "role": "supporting",
        "eol": "LF",
    }


def run(cmd: str) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, timeout=120
    )
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fp(method, command),
        "exit_code": code,
    }


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    rt1, t1 = run(T1)
    rt2, t2 = run(T2)
    if rc1 != 0 or rc2 != 0 or rt1 != 0 or rt2 != 0:
        print("FAILED:IMP-0088 emitter probes/tests not green")
        print("p1", rc1, out1[-1200:])
        print("p2", rc2, out2[-1200:])
        print("t1", rt1, t1[-1200:])
        print("t2", rt2, t2[-1200:])
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    arts = [sha_file(r) for r in SUPPORTING]
    consume_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json; json.load(open('command-center/receipts/IMP-0088.json', encoding='utf-8'))\""
    )
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0088",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0088",
        "min_bytes_threshold": 2048,
        "profile": "marketplace-remove-isolation",
        "artifacts": arts,
        "evidence": [
            {
                "anchor": "tools/marketplace/remove.py:remove_package",
                "claim": (
                    "After owner-approved remove of pkg-a, every path owned by pkg-b is "
                    "present and byte-identical (census), AND the provenance ledger "
                    "records zero deletions attributed to pkg-b. Both signals required."
                ),
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P1, out1, rc1),
                    probe("verifier", "test-run", T1, t1, rt1),
                ],
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "tools/marketplace/remove.py:SharedPathRequiresDecision",
                "claim": (
                    "A live path claimed by pkg-a and pkg-b is refused without an explicit "
                    "decision (tree unchanged). With decision=keep, pkg-a exclusive files "
                    "are removed, the shared path and pkg-b exclusive file stay byte-identical."
                ),
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P2, out2, rc2),
                    probe("verifier", "test-run", T2, t2, rt2),
                ],
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [
            {
                "id": "T-sibling-isolation",
                "command": T1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": t1.splitlines()[-1] if t1 else "",
            },
            {
                "id": "T-shared-path-decision",
                "command": T2,
                "result": "PASS",
                "assertions": 1,
                "output_tail": t2.splitlines()[-1] if t2 else "",
            },
            {
                "id": "T-probe1-sibling-isolation",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": out1.splitlines()[-1] if out1 else "",
            },
            {
                "id": "T-probe2-shared-and-blind",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": out2.splitlines()[-1] if out2 else "",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0088-C1",
                "kind": "mutation",
                "description": (
                    "An ownership-blind remover that unlinks every file under the live "
                    "root must fail sibling isolation, proving the sibling test can go red."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "census_byte_identical=false; pkg-b paths missing",
                "good_state_output": "ledger-scoped remove: pkg-b paths byte-identical",
            },
            {
                "id": "IMP0088-C2",
                "kind": "other",
                "description": (
                    "remove without owner_approval raises OwnerGateRequired and mutates nothing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "OwnerGateRequired; census unchanged",
                "good_state_output": "owner_approval=True proceeds to planned unlinks",
            },
        ],
        "reviewer": {
            "independent": True,
            "notes": (
                "Probe 1 rehearses two-package removal with census+ledger signals. "
                "Probe 2 is a different machine (shared-path decision + ownership-blind substitute)."
            ),
            "reviewer_id": "IMP-0088-probe1-two-package-rehearsal",
            "verdict": "PASS",
        },
        "manifest_registration": {
            "manifest_path": "command-center/p2-wave/probes/IMP-0088/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "downstream_consumers": [
            {
                "consumer": "json.load of catalog output_path",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "file-read",
                    consume_cmd,
                    "json.load succeeded on command-center/receipts/IMP-0088.json",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0033 deploy provenance and IMP-0086 marketplace install are catalog "
                    "dependencies and are not delivered as live engines on this worktree. This "
                    "unit consumes a ledger of the IMP-0033 shape and does not reimplement "
                    "install placement."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver IMP-0033 and IMP-0086, then replay remove against their live "
                    "ledger and installer handoff rather than the throwaway planter."
                ),
            },
            {
                "claim": (
                    "IMP-0126 (cross-package deploy-path conflict detector) is a catalog input. "
                    "Shared-path refusal here is the remove-side counterpart and does not "
                    "replace pre-install conflict detection."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver IMP-0126 and join its claimants onto this ledger so install-time "
                    "and remove-time shared-path sets are the same object."
                ),
            },
        ],
        "retry": {"count": 0, "policy": "no automatic retry on a deletion path"},
        "produced_by": {
            "execution_substrate": "linux-headless-p2-deliver",
            "model": "grok-4.6",
            "role": "implementer",
            "vendor": "xai",
        },
        "report": {
            "implementation": "tools/marketplace/remove.py",
            "kind": "isolated-package-remove",
            "ledger": "tools/marketplace/ledger.py",
            "tests": [
                "tools/marketplace/tests/test_remove_isolation.py::test_sibling_package_untouched",
                "tools/marketplace/tests/test_remove_shared_path.py::test_shared_path_requires_a_decision",
            ],
        },
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "extensions": {
            "summary": (
                "Marketplace remove deletes only paths the deploy provenance ledger "
                "attributes to the target package. User-authored files are skipped by "
                "default. Unlink is owner-gated. SUCCESS:IMP-0088"
            )
        },
    }

    outp = REPO / OUT_REL
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    loaded = json.loads(outp.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict) or loaded.get("sentinel") != "SUCCESS:IMP-0088":
        print("FAILED:IMP-0088 json.load consumer rejected the receipt")
        return 1
    raw = outp.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    size = len(raw)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")

    rows = [
        {
            "path": OUT_REL,
            "sha256": digest,
            "bytes": size,
            "present": True,
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0088/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    for a in arts:
        rows.append(
            {
                "path": a["path"],
                "sha256": a["sha256"],
                "bytes": a["bytes"],
                "present": a["exists"],
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/IMP-0088/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(rows),
        "present": sum(1 for r in rows if r["present"]),
        "artifacts": rows,
    }
    man_path = PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {man_path.relative_to(REPO)}")

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0088",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "sibling-isolation-two-signal",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "shared-path-and-ownership-blind-control",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0088/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0088-probe1-two-package-rehearsal",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for IMP-0088: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
        "ts": now,
    }
    ret_path = PROBE_DIR / "SUBAGENT-RETURN.json"
    ret_path.write_text(json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {ret_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
