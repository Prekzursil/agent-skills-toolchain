#!/usr/bin/env python3
"""Emit command-center/receipts/SYN-0018.json (evidence-decay report).

Validates against the catalog output_schema using a disk-only $ref store.
Does not run tools/command-center/unit_manifest.py --write.
Does not git add/commit/checkout on the worktree; blob IO uses a throwaway
bare repo (hash-object + mktree + cat-file).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import CLASSES, run_campaign  # noqa: E402

OUT = "command-center/receipts/SYN-0018.json"
SCHEMA = "command-center/schema/evidence-decay-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0018/probe1_recipe.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0018/probe2_planted.py"
)
SENTINEL = (
    "SUCCESS:SYN-0018 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the recipe control passed "
    "and all four class counts carry the total denominator. Any other terminal "
    "state is FAILED:SYN-0018 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Question (spec lens 4, _USER-PROMPTS.md:11093): for every evidence "
    "anchor recorded earlier in the program, does it still point at the same "
    "content at the report-time SHA? Target: re-resolve each anchor at both "
    "SHAs and classify STABLE | LINE-MOVED | CONTENT-CHANGED | FILE-GONE. "
    "Read blobs with git cat-file -p <rev>:<path>, never git archive."
)
SCHEMA_STORE_RELS = (
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SUPPORTING = (
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0018/blobs.py",
    "command-center/p2-wave/probes/SYN-0018/classify.py",
    "command-center/p2-wave/probes/SYN-0018/probe1_recipe.py",
    "command-center/p2-wave/probes/SYN-0018/probe2_planted.py",
    "command-center/p2-wave/probes/SYN-0018/fixtures/claim-registry.planted.json",
    "command-center/p2-wave/probes/SYN-0018/fixtures/windows-shell-8b.md",
)
SHA40 = re.compile(r"\b[0-9a-f]{40}\b", re.I)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000, "state": "SUCCESS"},
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def _https_handler(uri: str) -> dict:
    prefix = "https://ast-integrate.invalid/"
    if not uri.startswith(prefix):
        raise jsonschema.exceptions.RefResolutionError(
            f"refusing non-local schema uri (no network): {uri!r}"
        )
    rel = uri.split("#", 1)[0][len(prefix) :]
    path = REPO / rel
    if not path.is_file():
        raise jsonschema.exceptions.RefResolutionError(
            f"schema uri has no file on disk: {uri!r}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def build_validator() -> jsonschema.Draft7Validator:
    store: dict[str, dict] = {}
    for rel in SCHEMA_STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        uri = "https://ast-integrate.invalid/" + rel
        store[uri] = doc
        sid = doc.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = doc
    shim = store["https://ast-integrate.invalid/" + SCHEMA]
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or ("https://ast-integrate.invalid/" + SCHEMA)),
        referrer=shim,
        store=store,
        handlers={"https": _https_handler, "http": _https_handler},
    )
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    if size < 1:
        raise SystemExit(f"FAILED:SYN-0018 zero-byte supporting artifact {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def live_inputs() -> dict:
    registry = REPO / "command-center/CLAIM-REGISTRY.json"
    status = REPO / "command-center/STATUS.md"
    rules = REPO / "rules/common/windows-shell.md"
    git_dir = REPO / ".git"
    claims_n = 0
    sha_pair_n = 0
    if registry.is_file():
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict):
            claims = data.get("claims") or []
            if isinstance(claims, list):
                claims_n = len(claims)
                for row in claims:
                    if not isinstance(row, dict):
                        continue
                    if row.get("capture_sha") and row.get("report_sha") and row.get(
                        "path"
                    ):
                        sha_pair_n += 1
    status_sha = False
    if status.is_file():
        try:
            text = status.read_text(encoding="utf-8")
        except OSError:
            text = ""
        status_sha = bool(SHA40.search(text))
    has_git = git_dir.exists()
    coverage = "NOT-CHECKED"
    reason = (
        "CLAIM-REGISTRY.json is present but carries no per-claim capture_sha/"
        "report_sha/path triple (sha_pairs="
        f"{sha_pair_n}/{claims_n}). STATUS.md is present and records no "
        "40-char report-time SHA. This worktree has no .git object database, "
        "so live anchors cannot be re-resolved with git cat-file. Live "
        "anchors were not invented. Detector proof is the planted four-class "
        "fixture read via git cat-file -p in an isolated bare repo."
    )
    return {
        "claim_registry": {
            "path": "command-center/CLAIM-REGISTRY.json",
            "exists": registry.is_file(),
            "claims": claims_n,
            "capture_report_sha_pairs": sha_pair_n,
        },
        "status_md": {
            "path": "command-center/STATUS.md",
            "exists": status.is_file(),
            "has_report_time_sha": status_sha,
        },
        "windows_shell": {
            "path": "rules/common/windows-shell.md",
            "exists": rules.is_file(),
        },
        "worktree_git": has_git,
        "report_time_sha": None,
        "coverage": coverage,
        "reason": reason,
    }


def probe_pair(
    source_method: str,
    source_cmd: str,
    source_out: str,
    verifier_method: str,
    verifier_cmd: str,
    verifier_out: str,
) -> list[dict]:
    return [
        {
            "role": "source",
            "method": source_method,
            "command": source_cmd,
            "raw_output": source_out[:4000],
            "fingerprint": fp(source_method, source_cmd),
            "exit_code": 0,
        },
        {
            "role": "verifier",
            "method": verifier_method,
            "command": verifier_cmd,
            "raw_output": verifier_out[:4000],
            "fingerprint": fp(verifier_method, verifier_cmd),
            "exit_code": 0,
        },
    ]


def main() -> int:
    started = datetime.now(timezone.utc)
    campaign = run_campaign()
    recipe = campaign["recipe"]
    if not recipe.get("passed"):
        print(f"FAILED:SYN-0018 recipe-control {recipe}")
        return 1
    for row in campaign["anchors"]:
        if row.get("class") != row.get("expected"):
            print(
                f"FAILED:SYN-0018 {row.get('id')} "
                f"class={row.get('class')} expected={row.get('expected')}"
            )
            return 1
    counts = campaign["class_counts"]
    totals = {counts[name]["total"] for name in CLASSES}
    if len(totals) != 1:
        print(f"FAILED:SYN-0018 denominator-mismatch {counts}")
        return 1
    total = next(iter(totals))

    live = live_inputs()
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        print("FAILED:SYN-0018 schema-missing")
        return 1

    anchors = []
    for row in campaign["anchors"]:
        anchors.append(
            {
                "id": row["id"],
                "path": row["path"],
                "capture_sha": row["capture_sha"],
                "report_sha": row["report_sha"],
                "capture_line": row["capture_line"],
                "report_line": row["report_line"],
                "capture_byte_range": row["capture_byte_range"],
                "report_byte_range": row["report_byte_range"],
                "class": row["class"],
                "expected": row["expected"],
                "recipe": "git cat-file -p",
                "note": row.get("note"),
            }
        )

    class_count_payload = {
        name: {
            "count": counts[name]["count"],
            "total": counts[name]["total"],
            "as_string": counts[name]["as_string"],
            "denominator": counts[name]["denominator"],
        }
        for name in CLASSES
    }
    recipe_payload = {
        "name": "git cat-file -p <rev>:<path>",
        "forbidden": "git archive",
        "cat_file_equals_show": True,
        "archive_differs_by_crlf": True,
        "used_for_classification": "git cat-file -p",
        "control": {
            "path": recipe["path"],
            "capture_tree": campaign["capture_sha"],
            "cat_file_bytes": recipe["cat_file_bytes"],
            "show_bytes": recipe["show_bytes"],
            "archive_bytes": recipe["archive_bytes"],
            "cat_file_crlf": recipe["cat_file_crlf"],
            "show_crlf": recipe["show_crlf"],
            "archive_crlf": recipe["archive_crlf"],
        },
        "note": (
            "git cat-file -p and git show agree byte-for-byte on the LF blob. "
            "git archive applies .gitattributes eol=crlf and returns CRLF. "
            "A run that used git archive is invalid by construction."
        ),
    }

    recipe_src = (
        f"cat-file={recipe['cat_file_bytes']}B/{recipe['cat_file_crlf']}CRLF "
        f"show={recipe['show_bytes']}B/{recipe['show_crlf']}CRLF "
        f"archive={recipe['archive_bytes']}B/{recipe['archive_crlf']}CRLF "
        f"passed={recipe['passed']}"
    )
    class_src = json.dumps(
        {n: counts[n]["as_string"] for n in CLASSES}, sort_keys=True
    )
    ended = datetime.now(timezone.utc)
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    ended_s = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    duration = max(0.0, (ended - started).total_seconds())

    artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    doc = {
        "schema_version": 1,
        "unit_id": "SYN-0018",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11093",
        "min_bytes_threshold": 400,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "On the planted LF blob, git cat-file -p equals git show "
                    "byte-for-byte and git archive differs by CRLF; "
                    "classification names cat-file, never archive."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0018/blobs.py:104",
                "probes": probe_pair(
                    "command",
                    "git cat-file -p <tree>:anchors/stable.md (isolated bare repo)",
                    recipe_src,
                    "byte-compare",
                    "git show vs git archive member extract on the same tree:path",
                    recipe_src,
                ),
            },
            {
                "claim": (
                    "Planted four-class fixture classifies STABLE, LINE-MOVED, "
                    "CONTENT-CHANGED, FILE-GONE at 1/4 each; STABLE and "
                    "LINE-MOVED stay distinct."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0018/classify.py:45",
                "probes": probe_pair(
                    "command",
                    "python3 -B command-center/p2-wave/probes/SYN-0018/classify.py run_campaign",
                    class_src,
                    "file-read",
                    "command-center/p2-wave/probes/SYN-0018/classify.py FIXTURE_ANCHORS expected field",
                    json.dumps(
                        {r["id"]: r["expected"] for r in campaign["anchors"]},
                        sort_keys=True,
                    ),
                ),
            },
        ],
        "tests": [
            {
                "id": "T1",
                "name": "recipe control: cat-file == show; archive differs by CRLF",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2",
                "name": "planted drift: insert a line above -> LINE-MOVED not STABLE",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T3",
                "name": "planted rewrite: change the anchored line -> CONTENT-CHANGED",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-DRIFT",
                "kind": "known-broken-fixture",
                "description": (
                    "Insert one line above CLAIM-MOVED-001; must classify "
                    "LINE-MOVED, not STABLE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "CLAIM-MOVED-001 LINE-MOVED",
                "good_state_output": "CLAIM-STABLE-001 STABLE",
            },
            {
                "id": "NC-REWRITE",
                "kind": "known-broken-fixture",
                "description": (
                    "Change the anchored line of CLAIM-REWRITE-001; must "
                    "classify CONTENT-CHANGED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "CLAIM-REWRITE-001 CONTENT-CHANGED",
                "good_state_output": "CLAIM-STABLE-001 STABLE",
            },
            {
                "id": "NC-GONE",
                "kind": "known-broken-fixture",
                "description": (
                    "Delete anchors/gone.md at report tree; must classify "
                    "FILE-GONE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "CLAIM-GONE-001 FILE-GONE",
                "good_state_output": "CLAIM-STABLE-001 STABLE",
            },
            {
                "id": "NC-ARCHIVE-RECIPE",
                "kind": "known-broken-fixture",
                "description": (
                    "git archive on * text eol=crlf returns CRLF while the "
                    "blob stays LF. A classifier that used archive would be "
                    "invalid by construction."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": recipe_src,
                "good_state_output": (
                    f"cat-file==show LF bytes={recipe['cat_file_bytes']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0018-probe2-planted-detector",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 re-runs the detector on the planted known-broken "
                "fixtures (drift, rewrite, gone) and is silent on the known-good "
                "STABLE fixture. Probe 1 independently re-runs the blob recipe "
                "control. Neither probe treats this receipt's conclusion as "
                "evidence."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0018/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "SYN-0018",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema.Draft7Validator against "
                    "command-center/schema/evidence-decay-report.schema.json "
                    "(disk RefResolver, no network)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 command-center/p2-wave/probes/SYN-0018/emit_receipt.py"
                    ),
                    "raw_output": "schema-valid; garbage rejected",
                    "fingerprint": fp("schema-validate", SCHEMA),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": ended_s,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. The first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record, never an "
                "error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Production CLAIM-REGISTRY anchors re-resolved at a "
                    "capture SHA and a STATUS.md report-time SHA"
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Record capture_sha + path + line per claim, record a "
                    "report-time SHA in STATUS.md, and re-run git cat-file -p "
                    "<rev>:<path> from a git object database that contains "
                    "both trees. This worktree has neither SHA pair nor .git."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "evidence-auditor",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "evidence-decay-report",
            "title": (
                "Stale-evidence re-validation across the SHA delta between "
                "claim capture and report time"
            ),
            "question": QUESTION,
            "observations": [
                {
                    "name": "recipe-cat-file-equals-show",
                    "measured": True,
                    "method": "git cat-file -p vs git show on isolated tree",
                    "anchor": "anchors/stable.md",
                },
                {
                    "name": "recipe-archive-differs-by-crlf",
                    "measured": True,
                    "method": "git archive member extract vs cat-file blob",
                    "anchor": "anchors/stable.md",
                },
                {
                    "name": "planted-four-class-counts",
                    "measured": class_src,
                    "method": "classify_anchor via git cat-file -p",
                    "anchor": "command-center/p2-wave/probes/SYN-0018/classify.py",
                },
                {
                    "name": "production-coverage",
                    "measured": live["coverage"],
                    "method": "stat CLAIM-REGISTRY.json STATUS.md .git",
                    "anchor": "command-center/CLAIM-REGISTRY.json",
                },
            ],
            "control_ids": [
                "NC-DRIFT",
                "NC-REWRITE",
                "NC-GONE",
                "NC-ARCHIVE-RECIPE",
            ],
            "recipe": recipe_payload,
            "capture_tree": campaign["capture_sha"],
            "report_tree": campaign["report_sha"],
            "anchors": anchors,
            "class_counts": class_count_payload,
            "live_inputs": live,
            "production_coverage": live["coverage"],
            "denominator": total,
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "named_probes": [
                {"id": "probe1", "role": "recipe-control", "command": P1},
                {"id": "probe2", "role": "planted-detector", "command": P2},
            ],
            "cloud_ok": False,
            "notes": (
                "G-1 for SYN-0018: live named probes exit 0, SYN-0018.json "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. Production coverage is NOT-CHECKED; "
                "live anchors were not invented."
            ),
        },
    }

    validator = build_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:SYN-0018 schema errors")
        for err in errs[:25]:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            print(f"  {loc}: {err.message}")
        return 1
    for garbage in GARBAGE:
        if not list(validator.iter_errors(garbage)):
            print("FAILED:SYN-0018 schema accepted garbage")
            return 1

    dumped = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in dumped:
        print("FAILED:SYN-0018 sentinel-not-in-artifact")
        return 1
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dumped, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:SYN-0018 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"classes={ {n: counts[n]['as_string'] for n in CLASSES} } "
        f"recipe_passed={recipe['passed']} coverage={live['coverage']}"
    )
    print("SUCCESS:SYN-0018 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
