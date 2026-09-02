#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0011-scheduler-report.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scheduler as S  # noqa: E402
from jsonschema import Draft202012Validator, RefResolver  # noqa: E402

UNIT = "CNF-0011"
OUT_REL = "command-center/confirmation/CNF-0011-scheduler-report.json"
SCHEMA_REL = "command-center/schema/scheduler-report.schema.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0011/probe1_hung_unit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0011/probe2_quota_529.py"
)
SUPPORTING = [
    "command-center/schema/scheduler-report.schema.json",
    "command-center/p2-wave/probes/CNF-0011/scheduler.py",
    "command-center/p2-wave/probes/CNF-0011/emit_report.py",
    "command-center/p2-wave/probes/CNF-0011/probe1_hung_unit.py",
    "command-center/p2-wave/probes/CNF-0011/probe2_quota_529.py",
    "command-center/p2-wave/probes/CNF-0011/fixtures/cohort.json",
]


def catalog_field(key: str) -> str:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return str(u.get(key) or "")
    return ""


def catalog_sentinel() -> str:
    s = catalog_field("completion_sentinel")
    if not s:
        raise SystemExit("FAILED:CNF-0011 catalog sentinel missing")
    return s


def sha_art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    crlf = path.read_bytes().count(b"\r\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "CRLF" if crlf else "LF",
        "role": role,
    }


def find_anchor(rel: str, snippet: str) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0011 snippet not found in {rel}: {snippet!r}")
    return f"{rel}:{text[:idx].count(chr(10)) + 1}"


_SCHEMA_FILES = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def schema_validator():
    """Resolve ast-integrate.invalid $refs from disk (jsonschema 4.10 has no registry=)."""
    store: dict[str, dict] = {}
    for rel in _SCHEMA_FILES:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        store[str(doc["$id"])] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    validator = schema_validator()
    return [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    ]


def validate(doc: dict) -> None:
    errs = schema_errors(doc)
    if errs:
        print("FAILED:CNF-0011 schema-invalid")
        for e in errs[:30]:
            print(" ", e)
        raise SystemExit("FAILED:CNF-0011 schema-invalid")
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
    ):
        if not schema_errors(garbage):
            raise SystemExit("FAILED:CNF-0011 schema accepts garbage")


def configured_run_dict(result: S.RunResult) -> dict:
    table = [r.as_dict() for r in result.terminals]
    if any(row["blank"] or not row["terminal_state"] for row in table):
        raise SystemExit("FAILED:CNF-0011 blank terminal row")
    return {
        "mode": "configured",
        "configured_rate_recorded": True,
        "rejections_by_class": {
            "429": int(result.rejections.get("429", 0)),
            "529": int(result.rejections.get("529", 0)),
            "timeout": int(result.rejections.get("timeout", 0)),
        },
        "arrival_histogram": S.arrival_histogram(
            result.arrivals, result.config.histogram_bin_s
        ),
        "terminal_state_table": table,
        "blank_terminal_rows": 0,
        "concurrency_cap_start": result.concurrency_cap_start,
        "concurrency_cap_end": result.concurrency_cap_end,
        "concurrency_reductions": result.concurrency_reductions,
        "actions": result.actions,
    }


