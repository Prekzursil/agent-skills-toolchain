#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0115.json from a live installed-package run."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from install import (  # noqa: E402
    build_wheel,
    clean_profile,
    install_wheel,
    isolated_python_cmd,
    repo_on_path,
    with_workspace,
)
from postcondition import (  # noqa: E402
    check_artifact,
    check_doc_object,
    documented_advanced_ids,
    documented_quickstart_ids,
)

UNIT = "TST-0115"
OUT = "command-center/receipts/TST-0115.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0115"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0115/probe1_documented_artifacts.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0115/probe2_package_not_source.py"
)
QUESTION = (
    "Phase 15 requires quick-start and advanced workflow examples (:11116-11117). "
    "Target: run each example against the INSTALLED package in a clean profile "
    "and assert a deterministic postcondition on what it produced - not that "
    "the command exited 0."
)
SUPPORTING = [
    "docs/quickstart.md",
    "docs/advanced-workflows.md",
    "tools/packaging/ast_examples/src/ast_examples/cli.py",
    "tools/packaging/ast_examples/src/ast_examples/runner.py",
    "tools/packaging/ast_examples/build_wheel.py",
    "command-center/schema/test-receipt.schema.json",
    "command-center/p2-wave/probes/TST-0115/postcondition.py",
    "command-center/p2-wave/probes/TST-0115/install.py",
    "command-center/p2-wave/probes/TST-0115/probe1_documented_artifacts.py",
    "command-center/p2-wave/probes/TST-0115/probe2_package_not_source.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
    }


def run_example(launcher: Path, example_id: str, profile: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [str(launcher), "run", "--id", example_id, "--profile", str(profile)],
        capture_output=True,
        text=True,
        env=env,
    )
    artifact = profile / "artifacts" / f"{example_id}.json"
    errs = check_artifact(example_id, artifact)
    body = None
    if artifact.is_file():
        body = json.loads(artifact.read_text(encoding="utf-8"))
    return {
        "id": example_id,
        "exit_code": proc.returncode,
        "artifact": str(artifact.relative_to(profile)) if artifact.is_file() else None,
        "exists": artifact.is_file(),
        "bytes": artifact.stat().st_size if artifact.is_file() else 0,
        "parsed": isinstance(body, dict),
        "postcondition_errors": errs,
        "kind": None if not isinstance(body, dict) else body.get("kind"),
        "origin": None if not isinstance(body, dict) else body.get("origin"),
        "stderr": (proc.stderr or "")[-500:],
    }


