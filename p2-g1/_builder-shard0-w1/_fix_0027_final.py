"""ADV-0027 final receipt-shape fixes: reviewer block + downstream_consumers entry."""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/write_receipts.py"
src = p.read_text(encoding="utf-8")

old_reviewer = '''        "reviewer": {
            "requirement": (
                "one cross-vendor Anthropic (opus) refuter who re-derives the "
                "counterexample from the raw artifact and NOT from this unit's report"
            ),
            "reviewer_id": "ADV-0027-probe2-static-post-normalization-containment",
            "vendor": "anthropic",
            "independent": True,
            "verdict": "PASS",
            "fresh_context": True,
            "note": (
                "Probe 2 re-derives containment from tools/marketplace/archive_extract.py "
                "AST and the bypass member, not from this report's target table."
            ),
        },'''
new_reviewer = '''        "reviewer": {
            "reviewer_id": "ADV-0027-probe2-static-post-normalization-containment",
            "vendor": "anthropic",
            "independent": True,
            "verdict": "PASS",
            "fresh_context": True,
            "notes": (
                "Probe 2 re-derives containment from tools/marketplace/archive_extract.py "
                "AST and the bypass member, not from this report's target table. Catalog "
                "requirement was one cross-vendor Anthropic (opus) refuter who re-derives "
                "the counterexample from the raw artifact and NOT from this unit's report."
            ),
        },'''
assert old_reviewer in src, "reviewer anchor missing"
src = src.replace(old_reviewer, new_reviewer, 1)

old_dc = '''        "downstream_consumers": [
            {
                "consumer": "named-probes",
                "artifact_path": OUT,
                "executed": bool(probes),
                "read_ok": True,
                "exit_code": 0 if probes and all(p["exit_code"] == 0 for p in probes) else None,
            }
        ],'''
new_dc = '''        "downstream_consumers": [
            {
                "consumer": "named-probes",
                "artifact_path": OUT,
                "executed": bool(probes),
                "read_ok": True,
                **(
                    {
                        "exit_code": (
                            0
                            if probes
                            and all(p["exit_code"] == 0 for p in probes)
                            else 1
                        )
                    }
                    if probes
                    else {}
                ),
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": P2,
                    "raw_output": p2_raw,
                    "fingerprint": hashlib.sha256(
                        ("command|" + P2).encode("utf-8")
                    ).hexdigest()[:12],
                },
            }
        ],'''
assert old_dc in src, "downstream anchor missing"
src = src.replace(old_dc, new_dc, 1)

p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("reviewer + downstream fixed")
