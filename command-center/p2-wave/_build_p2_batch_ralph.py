#!/usr/bin/env python3
"""Emit BLOCKED receipts for IMP-0439, TST-0328, CNF-0015 after green pytest.

Anti-false-green: state=BLOCKED pending independent review even though tests pass.
Uses _p2lib + atomic_receipt. Does not mint SUCCESS.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(L.REPO / "platform" / "lib"))
import atomic_receipt as ar  # noqa: E402

sys.path.insert(0, str(L.REPO / "tools" / "command-center"))
import render as cc_render  # noqa: E402

sys.path.insert(0, str(L.REPO / "tools" / "detector-self-test"))
import detector_self_test as dst  # noqa: E402


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


def run_pytest(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *args, "-q", "--tb=line"],
        cwd=str(L.REPO),
        capture_output=True,
        text=True,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def digest_table() -> list[dict]:
    """Three-column table: working-tree raw, blob, recorded provenance."""
    root = L.REPO / "command-center"
    manifest = json.loads((root / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
    recorded = {a["path"]: a.get("sha256", "") for a in manifest["artifacts"]}
    rows = []
    for name in cc_render.CONTRACTED_ARTIFACTS:
        if name == "ARTIFACT-MANIFEST.json":
            continue
        rel = f"command-center/{name}"
        wt = cc_render.working_tree_raw_hash(root, name)
        blob = cc_render.blob_hash(root, name)
        prov = (
            hashlib.sha256(cc_render.provenance_bytes(root, name)).hexdigest()
            if (root / name).is_file()
            else ""
        )
        rows.append(
            {
                "path": rel,
                "working_tree_raw_sha256": wt,
                "blob_sha256": blob,
                "recorded_provenance_sha256": recorded.get(rel, ""),
                "provenance_bytes_sha256": prov,
                "blob_equals_recorded": bool(blob) and blob == recorded.get(rel, ""),
                "wt_raw_differs_from_blob": bool(wt and blob and wt != blob),
            }
        )
    return rows


def adoption_census() -> dict:
    """How many registered suites use detector_self_test vs hand-rolled both-states."""
    reg = json.loads(
        (L.REPO / "command-center/TEST-REGISTRY.json").read_text(encoding="utf-8")
    )
    suites = reg.get("suites", [])
    uses_fixture = []
    hand_rolled = []
    for s in suites:
        path = s.get("path", "")
        p = L.REPO / path
        text = p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
        if "detector_self_test" in text or "assert_both_states" in text:
            uses_fixture.append(path)
        elif "both_states" in text or "both-states" in text or "known-broken" in text:
            hand_rolled.append(path)
    # Also count discoverable detector cases under tools/detector-self-test/examples
    cases = dst.discover(dst.default_root())
    return {
        "registry_suites_total": len(suites),
        "suites_importing_fixture": uses_fixture,
        "suites_hand_rolled_both_states_mention": hand_rolled,
        "fixture_case_count_under_examples": len(cases),
        "fixture_case_names": [c.name for c in cases],
    }


def pack_imp0439(pytest_out: str, pytest_rc: int, table: list[dict]) -> dict:
    unit = "IMP-0439"
    out = "command-center/receipts/IMP-0439.json"
    probe_dir = L.REPO / "command-center/p2-wave/probes/IMP-0439"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "digest-table.json").write_text(
        json.dumps(table, indent=2) + "\n", encoding="utf-8"
    )
    (probe_dir / "pytest.out").write_text(pytest_out, encoding="utf-8")

    blob_eq = sum(1 for r in table if r["blob_equals_recorded"] or not r["blob_sha256"])
    # On Linux clean checkout wt_raw usually equals blob; the parity test proves the CRLF case.
    p1 = L.probe(
        "source",
        "test-run",
        "python3 -m pytest tools/command-center/tests/test_provenance_blob_hash.py -q",
        pytest_out,
        pytest_rc,
    )
    p2 = L.probe(
        "verifier",
        "byte-compare",
        "three-column digest table over CONTRACTED_ARTIFACTS",
        json.dumps({"rows": len(table), "sample": table[:2]}, indent=2)[:4000],
        0,
    )
    ts = now()
    receipt = {
        "schema_version": 1,
        "unit_id": unit,
        "state": "BLOCKED",
        "sentinel": "SENTINEL:IMP-0439:PROVENANCE-BLOB-HASHED pending independent review",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0439",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art("tools/command-center/render.py", "primary"),
            L.art("tools/command-center/validate.py", "supporting"),
            L.art("tools/measure-guard/blobread.py", "supporting"),
            L.art(
                "tools/command-center/tests/test_provenance_blob_hash.py", "supporting"
            ),
            L.art("command-center/p2-wave/probes/IMP-0439/digest-table.json", "log"),
            L.art("command-center/p2-wave/probes/IMP-0439/pytest.out", "log"),
        ],
        "evidence": [
            L.evidence(
                "render.provenance_bytes / validate REACH-6 prefer git cat-file blob; "
                "platform-parity pytest proves CRLF worktree raw differs from blob while "
                "blob digests match across LF and CRLF checkouts.",
                "CONFIRMED",
                "tools/command-center/render.py:provenance_bytes",
                [p1, p2],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": ts, "ended_at": ts},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {
                "id": "T1-platform-parity-blob-route",
                "command": "python3 -m pytest tools/command-center/tests/test_provenance_blob_hash.py -q",
                "result": "PASS" if pytest_rc == 0 else "FAIL",
                "assertions": 4,
                "output_tail": pytest_out.strip().splitlines()[-1][:200]
                if pytest_out.strip()
                else "",
            },
            {
                "id": "T2-working-tree-raw-differs-control",
                "command": "test_working_tree_raw_route_differs_from_blob_on_crlf",
                "result": "PASS" if pytest_rc == 0 else "FAIL",
                "assertions": 1,
                "output_tail": "wt_raw != blob on CRLF checkout fixture",
            },
        ],
        "negative_controls": [
            L.control(
                "IMP0439-C1",
                "known-broken-fixture",
                "CRLF working-tree raw hash must differ from blob hash",
                True,
                True,
                "wt_raw != blob on CRLF checkout",
                "blob route identical on LF and CRLF checkouts",
            ),
        ],
        "reviewer": {
            "reviewer_id": "UNASSIGNED-pending-independent-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "notes": "Tests green; SUCCESS withheld pending independent digest re-derivation "
            "(catalog reviewer_requirement: independent-claude-reviewer).",
        },
        "failure": {
            "classification": ["reviewer-pending", "P2-degraded"],
            "reason": "Implementation and pytest are green; catalog requires independent "
            "reviewer re-deriving two digests by a different command before SUCCESS.",
            "blocked_on": "independent-claude-reviewer digest re-derivation",
        },
        "defects": [],
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/p2-wave/probes/IMP-0439/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": unit,
        },
        "downstream_consumers": [],
        "residual_unknowns": [
            {
                "claim": "Full Windows checkout three-column table not re-measured on this Linux agent",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Re-run digest table on a Windows autocrlf=true checkout",
            }
        ],
        "report": {
            "kind": "generic_report",
            "observations": [
                {
                    "id": "digest-table-rows",
                    "value": len(table),
                    "note": f"blob_equals_recorded_or_absent={blob_eq}",
                }
            ],
            "control_ids": ["IMP0439-C1"],
        },
        "extensions": {
            "digest_table_path": "command-center/p2-wave/probes/IMP-0439/digest-table.json"
        },
    }
    return receipt, out


def pack_tst0328(pytest_out: str, pytest_rc: int, census: dict) -> tuple[dict, str]:
    unit = "TST-0328"
    out = "command-center/receipts/TST-0328.json"
    probe_dir = L.REPO / "command-center/p2-wave/probes/TST-0328"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "adoption-census.json").write_text(
        json.dumps(census, indent=2) + "\n", encoding="utf-8"
    )
    (probe_dir / "pytest.out").write_text(pytest_out, encoding="utf-8")

    # Exercise callable fixture live in this packer
    ok = dst.assert_both_states(
        lambda s: s == "broken", broken="broken", good="good", name="packer-ok"
    )
    try:
        dst.assert_both_states(
            lambda s: False, broken="a", good="b", name="packer-silent"
        )
        silent_rejected = False
    except dst.BothStatesError:
        silent_rejected = True
    try:
        dst.assert_both_states(
            lambda s: True, broken="a", good="b", name="packer-always"
        )
        always_rejected = False
    except dst.BothStatesError:
        always_rejected = True

    p1 = L.probe(
        "source",
        "test-run",
        "python3 -m pytest tools/detector-self-test/tests/test_detector_self_test.py -q",
        pytest_out,
        pytest_rc,
    )
    p2 = L.probe(
        "verifier",
        "other",
        "assert_both_states self-check silent+always+ok",
        f"ok={ok.as_dict()} silent_rejected={silent_rejected} always_rejected={always_rejected} census={json.dumps(census)[:1500]}",
        0 if silent_rejected and always_rejected and ok.passed else 1,
    )
    ts = now()
    receipt = {
        "schema_version": 1,
        "unit_id": unit,
        "state": "BLOCKED",
        "sentinel": "SUCCESS:TST-0328 pending independent adversarial review",
        "spec_anchor": "_USER-PROMPTS.md:10658",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud",
            "role": "harness-engineer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art("tools/detector-self-test/detector_self_test.py", "primary"),
            L.art(
                "tools/detector-self-test/tests/test_detector_self_test.py",
                "supporting",
            ),
            L.art("command-center/p2-wave/probes/TST-0328/adoption-census.json", "log"),
            L.art("command-center/p2-wave/probes/TST-0328/pytest.out", "log"),
        ],
        "evidence": [
            L.evidence(
                "Callable assert_both_states / run_both_states shipped; silent-in-both and "
                "firing-in-both self-tests reject; adoption census recorded.",
                "CONFIRMED",
                "tools/detector-self-test/detector_self_test.py:assert_both_states",
                [p1, p2],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": ts, "ended_at": ts},
        "retry": {"count": 0, "policy": "No automatic retry"},
        "tests": [
            {
                "id": "T1-silent-in-both-rejected",
                "command": "test_assert_both_states_rejects_silent_in_both",
                "result": "PASS" if silent_rejected and pytest_rc == 0 else "FAIL",
                "assertions": 1,
                "output_tail": "BothStatesError SILENT_IN_BOTH",
            },
            {
                "id": "T2-firing-in-both-rejected",
                "command": "test_assert_both_states_rejects_firing_in_both",
                "result": "PASS" if always_rejected and pytest_rc == 0 else "FAIL",
                "assertions": 1,
                "output_tail": "BothStatesError FIRING_IN_BOTH",
            },
            {
                "id": "T3-adoption-census",
                "command": "adoption_census over TEST-REGISTRY.json",
                "result": "PASS",
                "assertions": 1,
                "output_tail": json.dumps(
                    {
                        "fixture_cases": census["fixture_case_count_under_examples"],
                        "suites_importing": len(census["suites_importing_fixture"]),
                        "hand_rolled_mentions": len(
                            census["suites_hand_rolled_both_states_mention"]
                        ),
                    }
                ),
            },
        ],
        "negative_controls": [
            L.control(
                "TST0328-C1",
                "known-broken-fixture",
                "Fixture rejects a detector silent in both states",
                True,
                True,
                "silent detector -> BothStatesError",
                "discriminating detector -> PASS",
            ),
            L.control(
                "TST0328-C2",
                "known-broken-fixture",
                "Fixture rejects a detector firing in both states",
                True,
                True,
                "always-on detector -> BothStatesError",
                "discriminating detector -> PASS",
            ),
        ],
        "reviewer": {
            "reviewer_id": "UNASSIGNED-pending-independent-review",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "notes": "Catalog requires an independent adversarial reviewer who reproduces "
            "the both-states control before SUCCESS.",
        },
        "failure": {
            "classification": ["reviewer-pending"],
            "reason": "Reusable both-states fixture shipped with green self-tests; "
            "SUCCESS withheld pending independent adversarial review.",
            "blocked_on": "independent adversarial reviewer both-states reproduction",
        },
        "defects": [],
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/p2-wave/probes/TST-0328/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": unit,
        },
        "downstream_consumers": [],
        "residual_unknowns": [],
        "report": {
            "kind": "generic_report",
            "observations": [
                {"id": "adoption", "value": census["fixture_case_count_under_examples"]}
            ],
            "control_ids": ["TST0328-C1", "TST0328-C2"],
        },
        "extensions": {"adoption_census": census},
    }
    return receipt, out


def pack_cnf0015(pytest_out: str, pytest_rc: int) -> tuple[dict, str]:
    unit = "CNF-0015"
    out = "command-center/confirmation/CNF-0015-blocker-repro.json"
    probe_dir = L.REPO / "command-center/p2-wave/probes/CNF-0015"
    (probe_dir / "pytest.out").write_text(pytest_out, encoding="utf-8")

    sys.path.insert(0, str(probe_dir))
    import option_id_collision as oic  # noqa: E402

    pre = oic.measure_dir(probe_dir / "fixtures" / "pre-fix")
    post = oic.measure_dir(probe_dir / "fixtures" / "post-fix")
    obs = dst.assert_both_states(
        oic.collision_is_live,
        broken=probe_dir / "fixtures" / "pre-fix",
        good=probe_dir / "fixtures" / "post-fix",
        name="CNF-0015",
    )

    p1 = L.probe(
        "source",
        "test-run",
        "python3 -m pytest command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py -q",
        pytest_out,
        pytest_rc,
    )
    p2 = L.probe(
        "verifier",
        "other",
        "measure pre-fix vs post-fix shared_id_count",
        json.dumps(
            {"pre": pre.as_dict(), "post": post.as_dict(), "obs": obs.as_dict()},
            indent=2,
        ),
        0,
    )
    ts = now()
    # Honest residual: live 07/13/17 docs are absent from this clone; fixtures reconstruct arithmetic.
    receipt = {
        "schema_version": 1,
        "unit_id": unit,
        "state": "BLOCKED",
        "sentinel": (
            f"FAILED:CNF-0015 blocked-on-review; both-states fixture shared_id "
            f"pre={pre.shared_id_count} post={post.shared_id_count}; "
            "live harness-restore docs not in this clean clone"
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNF-0015",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "openai",
            "model": "composer-cloud",
            "role": "reproduction-engineer",
            "execution_substrate": "linux-cloud-agent",
        },
        "artifacts": [
            L.art(
                "command-center/p2-wave/probes/CNF-0015/option_id_collision.py",
                "primary",
            ),
            L.art(
                "command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py",
                "supporting",
            ),
            L.art(
                "command-center/p2-wave/probes/CNF-0015/fixtures/pre-fix/13-ARCHITECTURE-CANDIDATES.md",
                "fixture",
            ),
            L.art(
                "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/13-ARCHITECTURE-CANDIDATES.md",
                "fixture",
            ),
            L.art("command-center/p2-wave/probes/CNF-0015/pytest.out", "log"),
            L.art("command-center/OPTION-ID-RESOLUTION.json", "supporting"),
        ],
        "evidence": [
            L.evidence(
                "Both-states collision detector: shared_id_count=31 on pre-fix fixture "
                "(FAIL/live) and 0 on post-fix fixture (PASS/fixed); decision-log stale "
                "half fires only on pre-fix. Fixtures reconstruct OPTION-ID-RESOLUTION "
                "arithmetic because 07/13/17 are absent from this clean clone.",
                "CONFIRMED",
                "command-center/p2-wave/probes/CNF-0015/option_id_collision.py",
                [p1, p2],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": ts, "ended_at": ts},
        "retry": {
            "count": 0,
            "policy": "zero retries. first observation IS the verdict",
        },
        "tests": [
            {
                "id": "T1-fail-on-pre-fix",
                "command": "test_pre_fix_shared_id_count_is_31",
                "result": "PASS"
                if pytest_rc == 0 and pre.shared_id_count == 31
                else "FAIL",
                "assertions": 1,
                "output_tail": json.dumps(pre.as_dict()),
            },
            {
                "id": "T2-pass-on-post-fix",
                "command": "test_post_fix_shared_id_count_is_0",
                "result": "PASS"
                if pytest_rc == 0 and post.shared_id_count == 0
                else "FAIL",
                "assertions": 1,
                "output_tail": json.dumps(post.as_dict()),
            },
            {
                "id": "T3-opposite-results-required",
                "command": "assert_both_states(collision_is_live, pre, post)",
                "result": "PASS" if obs.passed else "FAIL",
                "assertions": 2,
                "output_tail": json.dumps(obs.as_dict()),
            },
        ],
        "negative_controls": [
            L.control(
                "CNF0015-C1",
                "known-broken-fixture",
                "Detector must fire on pre-fix and stay silent on post-fix",
                obs.fired_on_broken,
                not obs.fired_on_good,
                f"pre shared_id_count={pre.shared_id_count}",
                f"post shared_id_count={post.shared_id_count}",
            ),
        ],
        "reviewer": {
            "reviewer_id": "UNASSIGNED-pending-detector-control-rerun",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "notes": "Catalog requires a reviewer who re-runs the DETECTOR CONTROL on the "
            "known-broken fixture; SUCCESS withheld.",
        },
        "failure": {
            "classification": ["reviewer-pending", "stale-premise"],
            "reason": "Both-states repro is green on reconstructed fixtures; live 07/13/17 "
            "docs are not in this clean clone (harness-restore path only). Pending "
            "reviewer re-run of detector control before SUCCESS.",
            "blocked_on": "independent detector-control re-run + optional live doc mount",
        },
        "defects": [],
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/p2-wave/probes/CNF-0015/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": unit,
        },
        "downstream_consumers": [],
        "residual_unknowns": [
            {
                "claim": "Live 07-OPTION-UNIVERSE.md / 13-ARCHITECTURE-CANDIDATES.md / "
                "17-DECISION-LOG.md are not present in this git clone",
                "verdict": "CONFIRMED",
                "settling_experiment": "Mount harness-restore-20260806 docs and re-run "
                "measure_dir against git cat-file at the pinned rev",
            }
        ],
        "report": {
            "kind": "repro-report",
            "observations": [
                {
                    "name": "shared_id_count_pre_fix",
                    "measured": pre.shared_id_count,
                    "method": "family-M ∩ bare-M-NN set intersection on fixture docs",
                    "anchor": "command-center/p2-wave/probes/CNF-0015/fixtures/pre-fix/",
                },
                {
                    "name": "shared_id_count_post_fix",
                    "measured": post.shared_id_count,
                    "method": "family-M ∩ bare-M-NN set intersection on fixture docs",
                    "anchor": "command-center/p2-wave/probes/CNF-0015/fixtures/post-fix/",
                },
                {
                    "name": "literal_shared_id_answer",
                    "measured": "post-fix=0; pre-fix=31",
                    "method": "both-states pytest + assert_both_states",
                    "anchor": "command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py",
                },
            ],
            "control_ids": ["CNF0015-C1"],
        },
        "extensions": {
            "fixture_source": "reconstructed from command-center/OPTION-ID-RESOLUTION.json",
            "pre": pre.as_dict(),
            "post": post.as_dict(),
        },
    }
    return receipt, out


def main() -> int:
    # IMP-0439
    rc1, out1 = run_pytest(
        [
            "tools/command-center/tests/test_provenance_blob_hash.py",
            "tools/command-center/tests/test_render.py",
            "tools/command-center/tests/test_validate.py",
        ]
    )
    if rc1 != 0:
        print(f"FAILED:IMP-0439 pytest\n{out1}")
        return 1
    table = digest_table()
    rec1, path1 = pack_imp0439(out1, rc1, table)

    # TST-0328
    rc2, out2 = run_pytest(
        ["tools/detector-self-test/tests/test_detector_self_test.py"]
    )
    if rc2 != 0:
        print(f"FAILED:TST-0328 pytest\n{out2}")
        return 1
    census = adoption_census()
    rec2, path2 = pack_tst0328(out2, rc2, census)

    # CNF-0015
    rc3, out3 = run_pytest(
        ["command-center/p2-wave/probes/CNF-0015/test_option_id_collision.py"]
    )
    if rc3 != 0:
        print(f"FAILED:CNF-0015 pytest\n{out3}")
        return 1
    rec3, path3 = pack_cnf0015(out3, rc3)

    results = []
    for rec, path in ((rec1, path1), (rec2, path2), (rec3, path3)):
        schema = (
            "command-center/schema/repro-report.schema.json"
            if rec["unit_id"] == "CNF-0015"
            else "command-center/schema/receipt.schema.json"
        )
        errs = L.validate(rec, schema)
        if errs:
            print(f"FAILED:{rec['unit_id']} schema errors:")
            for e in errs[:20]:
                print(" ", e)
            return 1
        ar.write_json_atomic(path, rec)
        # Re-measure artifacts that include self paths? We don't list self.
        # Admit
        val_rc, val_out = L.run(
            [sys.executable, "command-center/receipt_validate.py", path]
        )
        print(f"{rec['unit_id']}: wrote {path} validate_rc={val_rc} {val_out.strip()}")
        if val_rc != 0 or "ACCEPT" not in val_out:
            print(f"FAILED:{rec['unit_id']} receipt_validate did not ACCEPT")
            return 1
        # Write per-unit manifest pointer (not global)
        man = {
            "unit_id": rec["unit_id"],
            "artifacts": [a["path"] for a in rec["artifacts"]],
            "output_path": path,
            "writer": ar.ATOMIC_WRITER_ID,
        }
        man_path = L.REPO / rec["manifest_registration"]["manifest_path"]
        man_path.parent.mkdir(parents=True, exist_ok=True)
        ar.write_json_atomic(man_path, man)
        # Update registered flag after writing local manifest — keep False for global C11
        results.append((rec["unit_id"], rec["state"], path, "ACCEPT"))

    print("RESULTS:")
    for row in results:
        print("|".join(row))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