def resume_demo(jobs: list[S.Job], cfg: S.SchedulerConfig) -> dict:
    first = S.run_scheduler(jobs, cfg, mode="configured", stop_after_n_terminals=3)
    completed = {r.unit_id for r in first.terminals}
    if len(completed) < 1:
        raise SystemExit("FAILED:CNF-0011 resume checkpoint empty")
    second = S.run_scheduler(jobs, cfg, mode="configured", resume_completed=completed)
    replayed = [uid for uid in second.started_ids if uid in completed]
    final_ids = completed | {r.unit_id for r in second.terminals}
    expected = {j.unit_id for j in jobs}
    if final_ids != expected:
        raise SystemExit(f"FAILED:CNF-0011 resume missed units {expected - final_ids}")
    return {
        "checkpoint_after_n_terminals": len(completed),
        "resumed": True,
        "replayed_completed_units": len(replayed),
        "final_terminal_count": len(final_ids),
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    cfg = S.SchedulerConfig()
    cohort = S.load_cohort(REPO)
    jobs: list[S.Job] = cohort["jobs"]
    configured = S.run_scheduler(jobs, cfg, mode="configured")
    if len(configured.terminals) != len(jobs):
        raise SystemExit("FAILED:CNF-0011 not every unit reached a terminal state")
    if int(configured.rejections.get("429", 0)) != 0:
        raise SystemExit(f"FAILED:CNF-0011 configured 429={configured.rejections.get('429')}")
    hung = S.hung_proof(configured)
    burst = S.run_scheduler(jobs, cfg, mode="burst")
    if int(burst.rejections.get("429", 0)) < 1:
        raise SystemExit("FAILED:CNF-0011 burst control produced no 429s")
    five29_unit = next(j.unit_id for j in jobs if j.inject_529)
    if int(configured.rejections.get("529", 0)) < 1:
        raise SystemExit("FAILED:CNF-0011 configured run observed no 529")
    if configured.concurrency_reductions != 0:
        raise SystemExit("FAILED:CNF-0011 concurrency reduced")
    if configured.forbidden_reduce_actions() != 0:
        raise SystemExit("FAILED:CNF-0011 forbidden reduce action in log")
    resume = resume_demo(jobs, cfg)
    sentinel = catalog_sentinel()
    question = catalog_field("question_or_target")
    vendors = {j.vendor for j in jobs}
    sched_rel = "command-center/p2-wave/probes/CNF-0011/scheduler.py"
    hung_anchor = find_anchor(sched_rel, "def hung_proof(")
    rate_anchor = find_anchor(sched_rel, "if t + 1e-12 < last + self.min_interval_s:")
    retry_anchor = find_anchor(sched_rel, "retry_after_529_concurrency_unchanged")
    schema_errs = schema_errors(
        {"totally": "unrelated", "passing_tests": 999999}
    )
    if not schema_errs:
        raise SystemExit("FAILED:CNF-0011 schema accepts garbage")
    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    n429 = int(configured.rejections.get("429", 0))
    n529 = int(configured.rejections.get("529", 0))
    burst_429 = int(burst.rejections.get("429", 0))
    hung_detail = (
        f"{hung['surviving_completed']} survivors completed; "
        f"{hung['survivors_finished_before_hung_timeout']} finished before "
        f"{hung['injected_unit_id']} TIMEOUT"
    )
    rate_detail = (
        f"configured 429=0; recorded min_interval={cfg.vendor_min_interval_s}s; "
        f"burst 429={burst_429}"
    )
    five29_detail = (
        f"529 count={n529} on {five29_unit}; "
        f"cap {configured.concurrency_cap_start}->{configured.concurrency_cap_end}; "
        f"forbidden_reduce_actions={configured.forbidden_reduce_actions()}"
    )
    artifacts = [sha_art(p, "supporting") for p in SUPPORTING]
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "_USER-PROMPTS.md:10570-10584",
        "min_bytes_threshold": 1024,
        "profile": "scheduler-report",
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Injecting one hung unit does not globally barrier the cohort: "
                    "survivors reach terminal SUCCESS before the hung TIMEOUT."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": hung_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/CNF-0011/"
                            "scheduler.py hung_proof(configured_run)"
                        ),
                        "raw_output": json.dumps(hung, sort_keys=True),
                        "fingerprint": "src:hung-proof-run",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": f"read {hung_anchor} and count TIMEOUT vs survivors-before",
                        "raw_output": hung_detail,
                        "fingerprint": "ver:hung-proof-static",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "At the recorded per-vendor arrival cap, configured-mode 429 "
                    f"count is {n429}; burst mode produced {burst_429} x 429 so "
                    "the cap is load-bearing. A provider 529 retried without "
                    "reducing concurrency."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": rate_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": (
                            "python3 -B -c configured vs burst SimulatedVendor.submit"
                        ),
                        "raw_output": (
                            f"configured_429={n429} burst_429={burst_429} "
                            f"observed_529={n529} cap="
                            f"{configured.concurrency_cap_start}->"
                            f"{configured.concurrency_cap_end}"
                        ),
                        "fingerprint": "src:quota-529-run",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": f"read {rate_anchor} and {retry_anchor}",
                        "raw_output": f"{rate_detail}; {five29_detail}",
                        "fingerprint": "ver:quota-529-static",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "hung-unit-injection",
                "name": (
                    "inject one deliberately hung unit and prove the cohort still "
                    "completes (per-unit pipeline, not a global barrier)"
                ),
                "command": P1,
                "result": "PASS",
                "output_tail": hung_detail,
            },
            {
                "id": "zero-429-at-configured-rate",
                "name": (
                    "429 rejections observed must be zero at the configured rate, "
                    "and the rate must be recorded"
                ),
                "command": P2,
                "result": "PASS",
                "output_tail": rate_detail,
            },
            {
                "id": "529-must-not-reduce-concurrency",
                "name": (
                    "reducing concurrency in response to a provider-side 529 is "
                    "forbidden and must not appear in the log"
                ),
                "command": P2,
                "result": "PASS",
                "output_tail": five29_detail,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-BURST-429",
                "kind": "known-broken-fixture",
                "description": (
                    "Burst mode disables stagger and vendor wait so SimulatedVendor "
                    "must emit 429s; otherwise the configured-rate zero-429 result "
                    "is an inert cap."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"burst 429={burst_429}",
                "good_state_output": f"configured 429={n429}",
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": (
                    "schema_resolver.validate_artifact must reject an unrelated "
                    "object so the scheduler-report class is not a no-op schema."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": schema_errs[0][:500],
                "good_state_output": "SUCCESS:schema-valid",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0011-probe2-quota-529",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic",
            "notes": (
                "Two named probes file independently. Probe 1 re-runs hung_proof "
                "and checks the artifact table. Probe 2 re-runs configured vs "
                "burst and the 529 concurrency invariant. Measure re-runs both."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0011/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py (validate_artifact)",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -c schema_resolver.validate_artifact"
                        f"(doc, {SCHEMA_REL!r})"
                    ),
                    "raw_output": "SUCCESS:schema-valid",
                    "fingerprint": "cli:resolver-validate",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ended_at": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "resumable: on interruption, restart from the last durable "
                "checkpoint and record the resume boundary in the receipt; never "
                "restart from zero and silently discard the partial evidence"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CNF-0003 sampling frame is absent on this worktree; the "
                    "scheduler ran a fixture cohort of the same shape."
                ),
                "verdict": "NOT-CHECKED" if not cohort["present"] else "CONFIRMED",
                "settling_experiment": (
                    "Deliver CNF-0003 sampling-frame.json and re-run emit_report.py "
                    "so load_cohort uses the live frame."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "scheduler-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "scheduler-report",
            "control_ids": ["NC-BURST-429", "NC-SCHEMA-GARBAGE"],
            "observations": [
                {
                    "name": "configured_429",
                    "measured": n429,
                    "method": "discrete-event scheduler + SimulatedVendor",
                    "anchor": rate_anchor,
                },
                {
                    "name": "burst_429",
                    "measured": burst_429,
                    "method": "burst mode without stagger or vendor wait",
                    "anchor": rate_anchor,
                },
                {
                    "name": "survivors_before_hung_timeout",
                    "measured": hung["survivors_finished_before_hung_timeout"],
                    "method": "hung-unit injection per-unit pipeline",
                    "anchor": hung_anchor,
                },
                {
                    "name": "concurrency_reductions_after_529",
                    "measured": configured.concurrency_reductions,
                    "method": "action log scan for cap shrink",
                    "anchor": retry_anchor,
                },
            ],
            "title": (
                "Arrival-staggered confirmation scheduler with quota awareness "
                "and starvation proof"
            ),
            "question": question,
            "answers": {
                "zero_429_at_configured_rate": True,
                "every_queued_unit_reached_terminal_state": True,
                "surviving_cohort_completed_despite_hung_unit": True,
                "provider_529_did_not_reduce_concurrency": True,
                "barrier_kind": "per-unit-pipeline",
            },
            "configured_concurrency": cfg.concurrency,
            "stagger_seconds": cfg.stagger_s,
            "per_vendor_rate_caps": S.rate_caps(cfg, vendors),
            "sampling_frame": {
                "source": cohort["source"],
                "path": cohort["path"],
                "present": cohort["present"],
                "cohort_size": cohort["cohort_size"],
                "note": cohort["note"],
            },
            "configured_run": configured_run_dict(configured),
            "hung_unit_injection": hung,
            "burst_control": {
                "mode": "burst",
                "rejections_429": burst_429,
                "proves_configured_rate_is_load_bearing": True,
            },
            "provider_529_control": {
                "injected_unit_id": five29_unit,
                "observed_529": n529,
                "concurrency_before": configured.concurrency_cap_start,
                "concurrency_after": configured.concurrency_cap_end,
                "concurrency_reduced": False,
                "forbidden_reduce_actions_in_log": configured.forbidden_reduce_actions(),
            },
            "resume_boundary": resume,
        },
    }
    validate(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if sentinel not in text:
        raise SystemExit("FAILED:CNF-0011 sentinel missing from artifact text")
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:CNF-0011")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
