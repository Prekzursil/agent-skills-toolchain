#!/usr/bin/env python3
"""Write SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json for the six
shard13-wave4 units whose probe directories were lost with the prior
builder. Manifest sha256 = CRLF-normalized digest of the live receipt,
byte-identical to command-center/p2-wave/_measure_one_delivered.py."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

UNITS = {
    "IMP-0441": {
        "probes": [
            ("probe1_dual_platform", "command-center/p2-wave/probes/IMP-0441/probe1_dual_platform.py"),
            ("probe2_prefix_was_red", "command-center/p2-wave/probes/IMP-0441/probe2_prefix_was_red.py"),
        ],
        "receipt_state": "SUCCESS (prior independent reviewer closure kept: verdict=PASS, independent=true; probes re-verified live 2026-10-26)",
        "notes": "Resume after prior builder death: probe dir absent on this worktree. Rebuilt probes + .gitattributes artifact + CI workflow; eol_policy CLI gained --dual-platform. Probes re-run live, exit 0. Receipt-internal artifact sha rows drift from this worktree (receipts were emitted on a different worktree) - reported to parent, closed receipts untouched.",
    },
    "IMP-0451": {
        "probes": [
            ("probe1_four_cell", "command-center/p2-wave/probes/IMP-0451/probe1_four_cell.py"),
            ("probe2_signal_collapse", "command-center/p2-wave/probes/IMP-0451/probe2_signal_collapse.py"),
        ],
        "receipt_state": "SUCCESS (prior independent reviewer closure kept: verdict=PASS, independent=true; probes re-verified live 2026-10-26)",
        "notes": "Resume after prior builder death: probe dir absent. Rebuilt four-cell + mutation probes; emit_receipt.py helper restored. Probes re-run live, exit 0. Receipt-internal artifact sha rows drift from this worktree - closed receipts untouched.",
    },
    "IMP-0461": {
        "probes": [
            ("probe1_resolution_refusal", "command-center/p2-wave/probes/IMP-0461/probe1_resolution_refusal.py"),
            ("probe2_independent_rewalk", "command-center/p2-wave/probes/IMP-0461/probe2_independent_rewalk.py"),
        ],
        "receipt_state": "SUCCESS (prior independent reviewer closure kept: verdict=PASS, independent=true; probes re-verified live 2026-10-26)",
        "notes": "Resume after prior builder death: probe dir absent. Rebuilt resolution/bare-refusal/CRLF probes against live two-bash Windows box (msys vs System32 WSL); tools/launcher/tests/test_explicit_interpreter.py restored (5/5). Probes re-run live, exit 0.",
    },
    "IMP-0465": {
        "probes": [
            ("probe1_transport_matrix", "command-center/p2-wave/probes/IMP-0465/probe1_transport_matrix.py"),
            ("probe2_roundtrip", "command-center/p2-wave/probes/IMP-0465/probe2_roundtrip.py"),
        ],
        "receipt_state": "SUCCESS (prior independent reviewer closure kept: verdict=PASS, independent=true; probes re-verified live 2026-10-26)",
        "notes": "Resume after prior builder death: probe dir absent. Rebuilt matrix/roundtrip probes; naive NUL crash (ValueError in CreateProcess) recorded as a measured naive-transport failure, implementation untouched. Probes re-run live, exit 0.",
    },
    "IMP-0476": {
        "probes": [
            ("probe1_verdicts", "command-center/p2-wave/probes/IMP-0476/probe1_verdicts.py"),
            ("probe2_independence", "command-center/p2-wave/probes/IMP-0476/probe2_independence.py"),
        ],
        "receipt_state": "SUCCESS (prior independent reviewer closure kept: verdict=PASS, independent=true; probes re-verified live 2026-10-26)",
        "notes": "Resume after prior builder death: probe dir absent. Rebuilt verdict + independence probes with fixtures inventory (7 checks: OK/DISAGREE/FAIL/NOT-CHECKED cells + positive control). Probes re-run live, exit 0.",
    },
    "IMP-0480": {
        "probes": [
            ("probe1_catalog_identical", "command-center/p2-wave/probes/IMP-0480/probe1_catalog_identical.py"),
            ("probe2_reviewer_novel_ast", "command-center/p2-wave/probes/IMP-0480/probe2_reviewer_novel_ast.py"),
        ],
        "receipt_state": "SUCCESS (prior independent reviewer closure kept: verdict=PASS, independent=true; probes re-verified live 2026-10-26)",
        "notes": "Resume after prior builder death: probe dir absent. Rebuilt catalog-identical + novel/AST probes (4 catalog + 3 novel injection classes; naive + plea both-states; AST body-to-apply_policy mutant detected). Receipt lists zero artifacts rows - reported to parent. Probes re-run live, exit 0.",
    },
}


def digest(path: Path):
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    for uid, cfg in UNITS.items():
        probe_dir = REPO / "command-center" / "p2-wave" / "probes" / uid
        receipt = REPO / "command-center" / "receipts" / ("%s.json" % uid)
        out_rel = "command-center/receipts/%s.json" % uid
        sha, nbytes = digest(receipt)

        ret = {
            "unit_id": uid,
            "status": "COMPLETED",
            "completed_at": NOW,
            "builder": "shard13-w4-resume (prior builder died mid-flight; probe dirs were lost; verified + completed)",
            "rebuild_provenance": "rebuild: probe scripts + fixtures + SUBAGENT-RETURN + manifest (implementation modules pre-existing and verified live)",
            "receipt_state": cfg["receipt_state"],
            "named_probes": [
                {
                    "id": pid,
                    "role": "named-probe",
                    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B %s" % rel,
                }
                for pid, rel in cfg["probes"]
            ],
            "notes": cfg["notes"],
        }
        (probe_dir / "SUBAGENT-RETURN.json").write_text(
            json.dumps(ret, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

        man = {
            "unit_id": uid,
            "generated_at": NOW,
            "receipt_state": "SUCCESS",
            "artifacts": [
                {
                    "unit_id": uid,
                    "path": out_rel,
                    "sha256": sha,
                    "bytes": nbytes,
                    "present": True,
                    "note": "primary artifact (CRLF-normalized digest)",
                }
            ],
        }
        (probe_dir / "UNIT-ARTIFACT-MANIFEST.json").write_text(
            json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print("WROTE %s sha256=%s bytes=%d" % (uid, sha[:16], nbytes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
