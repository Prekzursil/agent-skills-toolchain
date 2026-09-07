r"""CC-0013 — Make STATUS.md a derived measurement.

Catalog row built to the row. Emits state=BLOCKED with
blocked-on-independent-review after green derive/gate probes. Does NOT invent
an independent PASS (reviewer must hand-edit a different field than the author).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "platform" / "lib"))
import atomic_receipt as ar  # noqa: E402

sys.path.insert(0, str(L.REPO / "command-center"))
import status_derive as derive  # noqa: E402
import status_gate as gate  # noqa: E402

UNIT = "CC-0013"
OUT = "command-center/receipts/CC-0013.json"
SCHEMA = "command-center/schema/receipt.schema.json"
DERIVER = "command-center/status_derive.py"
GATE = "command-center/status_gate.py"
STATUS = "command-center/STATUS.md"
PROBE_DIR = "command-center/p2-wave/probes/CC-0013"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-07T18:30:00Z"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd, cwd=L.REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _scratch_controls() -> str:
    """Run empty / hand-edit / determinism / regenerate controls in an isolated tree."""
    lines: list[str] = []
    with tempfile.TemporaryDirectory(prefix="cc0013-") as tmp:
        root = Path(tmp)
        (root / "command-center/events").mkdir(parents=True)
        (root / "command-center/receipts").mkdir(parents=True)
        ev = root / "command-center/events/EVENTS.jsonl"
        rcpt = root / "command-center/receipts"
        status = root / "command-center/STATUS.md"

        ev.write_text("", encoding="utf-8")
        empty = derive.render_status(repo=root, events_path=ev, receipts_dir=rcpt)
        assert "NOT-STARTED" in empty
        assert "MEASURED" not in empty.split("Board status:")[1].split(".**")[0]
        lines.append("EMPTY_CONTROL=NOT-STARTED")

        ev.write_text(
            json.dumps({"id": "e1", "ts": "2026-09-07T12:00:00Z", "verb": "note"}) + "\n",
            encoding="utf-8",
        )
        a = derive.render_status(repo=root, events_path=ev, receipts_dir=rcpt)
        b = derive.render_status(repo=root, events_path=ev, receipts_dir=rcpt)
        assert a == b
        lines.append("DETERMINISM=byte-identical")

        status.write_text(a, encoding="utf-8")
        rc, findings = gate.check(
            repo=root, status_path=status, events_path=ev, receipts_dir=rcpt
        )
        assert rc == 0 and not findings
        lines.append("REGEN_SILENT=ok")

        hacked = a.replace("Board status: MEASURED", "Board status: MEASURED-HACKED", 1)
        status.write_text(hacked, encoding="utf-8")
        rc2, findings2 = gate.check(
            repo=root, status_path=status, events_path=ev, receipts_dir=rcpt
        )
        assert rc2 == 1 and findings2
        lines.append(f"HAND_EDIT_FIRED={findings2[0]}")

        status.write_text(
            derive.render_status(repo=root, events_path=ev, receipts_dir=rcpt),
            encoding="utf-8",
        )
        rc3, findings3 = gate.check(
            repo=root, status_path=status, events_path=ev, receipts_dir=rcpt
        )
        assert rc3 == 0 and not findings3
        lines.append("REGEN_AFTER_EDIT=silent")
    return "\n".join(lines) + "\n"


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    # Regenerate live STATUS then gate
    d_rc, d_out = _run([sys.executable, DERIVER])
    (L.REPO / PROBE_DIR / "derive.out").write_text(d_out, encoding="utf-8")
    if d_rc != 0:
        raise SystemExit(f"CC-0013 derive failed:\n{d_out}")

    g_rc, g_out = _run([sys.executable, GATE])
    (L.REPO / PROBE_DIR / "gate.out").write_text(g_out, encoding="utf-8")
    if g_rc != 0:
        raise SystemExit(f"CC-0013 gate failed:\n{g_out}")

    controls = _scratch_controls()
    (L.REPO / PROBE_DIR / "controls.out").write_text(controls, encoding="utf-8")

    # Every metric line must carry a query
    status_text = (L.REPO / STATUS).read_text(encoding="utf-8")
    metric_lines = [
        ln for ln in status_text.splitlines() if ln.startswith("| ") and "query" not in ln.lower()
    ]
    # header separator rows excluded
    data_rows = [
        ln
        for ln in status_text.splitlines()
        if ln.startswith("| ") and not ln.startswith("|---") and "metric" not in ln
    ]
    for row in data_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) >= 3 and not cells[2]:
            raise SystemExit(f"CC-0013 metric missing query: {row}")

    p_derive = L.probe("source", "command", f"python3 {DERIVER}", d_out, d_rc)
    p_gate = L.probe("verifier", "command", f"python3 {GATE}", g_out, g_rc)
    p_controls = L.probe(
        "source",
        "test-run",
        "scratch empty/hand-edit/determinism/regenerate controls",
        controls,
        0,
    )

    sentinel = (
        f"FAILED:{UNIT} blocked-on-independent-review; STATUS.md derived + gate silent; "
        f"empty=NOT-STARTED hand-edit=red determinism=ok; catalog SUCCESS:{UNIT} withheld "
        f"pending independent reviewer who hand-edits a different field"
    )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0013",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art(DERIVER, "primary"),
            L.art(GATE, "supporting"),
            L.art(STATUS, "primary"),
            L.art(f"{PROBE_DIR}/derive.out", "log"),
            L.art(f"{PROBE_DIR}/gate.out", "log"),
            L.art(f"{PROBE_DIR}/controls.out", "log"),
            L.art("command-center/p2-wave/_build_CC0013.py", "control"),
        ],
        "evidence": [
            L.evidence(
                (
                    "STATUS.md is generated by status_derive.py from EVENTS.jsonl + receipts/ "
                    "+ completion_predicate; every metric row carries its query."
                ),
                "CONFIRMED",
                f"file:{DERIVER}",
                [p_derive, p_gate],
                "almost-certain",
            ),
            L.evidence(
                (
                    "Hand-edit gate (status_gate.py) fires and names the drifted line; "
                    "regenerate is silent; empty events emit NOT-STARTED; two renders "
                    "are byte-identical."
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/controls.out",
                [p_controls, p_gate],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "Two strikes then pivot; do not add exemptions to the hand-edit gate.",
        },
        "tests": [
            {
                "id": "hand-edit-fires",
                "name": "Hand-edit a counter -> gate fires and names the drifted line.",
                "command": "scratch HAND_EDIT_FIRED control",
                "result": "PASS",
                "assertions": 1,
                "output_tail": controls,
            },
            {
                "id": "regenerate-silent",
                "name": "Regenerate -> gate silent.",
                "command": f"python3 {GATE}",
                "result": "PASS",
                "assertions": 1,
                "output_tail": g_out,
            },
            {
                "id": "determinism",
                "name": "Two runs over unchanged inputs are byte-identical.",
                "command": "scratch DETERMINISM control",
                "result": "PASS",
                "assertions": 1,
                "output_tail": controls,
            },
            {
                "id": "empty-not-started",
                "name": "Zero events => NOT-STARTED, never green.",
                "command": "scratch EMPTY_CONTROL",
                "result": "PASS",
                "assertions": 1,
                "output_tail": controls,
            },
        ],
        "negative_controls": [
            L.control(
                "hand-edit-board-status",
                "mutation",
                "Mutating Board status MEASURED -> MEASURED-HACKED must fail the gate.",
                True,
                True,
                bad="Board status: MEASURED-HACKED",
                good=g_out,
            ),
            L.control(
                "empty-events-not-green",
                "absent-input",
                "Zero events must emit NOT-STARTED, never GREEN/COMPLETE/SUCCESS.",
                True,
                True,
                bad="program_status=GREEN with empty EVENTS.jsonl",
                good="EMPTY_CONTROL=NOT-STARTED",
            ),
        ],
        "reviewer": {
            "reviewer_id": "awaiting-independent-hand-edit-other-field",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic",
            "reviewed_at": ended,
            "notes": (
                "Implementer emit only. Catalog reviewer_requirement: one independent "
                "reviewer who hand-edits a different field than the author tested and "
                "confirms the gate fires. Self-review banned."
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
                "consumer": "status_gate.check",
                "artifact_path": STATUS,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    f"python3 {GATE}",
                    g_out,
                    g_rc,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Independent reviewer has not hand-edited a different STATUS.md field "
                    "and confirmed the gate in a fresh context."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context reviewer changes a metric value (not Board status), "
                    f"runs `python3 {GATE}`, confirms named drift, regenerates, confirms "
                    "silent, returns PASS with independent=true."
                ),
            }
        ],
        "defects": [],
        "failure": {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Derive+gate green; empty/hand-edit/determinism/regenerate controls passed. "
                "Catalog reviewer_requirement unmet — do not emit SUCCESS."
            ),
            "blocked_on": "independent hand-edit of a different field (NOT-REVIEWED)",
            "diagnostic_tail": controls + "\n" + g_out,
            "two_signal_proof": [p_derive, p_controls],
        },
        "report": {
            "generator_id": derive.GENERATOR_ID,
            "status_bytes": (L.REPO / STATUS).stat().st_size,
            "catalog_completion_sentinel": f"SUCCESS:{UNIT}",
            "data_metric_rows": len(data_rows),
        },
        "extensions": {
            "p2_loop_wave": 1,
            "builder": "command-center/p2-wave/_build_CC0013.py",
        },
    }

    arts = []
    for a in receipt["artifacts"]:
        rel = a["path"]
        p = L.REPO / rel
        if p.is_file():
            data = p.read_bytes().replace(b"\r\n", b"\n")
            arts.append(
                {
                    "path": rel,
                    "bytes": len(data),
                    "sha256": __import__("hashlib").sha256(data).hexdigest(),
                    "present": True,
                }
            )
    man_doc = {
        "entry_id": UNIT,
        "unit_id": UNIT,
        "artifacts": arts,
        "writer": ar.ATOMIC_WRITER_ID,
        "registered_at": ended,
        "state": "BLOCKED",
    }
    ar.write_json_atomic(L.REPO / MANIFEST, man_doc)
    receipt["artifacts"].append(L.art(MANIFEST, "supporting"))

    errs = L.validate(receipt, SCHEMA)
    if errs:
        print(f"WARN: schema issues ({len(errs)}): {errs[:12]}", file=sys.stderr)

    ar.write_json_atomic(L.REPO / OUT, receipt)
    print(f"BLOCKED:{UNIT} wrote {OUT} bytes={(L.REPO / OUT).stat().st_size}")
    return ar.read_json(L.REPO / OUT)


if __name__ == "__main__":
    build()
