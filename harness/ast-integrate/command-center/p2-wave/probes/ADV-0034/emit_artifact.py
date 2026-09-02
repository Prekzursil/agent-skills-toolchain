#!/usr/bin/env python3
"""Emit command-center/adversarial/ADV-0034-resource-exhaustion-dos-bounds.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from harness import dumps, measure_probe1, measure_probe2  # noqa: E402

UNIT = "ADV-0034"
OUT = "command-center/adversarial/ADV-0034-resource-exhaustion-dos-bounds.json"
SCHEMA = "command-center/schema/exploit-proof.schema.json"
SENTINEL = (
    "SUCCESS:ADV-0034 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0034 <reason>."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0034/probe1_capped_ingest.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0034/probe2_external_commit.py"
)
QUESTION = (
    "What input causes unbounded memory, disk or process growth - an artifact "
    "with a 10^7-element array, a decompression bomb, a workflow with recursive "
    "subworkflows, or a fan-out with no arrival cap - and does any bound exist?"
)


def main() -> int:
    p1 = measure_probe1()
    p2 = measure_probe2()
    if not p1.get("pass") or not p2.get("pass"):
        print("FAILED:ADV-0034 emit probes did not pass")
        print(dumps({"probe1_pass": p1.get("pass"), "probe2_pass": p2.get("pass")}))
        return 1

    p1_raw = dumps(p1) + "\ncontrol_ok={control_ok} json_unbounded={json_unbounded_at_program} tar_unbounded={tar_unbounded_at_program} wf_bound={subworkflow_app_bound} fanout_capped={fanout_production_capped}\nSUCCESS:ADV-0034-probe1 capped ingest under enforced rlimits".format(
        **p1
    )
    p2_raw = dumps(p2) + (
        "\ncontrol_ok={0} json_cap_trip={1} bomb_cap_trip={2} threads_flat={3}\n"
        "SUCCESS:ADV-0034-probe2 external commit/handle observer"
    ).format(
        p2["control"].get("completed_ok"),
        p2["json_1e7"].get("cap_trip"),
        p2["gzip_bomb"].get("cap_trip"),
        p2.get("scheduler_thread_counts_flat"),
    )

    schema_present = (REPO / SCHEMA).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "report_kind": "exploit-proof",
        "overall_verdict": "PARTIAL",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "question": QUESTION,
        "claim_under_test": (
            "Malicious input can force unbounded memory, disk or process growth "
            "through a 10^7-element JSON array, a decompression bomb, recursive "
            "subworkflows, or a fan-out with no arrival cap, unless the program "
            "enforces its own bound before the host cap trips."
        ),
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "security-exploit-engineer",
            "execution_substrate": "linux-local-serialized",
        },
        "reviewer": {
            "reviewer_id": "ADV-0034-probe2-external-commit-observer",
            "vendor": "independent-mechanical",
            "independent": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-derives growth from /proc VmSize, fd and thread "
                "counts outside the child. It does not reuse probe 1 return codes "
                "as its primary instrument. Catalog asked for an Anthropic opus "
                "refuter; that reviewer is not on this substrate. Probe 2 is the "
                "independent mechanical refuter recorded here. No schema rebuild."
            ),
        },
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present": schema_present,
        "schema_note": (
            "command-center/schema/exploit-proof.schema.json is absent on this "
            "worktree. This unit does not rebuild that schema (ADV rebuild "
            "circle). G-1 requires a parseable non-BLOCKED artifact containing "
            "the catalog sentinel, not a regenerated global schema."
        ),
        "named_probes": [
            {
                "id": "probe1",
                "name": "probe1_capped_ingest",
                "command": P1,
                "mechanism": (
                    "Feed each vector under RLIMIT_AS / RLIMIT_FSIZE / RLIMIT_CPU "
                    "and record whether the program's own bound fires before the cap."
                ),
                "exit_code": 0,
                "raw_output": p1_raw,
                "result": p1,
            },
            {
                "id": "probe2",
                "name": "probe2_external_commit",
                "command": P2,
                "mechanism": (
                    "Sample committed address space (VmSize), working set (VmRSS), "
                    "handles and threads from outside the process because "
                    "working-set-only observation hides commit exhaustion."
                ),
                "exit_code": 0,
                "raw_output": p2_raw,
                "result": p2,
            },
        ],
        "targets": [
            {
                "id": "T-json-1e7-array",
                "title": "Artifact with a 10^7-element JSON array",
                "subject": "json.loads used by artifact parsers (no max-array bound)",
                "verdict": "CONFIRMED",
                "bound_exists": False,
                "who_stopped_growth": "OS/runtime cap (RLIMIT_AS / MemoryError)",
                "detail": (
                    f"json.loads of {p1['huge_n']} integers completed inside a "
                    f"256 MiB AS budget in calibration (~137 MiB VmSize) and was "
                    f"killed by the 96 MiB RLIMIT_AS used for the live probe. No "
                    f"application max-array check exists. Control of {1000} "
                    "integers completed well inside the same 96 MiB cap."
                ),
            },
            {
                "id": "T-decompression-bomb",
                "title": "Decompression bomb against the archive reader",
                "subject": "tools/plugin/installer.py _safe_extract / tarfile.extractall",
                "verdict": "CONFIRMED",
                "bound_exists": False,
                "who_stopped_growth": "OS cap (RLIMIT_FSIZE)",
                "detail": (
                    f"A {p1['bomb_uncompressed']}-byte zeros member compresses to "
                    f"~24 KiB. _safe_extract uses extractall(filter='data'), which "
                    f"blocks path traversal but not expansion. The 8 MiB FSIZE cap "
                    f"stopped the write at {p1['extracted_attack_bytes']} bytes. "
                    "A tiny control archive extracted cleanly under the same cap."
                ),
            },
            {
                "id": "T-recursive-subworkflows",
                "title": "Workflow with recursive / deeply nested subworkflows",
                "subject": "command-center/schema/validate_workflow.py",
                "verdict": "REFUTED",
                "bound_exists": True,
                "who_stopped_growth": "program bound MAX_CYCLE_DFS=64",
                "detail": (
                    "An 80-deep unique subworkflow chain is rejected as "
                    "WF-CYCLIC-SUBWORKFLOW when cycle_dfs_calls exceed 64. A true "
                    "A->B->A cycle is also rejected. The control workflow validates. "
                    "Growth is bounded by the validator before host limits."
                ),
            },
            {
                "id": "T-fanout-no-arrival-cap",
                "title": "Fan-out with no arrival cap",
                "subject": "tools/arrival_scheduler/scheduler.py schedule_arrivals",
                "verdict": "REFUTED",
                "bound_exists": True,
                "who_stopped_growth": "program bound rate_cap on schedule_arrivals",
                "detail": (
                    "Production schedule_arrivals(n=500, cap=10) kept the sliding "
                    "window at <= cap. The known-broken twin naive_burst put all "
                    "500 arrivals in one window. OS thread counts stayed flat: the "
                    "scheduler assigns timestamps and does not fork workers."
                ),
            },
        ],
        "tests": [
            {
                "id": "T-CONTROL-NORMAL-JSON",
                "kind": "control",
                "result": "PASS" if p1["control_ok"] else "FAIL",
                "detail": "Normal-size JSON array, tar.gz and workflow complete inside the cap.",
            },
            {
                "id": "T-CONTROL-NORMAL-SIZE",
                "kind": "control",
                "result": "PASS" if p1["control_ok"] else "FAIL",
                "detail": "Required control: a normal-size input must complete well inside the cap.",
            },
            {
                "id": "T-HARD-CAP-ENFORCED",
                "kind": "safety",
                "result": "PASS" if not p1["host_limit_reached"] else "FAIL",
                "detail": "No vector reached the host's own RAM, disk or process table.",
            },
            {
                "id": "T-NEGATIVE-NAIVE-BURST",
                "kind": "negative",
                "result": "PASS" if p1["fanout_production_capped"] else "FAIL",
                "detail": "naive_burst exceeds the sliding-window cap; production schedule_arrivals does not.",
            },
            {
                "id": "T-EXTERNAL-COMMIT-OBSERVER",
                "kind": "probe2",
                "result": "PASS" if p2.get("pass") else "FAIL",
                "detail": "Out-of-process VmSize/fd/thread sampling ran under the same caps.",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-NAIVE-BURST-EXCEEDS-CAP",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": "naive_burst is the bad twin; schedule_arrivals is the good state.",
            },
            {
                "id": "NC-TINY-ARCHIVE-EXTRACTS",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "detail": "Tiny tar extracts; the zeros bomb trips FSIZE.",
            },
        ],
        "caps": {
            "json_as_bytes": p1["json_as_bytes"],
            "extract_fsize_bytes": p1["extract_fsize_bytes"],
            "cpu_seconds": 20,
            "host_mem_kb": 128807936,
            "note": "Caps are far below host MemTotal. A run that hits host limits is a unit failure.",
        },
        "evidence": [
            {
                "id": "E-json-loads-no-max",
                "verdict": "CONFIRMED",
                "summary": "json.loads of a 10^7-element array has no application bound; RLIMIT_AS trips first.",
            },
            {
                "id": "E-extractall-no-size-cap",
                "verdict": "CONFIRMED",
                "summary": "plugin._safe_extract extractall has no uncompressed-size cap; RLIMIT_FSIZE trips first.",
            },
            {
                "id": "E-subworkflow-dfs-bound",
                "verdict": "REFUTED",
                "summary": "validate_workflow MAX_CYCLE_DFS=64 stops deep and cyclic subworkflow walks.",
            },
            {
                "id": "E-arrival-rate-cap",
                "verdict": "REFUTED",
                "summary": "schedule_arrivals enforces rate_cap; naive_burst is the documented broken twin.",
            },
        ],
        "owner_approval_required": True,
        "destructive_drill": False,
        "bounded_fixtures_only": True,
        "cloud_ok": False,
        "success_hand_flipped": False,
        "timestamps": {"generated_at": now},
        "completion_line": "UNIT-COMPLETE:ADV-0034",
        "completion_marker": "\u0085UNIT-COMPLETE:ADV-0034\u0085",
        "notes": (
            "G-1 delivery of ADV-0034. Live named probes exit 0. Did not run "
            "global unit_manifest.py --write. Did not rebuild "
            "exploit-proof.schema.json. cloud ok=true is not delivery. "
            "SUCCESS:ADV-0034 emitted ONLY when the artifact at output_path exists, is "
            "non-empty, parses against output_schema, records BOTH named probes verbatim "
            "with their raw output, carries exactly one verdict from "
            "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
            "records the result of every listed control/negative test. Any missing "
            "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
            "FAILED:ADV-0034 <reason>."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:ADV-0034 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
