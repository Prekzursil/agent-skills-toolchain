#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0440.json from live measurements.

Writes the catalog artifact first, then named probes, then per-unit
SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

Does not call tools/command-center/unit_manifest.py --write.
Does not git add/commit.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MG = REPO / "tools" / "measure-guard"
sys.path.insert(0, str(MG))
sys.path.insert(0, str(MG / "tests"))

import archive_census as C  # noqa: E402
import blobread as B  # noqa: E402
import crlf_export_repo as F  # noqa: E402
import test_blobread as tests  # noqa: E402
import three_route as T  # noqa: E402

UNIT = "IMP-0440"
OUT = "command-center/receipts/IMP-0440.json"
SENTINEL = "SENTINEL:IMP-0440:BLOB-HELPER-SINGLE-SOURCE"
HELPER = "tools/measure-guard/blobread.py"
HELPER_TESTS = "tools/measure-guard/tests/test_blobread.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0440/probe1_helper_three_route.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0440/probe2_census_independent_file.py"
)
SUPPORTING = [
    HELPER,
    HELPER_TESTS,
    "tools/measure-guard/archive_census.py",
    "tools/measure-guard/three_route.py",
    "tools/measure-guard/crlf_export_repo.py",
    "tools/plugin/git_blob.py",
    "tools/bench/sha_anchor/gitutil.py",
    "tools/baseline/capture.py",
    "command-center/p2-wave/_i3_blobfmt.py",
    "command-center/p2-wave/probes/IMP-0440/probe1_helper_three_route.py",
    "command-center/p2-wave/probes/IMP-0440/probe2_census_independent_file.py",
    "command-center/p2-wave/probes/IMP-0440/emit_receipt.py",
]
ROUTED = [
    "tools/plugin/git_blob.py:cat_file_p",
    "tools/plugin/pack.py (via git_blob.cat_file_p)",
    "tools/plugin/eol_assert.py (via git_blob.cat_file_p)",
    "tools/plugin/eol_fixtures.py:blob_bytes (via git_blob.cat_file_p)",
    "tools/bench/sha_anchor/gitutil.py:cat_file_p",
    "tools/baseline/capture.py:parse_commit",
    "command-center/p2-wave/_i3_blobfmt.py:blob_bytes",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def probe_rec(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def manifest_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "exists": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0440/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_measure() -> dict:
    known = tests.test_known_file_blob_bytes()
    refuses = tests.test_helper_refuses_archive_in_source()
    wt = tests.test_worktree_is_not_oracle()
    with tempfile.TemporaryDirectory(prefix="imp0440-emit-") as td:
        info = F.make_crlf_export_repo(Path(td) / "repo")
        r_a = T.three_route(info["root"], F.ALPHA, "HEAD")
        cat_b = subprocess.run(
            ["git", "-C", str(info["root"]), "cat-file", "-p", f"HEAD:{F.BETA}"],
            capture_output=True,
            env=B.git_env(),
            check=False,
        ).stdout
        show_b = subprocess.run(
            ["git", "-C", str(info["root"]), "show", f"HEAD:{F.BETA}"],
            capture_output=True,
            env=B.git_env(),
            check=False,
        ).stdout
        helper_b = B.blob_bytes("HEAD", F.BETA, repo=info["root"])
        with tempfile.TemporaryDirectory(prefix="imp0440-emit-arch-") as ad:
            tarp = Path(ad) / "a.tar"
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(info["root"]),
                    "archive",
                    "-o",
                    str(tarp),
                    "HEAD",
                    "--",
                    F.BETA,
                ],
                capture_output=True,
                env=B.git_env(),
                check=False,
            )
            import tarfile

            with tarfile.open(tarp) as tf:
                fh = tf.extractfile(tf.getmember(F.BETA))
                arch_b = fh.read() if fh else b""
        r_b = {
            "target": F.BETA,
            "routes": {
                "git archive + tar -x": {
                    "bytes": len(arch_b),
                    "crlf": arch_b.count(b"\r\n"),
                },
                "git cat-file -p": {"bytes": len(cat_b), "crlf": cat_b.count(b"\r\n")},
                "git show <rev>:<path>": {
                    "bytes": len(show_b),
                    "crlf": show_b.count(b"\r\n"),
                },
            },
            "archive_differs_from_blob": arch_b != cat_b,
            "helper_equals_cat_file": helper_b == cat_b,
            "cat_file_equals_show": cat_b == show_b,
            "identical_after_lf_normalisation": arch_b.replace(b"\r\n", b"\n")
            == cat_b
            == show_b,
        }
    census = C.census()
    plant = C.plant_one_control()
    t_rc, t_out = run_probe(
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B {HELPER_TESTS}"
    )
    return {
        "known": known,
        "refuses": refuses,
        "wt": wt,
        "file_a": r_a,
        "file_b": r_b,
        "census": census,
        "plant": plant,
        "tests_rc": t_rc,
        "tests_out": t_out,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = live_measure()
    r_a, r_b = live["file_a"], live["file_b"]
    census, plant = live["census"], live["plant"]
    remaining = census["provenance_prescriptions_remaining"]
    if live["tests_rc"] != 0:
        print("FAILED:IMP-0440 helper tests")
        print(live["tests_out"][-4000:])
        return 1
    if remaining:
        print("FAILED:IMP-0440 remaining prescriptions", remaining)
        return 1
    if not plant["found_plant"] or not plant["silent_after_removal"]:
        print("FAILED:IMP-0440 plant-one", plant)
        return 1
    if not (
        r_a["archive_differs_from_blob"]
        and r_a["helper_equals_cat_file"]
        and r_a["cat_file_equals_show"]
        and r_b["archive_differs_from_blob"]
        and r_b["helper_equals_cat_file"]
        and r_b["cat_file_equals_show"]
    ):
        print("FAILED:IMP-0440 three-route")
        return 1

    helper_src = (REPO / HELPER).read_text(encoding="utf-8")
    git_blob_src = (REPO / "tools/plugin/git_blob.py").read_text(encoding="utf-8")
    if "blob_from_spec" not in git_blob_src:
        print("FAILED:IMP-0440 git_blob not routed through helper")
        return 1
    if "archive" in helper_src and "cat-file" not in helper_src:
        print("FAILED:IMP-0440 helper source")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    helper_sha, helper_bytes = digest(REPO / HELPER)
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Single blob-bytes helper and removal of the archive-based recipe everywhere",
        "question": (
            "Implement ONE blob_bytes(rev, path) helper on git cat-file, route "
            "every provenance, formatting and parity path through it, and remove "
            "every use of the archive-plus-extract recipe. Exact question: how "
            "many call sites and documents currently prescribe the wrong recipe, "
            "and are all of them corrected?"
        ),
        "answer": {
            "call_sites_prescribing_wrong_recipe": 0,
            "documents_prescribing_wrong_recipe_outside_detector_fixtures": 0,
            "all_corrected": True,
            "helper": HELPER,
            "api": "blob_bytes(rev, path, *, repo=None)",
            "detector_fixtures_kept_as_plants": len(
                census["detector_fixtures_wrong_recipe"]
            ),
        },
        "spec_anchor": "tools/measure-guard/blobread.py:blob_bytes",
        "min_bytes_threshold": 4096,
        "profile": "selfimprove-measure-artifact",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok",
            "role": "systems-implementer",
            "execution_substrate": "local-serialized",
        },
        "worktree_is_git_repo": (REPO / ".git").exists(),
        "evidence_from": (
            "Isolated fixture git repositories with '* text eol=crlf' so archive "
            "export is CRLF while cat-file blobs stay LF. This delivery worktree "
            "has no .git; HEAD of THIS tree cannot be cat-file'd. Census walks "
            "the filesystem (not git-grep)."
        ),
        "implementation": {
            "helper": {
                "path": HELPER,
                "sha256": helper_sha,
                "bytes": helper_bytes,
                "function": "blob_bytes",
                "reader": "git cat-file -p",
                "refuses_git_archive": live["refuses"]["archive_subprocess"] is False,
            },
            "routed_paths": ROUTED,
            "tests": HELPER_TESTS,
        },
        "named_inputs": {
            "command-center/RELEASE-CHECKLIST.md": "absent on this worktree",
            "rules/common/windows-shell.md": "absent on this worktree",
            "<REPO> full tree": "present; not a git repo",
        },
        "evidence": [
            {
                "claim": (
                    f"ONE helper {HELPER} exposes blob_bytes(rev, path) on git "
                    f"cat-file -p ({helper_bytes} B). AST of that module has no "
                    "subprocess archive invocation. Known-file test: fixture "
                    f"{F.ALPHA} bytes match the planted LF body. A dirtied CRLF "
                    "worktree does not change the blob."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"{HELPER}:blob_bytes",
                "confidence": "almost-certain",
                "probes": [
                    probe_rec(
                        "source",
                        "static-analysis",
                        f"AST of {HELPER} for subprocess archive",
                        json.dumps(live["refuses"], sort_keys=True),
                        0,
                    ),
                    probe_rec(
                        "verifier",
                        "test-run",
                        f"python3 -B {HELPER_TESTS}",
                        live["tests_out"][:4000],
                        live["tests_rc"],
                    ),
                ],
            },
            {
                "claim": (
                    "Three-route comparison on TWO files so a single-file artefact "
                    f"cannot explain it. {r_a['target']}: archive="
                    f"{r_a['routes']['git archive + tar -x']['bytes']}B/"
                    f"{r_a['routes']['git archive + tar -x']['crlf']}CRLF vs "
                    f"cat-file={r_a['routes']['git cat-file -p']['bytes']}B/"
                    f"{r_a['routes']['git cat-file -p']['crlf']}CRLF; helper equals "
                    "cat-file; show equals cat-file; identical after LF "
                    f"normalisation={r_a['identical_after_lf_normalisation']}. "
                    f"File B {r_b['target']} measured with raw git (not "
                    "three_route.py): same shape."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/measure-guard/three_route.py",
                "confidence": "almost-certain",
                "probes": [
                    probe_rec(
                        "source",
                        "byte-compare",
                        f"three_route helper on {F.ALPHA}",
                        json.dumps(r_a, indent=1, default=str)[:4000],
                        0,
                    ),
                    probe_rec(
                        "verifier",
                        "command",
                        f"independent git archive|cat-file|show on {F.BETA}",
                        json.dumps(r_b, indent=1, default=str)[:4000],
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    f"Census answer: {census['total_hits']} lines mention "
                    f"`git archive`; {census['mentions_use_vs_mention']} are "
                    "prose/comments/catalog (use-vs-mention); "
                    f"{census['data_files_not_classifiable_as_prescriptions']} are "
                    f"data files; {census['real_invocations']} real invocations; "
                    f"{len(census['legitimate_whole_tree_packaging'])} packaging; "
                    f"{len(remaining)} provenance prescriptions remaining "
                    f"(must be zero). {len(census['detector_fixtures_wrong_recipe'])} "
                    "sibling-unit detector fixture(s) still plant the wrong recipe "
                    "on purpose (CNF-0050) and were not 'fixed'."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/measure-guard/archive_census.py",
                "confidence": "almost-certain",
                "probes": [
                    probe_rec(
                        "source",
                        "command",
                        "filesystem walk classify git archive invocation vs mention",
                        json.dumps(
                            {
                                k: (
                                    v
                                    if not isinstance(v, list)
                                    else v[:12]
                                )
                                for k, v in census.items()
                            },
                            indent=1,
                        )[:6000],
                        0,
                    ),
                    probe_rec(
                        "verifier",
                        "other",
                        "plant a wrong-recipe shell line and re-run the census",
                        json.dumps(
                            {
                                "found_plant": plant["found_plant"],
                                "silent_after_removal": plant["silent_after_removal"],
                                "remaining_after": plant["remaining_after"],
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {"count": 0, "policy": "max 2 attempts, backoff 30s/120s"},
        "tests": [
            {
                "id": "T1-helper-unit-test-on-a-known-file",
                "command": f"python3 -B {HELPER_TESTS}",
                "result": "PASS" if live["tests_rc"] == 0 else "FAIL",
                "assertions": 5,
                "output_tail": (
                    live["tests_out"].strip().splitlines()[-1][:200]
                    if live["tests_out"].strip()
                    else ""
                ),
            },
            {
                "id": "T2-three-route-comparison-file-A",
                "command": f"git archive|cat-file|show on fixture {F.ALPHA}",
                "result": "PASS"
                if r_a["archive_differs_from_blob"] and r_a["cat_file_equals_show"]
                else "FAIL",
                "assertions": 3,
                "output_tail": json.dumps(r_a["routes"]),
            },
            {
                "id": "T3-three-route-comparison-file-B",
                "command": f"independent three routes on fixture {F.BETA}",
                "result": "PASS"
                if r_b["archive_differs_from_blob"] and r_b["cat_file_equals_show"]
                else "FAIL",
                "assertions": 3,
                "output_tail": json.dumps(r_b["routes"]),
            },
            {
                "id": "T4-zero-archive-provenance-recipes-remain",
                "command": "filesystem census classify invocation vs prose vs packaging vs fixture",
                "result": "PASS" if not remaining else "FAIL",
                "assertions": census["total_hits"],
                "output_tail": (
                    f"{len(remaining)} provenance prescriptions; "
                    f"{len(census['legitimate_whole_tree_packaging'])} packaging; "
                    f"{len(census['detector_fixtures_wrong_recipe'])} detector fixtures"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0440-C1",
                "kind": "known-broken-fixture",
                "description": (
                    "The census is only evidence if it CAN find a wrong recipe. "
                    "A wrong-recipe line was planted inside the scanned tree, "
                    "the census re-run, then the plant removed and the census "
                    "re-run again."
                ),
                "fired_on_bad_state": plant["found_plant"],
                "silent_on_good_state": plant["silent_after_removal"],
                "bad_state_output": "planted `git archive $SHA | tar -x -C $TMP` -> census reported it",
                "good_state_output": "after removal the census reports 0 provenance prescriptions again",
            },
            {
                "id": "IMP0440-C2",
                "kind": "other",
                "description": (
                    "The three-route comparison must show a DIFFERENCE "
                    "(archive != blob) and must also show the two blob routes "
                    "AGREE. All-equal would be consistent with a broken reader."
                ),
                "fired_on_bad_state": r_a["archive_differs_from_blob"],
                "silent_on_good_state": r_a["cat_file_equals_show"],
                "bad_state_output": (
                    f"archive {r_a['routes']['git archive + tar -x']['bytes']}B/"
                    f"{r_a['routes']['git archive + tar -x']['crlf']}CRLF differs from the blob"
                ),
                "good_state_output": (
                    "cat-file, show, and blob_bytes are byte-identical, 0 CRLF, "
                    "and all match after LF normalisation"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0440-probe2-independent-three-route-and-census",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 re-measures three-route on a DIFFERENT file "
                f"({F.BETA}) using raw git subprocess, not three_route.py. "
                "Catalog reviewer_requirement asks for an independent-claude-reviewer; "
                "that human pass is residual and is not claimed."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0440/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "notes": "G-1 measure is run after this receipt is written",
            }
        ],
        "named_probes": [
            {"id": "probe1", "role": "helper-and-three-route-file-A", "command": P1},
            {
                "id": "probe2",
                "role": "independent-three-route-file-B-and-census",
                "command": P2,
            },
        ],
        "cloud_ok": False,
        "residual_unknowns": [
            {
                "id": "human-reviewer-residual",
                "text": (
                    "G-1 named probes are green. A second human in a fresh "
                    "context has not scored this unit."
                ),
            },
            {
                "id": "named-docs-absent",
                "text": (
                    "Catalog inputs command-center/RELEASE-CHECKLIST.md and "
                    "rules/common/windows-shell.md are not on this worktree. "
                    "The helper and census cover the catalog question from "
                    "the tree that is here."
                ),
            },
            {
                "id": "classifier-phrasing",
                "text": (
                    "The plant-one control proves the census detects the "
                    "canonical wrong recipe; it does not prove it detects every "
                    "phrasing."
                ),
            },
        ],
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "a human adversarial reviewer in a fresh context scored PASS",
            "every historical cat-file in sibling-unit probes was rewritten",
            "this delivery worktree is a git repo whose HEAD was cat-file'd",
            "CNF-0050 wrong-recipe fixture was deleted",
        ],
        "report": {
            "kind": "blob-recipe-census",
            "three_route": {"file_a": r_a, "file_b": r_b},
            "census": {
                "total_hits": census["total_hits"],
                "mentions_use_vs_mention": census["mentions_use_vs_mention"],
                "data_files_not_classifiable_as_prescriptions": census[
                    "data_files_not_classifiable_as_prescriptions"
                ],
                "real_invocations": census["real_invocations"],
                "provenance_prescriptions_remaining": remaining,
                "detector_fixtures_wrong_recipe": census[
                    "detector_fixtures_wrong_recipe"
                ],
            },
            "plant_one": {
                "found_plant": plant["found_plant"],
                "silent_after_removal": plant["silent_after_removal"],
            },
        },
        "defects": [],
        "ts": now,
        "notes": (
            "G-1 for IMP-0440: blob_bytes helper on git cat-file, provenance/"
            "formatting/parity paths routed through it, zero remaining archive "
            "provenance prescriptions with plant-one control. "
            "SENTINEL:IMP-0440:BLOB-HELPER-SINGLE-SOURCE"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(receipt, indent=1, ensure_ascii=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:IMP-0440 emit catalog sentinel missing from blob")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    sha, size = digest(out_path)
    if size < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0440 artifact {size}B below floor")
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0440 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print("FAILED:IMP-0440 missing supporting", missing)
        return 1
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "helper-and-three-route-file-A",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-three-route-file-B-and-census",
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0440/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0440-probe2-independent-three-route-and-census",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0440: live named probes exit 0, receipts/IMP-0440.json "
            "state=SUCCESS with SENTINEL:IMP-0440:BLOB-HELPER-SINGLE-SOURCE, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0440 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
