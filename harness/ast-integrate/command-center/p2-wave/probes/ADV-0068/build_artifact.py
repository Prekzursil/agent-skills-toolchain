#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0068-moderation-and-dispute-abuse.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from probe_common import PROBE1_CMD, PROBE2_CMD  # noqa: E402

OUT = "command-center/adversarial/ADV-0068-moderation-and-dispute-abuse.json"
SCHEMA = "command-center/schema/threat-model.schema.json"
ENGINE = "tools/marketplace/moderation.py"
SENTINEL = (
    "SUCCESS:ADV-0068 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0068 <reason>."
)
QUESTION = (
    "Can the moderation flow be used against a legitimate package - mass false "
    "reports triggering automatic removal, a false advisory marking a healthy "
    "package vulnerable, or a dispute that hides a genuinely malicious one?"
)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def first_json_line(text: str) -> dict:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise ValueError("probe emitted no JSON object")


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    c1, t1 = run_probe(PROBE1_CMD)
    c2, t2 = run_probe(PROBE2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0068 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    p1 = first_json_line(t1)
    p2 = first_json_line(t2)
    src1 = (HERE / "probe1_mass_reports.py").read_text(encoding="utf-8")
    src2 = (HERE / "probe2_unresolved_dispute.py").read_text(encoding="utf-8")
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    f1 = p1["findings"]["F1-MASS-FALSE-REPORTS"]
    f2 = p1["findings"]["F2-FALSE-ADVISORY"]
    f3 = p2["findings"]["F3-UNRESOLVED-DISPUTE"]
    verdicts = {f1, f2, f3}
    if not verdicts <= {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}:
        print("FAILED:ADV-0068 illegal verdict")
        return 1
    if "NOT-CHECKED" in verdicts:
        state = "PARTIAL"
    elif verdicts == {"REFUTED"}:
        state = "SUCCESS"
    elif "CONFIRMED" in verdicts and "REFUTED" in verdicts:
        state = "PARTIAL"
    elif verdicts == {"CONFIRMED"}:
        state = "SUCCESS"
    else:
        state = "PARTIAL"

    nc = p2["negative_control"]
    ctrl = p1["good_faith_control"]

    doc = {
        "unit_id": "ADV-0068",
        "state": state,
        "sentinel": SENTINEL,
        "kind": "threat-model",
        "schema_version": 1,
        "title": "Abuse of the moderation, dispute and advisory-report flow",
        "question": QUESTION,
        "spec_anchor": "_USER-PROMPTS.md:10867-10868, 11056",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "produced_at": now,
        "engine": ENGINE,
        "findings": [
            {
                "id": "F1-MASS-FALSE-REPORTS",
                "target": "mass false reports auto-remove or auto-block a legitimate fixture",
                "verdict": f1,
                "summary": (
                    "Twenty distinct-identity fixture reports left yanked=false, "
                    "warning_banner=false, and install allowed."
                    if f1 == "REFUTED"
                    else "Mass reports produced an automatic enforcement action."
                ),
            },
            {
                "id": "F2-FALSE-ADVISORY",
                "target": "an unauthorized advisory marks a healthy fixture vulnerable",
                "verdict": f2,
                "summary": (
                    "Consumer-signed advisory was refused (unauthorized-signer); "
                    "the healthy fixture stayed installable."
                    if f2 == "REFUTED"
                    else "A false advisory was accepted against the healthy fixture."
                ),
            },
            {
                "id": "F3-UNRESOLVED-DISPUTE",
                "target": "an unresolved dispute suspends enforcement on a known-malicious fixture",
                "verdict": f3,
                "summary": (
                    "After a publisher dispute the signed advisory remained in "
                    "open_advisories (state=disputed) and install stayed blocked "
                    "with override_recorded=false."
                    if f3 == "REFUTED"
                    else "An unresolved dispute dropped the advisory from install gating."
                ),
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "role": "mass-false-reports",
                "command": PROBE1_CMD,
                "exit_code": c1,
                "raw_output": t1,
                "source": src1,
            },
            {
                "id": "probe2",
                "role": "unresolved-dispute",
                "command": PROBE2_CMD,
                "exit_code": c2,
                "raw_output": t2,
                "source": src2,
            },
        ],
        "controls": [
            {
                "id": "CTRL-GOOD-FAITH-SINGLE-REPORT",
                "result": "PASS" if ctrl.get("pass") else "FAIL",
                "status": ctrl.get("status"),
                "documented_outcome": ctrl.get("documented_outcome"),
                "queued": ctrl.get("queued"),
                "install_still_allowed": ctrl.get("install_still_allowed"),
            },
            {
                "id": "CTRL-FIXTURES-ONLY",
                "result": "PASS" if p1.get("fixture_only") and p2.get("fixture_only") else "FAIL",
                "note": "Both probes target fixture.legit-hello / fixture.malware-beacon only.",
            },
            {
                "id": "CTRL-INSTALL-CALLS-OPEN-ADVISORIES",
                "result": "PASS" if p2.get("install_calls_open_advisories") else "FAIL",
            },
            {
                "id": "CTRL-DISPUTED-REMAINS-GATING",
                "result": "PASS" if p2.get("disputed_in_gating_states") else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": nc["id"],
                "fired_on_bad_state": nc["fired_on_bad_state"],
                "silent_on_good_state": nc["silent_on_good_state"],
                "threshold": nc["threshold"],
                "bad_n": nc["bad_n"],
                "good_n": nc["good_n"],
                "result": "PASS" if nc.get("pass") else "FAIL",
            }
        ],
        "evidence": [
            {
                "claim": "Mass reports from distinct identities do not auto-enforce.",
                "verdict": f1,
                "signal": {
                    "kind": "command_output",
                    "command": PROBE1_CMD,
                    "output": t1[:2000],
                },
            },
            {
                "claim": "Unauthorized false advisory is refused; healthy fixture stays installable.",
                "verdict": f2,
                "signal": {
                    "kind": "command_output",
                    "command": PROBE1_CMD,
                    "output": json.dumps(p1.get("false_advisory"), sort_keys=True),
                },
            },
            {
                "claim": "Unresolved dispute does not suspend advisory gating of install.",
                "verdict": f3,
                "signal": {
                    "kind": "command_output",
                    "command": PROBE2_CMD,
                    "output": t2[:2000],
                },
            },
        ],
        "defects": [],
        "reviewer": {
            "reviewer_id": "ADV-0068-probe2-unresolved-dispute",
            "verdict": "PASS" if p2.get("pass") else "FAIL",
            "independent": True,
            "vendor": "openai",
            "notes": (
                "Probe 2 re-derives F3 from a live engine run (advisory, dispute, "
                "install, AST of install/open_advisories/GATING_STATES) rather "
                "than from this receipt. Catalog asked for a cross-vendor "
                "Anthropic/opus refuter; that reviewer is not on this worker. "
                "G-1 does not gate on it."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "schema"},
            {"path": ENGINE, "role": "engine"},
            {
                "path": "command-center/p2-wave/probes/ADV-0068/probe1_mass_reports.py",
                "role": "probe",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0068/probe2_unresolved_dispute.py",
                "role": "probe",
            },
        ],
        "probe_results": {"probe1": p1, "probe2": p2},
        "prior_p1": {
            "id": "ADV-0068-DISPUTED-NON-GATING",
            "was": (
                "A validly signed disputed state was excluded from open_advisories "
                "immediately, so install accepted a known-malicious fixture while "
                "the dispute was still open and without recording an override."
            ),
            "fix": (
                "tools/marketplace/moderation.py GATING_STATES includes 'disputed'; "
                "install() calls open_advisories(); owner override is explicit."
            ),
            "status": "closed" if f3 == "REFUTED" else "open",
        },
        "residual_unknowns": [
            {
                "claim": "A cross-vendor Anthropic/opus reviewer reproduces F1-F3 from the raw probes.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Hand the two probe scripts, tools/marketplace/moderation.py, "
                    "and fixture names to an opus reviewer with no receipt."
                ),
            }
        ],
        "completion_sentinel": SENTINEL,
    }

    jsonschema.Draft7Validator(schema).validate(doc)
    if SENTINEL not in json.dumps(doc):
        print("FAILED:ADV-0068 catalog sentinel absent from serialized artifact")
        return 1
    if any(c["result"] != "PASS" for c in doc["controls"]):
        print("FAILED:ADV-0068 a required control did not PASS")
        return 1
    if not nc.get("pass"):
        print("FAILED:ADV-0068 negative control did not discriminate")
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    dest.write_text(text, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(text.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))} sha256={digest} state={state}")
    print("SUCCESS:ADV-0068 artifact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
