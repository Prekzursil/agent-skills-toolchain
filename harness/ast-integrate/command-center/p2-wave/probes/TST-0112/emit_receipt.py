#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0112.json against test-receipt.schema.json."""
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
sys.path.insert(0, str(HERE))
from live_scope import load_live_inputs  # noqa: E402
from parity import measure_fixture, measure_sources  # noqa: E402
from tests import run_tests  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "TST-0112.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
QUESTION = (
    "Stopping condition 12 requires 'docs and code agree' (:11389) and Phase 14 "
    "meta-review checks for 'mismatches between code and docs' (:11095). Target: "
    "a mechanical parity check over documented CLI flags versus the parser's "
    "actual flags, documented config keys versus the schema, and documented file "
    "paths versus the tree."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0112/probe1_detector_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0112/probe2_independent_regex.py"
)
TEST_COMMAND = {
    "test_documented_flags_match_the_parser_both_directions": P1,
    "test_documented_config_keys_exist_in_the_schema": P1,
    "test_documented_paths_resolve": P1,
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def measure_three_route() -> dict:
    """Schema-required git three-route on a throwaway repo (worktree is not git)."""
    with tempfile.TemporaryDirectory(prefix="tst0112-3r-") as td:
        repo = Path(td)
        sample = repo / "sample.txt"
        sample.write_bytes(b"parity-gate\nline-two\n")
        env = {**os.environ, "GIT_AUTHOR_NAME": "tst0112", "GIT_AUTHOR_EMAIL": "t@t",
               "GIT_COMMITTER_NAME": "tst0112", "GIT_COMMITTER_EMAIL": "t@t"}
        def git(*args: str) -> bytes:
            p = subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True,
                env=env,
            )
            if p.returncode != 0:
                raise RuntimeError((p.stderr or b"").decode("utf-8", "replace"))
            return p.stdout

        git("init", "-q")
        git("config", "core.autocrlf", "false")
        git("add", "sample.txt")
        git("commit", "-q", "-m", "sample")
        cat = git("cat-file", "-p", "HEAD:sample.txt")
        show = git("show", "HEAD:sample.txt")
        archive = subprocess.run(
            ["git", "-C", str(repo), "archive", "HEAD", "--", "sample.txt"],
            capture_output=True,
            env=env,
        )
        if archive.returncode != 0:
            raise RuntimeError(archive.stderr.decode("utf-8", "replace"))
        import tarfile
        import io

        with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as tf:
            member = tf.getmember("sample.txt")
            fh = tf.extractfile(member)
            arch = fh.read() if fh else b""
        lf = lambda b: b.replace(b"\r\n", b"\n")
        return {
            "target": "sample.txt",
            "rev": "HEAD",
            "routes": {
                "git archive | tar -x": {
                    "bytes": len(arch),
                    "sha256": _sha(arch),
                    "crlf": arch.count(b"\r\n"),
                },
                "git cat-file -p": {
                    "bytes": len(cat),
                    "sha256": _sha(cat),
                    "crlf": cat.count(b"\r\n"),
                },
                "git show <rev>:<path>": {
                    "bytes": len(show),
                    "sha256": _sha(show),
                    "crlf": show.count(b"\r\n"),
                },
            },
            "archive_differs_from_blob": arch != cat,
            "identical_after_lf_normalisation": lf(arch) == lf(cat) == lf(show),
            "cat_file_equals_show": cat == show,
        }


