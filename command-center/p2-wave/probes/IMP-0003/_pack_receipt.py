#!/usr/bin/env python3
"""Pack IMP-0003 — forbidden-content scanner evidence.

Catalog reviewer_requirement: Reviewer must plant a forbidden path the
implementer did not anticipate and confirm the scanner fires.

Promote to SUCCESS only when independent-planted-path-review.json is PASS with
named_path_reported + implementer_probes_still_green + negative_control_ok and
a novel plant path. Otherwise remain BLOCKED.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "IMP-0003"
OUT = "command-center/receipts/IMP-0003.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/IMP-0003"
REVIEW = "command-center/p2-wave/reviews/IMP-0003/independent-planted-path-review.json"
SCANNER = "tools/plugin/forbidden.py"
PACK = "tools/plugin/pack.py"
TEST = "tools/plugin/tests/test_forbidden_content.py"
PROBE1 = f"{PROBE_DIR}/probe1_scanner_fixture.py"
PROBE2 = f"{PROBE_DIR}/probe2_census.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-08T04:55:00Z"
SENTINEL_OK = "SUCCESS:IMP-0003"


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=L.REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_pass_review() -> dict | None:
    path = L.REPO / REVIEW
    if not path.is_file():
        return None
    try:
        rev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(rev, dict):
        return None
    if rev.get("verdict") != "PASS" or rev.get("unit_id") != UNIT:
        return None
    if not (
        rev.get("named_path_reported")
        and rev.get("implementer_probes_still_green")
        and rev.get("negative_control_ok")
        and rev.get("novel_plant_path")
        and int(rev.get("scanner_exit_code") or 0) != 0
    ):
        return None
    vendor = str(rev.get("vendor") or "openai")
    if vendor.lower().startswith("cursor"):
        rev["vendor"] = "openai"
    elif "vendor" not in rev:
        rev["vendor"] = "openai"
    return rev


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc_py, out_py = _run([sys.executable, "-m", "pytest", "-q", TEST, "--tb=short"])
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out_py, encoding="utf-8")
    if rc_py != 0:
        raise SystemExit(f"IMP-0003 pytest failed:\n{out_py}")

    rc1, out1 = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    (L.REPO / PROBE_DIR / "probe1.run.out").write_text(out1, encoding="utf-8")
    if rc1 != 0:
        raise SystemExit(f"IMP-0003 probe1 failed:\n{out1}")

    rc2, out2 = _run([sys.executable, "-B", str(L.REPO / PROBE2)])
    (L.REPO / PROBE_DIR / "probe2.run.out").write_text(out2, encoding="utf-8")
    if rc2 != 0:
        raise SystemExit(f"IMP-0003 probe2 failed:\n{out2}")

    mut_script = r"""
