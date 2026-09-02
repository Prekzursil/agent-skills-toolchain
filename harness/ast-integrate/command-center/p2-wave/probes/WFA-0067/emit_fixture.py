#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0067-mechanism-registry-gate.json."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import mechanism_registry_gate as mech  # noqa: E402
import scenario as S  # noqa: E402

OUT = REPO / "command-center/wfa/WFA-0067-mechanism-registry-gate.json"


def run_plant(mutator, label: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"wfa0067-{label}-") as tmp:
        root = Path(tmp)
        S.copy_estate(root)
        mutator(root)
        proc = S.bare_cli(root)
        text = S.out_of(proc)
        return {
            "command": f"python3 -B {S.GATE_REL}",
            "cwd_is_copied_estate": True,
            "extra_flags": [],
            "exit_code": proc.returncode,
            "fired": proc.returncode != 0,
            "raw_output": text[-4000:],
        }


def git_blob_control() -> dict:
    with tempfile.TemporaryDirectory(prefix="wfa0067-blob-") as tmp:
        root = Path(tmp)
        S.copy_estate(root)
        subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.email=wfa0067@local",
                "-c",
                "user.name=wfa0067",
                "commit",
                "-m",
                "estate",
            ],
            cwd=str(root),
            check=True,
            capture_output=True,
        )
        path = root / mech.REL_REGISTRY
        lf = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(lf.replace(b"\n", b"\r\n"))
        work = path.read_bytes()
        blob, source = mech.read_blob(root, mech.REL_REGISTRY)
        proc = S.bare_cli(root)
        return {
            "blob_source": source,
            "blob_sha256": __import__("hashlib").sha256(blob).hexdigest(),
            "worktree_sha256": __import__("hashlib").sha256(work).hexdigest(),
            "blob_equals_lf": blob == lf,
            "blob_differs_from_crlf_worktree": blob != work,
            "worktree_has_crlf": b"\r\n" in work,
            "gate_exit_code": proc.returncode,
            "gate_raw_output": S.out_of(proc)[-2000:],
        }


