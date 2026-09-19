r"""Pack command-center/receipts/CC-0013.json as BLOCKED (review owed).

Hard rule: no stub SUCCESS. Reviewer remains NOT-REVIEWED until an independent
fresh-context reviewer hand-edits a different field and confirms the gate fires.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "platform" / "lib"))
import atomic_receipt as ar  # noqa: E402

UNIT = "CC-0013"
OUT = "command-center/receipts/CC-0013.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0013"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
DERIVE = "command-center/status_derive.py"
GATE = "command-center/status_gate.py"
STATUS = "command-center/STATUS.md"
CONTROLS = f"{PROBE_DIR}/run_controls.py"


def _sha(rel: str) -> str:
    return hashlib.sha256((L.REPO / rel).read_bytes()).hexdigest()


def _run(cmd: list[str]) -> tuple[int, str]:
    return L.run(cmd)


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = ended

    # Re-run controls and refresh STATUS before packing so digests match disk.
    rc_ctrl, out_ctrl = _run([sys.executable, str(L.REPO / CONTROLS)])
    if rc_ctrl != 0:
        raise SystemExit(f"CC-0013 controls failed:\n{out_ctrl}")

    rc_der, out_der = _run([sys.executable, str(L.REPO / DERIVE)])
    if rc_der != 0:
        raise SystemExit(f"status_derive failed:\n{out_der}")
    rc_gate, out_gate = _run([sys.executable, str(L.REPO / GATE)])
    if rc_gate != 0:
        raise SystemExit(f"status_gate not silent after regenerate:\n{out_gate}")

    # Capture a live hand-edit demo for the receipt (names the drifted line).
    # Mutate a temp copy path via GATE against live STATUS after a deliberate edit,
    # then restore — run_controls already did this; reuse its raw output.
    hand_raw = (L.REPO / PROBE_DIR / "probe-hand-edit.raw.txt").read_text(
        encoding="utf-8"
    )
    silent_raw = (L.REPO / PROBE_DIR / "probe-regenerate-silent.raw.txt").read_text(
        encoding="utf-8"
    )
    det_raw = (L.REPO / PROBE_DIR / "probe-determinism.raw.txt").read_text(
        encoding="utf-8"
    )
    empty_raw = (L.REPO / PROBE_DIR / "probe-empty-events.raw.txt").read_text(
        encoding="utf-8"
    )
    summary_raw = (L.REPO / PROBE_DIR / "controls-summary.raw.txt").read_text(
        encoding="utf-8"
    )

    artifacts_rels = [
        (OUT, "primary"),
        (DERIVE, "supporting"),
        (GATE, "supporting"),
        (STATUS, "supporting"),
        (CONTROLS, "control"),
        (f"{PROBE_DIR}/probe-hand-edit.raw.txt", "primary"),
        (f"{PROBE_DIR}/probe-regenerate-silent.raw.txt", "primary"),
        (f"{PROBE_DIR}/probe-determinism.raw.txt", "primary"),
        (f"{PROBE_DIR}/probe-empty-events.raw.txt", "primary"),
        (f"{PROBE_DIR}/controls-summary.raw.txt", "log"),
        (MANIFEST, "supporting"),
        ("tools/command-center/render.py", "supporting"),
        ("platform/lib/completion_predicate.py", "supporting"),
    ]

    # Placeholder primary digest; rewrite after atomic write.
    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": (
            "FAILED:CC-0013 blocked-on-independent-review; generator+gate+four "
            "catalog controls PASS; SUCCESS withheld until a reviewer hand-edits a "
            "different field than the author tested and confirms the gate fires"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CC-0013",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-agent",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [],
        "evidence": [
            L.evidence(
                "Hand-edit of a STATUS.md counter makes status_gate.py fail and name the drifted line.",
                "CONFIRMED",
                f"{PROBE_DIR}/probe-hand-edit.raw.txt",
                [
                    L.probe(
                        "source",
                        "test-run",
                        f"python3 {CONTROLS}",
                        hand_raw,
                        exit_code=0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        f"read {PROBE_DIR}/probe-hand-edit.raw.txt",
                        hand_raw,
                        exit_code=0,
                    ),
                ],
                confidence="almost-certain",
            ),
            L.evidence(
                "After regenerate, status_gate.py is silent (exit 0, empty stdout with --quiet-ok).",
                "CONFIRMED",
                f"{PROBE_DIR}/probe-regenerate-silent.raw.txt",
                [
                    L.probe(
                        "source",
                        "test-run",
                        f"python3 {CONTROLS}",
                        silent_raw,
                        exit_code=0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        f"read {PROBE_DIR}/probe-regenerate-silent.raw.txt",
                        silent_raw,
                        exit_code=0,
                    ),
                ],
                confidence="almost-certain",
            ),
            L.evidence(
                "Two status_derive runs over unchanged inputs produce byte-identical STATUS.md.",
                "CONFIRMED",
                f"{PROBE_DIR}/probe-determinism.raw.txt",
                [
                    L.probe(
                        "source",
                        "test-run",
                        f"python3 {CONTROLS}",
                        det_raw,
                        exit_code=0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        f"read {PROBE_DIR}/probe-determinism.raw.txt",
                        det_raw,
                        exit_code=0,
                    ),
                ],
                confidence="almost-certain",
            ),
            L.evidence(
                "With zero events the generator emits board status NOT-STARTED and never a green status.",
                "CONFIRMED",
                f"{PROBE_DIR}/probe-empty-events.raw.txt",
                [
                    L.probe(
                        "source",
                        "test-run",
                        f"python3 {CONTROLS}",
                        empty_raw,
                        exit_code=0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        f"read {PROBE_DIR}/probe-empty-events.raw.txt",
                        empty_raw,
                        exit_code=0,
                    ),
                ],
                confidence="almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "T1-hand-edit-names-line",
                "name": "Hand-edit a counter -> gate must fire and name the drifted line.",
                "command": f"python3 {CONTROLS}",
                "result": "PASS",
                "assertions": 1,
                "output_tail": hand_raw[-1500:],
            },
            {
                "id": "T2-regenerate-silent",
                "name": "Regenerate -> gate silent.",
                "command": f"python3 {CONTROLS}",
                "result": "PASS",
                "assertions": 1,
                "output_tail": silent_raw[-800:],
            },
            {
                "id": "T3-determinism",
                "name": "Two runs over an unchanged event log produce byte-identical output.",
                "command": f"python3 {CONTROLS}",
                "result": "PASS",
                "assertions": 1,
                "output_tail": det_raw[-800:],
            },
            {
                "id": "T4-empty-not-started",
                "name": "Empty events => NOT-STARTED never green.",
                "command": f"python3 {CONTROLS}",
                "result": "PASS",
                "assertions": 1,
                "output_tail": empty_raw[-1200:],
            },
        ],
        "negative_controls": [
            L.control(
                "hand-edit-counter",
                "mutation",
                "Bump event_records by 1 in STATUS.md; gate must go red and name the line.",
                True,
                True,
                bad=hand_raw[-500:],
                good=silent_raw[-300:],
            ),
            L.control(
                "empty-events-not-green",
                "absent-input",
                "Zero-byte EVENTS.jsonl forces NOT-STARTED; green tokens absent.",
                True,
                True,
                bad="would emit GREEN/COMPLETE with empty events",
                good=empty_raw[-500:],
            ),
        ],
        "reviewer": {
            "reviewer_id": "pending-independent-reviewer-cc0013",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "unassigned",
            "reviewed_at": ended,
            "notes": (
                "BLOCKED until review. Catalog reviewer_requirement: one independent "
                "reviewer who hand-edits a different field than the author tested and "
                "confirms the gate fires. Implementer must not self-certify PASS."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/status_gate.py",
                "artifact_path": STATUS,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "verifier",
                    "command",
                    f"python3 {GATE}",
                    out_gate,
                    exit_code=rc_gate,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Independent reviewer has not yet hand-edited a different STATUS.md "
                    "field than event_records and confirmed status_gate.py names that line."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer regenerates STATUS.md, edits a non-author field "
                    "(e.g. receipt_files or a stamp line), runs python3 command-center/status_gate.py, "
                    "and records PASS with independent=true only if the gate names that line."
                ),
            }
        ],
        "defects": [],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot; do not add exemptions to the hand-edit gate "
                "on a third attempt."
            ),
            "attempts": [],
        },
        "failure": {
            "classification": [
                "blocked-on-independent-review",
                "overclaim",
                "detector-failure",
                "green-not-live",
            ],
            "reason": (
                "Implementation and the four catalog controls are green; SUCCESS:CC-0013 "
                "is withheld until independent review PASS."
            ),
            "blocked_on": (
                "Independent reviewer who hand-edits a different STATUS.md field than the "
                "author tested and confirms status_gate.py names that drifted line."
            ),
            "diagnostic_tail": summary_raw[-4000:],
            "two_signal_proof": [
                L.probe(
                    "source",
                    "test-run",
                    f"python3 {CONTROLS}",
                    summary_raw,
                    exit_code=rc_ctrl,
                ),
                L.probe(
                    "verifier",
                    "command",
                    f"python3 {GATE}",
                    out_gate,
                    exit_code=rc_gate,
                ),
            ],
        },
        "report": {
            "generator": DERIVE,
            "gate": GATE,
            "controls_summary": summary_raw.strip(),
            "derive_out": out_der.strip(),
            "gate_out": out_gate.strip(),
            "catalog_tests_required": [
                "Hand-edit a counter -> gate must fire and name the drifted line.",
                "Regenerate -> gate silent.",
                "Determinism: two runs over an unchanged event log must produce byte-identical output.",
                "Empty-input control: with zero events the generator must emit NOT-STARTED, never green.",
            ],
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": f"{PROBE_DIR}/build_receipt.py",
            "hard_rule": "BLOCKED until review; no stub SUCCESS",
        },
    }

    # Write per-unit manifest first (condition 11 option 1).
    manifest_doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "registered_at": ended,
        "output_path": OUT,
        "artifacts": [{"path": OUT, "role": "primary"}],
        "note": "STRUCTURAL-CONDITION-11 option 1: per-unit manifest; global --write not invoked.",
    }
    (L.REPO / MANIFEST).parent.mkdir(parents=True, exist_ok=True)
    (L.REPO / MANIFEST).write_text(
        json.dumps(manifest_doc, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    # First write with measured artifacts except self-digest placeholder.
    arts = []
    for rel, role in artifacts_rels:
        if rel == OUT:
            arts.append(
                {
                    "path": OUT,
                    "bytes": 1,
                    "sha256": "0" * 64,
                    "exists": True,
                    "eol": "LF",
                    "role": "primary",
                }
            )
        else:
            arts.append(L.art(rel, role))
    doc["artifacts"] = arts

    # Validate structure loosely via resolver before atomic write.
    errs = L.validate(doc, SCHEMA)
    # BLOCKED receipts may still have schema issues around failure block — check.
    if errs:
        # Filter nothing; print and continue only if schema allows BLOCKED shape.
        print("schema findings (pre-write):")
        for e in errs[:30]:
            print(" ", e)

    ar.write_json_atomic(OUT, doc)

    # Fix self-hash and re-write.
    primary = L.art(OUT, "primary")
    for i, a in enumerate(doc["artifacts"]):
        if a["path"] == OUT:
            doc["artifacts"][i] = primary
            break

    # Admission consumer.
    rc_adm, out_adm = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc["downstream_consumers"].append(
        {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc_adm == 0,
            "exit_code": rc_adm,
            "probe": L.probe(
                "verifier",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out_adm,
                exit_code=rc_adm,
            ),
        }
    )

    ar.write_json_atomic(OUT, doc)
    # Final self-hash after last mutation.
    primary = L.art(OUT, "primary")
    for i, a in enumerate(doc["artifacts"]):
        if a["path"] == OUT:
            doc["artifacts"][i] = primary
            break
    ar.write_json_atomic(OUT, doc)

    size = (L.REPO / OUT).stat().st_size
    print(
        f"wrote {OUT} ({size} B) state=BLOCKED controls_rc={rc_ctrl} admit_rc={rc_adm}"
    )
    if rc_adm != 0:
        print(out_adm)
        raise SystemExit("receipt_validate rejected CC-0013")

    # Refresh STATUS now that the receipt exists; update STATUS digest; re-admit.
    _run([sys.executable, str(L.REPO / DERIVE)])
    for i, a in enumerate(doc["artifacts"]):
        if a["path"] == STATUS:
            doc["artifacts"][i] = L.art(STATUS, "supporting")
            break
    ar.write_json_atomic(OUT, doc)
    primary = L.art(OUT, "primary")
    for i, a in enumerate(doc["artifacts"]):
        if a["path"] == OUT:
            doc["artifacts"][i] = primary
            break
    ar.write_json_atomic(OUT, doc)

    rc_adm2, out_adm2 = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    if rc_adm2 != 0:
        print(out_adm2)
        raise SystemExit("receipt_validate rejected CC-0013 after STATUS refresh")
    print(f"re-admit_rc={rc_adm2}")
    return doc


if __name__ == "__main__":
    build()
