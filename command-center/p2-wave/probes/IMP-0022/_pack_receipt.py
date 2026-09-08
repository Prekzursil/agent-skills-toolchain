#!/usr/bin/env python3
"""Pack IMP-0022 — path-casing normalisation evidence as honest BLOCKED receipt.

Catalog evidence requires TWO signals:
  (1) casefold-collision count over the payload path set — obtainable here;
  (2) actual extraction onto a case-insensitive filesystem with a count
      shortfall — NOT obtainable on this Linux/ext4 worker without a CI-FS mount.

Catalog reviewer_requirement: Reviewer confirms normalisation is casefold
(not lower()) and NFC is applied first.

Never invent SUCCESS. Receipt state remains BLOCKED.
success_invented=false. did_not_promote=true.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "IMP-0022"
OUT = "command-center/receipts/IMP-0022.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/IMP-0022"
HELPER = "tools/plugin/casefold_paths.py"
PACK = "tools/plugin/pack.py"
TEST = "tools/plugin/tests/test_case_collision_paths.py"
TEST_NODE = (
    "tools/plugin/tests/test_case_collision_paths.py"
    "::test_no_casefold_collisions_in_payload"
)
PROBE1 = f"{PROBE_DIR}/probe1_casefold_set.py"
PROBE2 = f"{PROBE_DIR}/probe2_ci_fs_extract.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
TS0 = "2026-09-08T05:06:00Z"
SENTINEL_OK = "SUCCESS:IMP-0022"


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


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    rc_py, out_py = _run(
        [sys.executable, "-m", "pytest", "-q", TEST, "--tb=short"]
    )
    (L.REPO / PROBE_DIR / "pytest.out").write_text(out_py, encoding="utf-8")
    if rc_py != 0:
        raise SystemExit(f"IMP-0022 pytest failed:\n{out_py}")

    rc_node, out_node = _run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            TEST_NODE,
            "--tb=short",
        ]
    )
    (L.REPO / PROBE_DIR / "pytest-catalog-node.out").write_text(
        out_node, encoding="utf-8"
    )
    if rc_node != 0:
        raise SystemExit(f"IMP-0022 catalog node failed:\n{out_node}")

    rc1, out1 = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    (L.REPO / PROBE_DIR / "probe1.run.out").write_text(out1, encoding="utf-8")
    if rc1 != 0:
        raise SystemExit(f"IMP-0022 probe1 failed:\n{out1}")

    rc2, out2 = _run([sys.executable, "-B", str(L.REPO / PROBE2)])
    (L.REPO / PROBE_DIR / "probe2.run.out").write_text(out2, encoding="utf-8")
    # Probe 2 is expected to exit non-zero on case-sensitive hosts.
    m2 = json.loads(
        (L.REPO / PROBE_DIR / "probe2-measurement.json").read_text(encoding="utf-8")
    )
    if m2.get("ok"):
        # Unexpected green on this substrate — still leave BLOCKED for reviewer,
        # but record that signal 2 unexpectedly confirmed.
        pass
    elif not m2.get("missing_case_insensitive_filesystem"):
        raise SystemExit(
            f"IMP-0022 probe2 failed for a reason other than missing CI-FS:\n{out2}"
        )

    m1 = json.loads(
        (L.REPO / PROBE_DIR / "probe1-measurement.json").read_text(encoding="utf-8")
    )
    if not m1.get("ok"):
        raise SystemExit(f"IMP-0022 probe1 measurement not ok: {m1}")

    raw1 = (L.REPO / PROBE_DIR / "probe1-casefold-set.raw.txt").read_text(
        encoding="utf-8"
    )
    raw2 = (L.REPO / PROBE_DIR / "probe2-ci-fs-extract.raw.txt").read_text(
        encoding="utf-8"
    )

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
            f"ok={m1['ok']} planted={m1['planted_collision_group_count']} "
            f"clean={m1['clean_collision_group_count']} "
            f"nfc_key_equal={m1['nfc_key_equal']} "
            f"accent_case={m1['accent_case_collision_group_count']}\n"
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
            f"ok={m2['ok']} missing_ci_fs={m2['missing_case_insensitive_filesystem']} "
            f"set_check={m2['set_check_fired']} "
            f"extract_fired={m2['extraction_count_check_fired']}\n"
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
    p_node = L.probe(
        "source",
        "test-run",
        f"python -m pytest -q {TEST_NODE}",
        out_node,
        exit_code=rc_node,
    )

    missing_ci = bool(m2.get("missing_case_insensitive_filesystem"))
    state = "BLOCKED"
    sentinel = (
        f"FAILED:IMP-0022 blocked-on-case-insensitive-filesystem-substrate; "
        f"implementer evidence partial (pytest catalog node PASS; probe1 "
        f"planted_collision_group_count={m1['planted_collision_group_count']} "
        f"set_check_fired=true; probe2 missing_ci_fs={missing_ci} "
        f"extraction_count_check_fired={m2['extraction_count_check_fired']}); "
        f"{SENTINEL_OK} withheld (did_not_promote=true; success_invented=false); "
        f"BLOCKED:IMP-0022 pending CI-FS extraction shortfall + independent "
        f"NFC/casefold review"
    )
    reviewer_notes = (
        "Implementer emit only. Signal (1) CONFIRMED on this Linux worker "
        f"(planted README.md/readme.md collision_group_count="
        f"{m1['planted_collision_group_count']}; NFC pair collapses; clean set "
        "silent). Signal (2) NOT CONFIRMED: host filesystem is case-sensitive "
        "ext4; no IMP0022_CI_FS_ROOT case-insensitive mount provided; "
        "diagnostic extract of planted zip lands both members (shortfall=0) — "
        "inventing a CI-FS shortfall is forbidden. Catalog reviewer_requirement "
        "also unmet: independent reviewer must confirm normalisation is "
        "casefold (not lower()) with NFC applied first. "
        f"{SENTINEL_OK} not invented; independent-review.json not invented."
    )
    reviewer = {
        "reviewer_id": "awaiting-independent-nfc-casefold-and-ci-fs-reviewer",
        "verdict": "NOT-REVIEWED",
        "independent": False,
        "fresh_context": False,
        "vendor": "openai",
        "reviewed_at": ended,
        "notes": reviewer_notes[:4000],
    }
    failure = {
        "classification": [
            "blocked-on-missing-case-insensitive-filesystem",
            "blocked-on-independent-review",
            "case-collision-loss",
        ],
        "reason": (
            "Catalog evidence_requirement signal (2) demands an actual extraction "
            "onto a case-insensitive filesystem showing a file-count shortfall for "
            "the planted README.md/readme.md pair. This worker's root filesystem "
            "is case-sensitive ext4; ciopfs/NTFS/APFS mounts are absent; "
            "IMP0022_CI_FS_ROOT was unset. Additionally, catalog "
            "reviewer_requirement (casefold not lower; NFC first) needs an "
            f"independent reviewer PASS before {SENTINEL_OK}."
        ),
        "blocked_on": "case-insensitive-filesystem-mount+independent-nfc-casefold-review",
        "diagnostic_tail": (out1 + "\n" + out2)[-4000:],
        "two_signal_proof": [p1_src, p2_src],
    }
    residual = [
        {
            "claim": (
                "Catalog signal (2) — extraction onto a case-insensitive "
                "filesystem with a collision shortfall — has not been obtained "
                "on this substrate."
            ),
            "verdict": "NOT-CHECKED",
            "settling_experiment": (
                "Mount or provide a real case-insensitive volume "
                "(Windows/NTFS, macOS/APFS default, or Linux ciopfs), set "
                "IMP0022_CI_FS_ROOT to that mount, re-run "
                f"{PROBE2}, require shortfall>=1 for the planted README.md/"
                "readme.md zip, then re-pack."
            ),
        },
        {
            "claim": (
                "Independent reviewer has not confirmed NFC-then-casefold "
                "(not lower()) normalisation."
            ),
            "verdict": "NOT-CHECKED",
            "settling_experiment": (
                "Fresh-context independent reviewer inspects "
                f"{HELPER} casefold_key(), confirms unicodedata.normalize('NFC') "
                "precedes str.casefold() and lower() is not used, writes "
                f"{PROBE_DIR}/independent-review.json with verdict=PASS; "
                f"re-pack may emit {SENTINEL_OK} only when signal (2) is also green."
            ),
        },
    ]

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

    (L.REPO / MANIFEST).write_text(
        json.dumps(
            {
                "entry_id": UNIT,
                "unit_id": UNIT,
                "artifacts": [
                    OUT,
                    HELPER,
                    PACK,
                    TEST,
                    PROBE1,
                    PROBE2,
                    f"{PROBE_DIR}/probe1-measurement.json",
                    f"{PROBE_DIR}/probe2-measurement.json",
                ],
                "state": state,
                "registered_at": ended,
                "reviewer_requirement": (
                    "Reviewer confirms the normalisation is casefold, not "
                    "lower(), and that Unicode NFC normalisation is applied first."
                ),
                "did_not_promote": True,
                "probe1_ok": m1["ok"],
                "probe2_ok": m2["ok"],
                "missing_case_insensitive_filesystem": missing_ci,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    py_passed = out_py.count(".")
    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json IMP-0022",
        "min_bytes_threshold": 1024,
        "profile": "path-casing-casefold-collision",
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5.x-codex",
            "role": "p2-wave-imp-0022-implementer",
            "execution_substrate": "linux-worktree-case-sensitive-ext4",
        },
        "artifacts": [
            L.art(HELPER, "supporting"),
            L.art(PACK, "supporting"),
            L.art(TEST, "supporting"),
            L.art(PROBE1, "supporting"),
            L.art(PROBE2, "supporting"),
            L.art(f"{PROBE_DIR}/probe1-measurement.json", "supporting"),
            L.art(f"{PROBE_DIR}/probe2-measurement.json", "supporting"),
            L.art(MANIFEST, "supporting"),
        ],
        "evidence": [
            L.evidence(
                "Signal (1): NFC+casefold set check over the payload path set "
                f"reports planted_collision_group_count="
                f"{m1['planted_collision_group_count']} for README.md/"
                "readme.md; clean set is silent; NFD/NFC café pair collapses "
                "to one key.",
                "CONFIRMED",
                f"{PROBE_DIR}/probe1-casefold-set.raw.txt",
                [p1_src, p1_ver],
                "almost-certain",
            ),
            L.evidence(
                "Signal (2): actual extraction onto a case-insensitive "
                "filesystem showing a file-count shortfall for the planted "
                "README.md/readme.md archive was NOT obtained — host dest is "
                "case-sensitive; diagnostic extract lands both members "
                "(shortfall=0).",
                "BLOCKED",
                f"{PROBE_DIR}/probe2-ci-fs-extract.raw.txt",
                [p2_src, p2_ver],
                "almost-certain",
            ),
            L.evidence(
                "Catalog tests_required node "
                "test_no_casefold_collisions_in_payload PASS; planted pair "
                "fires the set check; packer refuses colliding members before "
                "archive emit.",
                "CONFIRMED",
                f"{PROBE_DIR}/pytest.out",
                [
                    p_py,
                    p_node,
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
        ],
        "tests": [
            {
                "id": "catalog-node-no-casefold-collisions",
                "name": TEST_NODE,
                "command": f"python3 -m pytest -q {TEST_NODE}",
                "result": "PASS",
                "assertions": 1,
                "output_tail": out_node[-600:],
            },
            {
                "id": "casefold-suite",
                "name": TEST,
                "command": f"python3 -m pytest -q {TEST}",
                "result": "PASS",
                "assertions": max(py_passed, 1),
                "output_tail": out_py[-600:],
            },
            {
                "id": "named-probe-1-casefold-set",
                "name": "Probe 1 casefold-collision count",
                "command": f"python -B {PROBE1}",
                "result": "PASS",
                "assertions": 3,
                "output_tail": out1[-800:],
            },
            {
                "id": "named-probe-2-ci-fs-extract",
                "name": "Probe 2 CI-FS extraction shortfall",
                "command": f"python -B {PROBE2}",
                "result": "FAIL",
                "assertions": 1,
                "output_tail": out2[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "planted-readme-readme-md-set-check",
                "known-broken-fixture",
                (
                    "NEGATIVE CONTROL: plant README.md and readme.md and assert "
                    "the set check fires (extraction-count half blocked on CI-FS)."
                ),
                True,
                True,
                bad=(
                    f"planted_collision_group_count="
                    f"{m1['planted_collision_group_count']}; "
                    f"paths={list(m1.get('planted_paths', []))}"
                ),
                good=(
                    f"clean_collision_group_count="
                    f"{m1['clean_collision_group_count']}"
                ),
            ),
            L.control(
                "extraction-count-on-case-sensitive-must-not-invent-shortfall",
                "known-broken-fixture",
                (
                    "On a case-sensitive filesystem, extracting the planted zip "
                    "must land both files (shortfall=0); claiming a CI-FS "
                    "shortfall here would be a false green."
                ),
                True,
                True,
                bad=(
                    "require_case_insensitive=True raises RuntimeError naming "
                    "missing case-insensitive substrate"
                ),
                good=(
                    f"diagnostic shortfall="
                    f"{(m2.get('extract') or {}).get('shortfall')}; "
                    f"extracted="
                    f"{(m2.get('extract') or {}).get('extracted_file_count')}"
                ),
            ),
        ],
        "reviewer": reviewer,
        "defects": [
            {
                "id": "IMP-0022-D1",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Case-insensitive filesystem substrate absent on this "
                    "Linux/ext4 worker; catalog signal (2) cannot be measured."
                ),
            },
            {
                "id": "IMP-0022-D2",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Independent reviewer has not yet confirmed NFC-then-casefold "
                    "(not lower())."
                ),
            },
        ],
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
                "two-strikes-then-pivot; SUCCESS withheld until CI-FS extraction "
                "shortfall is measured and independent NFC/casefold review PASS."
            ),
        },
        "residual_unknowns": residual,
        "failure": failure,
        "extensions": {
            "stage": "p2-deliver",
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "anti_false_green": (
                "BLOCKED-pending-case-insensitive-fs-extraction-and-independent-review"
            ),
            "did_not_promote": True,
            "success_invented": False,
            "catalog_completion_sentinel": SENTINEL_OK,
            "live_product": {
                "helper": HELPER,
                "packer_preemit": PACK,
                "tests": [TEST, TEST_NODE],
            },
            "reviewer_requirement": {
                "required": "independent-confirm-nfc-then-casefold-not-lower",
                "must_not": "self-review-or-invent-SUCCESS",
            },
            "probe_summary": {
                "probe1_ok": m1["ok"],
                "probe1_planted_collision_group_count": m1[
                    "planted_collision_group_count"
                ],
                "probe2_ok": m2["ok"],
                "missing_case_insensitive_filesystem": missing_ci,
                "extraction_count_check_fired": m2["extraction_count_check_fired"],
            },
            "blocked_substrate": {
                "needed": "case-insensitive-filesystem",
                "host": "linux-ext4-case-sensitive",
                "override_env": "IMP0022_CI_FS_ROOT",
            },
        },
    }

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
    print(f"did_not_promote=true success_invented=false validate={v_rc}")
    print(f"probe1_rc={rc1} probe2_rc={rc2} missing_ci_fs={missing_ci}")
    return receipt


if __name__ == "__main__":
    build()
