#!/usr/bin/env python3
"""REL-0006 downgrade drill: four catalog tests on a fresh isolated HOME each.

Catalog tests:
  1. Corrupt stored N-1 -> retrievability gate blocks before any inverse runs.
  2. Version-string reports N-1 while behaviour is still N (disqualifies VERSION).
  3. Zero owner-authored files removed; hashes match the pre-downgrade census.
  4. MTTR measured with a named clock and compared to the runbook figure.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import canary as C  # noqa: E402


def _fresh_world(real_home: Path) -> dict[str, Any]:
    home = C.make_isolated(real_home)
    store_dir = Path(tempfile.mkdtemp(prefix="rel0006-store-"))
    store = C.build_release_store(store_dir)
    owner = C.seed_owner_files(home)
    inverses = C.load_inverses()
    n_raw = Path(store["n_path"]).read_bytes()
    n1_raw = Path(store["n1_path"]).read_bytes()
    return {
        "home": home,
        "store_dir": store_dir,
        "store": store,
        "owner_hashes": owner,
        "inverses": inverses,
        "n_raw": n_raw,
        "n1_raw": n1_raw,
        "real_home": real_home,
    }


def _cleanup(world: dict[str, Any]) -> None:
    for key in ("home", "store_dir"):
        path = world.get(key)
        if path:
            shutil.rmtree(path, ignore_errors=True)


def test_corrupt_blocks() -> dict[str, Any]:
    real = C.owner_home()
    world = _fresh_world(real)
    try:
        C.install_payload(world["home"], world["n1_raw"])
        C.install_payload(world["home"], world["n_raw"])
        C.write_journal(world["home"], downgrade_started=False, installed="n")
        before_version = C.read_version(world["home"])
        before_accept = C.run_n1_acceptance(world["home"], real)
        C.corrupt_n1(world["store"])
        blocked = False
        fetched = ""
        expected = world["store"]["n1_sha256"]
        error = ""
        try:
            C.fetch_n1(world["store"])
        except C.RetrievabilityBlocked as exc:
            blocked = True
            fetched = exc.fetched
            expected = exc.expected
            error = str(exc)
        journal = C.read_journal(world["home"])
        after_version = C.read_version(world["home"])
        after_accept = C.run_n1_acceptance(world["home"], real)
        downgrade_started = bool(journal.get("downgrade_started"))
        still_n = after_version == C.N_VERSION and (not after_accept["passed"])
        passed = (
            blocked
            and (not downgrade_started)
            and still_n
            and fetched != expected
            and before_version == C.N_VERSION
            and (not before_accept["passed"])
        )
        return {
            "id": "T1-corrupt-n1-blocks-before-downgrade",
            "result": "PASS" if passed else "FAIL",
            "blocked": blocked,
            "fetched_sha256": fetched,
            "manifest_sha256": expected,
            "downgrade_started": downgrade_started,
            "version_after": after_version,
            "behaviour_still_n": still_n,
            "error": error,
        }
    finally:
        _cleanup(world)


def test_version_string_is_not_acceptance() -> dict[str, Any]:
    real = C.owner_home()
    world = _fresh_world(real)
    try:
        C.install_payload(world["home"], world["n1_raw"])
        n1_ok = C.run_n1_acceptance(world["home"], real)
        C.install_payload(world["home"], world["n_raw"])
        (world["home"] / "plugin" / "VERSION").write_text(
            C.N1_VERSION + "\n", encoding="utf-8"
        )
        version = C.read_version(world["home"])
        accept = C.run_n1_acceptance(world["home"], real)
        passed = (
            n1_ok["passed"] is True
            and version == C.N1_VERSION
            and accept["passed"] is False
            and accept["output"] == C.N_BEHAVIOR
        )
        return {
            "id": "T2-version-string-reports-n1-behaviour-still-n",
            "result": "PASS" if passed else "FAIL",
            "n1_acceptance_on_n1_install": n1_ok["passed"],
            "version_string": version,
            "acceptance_passed": accept["passed"],
            "acceptance_output": accept["output"],
            "acceptance_command": accept["command"],
            "why_version_is_disqualified": (
                "VERSION reads 1.0.0-n-1 while the N-1 acceptance probe still "
                f"observes {accept['output']!r}; restored behaviour, not the "
                "version file, is the acceptance signal."
            ),
        }
    finally:
        _cleanup(world)


def test_owner_files_and_restore() -> dict[str, Any]:
    real = C.owner_home()
    world = _fresh_world(real)
    try:
        C.install_payload(world["home"], world["n1_raw"])
        C.install_payload(world["home"], world["n_raw"])
        pre = C.hash_owner_files(world["home"])
        snap = world["home"] / ".lifecycle" / "baseline"
        C.snapshot_plugin(world["home"], snap)
        C.write_journal(
            world["home"],
            resume_boundary="snapshot-before-downgrade",
            snapshot=str(snap),
        )
        fetch = C.fetch_n1(world["store"])
        applied = C.apply_downgrade(world["home"], fetch["raw"], world["inverses"])
        accept = C.run_n1_acceptance(world["home"], real)
        post = C.hash_owner_files(world["home"])
        missing = [p for p, h in post.items() if h == "MISSING"]
        changed = [p for p in pre if pre[p] != post.get(p)]
        owner_ok = (not missing) and (not changed)
        refuse = C.refuse_owner_delete(world["inverses"])
        passed = (
            fetch["match"]
            and accept["passed"]
            and owner_ok
            and refuse["refused"]
            and C.read_version(world["home"]) == C.N1_VERSION
        )
        return {
            "id": "T3-owner-authored-files-preserved",
            "result": "PASS" if passed else "FAIL",
            "pre_hashes": pre,
            "post_hashes": post,
            "missing": missing,
            "changed": changed,
            "restored_paths": applied["restored"],
            "skipped_owner_paths": applied["skipped_owner"],
            "acceptance_after": {
                "passed": accept["passed"],
                "output": accept["output"],
                "command": accept["command"],
            },
            "fetched_sha256": fetch["fetched_sha256"],
            "manifest_sha256": fetch["manifest_sha256"],
            "inverse_refuses_owner_delete": refuse,
        }
    finally:
        _cleanup(world)


def test_restore_mttr() -> dict[str, Any]:
    real = C.owner_home()
    world = _fresh_world(real)
    try:
        C.install_payload(world["home"], world["n1_raw"])
        before_n1 = C.run_n1_acceptance(world["home"], real)
        C.install_payload(world["home"], world["n_raw"])
        before = C.run_n1_acceptance(world["home"], real)
        slo = C.parse_runbook_slo()
        clock = (
            "time.perf_counter_ns (monotonic, process-local) "
            "+ time.time_ns (Unix epoch CLOCK_REALTIME) "
            "from retrievability-gate-begin to N-1-acceptance-pass"
        )
        wall_start = time.time_ns()
        mono_start = time.perf_counter_ns()
        fetch = C.fetch_n1(world["store"])
        C.apply_downgrade(world["home"], fetch["raw"], world["inverses"])
        after = C.run_n1_acceptance(world["home"], real)
        mono_end = time.perf_counter_ns()
        wall_end = time.time_ns()
        if not after["passed"]:
            raise RuntimeError("N-1 acceptance probe did not pass after downgrade")
        measured_s = (mono_end - mono_start) / 1_000_000_000
        cmp_ = C.compare_mttr_control(measured_s, slo)
        iso = C.isolation_check_fires_on_real_home(real)
        passed = (
            before_n1["passed"]
            and (not before["passed"])
            and after["passed"]
            and cmp_["pass"]
            and iso["fired"]
            and fetch["match"]
        )
        return {
            "id": "T4-mttr-named-clock-vs-runbook",
            "result": "PASS" if passed else "FAIL",
            "acceptance_before_upgrade_on_n1": {
                "passed": before_n1["passed"],
                "output": before_n1["output"],
            },
            "acceptance_before_downgrade": {
                "passed": before["passed"],
                "output": before["output"],
                "command": before["command"],
                "version_string": before["version_string"],
            },
            "acceptance_after_downgrade": {
                "passed": after["passed"],
                "output": after["output"],
                "command": after["command"],
                "version_string": after["version_string"],
            },
            "mttr": {
                "seconds": measured_s,
                "nanoseconds": mono_end - mono_start,
                "clock_source": clock,
                "wall_start_unix_ns": wall_start,
                "wall_end_unix_ns": wall_end,
                "runbook_slo_seconds": slo,
                "runbook_path": str(
                    C.RUNBOOK_PATH.relative_to(C.HERE.parents[3])
                    if C.RUNBOOK_PATH.is_relative_to(C.HERE.parents[3])
                    else C.RUNBOOK_PATH
                ),
                "within_slo": cmp_["real_slo_accepts"],
                "decision": "retrievability-gate-begin",
                "restored": "n-1-acceptance-probe-pass",
            },
            "mttr_both_states": cmp_,
            "isolation_negative": iso,
            "fetched_sha256": fetch["fetched_sha256"],
            "manifest_sha256": fetch["manifest_sha256"],
            "store": {
                "n1_path": world["store"]["n1_path"],
                "manifest_path": world["store"]["manifest_path"],
                "n1_sha256": world["store"]["n1_sha256"],
            },
        }
    finally:
        _cleanup(world)


def run_all() -> dict[str, Any]:
    t1 = test_corrupt_blocks()
    t2 = test_version_string_is_not_acceptance()
    t3 = test_owner_files_and_restore()
    t4 = test_restore_mttr()
    tests = [t1, t2, t3, t4]
    passed = all(t.get("result") == "PASS" for t in tests)
    return {
        "pass": passed,
        "tests": tests,
        "owner_home": str(C.owner_home()),
        "touched_owner_profile": False,
    }


def main() -> int:
    result = run_all()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("pass"):
        print("FAILED:REL-0006-drill")
        return 1
    print("SUCCESS:REL-0006-drill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