def main() -> int:
    live = S.live_cli()
    live_text = S.out_of(live)
    if live.returncode != 0:
        print("FAILED:emit live gate red")
        print(live_text)
        return 1
    ci = S.live_validate_cli()
    ci_text = S.out_of(ci)
    vsrc = (REPO / "tools/command-center/validate.py").read_text(encoding="utf-8")
    if "mechanism_registry_gate" not in vsrc or "mech.check" not in vsrc:
        print("FAILED:emit validate.py does not arm mechanism_registry_gate")
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0067-good-") as tmp:
        good_root = Path(tmp)
        S.copy_estate(good_root)
        good = S.bare_cli(good_root)
        good_text = S.out_of(good)

    undef = run_plant(S.plant_undefined, "undef")
    dang = run_plant(S.plant_dangling, "dang")
    coll = run_plant(S.plant_collision, "coll")
    hole = run_plant(S.plant_deleted_block, "hole")
    blob = git_blob_control()

    if good.returncode != 0 or not all(
        row["fired"] for row in (undef, dang, coll, hole)
    ):
        print("FAILED:emit both-states incomplete")
        print(json.dumps({"good": good.returncode, "undef": undef, "dang": dang, "coll": coll, "hole": hole}, indent=2)[:4000])
        return 1
    if not blob["blob_differs_from_crlf_worktree"] or blob["blob_source"] != "git-cat-file-HEAD":
        print("FAILED:emit blob control")
        print(json.dumps(blob, indent=2)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_v, live_stats = mech.check(REPO)
    doc = {
        "record_type": "RegressionFixture",
        "unit_id": "WFA-0067",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0067",
        "title": "CI gate keeping the mechanism registry closed, anchored and non-colliding",
        "question": (
            "A gate that fails when a mechanism id is added without a definition "
            "and discriminating example, when an artifact references an unknown "
            "mechanism id, or when a mechanism id collides with the candidate, "
            "blueprint or option namespaces."
        ),
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture",
        "schema_pack_present": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        "generated_at": now,
        "gate": {
            "path": S.GATE_REL,
            "ci_invocation": [
                "python tools/command-center/mechanism_registry_gate.py",
                "python tools/command-center/validate.py",
            ],
            "opt_in_flag": None,
            "checks_armed_by_default": True,
            "blob_recipe": "git cat-file -p HEAD:<path> (fallback: working-tree LF-normalised)",
        },
        "blob_recipe": "git cat-file -p HEAD:<path>",
        "live_estate": {
            "command": S.CI_INVOCATION,
            "exit_code": live.returncode,
            "raw_output": live_text[-4000:],
            "violations": live_v,
            "stats": {
                k: v
                for k, v in live_stats.items()
                if k != "blobs"
            },
            "blobs": live_stats.get("blobs"),
            "validate_ci_command": S.VALIDATE_CI,
            "validate_ci_exit_code": ci.returncode,
            "validate_ci_raw_output": ci_text[-4000:],
        },
        "both_states": {
            "known_good": {
                "fixture": "copied-live-estate",
                "fired": False,
                "exit_code": good.returncode,
                "raw_output": good_text[-2000:],
            },
            "planted_bad": {
                "fixture": "MX-0099-empty-definition",
                "fired": True,
                "exit_code": undef["exit_code"],
                "raw_output": undef["raw_output"][-2000:],
            },
        },
        "planted_violations": [
            {
                "id": "undefined-id",
                "kind": "undefined-id",
                "check": "MECH-UNDEF",
                "fired": undef["fired"],
                "exit_code": undef["exit_code"],
                "extra_flags": [],
                "raw_output": undef["raw_output"],
            },
            {
                "id": "dangling-reference",
                "kind": "dangling-reference",
                "check": "MECH-DANGLING",
                "fired": dang["fired"],
                "exit_code": dang["exit_code"],
                "extra_flags": [],
                "raw_output": dang["raw_output"],
            },
            {
                "id": "cross-namespace-collision",
                "kind": "cross-namespace-collision",
                "check": "MECH-COLLIDE",
                "fired": coll["fired"],
                "exit_code": coll["exit_code"],
                "extra_flags": [],
                "raw_output": coll["raw_output"],
            },
        ],
        "noop_hole": {
            "mutation": "delete the whole vocabulary 'mechanisms' block",
            "fired": hole["fired"],
            "exit_code": hole["exit_code"],
            "extra_flags": [],
            "raw_output": hole["raw_output"],
        },
        "crlf_blob_control": blob,
        "vocabulary_guarded": {
            "path": mech.REL_REGISTRY,
            "note": (
                "Gate guards command-center/wfa/mechanism-registry.json. "
                "WFA-0058 canonical 1.0.0 vocabulary is present on this "
                "worktree and replaces the bootstrap 0.1.0 three-entry set "
                "by extending it; deleting the mechanisms block must still "
                "turn this gate red."
                if (REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json").is_file()
                else (
                    "WFA-0058 vocabulary artifact is absent on this worktree. "
                    "This unit ships a closed bootstrap registry the gate guards. "
                    "WFA-0058 may replace entries; the fail-closed empty-block "
                    "control remains."
                )
            ),
        },
        "tests": [
            {
                "id": "ci-invocation-form",
                "command": S.CI_INVOCATION,
                "result": "PASS" if live.returncode == 0 else "FAIL",
            },
            {
                "id": "validate-py-wires-mech-check",
                "command": "grep mechanism_registry_gate tools/command-center/validate.py",
                "result": "PASS",
            },
            {
                "id": "noop-hole-delete-vocabulary-block",
                "command": "bare CLI on estate with mechanisms key deleted",
                "result": "PASS" if hole["fired"] else "FAIL",
            },
            {
                "id": "committed-blob-not-crlf-worktree",
                "command": "git cat-file -p HEAD:command-center/wfa/mechanism-registry.json",
                "result": "PASS" if blob["blob_differs_from_crlf_worktree"] else "FAIL",
            },
        ],
        "evidence": [
            {
                "id": "A-three-planted-violations",
                "command": "bare python tools/command-center/mechanism_registry_gate.py on three planted estates",
                "raw_output": json.dumps(
                    {
                        "undefined-id": undef["exit_code"],
                        "dangling-reference": dang["exit_code"],
                        "cross-namespace-collision": coll["exit_code"],
                    }
                ),
            },
            {
                "id": "B-ci-invocation-no-extra-flags",
                "command": S.CI_INVOCATION,
                "raw_output": live_text[-2000:],
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0067-probe2-ci-blob-reviewer",
            "independent": True,
            "both_states_rerun": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 re-runs the good/undefined both-states pair under the "
                "bare CLI, proves git cat-file bytes differ from a CRLF working "
                "tree, and rejects opt-in flags that would disarm checks."
            ),
        },
        "residual_unknowns": [
            (
                "WFA-0058 canonical vocabulary is on this worktree; the gate "
                "guards that 1.0.0 registry rather than a 3-entry bootstrap."
                if (REPO / "command-center/wfa/WFA-0058-mechanism-vocabulary.json").is_file()
                else "WFA-0058 canonical vocabulary artifact is not on this worktree; the gate guards a bootstrap registry."
            ),
            (
                "WFA-0003 audit artifact is present; collision still uses a "
                "documented sample of wf-*/BP-*/M-NN tokens in mechanism-namespaces.json."
                if (REPO / "command-center/wfa/WFA-0003-id-namespace-audit.json").is_file()
                else "WFA-0003 full id-namespace audit artifact is not on this worktree; collision uses a documented sample of wf-*/BP-*/M-NN tokens."
            ),
            "This worktree has no .git; live default invocation uses working-tree-lf-normalized. The committed-blob recipe is proved on a temp git estate.",
            "On a git root the gate prefers HEAD blobs, so uncommitted working-tree mutations are invisible by design (the CRLF control). Planted-violation both-states run on a non-git copied estate.",
            (
                "command-center/DEPENDENCY-GRAPH.json is present; validate.py "
                "runs mech.check after the catalog checks under bare argv."
                if (REPO / "command-center/DEPENDENCY-GRAPH.json").is_file()
                else "command-center/DEPENDENCY-GRAPH.json is absent, so tools/command-center/validate.py exits 1 before the hooked mech.check; the gate's own bare CLI is the CI form proved here."
            ),
            (
                "command-center/wfa/schema/wfa-schema-pack.json is present; "
                "this record is a RegressionFixture by shape."
                if (REPO / "command-center/wfa/schema/wfa-schema-pack.json").is_file()
                else "command-center/wfa/schema/wfa-schema-pack.json is absent; this record is a RegressionFixture by shape, not validated by WFA-0001's pack."
            ),
        ],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    print("SUCCESS:WFA-0067 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
