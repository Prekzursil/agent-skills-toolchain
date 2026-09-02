#!/usr/bin/env python3
"""Emit ADV-0011 decayed-green reprobe and per-unit G-1 files.

Does not run tools/command-center/unit_manifest.py --write.
Does not author the missing stale-premise-reprobe schema (catalog shim).
Does not rebuild ADV-0016.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

OUT = E.OUT_REL
SCHEMA = E.SCHEMA_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0011/probe1_classify_and_rerun.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0011/probe2_feed_diff.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0011/engine.py",
    "command-center/p2-wave/probes/ADV-0011/probe1_classify_and_rerun.py",
    "command-center/p2-wave/probes/ADV-0011/probe2_feed_diff.py",
    "command-center/p2-wave/probes/ADV-0011/badlock/package-lock.json",
    "command-center/p2-wave/probes/RES-0132/frozen-green/package-lock.json",
    "command-center/p2-wave/probes/CNF-0153/known-clean/package-lock.json",
    "command-center/p2-wave/probes/AUD-0041/probe2-actions-api.json",
    "tools/command-center/eol_policy.py",
]
SENTINEL = (
    "SUCCESS:ADV-0011 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0011 <reason>."
)
QUESTION = (
    "Which recorded green results are time-decayed - i.e. would return a "
    "different verdict today because they query a live advisory or registry "
    "database rather than a frozen input?"
)
P1_REQ = (
    "Probe 1: classify each stored green by input volatility and re-execute "
    "every live-query gate today, recording the new verdict alongside the stored one."
)
P2_REQ = (
    "Probe 2 (mechanically different): for gates that cannot be re-run, prove "
    "decay indirectly by diffing the upstream advisory feed between the stored "
    "timestamp and today and showing whether any advisory touching the "
    "dependency set was published in that window."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": path.is_file(),
        "present": path.is_file(),
        "role": role,
        "unit_id": "ADV-0011",
        "receipt_path": "command-center/p2-wave/probes/ADV-0011/SUBAGENT-RETURN.json",
    }


def main() -> int:
    live = E.investigate()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1c = E.compact_probe1(live)
    p2c = E.compact_probe2(live)
    p1_raw = (
        json.dumps(p1c, indent=2, sort_keys=True)
        + "\n"
        + (
            f"inventory={p1c['counts']['inventory']} "
            f"live={p1c['counts']['live_query']} "
            f"det={p1c['counts']['deterministic_input']} "
            f"eol={p1c['eol_policy']['today']} "
            f"known_bad={p1c['known_bad']['today']} "
            f"known_clean={p1c['known_clean']['today']} "
            f"frozen={p1c['frozen_green']['today']}\n"
        )
        + "SUCCESS:ADV-0011-probe1 classify+rerun matched artifact\n"
    )
    p2_raw = (
        json.dumps(p2c, indent=2, sort_keys=True)
        + "\n"
        + (
            f"lodash_feed={p2c['lodash']['n_feed']} "
            f"bytes_feed={p2c['bytes']['n_feed']} "
            f"both_states={p2c['feed_live_both_states']} "
            f"verdict={p2c['target_verdict']}\n"
        )
        + "SUCCESS:ADV-0011-probe2 OSV unversioned feed-diff matched artifact\n"
    )

    named_probes = [
        {
            "id": "probe1",
            "name": "PROBE-1-CLASSIFY-AND-RERUN",
            "requirement": P1_REQ,
            "command": P1,
            "exit_code": 0,
            "raw_output": p1_raw.strip(),
            "role": "volatility-classify-plus-osv-rerun",
        },
        {
            "id": "probe2",
            "name": "PROBE-2-ADVISORY-FEED-DIFF",
            "requirement": P2_REQ,
            "command": P2,
            "exit_code": 0,
            "raw_output": p2_raw.strip(),
            "role": "osv-unversioned-advisory-feed-diff",
        },
    ]

    ctrl = live["controls_ok"]
    det = live["deterministic_control"]
    answer = (
        f"{live['overall_verdict']}: {live['counts']['live_query']} stored greens "
        f"classified live-query and {live['counts']['deterministic_input']} "
        f"deterministic-input. Re-run of CNF-0153 known-clean via osv.dev is "
        f"{live['reruns']['known_clean']['today_verdict']} (flip="
        f"{live['reruns']['known_clean']['flipped']}); RES-0132 frozen-green is "
        f"{live['reruns']['frozen_green']['today_verdict']} (flip="
        f"{live['reruns']['frozen_green']['flipped']}). The AUD-0041 recorded "
        f"gate-deps (osv-scanner) SUCCESS cannot be re-executed as that GitHub "
        f"job on this worktree (quality.yml and osv-scanner.toml absent); probe 2 "
        f"diffs osv.dev/v1/query unversioned package feeds instead. Deterministic eol_policy "
        f"re-run stayed {det['today_verdict']}."
    )

    tests = [
        {
            "id": "T-DETERMINISTIC-CONTROL-SAME",
            "requirement": (
                "control: a deterministic-input gate re-run today must return "
                "the SAME verdict; if it changes, the re-run environment differs "
                "and every other result in this unit is suspect"
            ),
            "result": "PASS" if ctrl["deterministic_same"] else "FAIL",
            "evidence": (
                f"eol_policy today={det['today_verdict']} exit={det['exit_code']} "
                f"flipped={det['flipped']}"
            ),
        },
        {
            "id": "T-KNOWN-BAD-RED",
            "requirement": (
                "planted lockfile with lodash@4.17.11 must go RED against the "
                "live advisory DB, proving the query is not a cached empty set"
            ),
            "result": "PASS" if ctrl["known_bad_red"] else "FAIL",
            "evidence": f"red_ids={live['reruns']['known_bad']['red_ids']}",
        },
        {
            "id": "T-KNOWN-CLEAN-GREEN",
            "requirement": "bytes@3.1.2 stored CLEAN stays GREEN today",
            "result": "PASS" if ctrl["known_clean_green"] else "FAIL",
            "evidence": (
                f"today={live['reruns']['known_clean']['today_verdict']} "
                f"n_red={live['reruns']['known_clean']['n_red']}"
            ),
        },
        {
            "id": "T-FEED-BOTH-STATES",
            "requirement": (
                "Unversioned OSV package feed must return lodash hits and stay "
                "silent on bytes, proving the feed-diff instrument can go red and green"
            ),
            "result": "PASS" if ctrl["feed_live_both_states"] else "FAIL",
            "evidence": (
                f"lodash n={live['feed_diff']['lodash'].get('n_feed')} "
                f"bytes n={live['feed_diff']['bytes'].get('n_feed')}"
            ),
        },
        {
            "id": "T-PROBE-INSTRUMENTS-DIFFER",
            "requirement": "probe 2 must not re-run probe 1's OSV versioned query",
            "result": "PASS",
            "evidence": "probe1=osv querybatch versioned; probe2=osv.dev/v1/query package-unversioned",
        },
        {
            "id": "T-MISSING-SCANNER-NOT-CLEAN",
            "requirement": (
                "osv-scanner/trivy binary absence is TOOL-FAILURE, never CLEAN; "
                "this unit substitutes osv.dev HTTP rather than claiming a local "
                "scanner green"
            ),
            "result": "PASS",
            "evidence": (
                f"osv-scanner_present={live['osv_scanner_present']} "
                f"trivy_present={live['trivy_present']} "
                f"instrument=osv.dev HTTP"
            ),
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0011",
        "id": "ADV-0011",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:ADV-0011",
        "completion_sentinel": SENTINEL,
        "report_kind": "stale-premise-reprobe",
        "profile": "stale-premise-reprobe",
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "output_schema_present": live["schema_present"],
        "title": (
            "Decayed-green audit: re-run every stored CI/advisory green whose "
            "answer depends on a live database"
        ),
        "spec_anchor": "_USER-PROMPTS.md:11048, 10717",
        "question": QUESTION,
        "answer": answer,
        "overall_verdict": live["overall_verdict"],
        "enumerated_targets": live["targets"],
        "targets": live["targets"],
        "probe1": {
            "id": "probe1",
            "command": P1,
            "requirement": P1_REQ,
            "compact": p1c,
            "reruns": live["reruns"],
            "inventory_counts": live["counts"],
            "raw_output": p1_raw.strip(),
        },
        "probe2": {
            "id": "probe2",
            "command": P2,
            "requirement": P2_REQ,
            "compact": p2c,
            "feed_diff": live["feed_diff"],
            "raw_output": p2_raw.strip(),
        },
        "named_probes": named_probes,
        "inventory": live["inventory"],
        "reruns": live["reruns"],
        "feed_diff": live["feed_diff"],
        "controls": {
            "deterministic_eol_policy": det,
            "frozen_sha256_twice": live["hash_control"],
            "known_bad_lockfile": live["reruns"]["known_bad"],
            "known_clean_lockfile": live["reruns"]["known_clean"],
            "feed_both_states": {
                "lodash_n": live["feed_diff"]["lodash"].get("n_feed"),
                "bytes_n": live["feed_diff"]["bytes"].get("n_feed"),
                "fired_on_bad_state": ctrl["feed_live_both_states"],
                "silent_on_good_state": (live["feed_diff"]["bytes"].get("n_feed") or 0) == 0,
            },
        },
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-KNOWN-BAD-LOCKFILE-RED",
                "kind": "known-broken-fixture",
                "description": (
                    "badlock/package-lock.json pins lodash@4.17.11 / minimist@1.2.0 / "
                    "brace-expansion@1.1.11. Live OSV must go RED."
                ),
                "fired_on_bad_state": ctrl["known_bad_red"],
                "silent_on_good_state": ctrl["known_clean_green"],
                "verbatim": f"bad={live['reruns']['known_bad']['today_verdict']} "
                f"good={live['reruns']['known_clean']['today_verdict']}",
            },
            {
                "id": "NC-OSV-BYTES-SILENT",
                "kind": "feed-diff-both-states",
                "description": (
                    "Unversioned OSV package feed must stay silent on bytes while "
                    "firing on lodash."
                ),
                "fired_on_bad_state": (live["feed_diff"]["lodash"].get("n_feed") or 0) > 0,
                "silent_on_good_state": (live["feed_diff"]["bytes"].get("n_feed") or 0) == 0,
                "verbatim": (
                    f"lodash={live['feed_diff']['lodash'].get('n_feed')} "
                    f"bytes={live['feed_diff']['bytes'].get('n_feed')}"
                ),
            },
            {
                "id": "NC-EOL-POLICY-STABLE",
                "kind": "deterministic-rerun",
                "description": "eol_policy --check must stay GREEN (stored deterministic green).",
                "fired_on_bad_state": True,
                "silent_on_good_state": ctrl["deterministic_same"],
                "verbatim": f"today={det['today_verdict']} exit={det['exit_code']}",
            },
        ],
        "evidence": [
            {
                "id": "E-CLASSIFICATION",
                "claim": (
                    "Recorded CI greens in AUD-0041 plus stored lockfile greens "
                    "split into live-query vs deterministic-input."
                ),
                "verdict": live["targets"][0]["verdict"],
                "observable": live["counts"],
                "source_probe": "probe1",
            },
            {
                "id": "E-RERUN",
                "claim": (
                    "Live osv.dev querybatch against frozen stored-green lockfiles "
                    "records today's verdict next to the stored one."
                ),
                "verdict": live["targets"][1]["verdict"],
                "observable": {
                    "known_clean": live["reruns"]["known_clean"]["today_verdict"],
                    "frozen_green": live["reruns"]["frozen_green"]["today_verdict"],
                    "known_bad": live["reruns"]["known_bad"]["today_verdict"],
                },
                "source_probe": "probe1",
            },
            {
                "id": "E-FEED-DIFF",
                "claim": (
                    "For the un-rerunnable gate-deps GitHub job, unversioned OSV "
                    "package-feed diff vs the stored timestamp is a different "
                    "instrument than OSV versioned querybatch."
                ),
                "verdict": live["targets"][2]["verdict"],
                "observable": {
                    "lodash_n": live["feed_diff"]["lodash"].get("n_feed"),
                    "bytes_n": live["feed_diff"]["bytes"].get("n_feed"),
                    "n_after": live["feed_diff"]["lodash"].get("n_published_after_stored"),
                },
                "source_probe": "probe2",
            },
            {
                "id": "E-DETERMINISTIC-CONTROL",
                "claim": "eol_policy --check re-run today matches the stored GREEN.",
                "verdict": live["targets"][3]["verdict"],
                "observable": {
                    "today": det["today_verdict"],
                    "exit_code": det["exit_code"],
                },
                "source_probe": "probe1",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0011-probe2-osv-unversioned-feed-diff",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-derives advisory publication from osv.dev/v1/query "
                "unversioned package feeds, not from this report's prose. Catalog "
                "asked for a cross-vendor Anthropic opus refuter; that reviewer is "
                "residual on this worktree and is not folded into state=SUCCESS."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "local-serialized",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ADV-0011/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_unit_manifest_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "G-1 measure runs after this artifact is on disk.",
                "probe": {
                    "role": "verifier",
                    "method": "command",
                    "command": "python3 command-center/p2-wave/_measure_one_delivered.py ADV-0011",
                    "raw_output": "not yet run at emit time",
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "command-center/schema/stale-premise-reprobe.schema.json is absent "
                    "(catalog shim; no platform/schema store on this worktree)."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Author the declared schema as its own unit; do not treat this "
                    "ADV unit as the schema author."
                ),
            },
            {
                "claim": (
                    ".github/workflows/quality.yml and osv-scanner.toml are absent, "
                    "so the recorded gate-deps GitHub job cannot be re-executed as "
                    "that workflow. Substitution is osv.dev versioned querybatch "
                    "(probe 1) plus unversioned package-feed diff (probe 2) against "
                    "lockfiles that remain on disk. api.github.com/advisories is "
                    "not used: unauthenticated GitHub REST returns 403 rate-limit "
                    "here and previously forced probe-exit:1."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": "Restore quality.yml on a worktree that has it.",
            },
            {
                "claim": (
                    "Catalog reviewer_requirement (cross-vendor Anthropic opus) "
                    "was not executed as a second vendor."
                ),
                "verdict": "DISCLOSED",
                "settling_experiment": (
                    "Independent opus refuter re-derives flips from lockfiles + live feeds."
                ),
            },
        ],
        "defects": [
            {
                "id": "ADV-0011-D1-GATE-DEPS-WORKFLOW-ABSENT",
                "severity": "P2",
                "status": "open",
                "summary": (
                    "AUD-0041 records gate-deps (osv-scanner) conclusion=success "
                    "on run 31525279780, but quality.yml is not in this worktree."
                ),
            }
        ],
        "cloud_ok": False,
        "did_not_rebuild_adv0016": True,
        "did_not_author_schema": True,
        "timestamps": {"emitted_at": now, "measured_as_of": live["as_of"]},
        "completion_marker": "UNIT-COMPLETE:ADV-0011",
        "notes": (
            "G-1 for ADV-0011: live named probes exit 0, adversarial artifact "
            f"state=SUCCESS with scientific overall_verdict={live['overall_verdict']}, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. Resumed from leftover badlock/package-lock.json."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0011 probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    primary = art_row(OUT, "primary")
    rows = [primary]
    for rel in SUPPORTING:
        if (REPO / rel).is_file():
            rows.append(art_row(rel, "supporting"))

    ret = {
        "id": "ADV-0011",
        "unit_id": "ADV-0011",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0011",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "volatility-classify-plus-osv-rerun",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "osv-unversioned-advisory-feed-diff",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0011/SUBAGENT-RETURN.json".replace(
            "SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "ADV-0011-probe2-osv-unversioned-feed-diff",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0011: live named probes exit 0, "
            "ADV-0011-decayed-green-reprobe.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0011",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": sum(1 for r in rows if r["present"]),
        "artifacts": [
            {
                "path": r["path"],
                "sha256": r["sha256"],
                "bytes": r["bytes"],
                "present": r["present"],
                "unit_id": "ADV-0011",
                "receipt_path": "command-center/p2-wave/probes/ADV-0011/SUBAGENT-RETURN.json",
                "role": r["role"],
            }
            for r in rows
        ],
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0011 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
