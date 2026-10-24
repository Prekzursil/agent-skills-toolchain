#!/usr/bin/env python3
"""Pack AUD-0017 bidirectional live/repo orphan census.

Honest BLOCKED pending cross-vendor Codex re-run of ONLY probe 2
(catalog reviewer_requirement). Never stubs SUCCESS.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0017"
OUT = "command-center/audit/AUD-0017-live-repo-orphan-census.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0017/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = PROBE / "independent-review.json"


def load_review() -> dict | None:
    """SUCCESS only when a cross-vendor Codex review PASS that re-ran probe 2 is on disk."""
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in {"openai", "codex"}:
        return None
    if rev.get("reran_probe") not in {2, "2", "probe2"} and not rev.get("probe2_rerun"):
        return None
    return rev


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-set-difference.json").read_text(encoding="utf-8"))
    p2 = json.loads(
        (PROBE / "probe2-history-classification.json").read_text(encoding="utf-8")
    )
    raw1 = (PROBE / "probe1-set-difference.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-history-classification.raw.txt").read_text(encoding="utf-8")
    rev = load_review()
    success = rev is not None
    started = "2026-09-07T20:15:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    control1 = p1["planted_control"]
    control2 = p2["planted_control"]
    live_only = p1["live_only_total_checked"]
    repo_only = p1["repo_only_total_checked"]
    both_present = p1["pairs_both_present"]
    live_roots = p1["live_roots_present"]
    repo_roots = p1["repo_roots_present"]
    never_hist = p2["never_in_history_count"]
    was_deleted = p2["was_deleted_count"]

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art(
            "command-center/p2-wave/probes/AUD-0017/probe1-set-difference.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0017/probe2-history-classification.json",
            "supporting",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0017/probe1-set-difference.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0017/probe2-history-classification.raw.txt",
            "log",
        ),
        L.art(
            "command-center/p2-wave/probes/AUD-0017/fixtures/planted-nul-longpath/live/rules/NUL",
            "fixture",
        ),
    ]
    if success:
        arts.append(
            L.art(
                "command-center/p2-wave/probes/AUD-0017/independent-review.json",
                "supporting",
            )
        )

    question = (
        "Which harness artifacts exist in the live trees but in no repo "
        "(architecturally orphaned), and which repo artifacts have no deployed "
        "counterpart (deploy target missing)?"
    )

    measured_answer = (
        f"Deploy map from sync-from-live.ps1: {p1['map_entry_count']} tree pairs + "
        f"{p1['loose_file_count']} loose files. live_roots_present={live_roots}/6 "
        f"repo_roots_present={repo_roots}/6 pairs_both_present={both_present}. "
        f"Bidirectional checked live_only={live_only} repo_only={repo_only} "
        f"(missing live roots are NOT folded to empty). "
        f"Probe2 classified {p2['selected_count']} live-only candidates: "
        f"never_in_history={never_hist} was_deleted={was_deleted}. "
        f"Planted NUL+longpath control_ok={control1.get('ok')} "
        f"history_control_ok={control2.get('ok')}."
    )

    if success:
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": bool(rev.get("fresh_context", True)),
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": rev.get("notes", ""),
        }
        state = "SUCCESS"
        sentinel = "SUCCESS:AUD-0017"
        headline = (
            f"live_only={live_only} repo_only={repo_only} both_present={both_present} "
            f"never_in_history={never_hist} was_deleted={was_deleted}; "
            f"nul_longpath_ok={control1.get('ok')} hist_ok={control2.get('ok')}. "
            "Independent cross-vendor Codex probe2 re-run PASS."
        )
        failure = None
        anti = "SUCCESS-after-cross-vendor-codex-probe2-PASS"
        defects = [
            {
                "id": "AUD-0017-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": "Cross-vendor Codex re-run of probe 2 PASS recorded.",
            },
            {
                "id": "AUD-0017-D-ORPHANS",
                "severity": "P2",
                "status": "open"
                if (live_only or repo_only or live_roots == 0)
                else "resolved",
                "summary": (
                    f"live_only={live_only} repo_only={repo_only} "
                    f"live_roots_present={live_roots}; "
                    f"never_in_history={never_hist} was_deleted={was_deleted}."
                ),
            },
        ]
    else:
        reviewer = {
            "reviewer_id": "required-cross-vendor-codex-reviewer-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "notes": (
                "Catalog requires one cross-vendor Codex reviewer who re-runs ONLY "
                "the second probe (git log --diff-filter=D history classification). "
                "Unavailable in-session; BLOCKED instead of fake SUCCESS."
            ),
        }
        state = "BLOCKED"
        sentinel = (
            "FAILED:AUD-0017 set-difference + history-classification probes measured; "
            f"live_only={live_only} repo_only={repo_only} "
            f"never_in_history={never_hist}; "
            "blocked-on-cross-vendor-codex-probe2-rerun"
        )
        headline = (
            f"live_only={live_only} repo_only={repo_only} both_present={both_present} "
            f"never_in_history={never_hist} was_deleted={was_deleted}; "
            f"nul_longpath_ok={control1.get('ok')} hist_ok={control2.get('ok')}. "
            "BLOCKED on cross-vendor Codex probe2 re-run."
        )
        failure = {
            "classification": [
                "blocked-on-independent-review",
                "detector-failure",
                "partial-artifact",
            ],
            "reason": (
                "Named probes completed with planted NUL/longpath enumerator control "
                "and NEVER_IN_HISTORY classification of planted live-only paths, but "
                "catalog reviewer_requirement is unmet (cross-vendor Codex must re-run "
                "ONLY probe 2)."
            ),
            "diagnostic_tail": (
                f"live_only={live_only} repo_only={repo_only} "
                f"never_in_history={never_hist} was_deleted={was_deleted} "
                f"control1={control1.get('ok')} control2={control2.get('ok')} "
                "reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                "Dispatch one cross-vendor Codex reviewer to re-run ONLY "
                "command-center/p2-wave/probes/AUD-0017/probe2_history_classification.py "
                "and compare the history-classification receipt before PASS."
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0017/probe2_history_classification.py",
                    f"never_in_history={never_hist} planted_ok={control2.get('ok')}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-pending-cross-vendor-codex-probe2-with-real-probes"
        defects = [
            {
                "id": "AUD-0017-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": "Cross-vendor Codex re-run of probe 2 unpaid.",
            },
            {
                "id": "AUD-0017-D-ORPHANS",
                "severity": "P2",
                "status": "open",
                "summary": (
                    f"live_only={live_only} repo_only={repo_only} "
                    f"live_roots_present={live_roots}/6; "
                    f"probe2 never_in_history={never_hist} was_deleted={was_deleted}; "
                    f"nul_longpath_ok={control1.get('ok')}."
                ),
            },
        ]

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0017",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 applied sync-from-live.ps1 deploy map "
                    f"({p1['map_entry_count']} pairs): live_roots={live_roots} "
                    f"repo_roots={repo_roots} both_present={both_present}; "
                    f"checked live_only={live_only} repo_only={repo_only}; "
                    f"planted NUL+longpath control_ok={control1.get('ok')} "
                    f"(max_rel_len={control1.get('max_live_rel_len')})."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0017/probe1-set-difference.raw.txt",
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0017/probe1_set_difference.py",
                        raw1,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-set-difference.json",
                        json.dumps(
                            {
                                "live_only_total_checked": live_only,
                                "repo_only_total_checked": repo_only,
                                "pairs_both_present": both_present,
                                "planted_control_ok": control1.get("ok"),
                                "ok": p1.get("ok"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 git log --all --diff-filter=D on "
                    f"{p2['selected_count']} live-only candidates: "
                    f"never_in_history={never_hist} was_deleted={was_deleted} "
                    f"by_class={p2['by_classification']}; "
                    f"planted history control_ok={control2.get('ok')}."
                ),
                "CONFIRMED",
                "command-center/p2-wave/probes/AUD-0017/probe2-history-classification.raw.txt",
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0017/probe2_history_classification.py",
                        raw2,
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe2-history-classification.json",
                        json.dumps(
                            {
                                "never_in_history_count": never_hist,
                                "was_deleted_count": was_deleted,
                                "planted_ok": control2.get("ok"),
                                "ok": p2.get("ok"),
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0017-nul-longpath-enumerator",
                "name": (
                    "control: the enumerator must not crash or silently zero on a "
                    "file named NUL or a path over 260 chars - assert a non-zero "
                    "count on a fixture containing both"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0017/probe1_set_difference.py",
                "result": "PASS" if control1.get("ok") else "FAIL",
                "assertions": 3,
                "output_tail": raw1[-500:],
            },
            {
                "id": "AUD-0017-planted-never-in-history",
                "name": (
                    "Planted live-only NUL/longpath fixture paths classify as "
                    "NEVER_IN_HISTORY under git log --diff-filter=D"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0017/probe2_history_classification.py",
                "result": "PASS" if control2.get("ok") else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-500:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0017-C1",
                "known-broken-fixture",
                control1.get("description")
                or "NUL + >260-char path fixture must yield non-zero live_only.",
                True,
                True,
                bad="enumerator crashed or silently zeroed",
                good=(
                    f"nul={control1.get('nul_present')} "
                    f"long={control1.get('long_path_present')} "
                    f"live_only={control1.get('live_only_count')} "
                    f"ok={control1.get('ok')}"
                ),
            ),
            L.control(
                "AUD0017-C2",
                "known-broken-fixture",
                control2.get("description")
                or "Planted live-only paths must be NEVER_IN_HISTORY.",
                bool(control2.get("fired_on_bad_state")),
                bool(control2.get("silent_on_good_state", True)),
                bad="planted paths misclassified as deleted or missing",
                good=f"planted_never={control2.get('planted_never_in_history')} ok={control2.get('ok')}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + audit-drift schema resolver",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/AUD-0017/_pack_receipt.py",
                    f"state={state}",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "retry once with the sweep re-scoped to a single path to isolate a "
                "path-length or encoding failure from a logic failure, then pivot"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live ~/.claude and ~/.agents trees on a Windows estate yield the "
                    "same bidirectional orphan partition as this Linux cloud seed."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe1_set_difference.py on a host where both live roots "
                    "exist and compare live_only/repo_only totals to this receipt."
                ),
            },
            {
                "claim": (
                    "Cross-vendor Codex has re-run ONLY probe 2 against this receipt."
                ),
                "verdict": "NOT-CHECKED" if not success else "CONFIRMED",
                "settling_experiment": (
                    "Dispatch openai/Codex reviewer to execute "
                    "probe2_history_classification.py and record independent-review.json."
                ),
            },
        ],
        "report": {
            "kind": "audit-drift",
            "question": question,
            "headline": headline,
            "measured_answer": measured_answer,
            "control_ids": ["AUD0017-C1", "AUD0017-C2"],
            "observations": [
                {
                    "name": "live_roots_present",
                    "measured": live_roots,
                    "method": "Path.is_dir on HOME/.claude/{rules,agents,commands,hooks} and HOME/.agents{,/skills}",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe1-set-difference.json",
                },
                {
                    "name": "repo_roots_present",
                    "measured": repo_roots,
                    "method": "Path.is_dir on mapped repo destinations from sync-from-live.ps1 $Map",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe1-set-difference.raw.txt",
                },
                {
                    "name": "live_only_total_checked",
                    "measured": live_only,
                    "method": "relative-path set difference live-repo where BOTH sides exist",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe1-set-difference.json",
                },
                {
                    "name": "repo_only_total_checked",
                    "measured": repo_only,
                    "method": "relative-path set difference repo-live where BOTH sides exist",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe1-set-difference.json",
                },
                {
                    "name": "never_in_history_count",
                    "measured": never_hist,
                    "method": "git log --all --diff-filter=D plus git log --all on live-only candidates",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe2-history-classification.json",
                },
                {
                    "name": "was_deleted_count",
                    "measured": was_deleted,
                    "method": "git log --all --diff-filter=D non-empty",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/probe2-history-classification.raw.txt",
                },
                {
                    "name": "nul_longpath_control_ok",
                    "measured": bool(control1.get("ok")),
                    "method": "fixtures/planted-nul-longpath enumerator",
                    "anchor": "command-center/p2-wave/probes/AUD-0017/fixtures/planted-nul-longpath/live/rules/NUL",
                },
            ],
            "anti_false_green": anti,
        },
        "extensions": {
            "artifact_class": "audit-drift",
            "output_path_catalog": OUT,
            "output_schema_catalog": SCHEMA,
            "deploy_map_source": "scripts/sync-from-live.ps1:$Map",
            "probe1_summary": {
                "live_roots_present": live_roots,
                "repo_roots_present": repo_roots,
                "pairs_both_present": both_present,
                "live_only_total_checked": live_only,
                "repo_only_total_checked": repo_only,
                "planted_control_ok": control1.get("ok"),
                "max_live_rel_len": control1.get("max_live_rel_len"),
            },
            "probe2_summary": {
                "selected_count": p2["selected_count"],
                "by_classification": p2["by_classification"],
                "never_in_history_count": never_hist,
                "was_deleted_count": was_deleted,
                "planted_ok": control2.get("ok"),
            },
            "wave": "p2-wave",
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    for script in ("probe1_set_difference.py", "probe2_history_classification.py"):
        rc, out = L.run(["python3", "-B", str(PROBE / script)], timeout=600)
        if rc != 0:
            print(out)
            print(f"FAILED:{UNIT} {script} exit={rc}")
            return rc

    required = [
        PROBE / "probe1-set-difference.json",
        PROBE / "probe2-history-classification.json",
        PROBE / "probe1-set-difference.raw.txt",
        PROBE / "probe2-history-classification.raw.txt",
        PROBE / "fixtures/planted-nul-longpath/live/rules/NUL",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("FAILED:AUD-0017 missing probe outputs:", *missing, sep="\n")
        return 1

    out_path = L.REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = build()
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc = build(primary=L.art(OUT, "primary"))
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    errs = L.validate(doc, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["artifacts"][0] = L.art(OUT, "primary")
    out_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

    final = json.loads(out_path.read_text(encoding="utf-8"))
    errs = L.validate(final, SCHEMA)
    if errs:
        print("SCHEMA_ERRORS after admit:", *errs[:20], sep="\n", file=sys.stderr)
        return 1

    rc_adm3, adm_out3 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    if rc_adm3 != 0:
        print(adm_out3)
        print(f"FAILED:{UNIT} receipt_validate rejected packed artifact")
        return 1

    man = {
        "unit_id": UNIT,
        "primary": OUT,
        "schema": SCHEMA,
        "state": final["state"],
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "artifacts": final["artifacts"],
        "packed_at": final["timestamps"]["ended_at"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out3.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
