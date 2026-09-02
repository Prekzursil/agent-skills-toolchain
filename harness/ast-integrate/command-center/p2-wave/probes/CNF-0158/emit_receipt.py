"""Emit command-center/receipts/CNF-0158.json from a live independent reproduction."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from reproduce import (  # noqa: E402
    P1,
    P2,
    blinding_attestation_hash,
    circular_read_is_rejected,
    plant_timeout_leak,
    quota_not_refuted,
    reproduce_all,
    rollback_detached,
    sha256_file,
    stale_fixed_ok,
    write_relabelled,
)

OUT_REL = "command-center/receipts/CNF-0158.json"
SCHEMA_REL = "command-center/schema/confirmation-record.schema.json"
LOCAL_SCHEMA = HERE / "confirmation-record.local.schema.json"
QUESTION = (
    "Question: is every leak in the documented abstraction-leak register still real? "
    "Take the register produced by the implementation bucket and independently "
    "reproduce each leak in each vendor runtime. A leak that cannot be reproduced "
    "is either fixed (and the register is stale) or was never real (and the "
    "register is wrong); both outcomes are findings, and neither may be recorded "
    "as 'confirmed by reading the register'."
)


def probe_ref(pid: str, command: str, path: Path) -> dict:
    return {
        "id": pid,
        "command": command,
        "fingerprint": sha256_file(path),
        "path": str(path.relative_to(REPO).as_posix()),
    }


def load_local_schema() -> dict:
    return json.loads(LOCAL_SCHEMA.read_text(encoding="utf-8"))


def validate_record(doc: dict, schema: dict | None = None) -> None:
    # Catalog confirmation-record.schema.json is a generated $ref shim whose
    # target is https://ast-integrate.invalid/... . jsonschema 4.10 fetches
    # that URL. Validate against the unit-local Draft-07 schema instead.
    schema = schema if schema is not None else load_local_schema()
    jsonschema.Draft7Validator(schema).validate(doc)
    src = str((doc.get("source_probe") or {}).get("fingerprint") or "")
    ver = str((doc.get("verifier_probe") or {}).get("fingerprint") or "")
    if doc.get("verdict") in {"CONFIRMED", "REFUTED"} and len(src) < 16:
        raise jsonschema.ValidationError("empty source_probe on CONFIRMED|REFUTED")
    if src and ver and src == ver:
        raise jsonschema.ValidationError("same-probe-rerun: fingerprints identical")


def build() -> dict:
    result = reproduce_all()
    write_relabelled(result["relabelled"])
    planted = plant_timeout_leak()
    rolled = rollback_detached()
    quota = quota_not_refuted()
    stale = stale_fixed_ok(result)
    circular_ok = circular_read_is_rejected(result)

    src = probe_ref("probe1", P1, HERE / "probe1_reproduce.py")
    ver = probe_ref("probe2", P2, HERE / "probe2_controls.py")
    if src["fingerprint"] == ver["fingerprint"]:
        raise RuntimeError("source_probe fingerprint equals verifier_probe")

    leak_summaries = []
    for row in result["rows"]:
        leak_summaries.append(
            {
                "leak_id": row["id"],
                "field": row["field"],
                "verdict": row["overall"],
                "register_claimed_status": row["register_claimed_status"],
                "reproduction_commands": {
                    vendor: vr["command"] for vendor, vr in row["vendors"].items()
                },
                "observed_divergence": {
                    vendor: vr["divergence"] for vendor, vr in row["vendors"].items()
                },
                "vendor_verdicts": {
                    vendor: {
                        "verdict": vr["verdict"],
                        "observed_present": vr["observed_present"],
                        "claimed": vr["claimed"],
                    }
                    for vendor, vr in row["vendors"].items()
                },
            }
        )

    baseline = {
        "kind": "independent-observation",
        "register_path": "command-center/p2-wave/probes/CNF-0158/fixtures/b07-leak-register.json",
        "reproduced": result["reproduced_count"],
        "both_states": result["both_states"],
        "leaks": leak_summaries,
        "circular_read_rejected": circular_ok,
    }
    corrected = {
        "kind": "register-relabel-plus-fixed-hold",
        "relabelled_path": "command-center/p2-wave/probes/CNF-0158/fixtures/b07-leak-register.relabelled.json",
        "relabel_ok": result["relabel_ok"],
        "fixed_hold": [c for c in stale],
        "planted_control_clean": planted["clean_absent"],
    }
    rollback = {
        "kind": "re-enable-detached-on-openai",
        "reintroduces_leak": rolled["rollback_reintroduces"],
        "restored_absent": rolled["restored_absent"],
        "pass": rolled["pass"],
    }
    regression = {
        "claim_every_leak_still_real": False,
        "still_real": [s["leak_id"] for s in leak_summaries if s["verdict"] == "REPRODUCED"],
        "fixed": [s["leak_id"] for s in leak_summaries if s["verdict"] == "FIXED"],
        "never_real": [s["leak_id"] for s in leak_summaries if s["verdict"] == "NEVER-REAL"],
        "non_reproduced_relabelled": result["non_reproduced"],
    }

    tests = [
        {
            "id": "both-states",
            "result": "PASS" if result["both_states"] else "FAIL",
            "detail": {
                "reproduced": result["reproduced_count"],
                "absent_as_expected": result["absent_as_expected"],
            },
        },
        {
            "id": "detector-control-planted-leak",
            "result": "PASS" if planted["pass"] else "FAIL",
            "detail": planted,
        },
        {
            "id": "staleness-fixed-vs-marker",
            "result": "PASS" if stale and all(c["pass"] for c in stale) else "FAIL",
            "detail": stale,
        },
        {
            "id": "register-update-non-reproduced",
            "result": "PASS" if result["relabel_ok"] else "FAIL",
            "detail": {"non_reproduced": result["non_reproduced"]},
        },
        {
            "id": "quota-429-not-refuted",
            "result": "PASS" if quota["pass"] else "FAIL",
            "detail": quota,
        },
        {
            "id": "circular-register-read-rejected",
            "result": "PASS" if circular_ok else "FAIL",
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        raise RuntimeError("control tests failed: " + json.dumps(tests)[:2000])

    att = blinding_attestation_hash(result)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "kind": "confirmation-record",
        "claim_id": "CNF-0158",
        "unit_id": "CNF-0158",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0158",
        "title": "Reproduce each documented cross-vendor abstraction leak",
        "question": QUESTION,
        "confirmer": {
            "identity": "CNF-0158-cross-vendor-confirmer",
            "vendor": "openai",
            "role": "cross-vendor-confirmer",
            "model": "gpt-5-codex",
        },
        "blinding_attestation_hash": att,
        "baseline_repro": baseline,
        "corrected_repro": corrected,
        "rollback_repro": rollback,
        "regression_diff": regression,
        "discrepancies": result["discrepancies"],
        "verdict": "PARTIAL",
        "source_probe": src,
        "verifier_probe": ver,
        "residual_caveat": (
            "Live vendor CLIs (codex, claude) were not the execution substrate; "
            "reproduction ran against in-process IMP-0420/IMP-0421 adapter fixtures "
            f"because which(codex)={result['live_clis'].get('codex')} "
            f"which(claude)={result['live_clis'].get('claude')}. "
            "IMP-0422.json is absent on this worktree; the working register is "
            "fixtures/b07-leak-register.json reconstructed from catalog contracts. "
            "Claimed labels were never used as evidence. 429/529 is QuotaStorm, "
            "never REFUTED. Worktree is not git; FIXED verdicts are cross-checked "
            "against content-addressed markers in vendor_runtime.py."
        ),
        "leaks": leak_summaries,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "CNF-0158-probe2-largest-three",
            "verdict": "PASS",
            "independent": True,
            "scope": [
                "LEAK-WIN-ARG-INLINE",
                "LEAK-PERMS-UNENFORCED",
                "LEAK-DETACHED-BG",
            ],
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "catalog-schema-shim"},
            {
                "path": "command-center/p2-wave/probes/CNF-0158/confirmation-record.local.schema.json",
                "exists": True,
                "role": "schema",
            },
        ],
        "ts": now,
        "produced_by": "command-center/p2-wave/probes/CNF-0158/emit_receipt.py",
    }
    validate_record(doc)
    # Recompute attestation after the fact from stored payload fields.
    recomputed = blinding_attestation_hash(result)
    if recomputed != att:
        raise RuntimeError("attestation hash not stable")
    return doc


def main() -> int:
    doc = build()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2) + "\n"
    out.write_text(text, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT_REL} bytes={len(raw)} sha256={digest}")
    print("SUCCESS:CNF-0158")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
