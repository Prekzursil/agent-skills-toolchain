#!/usr/bin/env python3
"""Probe 2: regression seed + independent mutants (name-only vs byte compare)."""

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
    extract_recipes,
    judge,
    judge_name_only,
    run_recipe,
)
from fixture import CONTROL_BODY, build_fixture  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0252-probe2 {msg}")
    return 1


def main() -> int:
    built = build_fixture()
    repo = built["repo"]
    rel = built["control_rel"]
    authority = authority_bytes(repo, rel)
    seed = built["seed_doc"].read_text(encoding="utf-8")
    extracted = extract_recipes(seed, str(built["seed_doc"]))

    kinds = {r.kind for r in extracted}
    judged = []
    for rec in extracted:
        run = run_recipe(repo, rec.command)
        real = judge(run, authority)
        judged.append(
            {
                "kind": rec.kind,
                "command": rec.command,
                "line": rec.line,
                "path": rec.path,
                "verdict": real["verdict"],
                "reason": real["reason"],
                "exit_code": real["exit_code"],
                "eol_only": real["compare"]["eol_only_difference"],
                "got_crlf": real["compare"]["got"]["crlf"],
                "got_bytes": real["compare"]["got"]["bytes"],
            }
        )

    archive_rows = [j for j in judged if j["kind"] == "archive"]
    cat_rows = [j for j in judged if j["kind"] == "cat-file"]

    # Planted non-git recipe: exit 0, CRLF bytes, not the string `git archive`.
    crlf_body = CONTROL_BODY.replace("\n", "\r\n")
    planted_cmd = (
        "python3 -c \"import sys; sys.stdout.buffer.write("
        + repr(crlf_body.encode('ascii'))
        + ")\""
    )
    planted_run = run_recipe(repo, planted_cmd)
    planted_real = judge(planted_run, authority)
    planted_name = judge_name_only(planted_run, authority)

    good_cmd = f"git cat-file -p HEAD:{rel}"
    good_run = run_recipe(repo, good_cmd)
    good_name = judge_name_only(good_run, authority)

    payload = {
        "probe": "probe2-regression-seed",
        "unit_id": "TST-0252",
        "seed_doc": str(built["seed_doc"].relative_to(REPO)),
        "extracted_n": len(extracted),
        "extracted_kinds": sorted(kinds),
        "judged": judged,
        "planted_nongit_wrong_bytes": {
            "command": planted_cmd[:120],
            "exit_code": planted_run.exit_code,
            "real_verdict": planted_real["verdict"],
            "real_reason": planted_real["reason"],
            "name_only_verdict": planted_name["verdict"],
            "name_only_reason": planted_name["reason"],
            "eol_only": planted_real["compare"]["eol_only_difference"],
        },
        "name_only_on_catfile": good_name["verdict"],
        "pass": False,
    }

    if "archive" not in kinds:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("extractor-missed-git-archive-seed")
    if "cat-file" not in kinds:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("extractor-missed-git-cat-file-control")
    if not archive_rows:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("no-archive-row")
    if any(r["exit_code"] != 0 for r in archive_rows):
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("archive-recipe-did-not-run")
    if any(r["verdict"] != "FAIL" for r in archive_rows):
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("archive-seed-not-caught")
    if any(not r["eol_only"] for r in archive_rows):
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("archive-seed-not-eol-only")
    if not cat_rows or any(r["verdict"] != "PASS" for r in cat_rows):
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("cat-file-seed-did-not-pass")

    # Prose mention of `git archive` must not become a third recipe.
    if len(extracted) != 2:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail(f"extractor-overclaim-n={len(extracted)}")

    if planted_run.exit_code != 0:
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("planted-nonzero")
    if planted_real["verdict"] != "FAIL":
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("real-harness-missed-nongit-wrong-bytes")
    if planted_name["verdict"] != "PASS":
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("name-only-mutant-did-not-false-green-on-nongit")
    if good_name["verdict"] != "PASS":
        print(json.dumps(payload, sort_keys=True, default=str))
        return fail("name-only-mutant-failed-catfile")

    payload["pass"] = True
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        "SUCCESS:TST-0252-probe2 RELEASE-CHECKLIST git-archive seed FAIL "
        "(eol-only); cat-file PASS; name-only mutant misses planted non-git "
        "wrong-bytes which the real harness catches"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