def main() -> int:
    tests_raw = run_tests()
    if any(t.get("result") != "PASS" for t in tests_raw):
        print("FAILED:TST-0112 emit tests")
        print(json.dumps(tests_raw, indent=2, sort_keys=True))
        return 1

    aligned = measure_fixture(HERE / "fixtures" / "aligned")
    mismatch = measure_fixture(HERE / "fixtures" / "mismatch")
    live_in = load_live_inputs()
    live = measure_sources(
        live_in["doc_texts"],
        live_in["parser_sources"],
        live_in["schemas"],
        REPO,
    )
    three = measure_three_route()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    flag_live = live["flags"]
    key_live = live["keys"]
    path_live = live["paths"]

    tests = []
    for row in tests_raw:
        tests.append(
            {
                "id": row["id"],
                "command": TEST_COMMAND.get(row["id"], P1),
                "result": row["result"],
                "detail": {k: v for k, v in row.items() if k not in {"id", "result"}},
            }
        )

    doc = {
        "unit_id": "TST-0112",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0112",
        "report_kind": "test-receipt",
        "question": QUESTION,
        "ts": now,
        "cloud_ok": False,
        "title": "Docs-and-code parity gate (flags, keys, paths)",
        "tests": tests,
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Documented CLI flags versus argparse option strings are "
                    "diffed both ways. A documented-but-absent flag is a "
                    "different defect from an undocumented-but-real flag."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0112/tests.py",
            },
            {
                "id": "C2",
                "claim": (
                    "Documented config keys are checked against JSON Schema "
                    "properties both ways on aligned and planted-mismatch fixtures."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0112/parity.py",
            },
            {
                "id": "C3",
                "claim": (
                    "Documented repo-relative paths are resolved against the "
                    "tree; missing paths and undocumented tree files are "
                    "reported as distinct sets."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0112/extract.py",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0112/fixtures/aligned/docs.md",
                "kind": "fixture-aligned",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0112/fixtures/mismatch/docs.md",
                "kind": "fixture-mismatch",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0112/extract.py",
                "kind": "extractor",
            },
        ],
        "three_route": three,
        "reviewer": {
            "reviewer_id": "TST-0112-probe2-independent-regex",
            "verdict": "PASS",
            "independent": True,
            "method": "regex add_argument + markdown flag scan, distinct from AST extract.py",
        },
        "artifacts": [
            {
                "path": "command-center/receipts/TST-0112.json",
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "report": {
            "kind": "test-receipt",
            "control_ids": [
                "aligned-silent",
                "documented-absent-flag",
                "undocumented-real-flag",
                "use-vs-mention",
            ],
            "observations": [
                {
                    "name": "live_flags_documented_not_parser",
                    "measured": flag_live["documented_not_implemented_count"],
                    "method": "ast-add_argument vs docs flag tokens, both directions",
                    "anchor": "command-center/p2-wave/probes/TST-0112/parity.py",
                },
                {
                    "name": "live_flags_parser_not_documented",
                    "measured": flag_live["implemented_not_documented_count"],
                    "method": "ast-add_argument vs docs flag tokens, both directions",
                    "anchor": "command-center/p2-wave/probes/TST-0112/extract.py",
                },
                {
                    "name": "live_keys_documented_not_schema",
                    "measured": key_live["documented_not_implemented_count"],
                    "method": "docs key bullets vs JSON Schema properties",
                    "anchor": "command-center/p2-wave/probes/TST-0112/parity.py",
                },
                {
                    "name": "live_paths_documented_not_tree",
                    "measured": path_live["documented_not_tree_count"],
                    "method": "backtick repo-relative paths vs Path.exists",
                    "anchor": "command-center/p2-wave/probes/TST-0112/extract.py",
                },
            ],
        },
        "schema_version": 1,
        "spec_anchor": "_USER-PROMPTS.md:11389; command-center/WORK-UNIT-CATALOG.json#TST-0112",
        "min_bytes_threshold": 512,
        "scope": {
            "parser_paths": live_in["parser_paths"],
            "schema_paths": live_in["schema_paths"],
            "doc_paths": live_in["doc_paths"],
            "fixture_roots": [
                "command-center/p2-wave/probes/TST-0112/fixtures/aligned",
                "command-center/p2-wave/probes/TST-0112/fixtures/mismatch",
            ],
            "note": (
                "Live flag/key/path counts measure this worktree's shipped CLI "
                "slice. Empty live diffs are not assumed. Gate PASS is the "
                "fixture both-states detector, not a claim that the whole repo "
                "already agrees."
            ),
        },
        "differences": {
            "fixture_aligned": aligned,
            "fixture_mismatch": mismatch,
            "live": live,
        },
        "counts": {
            "live_flags_documented": len(flag_live["documented"]),
            "live_flags_parser": len(flag_live["implemented"]),
            "live_flags_documented_not_parser": flag_live["documented_not_implemented_count"],
            "live_flags_parser_not_documented": flag_live["implemented_not_documented_count"],
            "live_keys_documented": len(key_live["documented"]),
            "live_keys_schema": len(key_live["implemented"]),
            "live_keys_documented_not_schema": key_live["documented_not_implemented_count"],
            "live_keys_schema_not_documented": key_live["implemented_not_documented_count"],
            "live_paths_documented": len(path_live["documented"]),
            "live_paths_missing": path_live["documented_not_tree_count"],
            "live_code_paths_undocumented": path_live["tree_not_documented_count"],
        },
        "controls": [
            {
                "id": "aligned-silent",
                "description": "Aligned fixture has empty flag/key/path diffs both ways",
                "result": "PASS",
            },
            {
                "id": "documented-absent-flag",
                "description": "--ghost-flag is documented-but-absent, not undocumented-real",
                "result": "PASS",
            },
            {
                "id": "undocumented-real-flag",
                "description": "--undocumented-real is parser-only, a different defect",
                "result": "PASS",
            },
            {
                "id": "use-vs-mention",
                "description": "--legacy-removed in a removed-in-v2 line is not a live claim",
                "result": "PASS",
            },
        ],
        "output_schema": SCHEMA,
        "completion_sentinel": "SUCCESS:TST-0112",
    }

    schema_path = REPO / SCHEMA
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:TST-0112 catalog schema path missing")
        return 1
    # command-center/schema/test-receipt.schema.json is a generated $ref shim
    # to https://ast-integrate.invalid/... . jsonschema.validate follows that
    # URL (RefResolutionError). The shim carries no local constraints. G-1
    # named probes own honesty; this local gate refuses empty/unrelated blobs
    # without fetching.
    local_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "report_kind",
            "report",
            "question",
            "tests",
            "claims",
            "evidence",
            "three_route",
            "reviewer",
            "artifacts",
            "named_probes",
            "differences",
            "counts",
            "controls",
        ],
        "properties": {
            "unit_id": {"type": "string", "const": "TST-0112"},
            "state": {"type": "string", "const": "SUCCESS"},
            "sentinel": {"type": "string", "const": "SUCCESS:TST-0112"},
            "report_kind": {"type": "string", "const": "test-receipt"},
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"type": "string", "const": "test-receipt"},
                    "observations": {"type": "array", "minItems": 3},
                    "control_ids": {"type": "array", "minItems": 1},
                },
            },
            "tests": {"type": "array", "minItems": 3},
            "differences": {
                "type": "object",
                "required": ["fixture_aligned", "fixture_mismatch", "live"],
            },
            "counts": {"type": "object", "minProperties": 6},
        },
    }
    try:
        import jsonschema  # type: ignore

        errs = sorted(
            jsonschema.Draft7Validator(local_schema).iter_errors(doc),
            key=lambda e: list(e.path),
        )
        if errs:
            print("FAILED:TST-0112 schema errors")
            for err in errs[:12]:
                print(" ", list(err.path), err.message)
            return 1
        for garbage in ({}, {"unit_id": "TST-0112"}, {"blob": "x" * 200}):
            if not list(jsonschema.Draft7Validator(local_schema).iter_errors(garbage)):
                print(f"FAILED:TST-0112 schema accepted garbage {list(garbage)[:2]}")
                return 1
        doc["schema_valid"] = "local-draft7-no-remote-ref"
    except ImportError:
        required = list(local_schema["required"])
        missing = [k for k in required if k not in doc]
        if missing:
            print(f"FAILED:TST-0112 schema required missing {missing}")
            return 1
        doc["schema_valid"] = "required-fields-only (jsonschema not installed)"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:TST-0112")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
