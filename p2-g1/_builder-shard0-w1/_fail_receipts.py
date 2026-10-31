"""Write honest FAILED receipts for the two dependency-blocked units."""
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

FAILURES = {
    "ADV-0033": {
        "reason": (
            "Cannot deliver on this worktree: the unit's probes hard-read two "
            "cross-unit evidence files that do not exist here - "
            "command-center/p2-wave/probes/TST-0082/dispatcher.py (TST-0082 is "
            "delivered by receipt only in command-center/receipts/TST-0082.json; "
            "its probe-dir fixture was never materialized on p2-g1) and "
            "command-center/p2-wave/probes/ARC-0083/completeness.py (ARC-form "
            "unit with no receipt and no probe dir anywhere on this box - "
            "per program contract ARC-form artifacts are never guessed and go "
            "to the catalog-forensics agent only). probe1_control.py and "
            "probe2_router.py raise FileNotFoundError on the missing files, so "
            "the delivery predicate (probes exit 0) cannot pass. The prior "
            "artifact at output_path is left untouched. Builder could not "
            "author either dependency file without guessing another unit's "
            "deliverable."
        ),
        "classification": ["dependency-absent", "arc-unknown-token"],
    },
    "ADV-0037": {
        "reason": (
            "Cannot deliver on this worktree: probe_case.py imports "
            "secret_scrub_gate from command-center/p2-wave/probes/IMP-0458/ "
            "(an IMP-form cross-unit dependency). That directory does not exist "
            "on p2-g1; no module named secret_scrub_gate exists anywhere in the "
            "tree (the g1-surface stub marketplace/secret_gate.py is a generated "
            "no-op and tools/marketplace/secret_gate.py lacks both "
            "synthetic_canary_value and the (bytes, label) scan_bytes API the "
            "probe calls - ModuleNotFoundError is fatal at probe runtime). "
            "IMP-0458 is delivered by receipt only "
            "(command-center/receipts/IMP-0458.json, state=SUCCESS, legacy "
            "phase); per program contract IMP-form artifacts are never guessed. "
            "The prior artifact at output_path is left untouched."
        ),
        "classification": ["dependency-absent", "imp-unknown-token"],
    },
}

for uid, spec in FAILURES.items():
    rp = REPO / "command-center" / "p2-wave" / "probes" / uid / "SUBAGENT-RETURN.json"
    ret = json.loads(rp.read_text(encoding="utf-8"))
    prev_reviewer = ret.get("reviewer")
    ret["status"] = "FAILED"
    ret["state"] = "FAILED"
    ret["failure"] = {
        "classification": spec["classification"],
        "reason": spec["reason"],
    }
    ret["reviewer"] = None
    ext = ret.get("extensions") if isinstance(ret.get("extensions"), dict) else {}
    ext["prev_closure"] = prev_reviewer if isinstance(prev_reviewer, dict) else None
    ext["shard0_w1_resume_2026-10-24"] = {
        "builder": "shard0 wave-1 builder (resume)",
        "action": (
            "Probes re-run live this session and crash on absent cross-unit "
            "dependency files; prior DELIVERED/SUCCESS receipt was stale "
            "(did not verify live). Marked FAILED with the precise reason; "
            "artifact left untouched."
        ),
    }
    ret["extensions"] = ext
    ret["notes"] = (
        f"Shard0 wave-1 builder (resume) 2026-10-24: {uid} FAILED - dependency-"
        "absent (see failure.reason). Prior receipt claimed DELIVERED/SUCCESS "
        "but the probes no longer verify live on this worktree. Honesty over "
        "optics: reported failed with the precise missing-dependency list."
    )
    ret["ts"] = NOW
    ret.pop("measure_line", None)
    ret.pop("measure", None)
    rp.write_text(json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{uid} -> FAILED receipt written")
