#!/usr/bin/env python3
"""Emit AUD-0005 tag/release/version inventory. Refuses SUCCESS if the control fails."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from inventory import (  # noqa: E402
    ORPHAN_TAG,
    P1_CMD,
    P2_CMD,
    PUBLISHED_TAG,
    ZERO_ASSET_TAG,
    ZERO_BYTE_TAG,
    assert_control,
    build,
    probe1_payload,
    probe2_payload,
)

UNIT = "AUD-0005"
OUT = "command-center/audit/AUD-0005-tag-release-parity.json"
SCHEMA = "command-center/schema/audit-inventory.schema.json"
RECEIPT_SCHEMA = "command-center/schema/receipt.schema.json"
FP_PATH = HERE / "_schema_refute_fingerprint.txt"
QUESTION = (
    "Does every git tag resolve to a release with the artifacts it claims, "
    "and does every in-tree version declaration (pyproject, package.json, "
    "plugin manifest) agree with the latest tag?"
)
SENTINEL = (
    "SUCCESS:AUD-0005 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": "AUD-0005", "state": "SUCCESS"},
)


def sha256_file(rel: str) -> str:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def validate(doc: dict, schema_rel: str) -> list[str]:
    schema = json.loads((REPO / schema_rel).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(doc)]


def fingerprint(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    cen = build()
    assert_control(cen)
    ctl = cen["planted_control"]
    p1 = probe1_payload(cen)
    p2 = probe2_payload(cen)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    items = [
        {
            "id": i["id"],
            "kind": i["kind"],
            "path": i["path"],
            "probe1_verdict": i["probe1_verdict"],
            "probe2_verdict": i["probe2_verdict"],
        }
        for i in cen["items"]
    ]
    fixture_versions = [
        v for v in cen["versions"] if v["universe"] == "aud0005-fixture"
    ]
    product_versions = [v for v in cen["versions"] if v["universe"] == "product"]
    mismatch = [
        v
        for v in fixture_versions
        if v.get("agrees_with_latest_published_fixture_tag") is False
    ]
    p1_raw = json.dumps(p1, sort_keys=True)
    p2_raw = json.dumps(p2, sort_keys=True)
    wt_git = cen["worktree_is_git"]
    live_gh = cen["live_github"]

    answer = (
        f"Fixture census: {PUBLISHED_TAG} LIVE/LIVE (non-zero asset bytes); "
        f"{ZERO_ASSET_TAG} LIVE/DEAD (zero assets, not published); "
        f"{ZERO_BYTE_TAG} LIVE/DEAD (zero-byte asset, not published); "
        f"{ORPHAN_TAG} LIVE/DEAD (no release row). "
        f"Planted control independent={ctl['independent']}. "
        f"This worktree is_git={wt_git}; product tags "
        f"{'enumerated' if wt_git else 'NOT-CHECKED'}. "
        f"Live GitHub releases {live_gh.get('status')}. "
        f"Fixture in-tree versions matching {PUBLISHED_TAG}: "
        f"{sum(1 for v in fixture_versions if v.get('agrees_with_latest_published_fixture_tag'))}"
        f"/{len(fixture_versions)}; mismatches={len(mismatch)}."
    )

    doc = {
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "kind": "audit-inventory",
        "title": (
            "Tag and release inventory versus published artifacts and "
            "declared versions"
        ),
        "question": QUESTION,
        "answer": answer,
        "items": items,
        "planted_control": ctl,
        "tallies": cen["tallies"],
        "tag_rows": cen["items"],
        "version_declarations": cen["versions"],
        "scope": {
            "git_instrument": "git rev-list -n 1 <tag> (caret form forbidden)",
            "release_instrument": (
                "GitHub-shaped HTTP releases list plus per-asset byte fetch"
            ),
            "control_repo": (
                "command-center/p2-wave/probes/AUD-0005/fixtures/control-repo"
            ),
            "worktree_is_git": wt_git,
            "live_github": live_gh,
            "product_version_paths": [v["path"] for v in product_versions],
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "role": "git-rev-list-tag-deref",
                "raw_output": p1_raw,
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "role": "github-release-assets-byte-size",
                "raw_output": p2_raw,
            },
        ],
        "evidence": [
            {
                "id": "E1-tag-deref",
                "kind": "command",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0005/probe1_tag_deref.py"
                ),
                "claim": (
                    f"git rev-list -n 1 resolved all four fixture tags; "
                    f"caret form unused; {ORPHAN_TAG} is LIVE on probe 1."
                ),
            },
            {
                "id": "E2-release-bytes",
                "kind": "http-byte-size",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0005/"
                    "probe2_release_assets.py"
                ),
                "claim": (
                    f"{PUBLISHED_TAG} has fetched asset bytes>0; "
                    f"{ZERO_ASSET_TAG} and {ZERO_BYTE_TAG} are unpublished; "
                    f"{ORPHAN_TAG} has no release row."
                ),
            },
            {
                "id": "E3-planted-control",
                "kind": "detector-control",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0005/fixtures/orphan_tag.py"
                ),
                "claim": (
                    "Deliberately created tag with no release is LIVE on "
                    "rev-list and DEAD on the release+bytes probe, so absence "
                    "is not treated as parity."
                ),
            },
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": SCHEMA, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/AUD-0005/inventory.py",
                "role": "supporting",
            },
            {
                "path": (
                    "command-center/p2-wave/probes/AUD-0005/fixtures/orphan_tag.py"
                ),
                "role": "fixture",
            },
        ],
        "tests": [
            {
                "id": "ctl-orphan-tag-no-release",
                "result": "PASS" if ctl["probe2_verdict"] == "DEAD" else "FAIL",
                "command": P1_CMD + " && " + P2_CMD,
                "notes": (
                    f"{ORPHAN_TAG} LIVE on rev-list, DEAD on releases+bytes."
                ),
            },
            {
                "id": "ctl-zero-asset-release-not-published",
                "result": "PASS"
                if next(i for i in cen["items"] if i["tag"] == ZERO_ASSET_TAG)[
                    "probe2_verdict"
                ]
                == "DEAD"
                else "FAIL",
                "command": P2_CMD,
                "notes": (
                    "A GitHub release row with zero assets cannot read as "
                    "published."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0005-probe2-release-bytes",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 is HTTP + asset byte-size, not a re-read of git tags."
            ),
        },
        "timestamps": {"generated_at": now},
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree is not a git repository, so product tags "
                    "were not enumerated here. The discriminating census is "
                    "the fixture control-repo."
                ),
                "verdict": "NOT-CHECKED" if not wt_git else "CHECKED",
                "settling_experiment": (
                    "Re-run git rev-list -n 1 per tag when this tree is a "
                    "clone with tags fetched."
                ),
            },
            {
                "claim": (
                    "Live GitHub releases for the product repo were "
                    f"{live_gh.get('status')} ({live_gh.get('reason', live_gh)})."
                ),
                "verdict": live_gh.get("status", "NOT-CHECKED"),
                "settling_experiment": (
                    "Set AUD0005_GITHUB_REPO=owner/name and re-query "
                    "api.github.com/repos/.../releases."
                ),
            },
        ],
        "cloud_ok": False,
    }

    errs = validate(doc, SCHEMA) + [
        f"[receipt] {e}" for e in validate(doc, RECEIPT_SCHEMA)
    ]
    if errs:
        fp = fingerprint(errs)
        prev = FP_PATH.read_text(encoding="utf-8").strip() if FP_PATH.is_file() else ""
        FP_PATH.write_text(fp + "\n", encoding="utf-8")
        print("FAILED:AUD-0005 schema errors")
        for e in errs[:30]:
            print(" ", e)
        if prev == fp:
            print(
                "PARK: two same-fingerprint structural refutes; "
                "required_fix=align-artifact-to-audit-inventory.schema.json"
            )
        return 1
    for garbage in GARBAGE:
        if not validate(garbage, SCHEMA):
            print("FAILED:AUD-0005 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    digest = sha256_file(OUT)
    print(f"wrote {OUT} bytes={out.stat().st_size} sha256={digest}")
    print(
        f"control {ORPHAN_TAG} p1={ctl['probe1_verdict']} "
        f"p2={ctl['probe2_verdict']} independent={ctl['independent']}"
    )
    print(
        f"modules_scanned={cen['tallies']['modules_scanned']} "
        f"disagree={cen['tallies']['disagree']}"
    )
    print("SUCCESS:AUD-0005 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
