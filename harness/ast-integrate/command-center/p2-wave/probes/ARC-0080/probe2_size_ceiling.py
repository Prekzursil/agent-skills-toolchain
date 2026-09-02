#!/usr/bin/env python3
"""Probe 2: size ceiling fails rather than warns; independent schema review; live candidate.

Mechanically different from probe1: no planted .git/credential. Exercises the ceiling,
the schema's structural bans (warn, denylist, vacuous garbage), and the evidence
requirement (packed members diffed against the repository tree).
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import packer as P  # noqa: E402

ART = REPO / "command-center/phase4/contracts/ARC-0080.json"
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
CEILING = 5 * 1024 * 1024
TINY_CEILING = 1024


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0080-probe2 {msg}")
    return 1


def schema_errors(schema: dict, instance: object) -> list[str]:
    import jsonschema

    v = jsonschema.Draft202012Validator(schema)
    return [e.message for e in v.iter_errors(instance)]


def main() -> int:
    if not ART.is_file():
        return _fail("contract missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:ARC-0080" not in text:
        return _fail("sentinel absent")
    schema = json.loads(text)
    if str(schema.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return _fail(f"self-declared {schema.get('state')}")

    import jsonschema

    jsonschema.Draft202012Validator.check_schema(schema)
    print("check_schema=ok")

    for i, probe in enumerate(GARBAGE):
        errs = schema_errors(schema, probe)
        print(f"garbage[{i}] errors={len(errs)}")
        if not errs:
            return _fail(f"schema-document-vacuous garbage[{i}] accepted")

    # Consumer call site: real candidate from this repository.
    with tempfile.TemporaryDirectory(prefix="arc0080-p2-live-") as td:
        stage = Path(td)
        P.stage_candidate(stage, REPO)
        live = P.pack_stage(
            stage,
            list(P.CANDIDATE_GLOBS),
            CEILING,
            package_id="a2-typed-registry-pack",
            repo_root=REPO,
        )
        zip_bytes = live.pop("_zip_bytes", None)
        live2 = P.pack_stage(
            stage,
            list(P.CANDIDATE_GLOBS),
            CEILING,
            package_id="a2-typed-registry-pack",
            repo_root=REPO,
        )
        live2.pop("_zip_bytes", None)

    print(
        f"live verdict={live['verdict']} members={live['integrity']['member_count']} "
        f"bytes={live['integrity']['total_bytes']} zip={zip_bytes is not None}"
    )
    if live["verdict"] != "accept" or zip_bytes is None:
        return _fail(f"live candidate rejected: {live.get('failures')}")
    if live["integrity"]["digest"] != live2["integrity"]["digest"]:
        return _fail("two packer runs of the same stage produced different digests")
    if not live["reproducibility"]["repeat_digest_agrees"]:
        return _fail("repeat_digest_agrees is false")

    diff = P.repo_tree_diff(live, REPO)
    print(
        f"repo_diff tree={diff['tree_file_count']} packed={diff['packed_count']} "
        f"omitted={len(diff['omitted_from_scanned_trees'])} extra={diff['packed_not_in_tree']}"
    )
    if not diff["every_included_path_justified"]:
        return _fail(f"unjustified or extra members: {diff}")
    if diff["packed_count"] != len(P.CANDIDATE_PATHS):
        return _fail("packed count != candidate paths")
    # Omitted files in the scanned trees must exist (A2 REFUTATION, generator.py, …)
    # proving the allowlist is not "the whole tree".
    if len(diff["omitted_from_scanned_trees"]) < 1:
        return _fail("allowlist selected the entire scanned tree — not a boundary")
    for rel in P.CANDIDATE_PATHS:
        if rel not in diff["included"]:
            return _fail(f"candidate path missing from packed members: {rel}")

    # Size-ceiling: plant an oversized blob that is NOT on the allowlist.
    with tempfile.TemporaryDirectory(prefix="arc0080-p2-size-") as td:
        stage = Path(td)
        P.stage_candidate(stage, REPO)
        blob = stage / "junk" / "unrelated.bin"
        blob.parent.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(b"X" * (TINY_CEILING + 2048))
        oversized = P.pack_stage(
            stage,
            list(P.CANDIDATE_GLOBS),
            TINY_CEILING,
            package_id="a2-typed-registry-pack",
            repo_root=REPO,
        )
    oz = oversized.pop("_zip_bytes", None)
    print(
        f"oversize verdict={oversized['verdict']} on_exceed={oversized['size_ceiling']['on_exceed']} "
        f"zip={oz is not None} failures={len(oversized['failures'])}"
    )
    if oversized["verdict"] != "reject":
        return _fail("oversize build accepted — ceiling warned or ignored")
    if oversized["size_ceiling"]["on_exceed"] != "fail":
        return _fail("on_exceed is not fail")
    if oz is not None:
        return _fail("oversize reject still emitted an archive")
    size_fails = [f for f in oversized["failures"] if f.get("class") == "size_ceiling"]
    if not size_fails:
        return _fail("no size_ceiling failure class on oversized input")
    named = {f.get("path") for f in size_fails}
    if "junk/unrelated.bin" not in named and "*" not in named:
        return _fail(f"oversize path not named: {named}")
    member_paths = {m["path"] for m in oversized["members"]}
    if "junk/unrelated.bin" in member_paths:
        return _fail("unrelated blob present in members")

    # Independent contract review: warn and denylist are unrepresentable.
    warn = copy.deepcopy(live)
    warn["size_ceiling"]["on_exceed"] = "warn"
    warn_errs = schema_errors(schema, warn)
    print(f"warn_mutant errors={len(warn_errs)}")
    if not warn_errs:
        return _fail("on_exceed=warn was schema-valid — ceiling can warn")

    deny = copy.deepcopy(live)
    deny["content_boundary"]["selection_policy"] = "denylist"
    deny_errs = schema_errors(schema, deny)
    print(f"denylist_mutant errors={len(deny_errs)}")
    if not deny_errs:
        return _fail("denylist selection_policy was schema-valid")

    missing = copy.deepcopy(live)
    del missing["integrity"]
    miss_errs = schema_errors(schema, missing)
    print(f"missing_integrity errors={len(miss_errs)}")
    if not miss_errs:
        return _fail("report without integrity was accepted")

    print("SUCCESS:ARC-0080-probe2 size-ceiling fail-not-warn schema-review live-candidate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
