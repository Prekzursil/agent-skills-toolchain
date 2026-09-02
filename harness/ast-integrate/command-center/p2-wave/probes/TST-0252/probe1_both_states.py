#!/usr/bin/env python3
"""Probe 1: both-states — cat-file PASS, archive FAIL; exit-code mutant is blind."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from docsverify.harness import (  # noqa: E402
    authority_bytes,
    judge,
    judge_exit_code_only,
    run_recipe,
)
from fixture import build_fixture  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0252-probe1 {msg}")
    return 1


def main() -> int:
    built = build_fixture()
    repo = built["repo"]
    rel = built["control_rel"]
    routes = built["routes"]
    authority = authority_bytes(repo, rel)

    archive_cmd = f"git archive HEAD {rel} | tar -xO"
    cat_cmd = f"git cat-file -p HEAD:{rel}"
    run_arch = run_recipe(repo, archive_cmd)
    run_cat = run_recipe(repo, cat_cmd)
    real_arch = judge(run_arch, authority)
    real_cat = judge(run_cat, authority)
    mutant_arch = judge_exit_code_only(run_arch, authority)
    mutant_cat = judge_exit_code_only(run_cat, authority)

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0252",
        "rev": built["rev"],
        "routes": routes,
        "real_harness": {
            "cat-file": {
                "verdict": real_cat["verdict"],
                "reason": real_cat["reason"],
                "exit_code": real_cat["exit_code"],
                "bytes": real_cat["compare"]["got"]["bytes"],
                "crlf": real_cat["compare"]["got"]["crlf"],
            },
            "archive": {
                "verdict": real_arch["verdict"],
                "reason": real_arch["reason"],
                "exit_code": real_arch["exit_code"],
                "bytes": real_arch["compare"]["got"]["bytes"],
                "crlf": real_arch["compare"]["got"]["crlf"],
                "eol_only": real_arch["compare"]["eol_only_difference"],
            },
        },
        "exit_code_only_mutant": {
            "cat-file": mutant_cat["verdict"],
            "archive": mutant_arch["verdict"],
        },
        "pass": False,
    }

    if not routes["catfile_equals_show"]:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("cat-file-and-show-disagree")
    if not routes["archive_differs_from_blob"]:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("archive-did-not-differ-from-blob")
    if not routes["archive_eol_only"]:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("archive-difference-was-not-eol-only")
    arch_crlf = routes["routes"]["git archive | tar -xO"]["crlf"]
    blob_crlf = routes["routes"]["git cat-file -p"]["crlf"]
    if arch_crlf <= 0 or blob_crlf != 0:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail(f"crlf-counts archive={arch_crlf} blob={blob_crlf}")
    if run_arch.exit_code != 0 or run_cat.exit_code != 0:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("recipe-nonzero-exit")
    if real_cat["verdict"] != "PASS":
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail(f"cat-file-should-pass:{real_cat['reason']}")
    if real_arch["verdict"] != "FAIL" or real_arch["reason"] != "wrong-bytes-eol-only":
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail(f"archive-should-fail-eol:{real_arch['reason']}")
    if mutant_arch["verdict"] != "PASS" or mutant_cat["verdict"] != "PASS":
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("exit-code-mutant-did-not-pass-both")

    payload["pass"] = True
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        "SUCCESS:TST-0252-probe1 cat-file PASS; archive FAIL (wrong-bytes-eol-only "
        f"exit={run_arch.exit_code}); exit-code-only mutant false-green on archive"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
