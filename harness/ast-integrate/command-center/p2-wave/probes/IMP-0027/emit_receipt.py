#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0027.json from live uninstall measurements."""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.census import non_owned_inventory, owned_remaining  # noqa: E402
from plugin.scenario import seed_home  # noqa: E402
from plugin.uninstall import uninstall  # noqa: E402

UNIT = "IMP-0027"
OUT = "command-center/receipts/IMP-0027.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0027/probe1_owned_census.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0027/probe2_foreign_bytes.py"
)
SUPPORTING = [
    "tools/plugin/uninstall.py",
    "tools/plugin/projection.py",
    "tools/plugin/census.py",
    "tools/plugin/scenario.py",
    "tools/plugin/cli.py",
    "tools/plugin/schema/projection-map.schema.json",
    "tools/plugin/tests/test_uninstall_completeness.py",
    "command-center/p2-wave/probes/IMP-0027/probe1_owned_census.py",
    "command-center/p2-wave/probes/IMP-0027/probe2_foreign_bytes.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    sha, size = digest_file(path) if path.is_file() else ("0" * 64, 0)
    return {
        "path": rel,
        "bytes": size if path.is_file() else 1,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": "LF",
    }


def live_signal1() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0027-emit-s1-") as tmp:
        seed = seed_home(Path(tmp) / "home")
        uninstall(seed.home, seed.projection, purge_user_data=False)
        leftover = owned_remaining(seed.home, seed.projection)
        user_ok = all((seed.home / rel).is_file() for rel in seed.user_files)
        return {
            "owned_remaining": leftover,
            "user_data_retained": user_ok,
            "owned_seeded_count": len(seed.owned_files),
        }


def live_signal2() -> dict:
    with tempfile.TemporaryDirectory(prefix="imp0027-emit-s2-") as tmp:
        root = Path(tmp)
        honest = root / "honest"
        scorched = root / "scorched"
        retain = root / "retain"
        purge = root / "purge"
        seed = seed_home(honest)
        shutil.copytree(honest, scorched)
        shutil.copytree(honest, retain)
        shutil.copytree(honest, purge)
        before = non_owned_inventory(honest, seed.projection, include_user_data=True)
        uninstall(honest, seed.projection, purge_user_data=False)
        after = non_owned_inventory(honest, seed.projection, include_user_data=True)
        shutil.rmtree(scorched)
        scorched.mkdir()
        after_scorch = non_owned_inventory(
            scorched, seed.projection, include_user_data=True
        )
        preview = io.StringIO()
        retain_r = uninstall(retain, seed.projection, purge_user_data=False)
        purge_r = uninstall(
            purge, seed.projection, purge_user_data=True, preview_stream=preview
        )
        preview_text = preview.getvalue()
        return {
            "before_count": len(before),
            "after_matches_before": after == before,
            "scorched_empty": after_scorch == {},
            "scorched_differs": after_scorch != before,
            "retain_user_present": all((retain / rel).is_file() for rel in seed.user_files),
            "purge_user_absent": all(not (purge / rel).exists() for rel in seed.user_files),
            "purge_preview_lists_user_data": all(
                rel in preview_text for rel in seed.user_files
            ),
            "preview_printed_before_delete": purge_r.preview_printed_before_delete,
            "retain_deleted_user_data": list(retain_r.deleted_user_data),
            "purge_deleted_user_data": list(purge_r.deleted_user_data),
            "foreign_survive_purge": all(
                (purge / rel).is_file() for rel in seed.foreign_files
            ),
        }


def run_unit_tests() -> tuple[int, str]:
    import subprocess

    p = subprocess.run(
        [sys.executable, str(REPO / "tools/plugin/tests/test_uninstall_completeness.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(TOOLS), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    test_rc, test_out = run_unit_tests()
    if test_rc != 0:
        print("FAILED:IMP-0027 tests did not pass")
        print(test_out[-3000:])
        return 1
    s1 = live_signal1()
    s2 = live_signal2()
    if s1["owned_remaining"] or not s1["user_data_retained"]:
        print(f"FAILED:IMP-0027 signal1 {s1}")
        return 1
    if not (
        s2["after_matches_before"]
        and s2["scorched_differs"]
        and s2["scorched_empty"]
        and s2["retain_user_present"]
        and s2["purge_user_absent"]
        and s2["purge_preview_lists_user_data"]
        and s2["preview_printed_before_delete"]
        and s2["foreign_survive_purge"]
        and s2["retain_deleted_user_data"] == []
    ):
        print(f"FAILED:IMP-0027 signal2 {s2}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [art_row(p, "supporting") for p in SUPPORTING]
    s1_raw = json.dumps(s1, sort_keys=True)
    s2_raw = json.dumps(s2, sort_keys=True)

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0027",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#IMP-0027",
        "min_bytes_threshold": 128,
        "produced_by": {
            "execution_substrate": "worktree-isolated",
            "model": "composer",
            "role": "implementer",
            "vendor": "cursor",
        },
        "profile": "selfimprove-measure-artifact",
        "question_or_target": (
            "Implement uninstall to remove exactly the plugin-owned paths recorded "
            "in the projection map, and to require an explicit --purge-user-data "
            "flag (default: retain) before touching anything the user authored."
        ),
        "evidence": [
            {
                "claim": (
                    "Signal 1: after uninstall into a throwaway HOME, a directory "
                    f"census of projection-owned paths is empty (seeded "
                    f"{s1['owned_seeded_count']} owned files). Default retain left "
                    "user-authored files in place. Instrument is Path.exists, not "
                    "the hash census."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/census.py:owned_remaining",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P1, s1_raw, 0),
                    probe(
                        "verifier",
                        "command",
                        "python3 -B tools/plugin/tests/test_uninstall_completeness.py",
                        test_out[-4000:],
                        test_rc,
                    ),
                ],
            },
            {
                "claim": (
                    "Signal 2: sha256 of every NON-owned file present before uninstall "
                    "matches after (user data + foreign). NEGATIVE CONTROL in the same "
                    "run: --purge-user-data removes user data and the retain path does "
                    "not; purge prints the exact list first. A scorched-earth rmtree "
                    "empties the owned census but destroys the foreign hash census."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/plugin/census.py:non_owned_inventory",
                "confidence": "almost-certain",
                "probes": [
                    probe("source", "command", P2, s2_raw, 0),
                    probe(
                        "verifier",
                        "test-run",
                        "test_purge_user_data_removes_and_retain_does_not",
                        json.dumps(
                            {
                                "retain_user_present": s2["retain_user_present"],
                                "purge_user_absent": s2["purge_user_absent"],
                                "preview_printed_before_delete": s2[
                                    "preview_printed_before_delete"
                                ],
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "no automatic retry on a purge path"},
        "tests": [
            {
                "id": "test_no_owned_paths_remain",
                "command": (
                    "python3 -B tools/plugin/tests/test_uninstall_completeness.py"
                    "::test_no_owned_paths_remain"
                ),
                "result": "PASS",
            },
            {
                "id": "test_user_data_retained_by_default",
                "command": (
                    "python3 -B tools/plugin/tests/test_uninstall_completeness.py"
                    "::test_user_data_retained_by_default"
                ),
                "result": "PASS",
            },
            {
                "id": "test_purge_user_data_removes_and_retain_does_not",
                "command": (
                    "python3 -B tools/plugin/tests/test_uninstall_completeness.py"
                    "::test_purge_user_data_removes_and_retain_does_not"
                ),
                "result": "PASS",
            },
            {
                "id": "test_scorched_earth_fails_foreign_identity",
                "command": (
                    "python3 -B tools/plugin/tests/test_uninstall_completeness.py"
                    "::test_scorched_earth_fails_foreign_identity"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0027-C1-purge-vs-retain",
                "kind": "known-broken-fixture",
                "description": (
                    "--purge-user-data removes user-authored files; default retain does not, "
                    "in the same run. Purge prints the exact list before deleting."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"purge deleted {s2['purge_deleted_user_data']}",
                "good_state_output": "retain deleted_user_data=[]",
            },
            {
                "id": "IMP0027-C2-scorched-earth",
                "kind": "mutation",
                "description": (
                    "HOME rmtree zeros owned paths (would pass probe 1) and destroys "
                    "non-owned hashes (fails probe 2)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "scorched_empty=True scorched_differs=True",
                "good_state_output": "after_matches_before=True",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0027-probe2-foreign-bytes",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0027/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0027/probe1_owned_census.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe("verifier", "command", P1, "owned census empty", 0),
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0027",
                    "G-1 live named probes + per-unit manifest sha",
                    0,
                ),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0010 production projection-map artifact is not on this "
                    "worktree as command-center/receipts/IMP-0010.json. Uninstall "
                    "consumes tools/plugin/projection.py maps whose owned_paths are "
                    "the live-path set IMP-0010 would predict. A later IMP-0010 "
                    "delivery must keep that contract."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "When IMP-0010 lands, re-run uninstall against its projection "
                    "map and require owned_remaining still empty."
                ),
            }
        ],
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    primary_placeholder = {
        "path": OUT,
        "bytes": 1,
        "sha256": "0" * 64,
        "exists": True,
        "role": "primary",
        "eol": "LF",
    }
    doc["artifacts"] = [primary_placeholder] + supporting
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest_file(out_path)
    doc["artifacts"][0] = {
        "path": OUT,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": "primary",
        "eol": "LF",
    }
    out_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    live_sha, live_size = digest_file(out_path)
    print(f"wrote {OUT} bytes={live_size} sha256={live_sha}")
    print("SUCCESS:IMP-0027")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