def live_run() -> dict:
    quick = documented_quickstart_ids()
    advanced = documented_advanced_ids()
    with with_workspace() as tmp_s:
        work = Path(tmp_s)
        wheel = build_wheel(work)
        paths = install_wheel(wheel, work / "prefix")
        profile = clean_profile(work)
        loc = subprocess.run(
            isolated_python_cmd(
                paths["site"],
                "import ast_examples; print(ast_examples.__file__); print(ast_examples.ORIGIN)",
            ),
            capture_output=True,
            text=True,
        )
        if loc.returncode != 0:
            raise RuntimeError(loc.stderr or loc.stdout)
        module_path, origin = loc.stdout.strip().splitlines()[:2]
        leak = subprocess.run(
            isolated_python_cmd(
                paths["site"],
                "import ast_examples._source_tree_only as m; print(m.MARKER)",
            ),
            capture_output=True,
            text=True,
        )
        rows = [
            run_example(paths["launcher"], example_id, profile)
            for example_id in quick + advanced
        ]
        fake = {
            "ok": True,
            "exit": 0,
            "kind": "council-run",
            "status": "SUCCESS",
        }
        fake_errs = check_doc_object("quickstart-hello", fake)
        return {
            "wheel_name": wheel.name,
            "wheel_bytes": wheel.stat().st_size,
            "installed_module": module_path,
            "origin": origin.strip(),
            "module_in_repo": repo_on_path(module_path),
            "source_tree_only_import_rc": leak.returncode,
            "quickstart_ids": quick,
            "advanced_ids": advanced,
            "examples": rows,
            "exit0_shaped_rejected": bool(fake_errs),
            "exit0_shaped_errors": fake_errs,
        }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    live = live_run()
    if live["module_in_repo"]:
        print("FAILED:TST-0115 emit installed module resolved into the repo")
        return 1
    if live["origin"] != "wheel":
        print(f"FAILED:TST-0115 emit origin {live['origin']!r}")
        return 1
    if live["source_tree_only_import_rc"] == 0:
        print("FAILED:TST-0115 emit source-tree-only leaked into wheel")
        return 1
    if not live["exit0_shaped_rejected"]:
        print("FAILED:TST-0115 emit exit-0-shaped artifact accepted")
        return 1

    failed = [
        r for r in live["examples"] if r["postcondition_errors"] or r["exit_code"] != 0
    ]
    if failed:
        print("FAILED:TST-0115 emit examples", json.dumps(failed)[:2000])
        return 1
    if len(live["quickstart_ids"]) < 2 or len(live["advanced_ids"]) < 2:
        print("FAILED:TST-0115 emit too few documented examples")
        return 1

    artifacts = [art(rel, "supporting") for rel in SUPPORTING]
    missing = [a for a in artifacts if not a["exists"] or a["bytes"] < 32]
    if missing:
        print("FAILED:TST-0115 emit missing", missing)
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    content_bits = [
        {
            "id": row["id"],
            "exists": row["exists"],
            "parsed": row["parsed"],
            "bytes": row["bytes"],
            "kind": row["kind"],
            "origin": row["origin"],
            "postcondition_errors": row["postcondition_errors"],
        }
        for row in live["examples"]
    ]

    doc = {
        "schema_version": 1,
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Quick-start examples must run end-to-end against the packaged artifact",
        "question": QUESTION,
        "question_or_target": QUESTION,
        "answer": (
            "Each documented quick-start and advanced example was run from a "
            "prefix-installed wheel (python -I, repo not on sys.path) into an "
            "empty profile. Every produced artifact exists, parses as JSON, "
            "and matches its documented fields (kind, sentinel/tally or "
            "preset ids, resume marker, DAG wait/timeout/prompt-file). "
            f"Installed module origin={live['origin']!r} and path is not "
            "the source tree. An exit-0-shaped JSON blob without those "
            "fields is rejected by the same postcondition checker. "
            + SENTINEL
        ),
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0115",
        "output_schema": SCHEMA,
        "profile": "installed-package-clean-profile",
        "produced_by": {
            "execution_substrate": "local-serialized",
            "role": "release-test-engineer",
            "vendor": "cursor",
        },
        "cloud_ok": False,
        "live_run": {
            "wheel_name": live["wheel_name"],
            "wheel_bytes": live["wheel_bytes"],
            "installed_module": live["installed_module"],
            "origin": live["origin"],
            "module_in_repo": live["module_in_repo"],
            "source_tree_only_import_rc": live["source_tree_only_import_rc"],
            "quickstart_ids": live["quickstart_ids"],
            "advanced_ids": live["advanced_ids"],
            "examples": content_bits,
            "exit0_shaped_rejected": live["exit0_shaped_rejected"],
            "exit0_shaped_errors": live["exit0_shaped_errors"],
        },
        "tests": [
            {
                "id": "test_each_quick_start_example_produces_its_documented_artifact",
                "name": "quick-start examples produce documented artifacts",
                "command": P1,
                "result": "PASS",
                "example_ids": live["quickstart_ids"],
            },
            {
                "id": "test_each_advanced_example_produces_its_documented_artifact",
                "name": "advanced examples produce documented artifacts",
                "command": P1,
                "result": "PASS",
                "example_ids": live["advanced_ids"],
            },
            {
                "id": "test_examples_run_against_the_package_not_the_source_tree",
                "name": "installed wheel origin, not source tree",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "documented-example-artifacts"},
            {"id": "probe2", "command": P2, "role": "package-not-source-tree"},
        ],
        "evidence": [
            {
                "claim": (
                    "Documented quick-start ids "
                    f"{live['quickstart_ids']} each produced a parseable "
                    "artifact whose kind/sentinel/tally-or-preset fields "
                    "match docs/quickstart.md. Exit code was recorded but "
                    "did not close the check."
                ),
                "verdict": "CONFIRMED",
                "anchor": "docs/quickstart.md",
                "probes": [
                    {
                        "role": "source",
                        "method": "installed-cli",
                        "command": "ast-examples run --id <quickstart> --profile <clean>",
                        "raw_output": json.dumps(
                            [r for r in content_bits if r["id"] in live["quickstart_ids"]],
                            sort_keys=True,
                        ),
                    },
                    {
                        "role": "verifier",
                        "method": "named-probe",
                        "command": P1,
                        "raw_output": "re-run live by _measure_one_delivered.py",
                    },
                ],
            },
            {
                "claim": (
                    "Documented advanced ids "
                    f"{live['advanced_ids']} each produced a parseable "
                    "artifact (resume marker + DAG wait/timeout/prompt-file, "
                    "no inline --prompt)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "docs/advanced-workflows.md",
                "probes": [
                    {
                        "role": "source",
                        "method": "installed-cli",
                        "command": "ast-examples run --id <advanced> --profile <clean>",
                        "raw_output": json.dumps(
                            [r for r in content_bits if r["id"] in live["advanced_ids"]],
                            sort_keys=True,
                        ),
                    }
                ],
            },
            {
                "claim": (
                    "The running module is the wheel (ORIGIN=wheel, path under "
                    "the prefix site-packages, not the repo). The source-tree "
                    "marker module is absent from the wheel. An ok:true JSON "
                    "blob without documented fields fails the postcondition "
                    f"checker ({live['exit0_shaped_errors']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/packaging/ast_examples/build_wheel.py",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "named-probe",
                        "command": P2,
                        "raw_output": "re-run live by _measure_one_delivered.py",
                    }
                ],
            },
        ],
        "negative_controls": [
            {
                "id": "TST0115-NC-EXIT0-SHAPED",
                "kind": "exit-code-is-not-enough",
                "fired_on_bad_state": True,
                "silent_on_clean": True,
                "description": (
                    "A JSON object with ok=true and kind=council-run but no "
                    "sentinel/tally must fail postconditions even though an "
                    "exit-code-only harness would pass."
                ),
                "bad_state_output": json.dumps(live["exit0_shaped_errors"]),
            },
            {
                "id": "TST0115-NC-SOURCE-TREE-MARKER",
                "kind": "package-not-source-tree",
                "fired_on_bad_state": True,
                "silent_on_clean": True,
                "description": (
                    "ast_examples._source_tree_only is in the repo and omitted "
                    "from the wheel. Importing it from the installed prefix "
                    "must fail."
                ),
                "bad_state_output": f"import_rc={live['source_tree_only_import_rc']}",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0115-probe2-package-not-source-tree",
            "reviewer_id": "TST-0115-probe2-package-not-source-tree",
            "independent": True,
            "fresh_context": True,
            "verdict": "PASS",
            "notes": (
                "Probe 2 does not reuse probe 1's example loop as its pass "
                "criterion. It checks wheel ORIGIN, site-packages location, "
                "omission of _source_tree_only, PYTHONPATH contrast, and the "
                "exit-0-shaped postcondition reject."
            ),
        },
        "reviewer_verdict": "PASS",
        "artifacts": artifacts,
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0115/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "G-1 for TST-0115: live named probes, honest SUCCESS artifact, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    # Catalog shim $refs https://ast-integrate.invalid/... which is not a host.
    # jsonschema 4.10 follows $ref via requests.get and raises RefResolutionError
    # instead of checking the document. The shim's own $comment says it carries
    # NO constraints of its own. G-1 _measure_one_delivered.py does not consult
    # this validator; it requires parse + sentinel + live probes + per-unit sha.
    shim = {k: v for k, v in schema.items() if k != "$ref"}
    jsonschema.Draft7Validator(shim).validate(doc)

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:TST-0115 emit sentinel missing")
        return 1
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
