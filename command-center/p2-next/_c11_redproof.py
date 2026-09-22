"""C11 lane red-proof: the producer must go RED on the real tree when a
registered unit's artifact is deleted, and the receipt gate must accept the new
manifest via manifest_path in the good state and reject it when absent.

Cases (all on the LIVE tree, every mutation restored and hash-verified):
  R1 drift-red   -- rename one registered artifact (not itself a declaring
                    receipt) to a hidden sibling; --check must exit 1.
                    Restore; --check must exit 0 again.
  G1 gate-good   -- receipt_schema_gate.evaluate_gate_a on a probe receipt
                    {registered: true, manifest_path: UNIT-ARTIFACT-MANIFEST.json}
                    with verify_filesystem=True, root=REPO -> condition 11
                    SATISFIED.
  G2 gate-bad    -- same receipt, root=tempdir without the manifest ->
                    condition 11 UNSATISFIED ("manifest absent on disk").

If this file still reads UNKNOWN, the probe died before measuring and nothing
here may be cited.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "command-center/UNIT-ARTIFACT-MANIFEST.json"
GATE_PATH = ROOT / "platform/lib/receipt_schema_gate.py"
PRODUCER = "tools/command-center/unit_manifest.py"


def run_check() -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, PRODUCER, "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, (r.stdout + r.stderr).strip()


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    result: dict = {
        "R1_drift_red": "UNKNOWN - not yet measured",
        "R1_restore_green": "UNKNOWN - not yet measured",
        "G1_gate_good": "UNKNOWN - not yet measured",
        "G2_gate_bad": "UNKNOWN - not yet measured",
        "chosen_artifact": None,
        "artifact_sha256_before": None,
        "artifact_sha256_after": None,
    }
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    claimer_receipts = {row["receipt_path"] for row in manifest["artifacts"]}
    claimer_receipts |= {u["receipt_path"] for u in manifest["unregistrable"]}

    # pick a registered artifact that is not itself a declaring receipt
    target = None
    for row in manifest["artifacts"]:
        if row["path"] not in claimer_receipts:
            target = row
            break
    if target is None:
        print(
            "FAILED:c11-redproof no registered artifact separable from claimer receipts"
        )
        return 1

    art = ROOT / target["path"]
    hidden = art.with_name(art.name + ".c11-redproof-hidden")
    result["chosen_artifact"] = target["path"]
    result["artifact_sha256_before"] = sha256(art)

    try:
        # -- good state baseline
        rc, out = run_check()
        if rc != 0:
            print(f"FAILED:c11-redproof baseline --check not green: {out}")
            return 1
        # -- R1: delete (rename) the artifact -> producer must go red
        art.rename(hidden)
        rc_red, out_red = run_check()
        result["R1_drift_red"] = f"rc={rc_red} out={out_red[:160]}"
        ok_red = rc_red == 1
        # -- restore -> green again
        hidden.rename(art)
        rc_green, out_green = run_check()
        result["R1_restore_green"] = f"rc={rc_green} out={out_green[:160]}"
        result["artifact_sha256_after"] = sha256(art)
        ok_restore = (
            rc_green == 0
            and result["artifact_sha256_after"] == result["artifact_sha256_before"]
        )
    finally:
        if hidden.exists() and not art.exists():
            hidden.rename(art)  # never leave the tree mutated

    # -- G1/G2: the receipt gate must accept the manifest via manifest_path
    spec = importlib.util.spec_from_file_location("receipt_schema_gate", GATE_PATH)
    gate = importlib.util.module_from_spec(spec)
    sys.modules["receipt_schema_gate"] = gate
    spec.loader.exec_module(gate)

    probe = {
        "unit_id": "C11-REDPROBE",
        "state": "SUCCESS",
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/UNIT-ARTIFACT-MANIFEST.json",
        },
    }
    res_good = gate.evaluate_gate_a(probe, repo_root=ROOT, verify_filesystem=True)
    c11_good = next(c for c in res_good.conditions if c.n == 11)
    result["G1_gate_good"] = f"{c11_good.outcome}: {c11_good.basis}"
    ok_g1 = c11_good.outcome == "SATISFIED"

    with tempfile.TemporaryDirectory() as td:
        res_bad = gate.evaluate_gate_a(
            probe, repo_root=pathlib.Path(td), verify_filesystem=True
        )
        c11_bad = next(c for c in res_bad.conditions if c.n == 11)
        result["G2_gate_bad"] = f"{c11_bad.outcome}: {c11_bad.basis}"
        ok_g2 = c11_bad.outcome == "UNSATISFIED" and "absent" in c11_bad.basis

    out_path = ROOT / "command-center/p2-next/C11-REDPROOF.json"
    out_path.write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    all_ok = ok_red and ok_restore and ok_g1 and ok_g2
    for k in ("R1_drift_red", "R1_restore_green", "G1_gate_good", "G2_gate_bad"):
        print(f"  {k}: {result[k]}")
    print(
        ("SUCCESS:c11-redproof" if all_ok else "FAILED:c11-redproof")
        + f" -> {out_path.relative_to(ROOT)}"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
