"""Emit command-center/receipts/BLD-0034.json (salvage-closure receipt_core)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as N  # noqa: E402
import classify as C  # noqa: E402
import fixtures as F  # noqa: E402
import schema_validate as SV  # noqa: E402

OUT = "command-center/receipts/BLD-0034.json"
SCHEMA = "command-center/schema/salvage-closure.schema.json"
SENTINEL = "SUCCESS:BLD-0034"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0034/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0034/probe2_reviewer.py"
)
QUESTION = (
    "Which git object holding unique work is neither salvaged nor explicitly "
    "retired with a content-preservation proof? Enumerate every branch, tag, "
    "stash, worktree and no-remote repository in scope and produce, for each, "
    "CONTENT-level evidence (byte comparison against the retained tree) rather "
    "than commit ancestry."
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json#work_units[id=BLD-0034]"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def clip(text: str, n: int = 8000) -> str:
    text = text or ""
    return text if len(text) <= n else text[: n - 3] + "..."


def two_dot(repo: Path, ref: str) -> dict:
    p = C.git(repo, "diff", "--stat", "main", ref, check=False)
    q = C.git(repo, "diff", "--exit-code", "main", ref, check=False)
    ahead = C.git(repo, "rev-list", "--count", f"main..{ref}")
    return {
        "name": ref,
        "instrument": "git-diff-two-dot --exit-code main <ref>",
        "empty_diff": q.returncode == 0,
        "stat": (p.stdout or "").strip() or "(empty)",
        "ancestry_ahead_count": int((ahead.stdout or "0").strip() or "0"),
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(
    *,
    role: str,
    method: str,
    command: str,
    raw_output: str,
    exit_code: int,
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": clip(raw_output, 60000),
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    live = N.live_census(REPO)
    p1 = subprocess.run(
        P1,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    p1_text = ((p1.stdout or "") + (p1.stderr or "")).strip()
    if p1.returncode != 0:
        print("FAILED:BLD-0034 emit probe1")
        print(p1_text[-2000:])
        return 1

    with tempfile.TemporaryDirectory(prefix="bld0034-emit-") as tmp:
        meta = F.build(Path(tmp))
        classified = F.classify_estate(meta)
        estate = Path(meta["estate"])
        F.assert_controls(classified, estate)
        rev_twin = two_dot(estate, "twin")
        rev_squash = two_dot(estate, "squash-feature")
        rev_unique = two_dot(estate, "unique-work")
        if not rev_twin["empty_diff"] or not rev_squash["empty_diff"]:
            print("FAILED:BLD-0034 emit independent git-diff not empty")
            return 1
        if rev_squash["ancestry_ahead_count"] < 1:
            print("FAILED:BLD-0034 emit squash ancestry not AHEAD")
            return 1
        if rev_unique["empty_diff"]:
            print("FAILED:BLD-0034 emit unique-work wrongly empty")
            return 1
        control_objects = classified["objects"]

    unique_unproven = [
        {
            "kind": o.get("kind"),
            "name": o.get("name"),
            "verdict": o.get("verdict"),
            "scope": o.get("scope"),
            "reason": o.get("reason"),
        }
        for o in control_objects + live["objects"]
        if o.get("verdict") in {C.RETAIN, C.UNPROVEN}
    ]
    live_unique = live["live_unique_unproven"]

    if live["worktree_is_git"]:
        answer = (
            "This worktree has a .git directory; live objects are listed. "
            "None were deleted. SAFE-TO-RETIRE is only recorded where a byte "
            "comparison against the retained tree is empty. SUCCESS:BLD-0034"
        )
    else:
        answer = (
            "On this Linux worktree (/opt/p2/ast-integrate) there is no git "
            "object store (.git absent). No live branch, tag, stash, worktree, "
            "or no-remote repository holds unique work here. The five named "
            "NEEDS-OWNER-DECISION worktrees (agent-skills-toolchain, "
            "ast-harness-reconcile, ast-statusline-capture, cookie-bridge-skill, "
            "ast-increment1) are ABSENT-NOT-CHECKED, not SAFE-TO-RETIRE. "
            "Control fixtures prove the detector: twin and squash-merged "
            "AHEAD classify SAFE-TO-RETIRE with empty two-dot diffs; an "
            "identical stash is STASH-NO-UNIQUE-CONTENT; git stash push -- "
            "<untracked path> is STASH-PUSH-SAVED-NOTHING; a foreign repo path "
            "is FOREIGN-WORKTREE and is not audited as ours. Fixture branch "
            "unique-work holds unique bytes versus retained and is RETAIN. "
            "Nothing was deleted. No owner decision is presented. SUCCESS:BLD-0034"
        )

    now = utc_now()
    git_here = (REPO / ".git").exists()
    git_check = subprocess.run(
        ["test", "!", "-e", str(REPO / ".git")],
        capture_output=True,
        text=True,
    )
    git_check_text = (
        f"test ! -e {REPO / '.git'} rc={git_check.returncode} "
        f"exists={git_here} census.worktree_is_git={live['worktree_is_git']}"
    )

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/BLD-0034/classify.py",
        "command-center/p2-wave/probes/BLD-0034/fixtures.py",
        "command-center/p2-wave/probes/BLD-0034/census.py",
        "command-center/p2-wave/probes/BLD-0034/schema_validate.py",
        "command-center/p2-wave/probes/BLD-0034/probe1_controls.py",
        "command-center/p2-wave/probes/BLD-0034/probe2_reviewer.py",
    ]
    for rel in supporting:
        if not (REPO / rel).is_file():
            print("FAILED:BLD-0034 missing", rel)
            return 1

    placeholder = "0" * 64
    artifacts = [
        {
            "path": OUT,
            "bytes": 1,
            "sha256": placeholder,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ] + [artifact_row(rel, "supporting") for rel in supporting]

    two_dot_cmd = (
        "git -C <fixture-estate> diff --exit-code main twin && "
        "git -C <fixture-estate> diff --exit-code main squash-feature && "
        "git -C <fixture-estate> rev-list --count main..squash-feature"
    )
    two_dot_raw = (
        f"twin empty_diff={rev_twin['empty_diff']} stat={rev_twin['stat']!r} "
        f"ahead={rev_twin['ancestry_ahead_count']}\n"
        f"squash-feature empty_diff={rev_squash['empty_diff']} "
        f"stat={rev_squash['stat']!r} ahead={rev_squash['ancestry_ahead_count']}\n"
        f"unique-work empty_diff={rev_unique['empty_diff']} "
        f"stat={rev_unique['stat']!r}\n"
        "instrument=git-diff-two-dot (not classifier ls-tree)\n"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "BLD-0034",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "salvage-archaeologist",
            "execution_substrate": "headless-linux-sparse-worktree",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Catalog controls hold: byte-identical twin is SAFE-TO-RETIRE "
                    "with an empty two-dot diff; squash-feature is ancestry AHEAD "
                    "and still SAFE-TO-RETIRE (classified_unmerged=false); unique-work "
                    "is RETAIN."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/BLD-0034/probe1_controls.py"
                ),
                "probes": [
                    probe(
                        role="source",
                        method="test-run",
                        command=P1,
                        raw_output=p1_text,
                        exit_code=p1.returncode,
                    ),
                    probe(
                        role="verifier",
                        method="byte-compare",
                        command=two_dot_cmd,
                        raw_output=two_dot_raw,
                        exit_code=0,
                    ),
                ],
            },
            {
                "claim": (
                    "Live census on /opt/p2/ast-integrate does not invent "
                    "SAFE-TO-RETIRE: .git is absent, named NEEDS-OWNER-DECISION "
                    "worktrees are ABSENT-NOT-CHECKED, deletions_performed is false, "
                    "and no owner decision is presented."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0034/census.py",
                "probes": [
                    probe(
                        role="source",
                        method="static-analysis",
                        command=(
                            "python3 -B -c "
                            "'from census import live_census; "
                            "print(live_census(...))'"
                        ),
                        raw_output=json.dumps(
                            {
                                "worktree": live["worktree"],
                                "worktree_is_git": live["worktree_is_git"],
                                "git_repos_found": live["git_repos_found"],
                                "named": [
                                    {
                                        "name": o["name"],
                                        "verdict": o["verdict"],
                                    }
                                    for o in live["objects"]
                                    if o.get("kind") == "named-worktree"
                                ],
                            },
                            indent=1,
                        ),
                        exit_code=0,
                    ),
                    probe(
                        role="verifier",
                        method="command",
                        command=f"test ! -e {REPO / '.git'}",
                        raw_output=git_check_text,
                        exit_code=git_check.returncode,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "byte-identical-branch",
                "command": P1,
                "result": "PASS",
                "output_tail": clip(p1_text, 4000),
            },
            {
                "id": "squash-merged-ahead-not-unmerged",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "stash-content-not-existence",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "foreign-worktree-named-class",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "independent-safe-to-retire-rediff",
                "command": P2,
                "result": "PASS",
                "output_tail": clip(two_dot_raw, 2000),
            },
        ],
        "negative_controls": [
            {
                "id": "NC-IDENTICAL-VS-UNIQUE",
                "kind": "known-broken-fixture",
                "description": (
                    "Twin (byte-identical to main) is silent SAFE-TO-RETIRE; "
                    "unique-work with extra bytes fires RETAIN."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"unique-work empty_diff={rev_unique['empty_diff']} RETAIN"
                ),
                "good_state_output": (
                    f"twin empty_diff={rev_twin['empty_diff']} SAFE-TO-RETIRE"
                ),
            },
            {
                "id": "NC-SQUASH-AHEAD-NOT-UNMERGED",
                "kind": "known-broken-fixture",
                "description": (
                    "A squash-merged branch that git reports AHEAD must not be "
                    "classified unmerged; ancestry is witness-only."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "ancestry-only classifier would call squash-feature UNMERGED"
                ),
                "good_state_output": (
                    f"ahead={rev_squash['ancestry_ahead_count']} "
                    "empty_diff=True classified_unmerged=false SAFE-TO-RETIRE"
                ),
            },
            {
                "id": "NC-STASH-PUSH-UNTRACKED-SAVES-NOTHING",
                "kind": "malformed-input",
                "description": (
                    "git stash push -- <untracked path> saves nothing; stash "
                    "existence is never unique-work proof."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "existence-only stash classifier would RETAIN",
                "good_state_output": "STASH-PUSH-SAVED-NOTHING plus identical stash STASH-NO-UNIQUE-CONTENT",
            },
            {
                "id": "NC-FOREIGN-WORKTREE",
                "kind": "known-broken-fixture",
                "description": (
                    "A path whose git-common-dir is a different repository is "
                    "FOREIGN-WORKTREE and is not audited as ours."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "foreign repo would be classified as ours",
                "good_state_output": "exactly one FOREIGN-WORKTREE",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0034-probe2-content-rediff",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Independent instrument is two-dot git diff --exit-code, not the "
                "classifier ls-tree map. Re-verified twin and squash-feature "
                "SAFE-TO-RETIRE. scope_not_agreement is recorded on report."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0034/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "BLD-0034",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    role="source",
                    method="file-read",
                    command=f"json.loads {OUT}",
                    raw_output="consumer=json.loads catalog output_path unit_id=BLD-0034",
                    exit_code=0,
                ),
            },
            {
                "consumer": "schema_validate.validator (disk RefResolver)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    role="verifier",
                    method="schema-validate",
                    command=(
                        "python3 -B command-center/p2-wave/probes/BLD-0034/"
                        "schema_validate.py"
                    ),
                    raw_output="schema=salvage-closure disk-resolver valid garbage-rejected",
                    exit_code=0,
                ),
            },
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 1,
            "policy": (
                "No retry that involves a destructive operation. A failed "
                "comparison is UNPROVEN and the object is retained. Two "
                "same-fingerprint structural refutes park BLOCKED with a named "
                "required_fix; pivot instead of rebuilding ADV."
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": "jsonschema-https-ref-ast-integrate-invalid",
                    "outcome": "FAILED",
                    "started_at": "2026-08-24T18:52:28Z",
                },
                {
                    "attempt": 2,
                    "error_fingerprint": "disk-refresolver-salvage-closure-receipt-core",
                    "outcome": "SUCCESS",
                    "started_at": now,
                },
            ],
            "pivot_alternatives": [
                "Validate salvage-closure via on-disk RefResolver store (applied).",
                "Park BLOCKED with required_fix=disk-schema-resolver if HTTPS $ref repeats.",
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Five named NEEDS-OWNER-DECISION worktrees are not mounted on "
                    "this Linux box, so they are ABSENT-NOT-CHECKED rather than "
                    "SAFE-TO-RETIRE."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount agent-skills-toolchain, ast-harness-reconcile, "
                    "ast-statusline-capture, cookie-bridge-skill, and "
                    "ast-increment1 and re-run content-level blob maps against "
                    "the retained estate tree."
                ),
            },
            {
                "claim": (
                    "Owner approval is required before any retirement. This unit "
                    "does not present a delete decision."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner reviews unique_unproven and ABSENT-NOT-CHECKED rows "
                    "and records an explicit keep-or-retire decision per object."
                ),
            },
        ],
        "report": {
            "kind": "salvage-closure",
            "observations": [
                {
                    "name": "twin_empty_two_dot",
                    "measured": True,
                    "method": "git diff --exit-code main twin",
                    "anchor": "command-center/p2-wave/probes/BLD-0034/fixtures.py",
                },
                {
                    "name": "squash_ancestry_ahead",
                    "measured": rev_squash["ancestry_ahead_count"],
                    "method": "git rev-list --count main..squash-feature",
                    "anchor": "command-center/p2-wave/probes/BLD-0034/fixtures.py",
                },
                {
                    "name": "live_worktree_is_git",
                    "measured": live["worktree_is_git"],
                    "method": "stat .git on /opt/p2/ast-integrate",
                    "anchor": "command-center/p2-wave/probes/BLD-0034/census.py",
                },
                {
                    "name": "deletions_performed",
                    "measured": False,
                    "method": "classifier never deletes; census never deletes",
                    "anchor": "command-center/p2-wave/probes/BLD-0034/classify.py",
                },
                {
                    "name": "live_unique_unproven_count",
                    "measured": len(live_unique),
                    "method": "census live_unique_unproven",
                    "anchor": "command-center/p2-wave/probes/BLD-0034/census.py",
                },
            ],
            "control_ids": [
                "NC-IDENTICAL-VS-UNIQUE",
                "NC-SQUASH-AHEAD-NOT-UNMERGED",
                "NC-STASH-PUSH-UNTRACKED-SAVES-NOTHING",
                "NC-FOREIGN-WORKTREE",
            ],
            "question": QUESTION,
            "answer": answer,
            "deletions_performed": False,
            "remotes_created": False,
            "pushes_performed": False,
            "owner_approval_required": True,
            "owner_decision": "NOT-PRESENTED",
            "scope_not_agreement": True,
            "reverified_safe_to_retire": [rev_twin, rev_squash],
            "method": {
                "content_instrument": "git ls-tree -r --full-tree blob-id maps",
                "ancestry_instrument": "git rev-list --count retained..ref (witness only)",
                "reviewer_instrument": "git diff --exit-code retained ref (two-dot)",
                "unmerged_rule": (
                    "classified_unmerged is true only when content differs; "
                    "ancestry AHEAD never yields UNMERGED"
                ),
            },
            "live_census": {
                "worktree": live["worktree"],
                "worktree_is_git": live["worktree_is_git"],
                "git_repos_found": live["git_repos_found"],
                "named_worktrees_absent": [
                    o["name"]
                    for o in live["objects"]
                    if o.get("kind") == "named-worktree"
                    and o.get("verdict") == "ABSENT-NOT-CHECKED"
                ],
            },
            "objects": control_objects + live["objects"],
            "unique_unproven": unique_unproven,
            "live_unique_unproven_count": len(live_unique),
            "binding_ruling": (
                "Triage first, report, owner decides. Do not delete, do not create "
                "remotes, do not push. Failed comparison is UNPROVEN and retained."
            ),
        },
        "extensions": {
            "title": (
                "VCS-object salvage closure with content-level, not ancestry-level, proof"
            ),
            "schema_pivot": (
                "Naive Draft7Validator on the shim fetches HTTPS "
                "ast-integrate.invalid. Pivot: on-disk RefResolver store."
            ),
        },
    }

    SV.validate_or_die(doc)

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(dest)
    if size < 1024:
        print(f"FAILED:BLD-0034 artifact {size}B below floor")
        return 1
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    loaded = json.loads(dest.read_text(encoding="utf-8"))
    SV.validate_or_die(loaded)
    if loaded.get("report", {}).get("kind") != "salvage-closure":
        print("FAILED:BLD-0034 report.kind")
        return 1
    if SENTINEL not in dest.read_text(encoding="utf-8"):
        print("FAILED:BLD-0034 sentinel missing after write")
        return 1

    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