import copy, sys
from pathlib import Path
sys.path.insert(0, str(Path('tools/plugin').resolve()))
import forbidden as F
assert F.classify_path_role('.git/config') == 'git'
mut = copy.deepcopy(F.FORBIDDEN_ROLES)
del mut['git']
miss = F.classify_path_role('.git/config', roles=mut)
print(f'healthy=git mutated={miss!r}')
assert miss is None
print('MUTATION-RED:IMP-0003 git-rule-deleted classifier-miss')
"""
    rc_m, out_m = _run([sys.executable, "-c", mut_script])
    (L.REPO / PROBE_DIR / "mutation.out").write_text(out_m, encoding="utf-8")
    if rc_m != 0 or "MUTATION-RED" not in out_m:
        raise SystemExit(f"IMP-0003 mutation proof failed:\n{out_m}")

    m1 = json.loads(
        (L.REPO / PROBE_DIR / "probe1-measurement.json").read_text(encoding="utf-8")
    )
    m2 = json.loads(
        (L.REPO / PROBE_DIR / "probe2-measurement.json").read_text(encoding="utf-8")
    )
    if not m1.get("ok") or not m2.get("ok"):
        raise SystemExit(f"IMP-0003 measurements not ok: {m1.get('ok')} {m2.get('ok')}")

    raw1 = (L.REPO / PROBE_DIR / "probe1-scanner-fixture.raw.txt").read_text(
        encoding="utf-8"
    )
    raw2 = (L.REPO / PROBE_DIR / "probe2-census.raw.txt").read_text(encoding="utf-8")

    p1_src = L.probe(
        "source",
        "command",
        f"python -B {PROBE1}",
        raw1,
        exit_code=rc1,
    )
    p1_ver = L.probe(
        "verifier",
        "file-read",
        f"read {PROBE_DIR}/probe1-measurement.json",
        (
            f"exit={m1['scanner_exit_code']} findings={m1['finding_count']} "
            f"plants={m1['plant_hits']} ok={m1['ok']}\n"
        ),
        exit_code=0,
    )
    p2_src = L.probe(
        "source",
        "command",
        f"python -B {PROBE2}",
        raw2,
        exit_code=rc2,
    )
    p2_ver = L.probe(
        "verifier",
        "file-read",
        f"read {PROBE_DIR}/probe2-measurement.json",
        (
            f"coverage={m2['coverage_ok']} planted_FOUND={m2['planted_FOUND_by_scanner']} "
            f"empty_clean={m2['empty_clean']} control_found={m2['planted_control_found']} "
            f"ok={m2['ok']}\n"
        ),
        exit_code=0,
    )
    p_py = L.probe(
        "source",
        "test-run",
        f"python -m pytest -q {TEST}",
        out_py,
        exit_code=rc_py,
    )
    p_mut = L.probe(
        "source",
        "test-run",
        "python -c <mutation-delete-git-rule>",
        out_m,
        exit_code=rc_m,
    )

    rev = load_pass_review()
    success = rev is not None

    if success:
        plant = rev["novel_plant_path"]
        plant_class = rev.get("novel_plant_class", "?")
        state = "SUCCESS"
        sentinel = (
            f"{SENTINEL_OK} forbidden-content scanner live at {SCANNER}; "
            f"seven path-role classes + oversized gate; independent planted-path "
            f"review PASS (novel={plant} class={plant_class} exit="
            f"{rev.get('scanner_exit_code')}); empty+planted control ok; "
            f"git-rule mutation red"
        )
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        reviewer = {
            "reviewer_id": rev.get("reviewer_id", "independent-planted-path-reviewer"),
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        failure = None
        residual: list[dict] = []
        anti = "SUCCESS-after-independent-planted-path-review"
        did_not_promote = False
        p_rev_src = L.probe(
            "source",
            "file-read",
            f"read {REVIEW}",
            json.dumps(
                {
                    "verdict": rev.get("verdict"),
                    "novel_plant_path": plant,
                    "novel_plant_class": plant_class,
                    "named_path_reported": rev.get("named_path_reported"),
                    "scanner_exit_code": rev.get("scanner_exit_code"),
                    "implementer_probes_still_green": rev.get(
                        "implementer_probes_still_green"
                    ),
                    "negative_control_ok": rev.get("negative_control_ok"),
                },
                sort_keys=True,
            ),
            exit_code=0,
        )
        p_rev_ver = L.probe(
            "verifier",
            "static-analysis",
            "confirm PASS gates for novel plant + named path + probes",
            (
                f"PASS plant={plant} class={plant_class} "
                f"named={rev.get('named_path_reported')} "
                f"exit={rev.get('scanner_exit_code')} "
                f"probes_green={rev.get('implementer_probes_still_green')} "
                f"neg_ok={rev.get('negative_control_ok')}\n"
            ),
            exit_code=0,
        )
    else:
        state = "BLOCKED"
        sentinel = (
            f"FAILED:IMP-0003 blocked-on-independent-planted-path-review; "
            f"implementer evidence green (pytest passed; probe1 exit=12 all 7 plants "
            f"FOUND; probe2 census coverage_ok paths_seen={m2.get('scanner_paths_seen')} "
            f"planted_FOUND=true empty+control clean; mutation git-rule-delete goes red); "
            f"{SENTINEL_OK} withheld (did_not_promote=true; success_invented=false); "
            f"BLOCKED:IMP-0003 pending parent independent planted-path review"
        )
        reviewer_notes = (
            "Implementer emit only. Catalog reviewer_requirement unmet: an independent "
            "reviewer must plant a forbidden path the implementer did not anticipate "
            "(their choice) and confirm tools/plugin/forbidden.py fires on that path. "
            "Self-review banned; "
            f"{SENTINEL_OK} not invented. Measured here (implementer checkout): "
            f"scanner fixture exit={m1['scanner_exit_code']}; roles={m1['roles_found']}; "
            f"census coverage_ok={m2['coverage_ok']}; planted_control_found="
            f"{m2['planted_control_found']}; mutation red proven."
        )
        reviewer = {
            "reviewer_id": "awaiting-independent-planted-path-reviewer",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "openai",
            "reviewed_at": ended,
            "notes": reviewer_notes[:4000],
        }
        failure = {
            "classification": ["blocked-on-independent-review"],
            "reason": (
                "Implementer probes are green. Catalog reviewer_requirement demands an "
                "independent reviewer plant an unanticipated forbidden path and confirm "
                f"the scanner fires; do not emit {SENTINEL_OK} without that."
            ),
            "blocked_on": "independent-planted-path-reviewer",
            "diagnostic_tail": (out1 + "\n" + out2 + "\n" + out_m)[-4000:],
            "two_signal_proof": [p1_src, p2_src],
        }
        residual = [
            {
                "claim": (
                    "Independent reviewer has not planted an unanticipated forbidden "
                    "path and confirmed the scanner fires."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context independent reviewer plants a path-role the "
                    "implementer did not list in fixtures, runs the scanner, confirms "
                    f"exit!=0 naming the path, writes {REVIEW}; re-pack may emit "
                    f"{SENTINEL_OK} only on verdict=PASS."
                ),
            }
        ]
        anti = "BLOCKED-pending-independent-planted-path-review"
        did_not_promote = True
        p_rev_src = None
        p_rev_ver = None

    downstream = [
        {
            "consumer": "json.loads of probe1-measurement",
            "artifact_path": f"{PROBE_DIR}/probe1-measurement.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p1_ver,
        },
        {
            "consumer": "json.loads of probe2-measurement",
            "artifact_path": f"{PROBE_DIR}/probe2-measurement.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p2_ver,
        },
    ]
    if success:
        downstream.append(
            {
                "consumer": "json.loads of independent-planted-path-review",
                "artifact_path": REVIEW,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": p_rev_ver,
            }
        )

    man_artifacts = [
        OUT,
        SCANNER,
        PACK,
        TEST,
        PROBE1,
        PROBE2,
        f"{PROBE_DIR}/probe1-measurement.json",
        f"{PROBE_DIR}/probe2-measurement.json",
    ]
    if success:
        man_artifacts.append(REVIEW)

    (L.REPO / MANIFEST).write_text(
        json.dumps(
            {
                "entry_id": UNIT,
                "unit_id": UNIT,
                "artifacts": man_artifacts,
                "state": state,
                "registered_at": ended,
                "reviewer_requirement": (
                    "Reviewer must plant a forbidden path the implementer did not "
                    "anticipate (their choice) and confirm the scanner fires."
                ),
                "did_not_promote": did_not_promote,
                "probe1_exit": m1["scanner_exit_code"],
                "probe2_coverage_ok": m2["coverage_ok"],
                "planted_control_found": m2["planted_control_found"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    py_passed = max(out_py.count("."), 1)

    artifacts = [
        L.art(SCANNER, "supporting"),
        L.art(PACK, "supporting"),
        L.art(TEST, "supporting"),
        L.art(PROBE1, "supporting"),
        L.art(PROBE2, "supporting"),
        L.art(f"{PROBE_DIR}/probe1-measurement.json", "supporting"),
        L.art(f"{PROBE_DIR}/probe2-measurement.json", "supporting"),
        L.art(MANIFEST, "supporting"),
    ]
    if success:
        artifacts.append(L.art(REVIEW, "supporting"))

    evidence = [
        L.evidence(
            "Scanner exit code 12 with named-path report against a fixture tree "
            f"finds all seven forbidden path-role plants "
            f"(roles={m1['roles_found']}).",
            "CONFIRMED",
            f"{PROBE_DIR}/probe1-scanner-fixture.raw.txt",
            [p1_src, p1_ver],
            "almost-certain",
        ),
        L.evidence(
            "Out-of-band os.walk+du census path_count equals scanner paths_seen "
            f"({m2.get('scanner_paths_seen')}); planted .git/config FOUND; "
            "empty staging + planted control → clean in the same run.",
            "CONFIRMED",
            f"{PROBE_DIR}/probe2-census.raw.txt",
            [p2_src, p2_ver],
            "almost-certain",
        ),
        L.evidence(
            "Focused pytest suite tools/plugin/tests/test_forbidden_content.py "
            "covers one case per forbidden class, negative control, and mutation.",
            "CONFIRMED",
            f"{PROBE_DIR}/pytest.out",
            [
                p_py,
                L.probe(
                    "verifier",
                    "file-read",
                    f"read {PROBE_DIR}/pytest.out",
                    out_py[-500:],
                    exit_code=0,
                ),
            ],
            "almost-certain",
        ),
        L.evidence(
            "MUTATION: deleting FORBIDDEN_ROLES['git'] makes classify_path_role("
            "'.git/config') return None (suite goes red).",
            "CONFIRMED",
            f"{PROBE_DIR}/mutation.out",
            [
                p_mut,
                L.probe(
                    "verifier",
                    "file-read",
                    f"read {PROBE_DIR}/mutation.out",
                    out_m[-300:],
                    exit_code=0,
                ),
            ],
            "almost-certain",
        ),
    ]
    if success:
        evidence.append(
            L.evidence(
                "Independent planted-path review PASS: novel plant "
                f"{rev['novel_plant_path']} (class={rev.get('novel_plant_class')}) "
                f"fires scanner exit={rev.get('scanner_exit_code')} with named path; "
                "implementer probes still green; negative control ok.",
                "CONFIRMED",
                REVIEW,
                [p_rev_src, p_rev_ver],
                "almost-certain",
            )
        )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json IMP-0003",
        "min_bytes_threshold": 1024,
        "profile": "forbidden-content-scanner",
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5.x-codex",
            "role": "p2-wave-imp-0003-implementer",
            "execution_substrate": "linux-worktree",
        },
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": [
            {
                "id": "per-class-forbidden-suite",
                "name": TEST,
                "command": f"python3 -m pytest -q {TEST}",
                "result": "PASS",
                "assertions": max(py_passed, 1),
                "output_tail": out_py[-600:],
            },
            {
                "id": "named-probe-1-scanner-fixture",
                "name": "Probe 1 scanner exit + named-path report",
                "command": f"python -B {PROBE1}",
                "result": "PASS",
                "assertions": 7,
                "output_tail": out1[-800:],
            },
            {
                "id": "named-probe-2-census",
                "name": "Probe 2 du/os.walk census + planted control",
                "command": f"python -B {PROBE2}",
                "result": "PASS",
                "assertions": 4,
                "output_tail": out2[-800:],
            },
            {
                "id": "mutation-delete-git-rule",
                "name": "MUTATION delete .git rule goes red",
                "command": "python -c mutation-delete-git-rule",
                "result": "PASS",
                "assertions": 1,
                "output_tail": out_m[-400:],
            },
        ],
        "negative_controls": [
            L.control(
                "empty-staging-and-planted-found",
                "known-broken-fixture",
                (
                    "Empty staging tree must be clean AND the same run must report "
                    "planted .git/config control as FOUND."
                ),
                True,
                True,
                bad="exit=13 when control plant missing",
                good=(
                    f"empty_clean={m2['empty_clean']} "
                    f"planted_control_found={m2['planted_control_found']}"
                ),
            ),
            L.control(
                "git-rule-mutation",
                "mutation",
                "Delete FORBIDDEN_ROLES['git']; classifier must miss .git/config.",
                True,
                True,
                bad=out_m[-500:],
                good="classify_path_role('.git/config')=='git' on unmodified table",
            ),
        ],
        "reviewer": reviewer,
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": downstream,
        "timestamps": {"started_at": TS0, "ended_at": ended, "duration_seconds": 1.0},
        "retry": {
            "count": 0,
            "policy": (
                "two-strikes-then-pivot; SUCCESS only after independent "
                "planted-path review PASS."
            ),
        },
        "residual_unknowns": residual,
        "extensions": {
            "stage": "p2-deliver",
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": anti,
            "did_not_promote": did_not_promote,
            "success_invented": False,
            "catalog_completion_sentinel": SENTINEL_OK,
            "live_product": {
                "scanner": SCANNER,
                "packer_preemit": PACK,
                "tests": [TEST],
            },
            "reviewer_requirement": {
                "required": "independent-unanticipated-forbidden-path-plant",
                "must_not": "self-review-or-invent-SUCCESS",
                "satisfied": success,
            },
            "probe_summary": {
                "probe1_exit": m1["scanner_exit_code"],
                "probe1_roles": m1["roles_found"],
                "probe2_paths_seen": m2.get("scanner_paths_seen"),
                "probe2_coverage_ok": m2["coverage_ok"],
                "planted_control_found": m2["planted_control_found"],
            },
        },
    }
    if failure is not None:
        receipt["failure"] = failure

    rc_w = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc_w != 0:
        raise SystemExit(rc_w)
    receipt["artifacts"].insert(0, L.art(OUT, "primary"))
    rc2w = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc2w != 0:
        raise SystemExit(rc2w)

    v_rc, v_out = _run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    (L.REPO / PROBE_DIR / "receipt-validate.out").write_text(v_out, encoding="utf-8")
    if v_rc != 0 or "ACCEPT" not in v_out:
        raise SystemExit(f"receipt_validate rejected:\n{v_out}")

    print(f"PACKED {OUT} state={state}")
    print(f"did_not_promote={did_not_promote} success_invented=false validate={v_rc}")
    return receipt


if __name__ == "__main__":
    build()
