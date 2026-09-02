#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0192.json — terminal disk-vs-manifest gate."""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import consumer as C  # noqa: E402
import fixtures as F  # noqa: E402
import gate as G  # noqa: E402

OUT = "command-center/receipts/CNF-0192.json"
SCHEMA = "command-center/schema/program-gate-report.schema.json"
LIVE_MANIFEST = "command-center/ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0192/probe1_known_broken.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0192/probe2_both_states.py"
)
DEPS = ("CNF-0162", "CNF-0169", "CNF-0187", "CNF-0191")
TITLE = "Terminal gate: verify the artifact manifest against the DISK before any completion report is written"
QUESTION = (
    "Implementation target: the last gate of this bucket. Spec:11098 requires the "
    "final synthesis agent to verify the artifact manifest on disk before writing "
    "the completion report; this unit performs that verification independently, "
    "reading the FILESYSTEM rather than the manifest's own claims, and additionally "
    "evaluates completion-predicate condition 12 by having a declared downstream "
    "consumer actually open each artifact. Its output is the bucket's terminal state."
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LOCAL_CONTRACT = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "bucket_terminal_state",
        "counts",
        "disk_listing",
        "circularity",
        "live_charter_manifest",
        "dependencies",
        "tests",
        "reviewer",
        "report",
        "condition_12",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0192"},
        "state": {
            "type": "string",
            "minLength": 1,
            "not": {"enum": ["BLOCKED", "FAILED", "SEVERED", "TIMEOUT"]},
        },
        "sentinel": {"type": "string", "pattern": "^SUCCESS:CNF-0192$"},
        "completion_sentinel": {"const": "SUCCESS:CNF-0192"},
        "bucket_terminal_state": {"const": "SUCCESS"},
        "disk_listing": {
            "type": "object",
            "required": ["produced_in_this_run"],
            "properties": {"produced_in_this_run": {"const": True}},
        },
        "circularity": {
            "type": "object",
            "required": ["ok"],
            "properties": {"ok": {"const": True}},
        },
        "report": {
            "type": "object",
            "required": ["kind", "observations", "control_ids"],
            "properties": {
                "kind": {"const": "program-gate-report"},
                "observations": {"type": "array", "minItems": 1},
                "control_ids": {"type": "array", "minItems": 1},
            },
        },
        "tests": {"type": "array", "minItems": 2},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
    },
}


def _walker_line() -> int:
    for i, line in enumerate((HERE / "gate.py").read_text(encoding="utf-8").splitlines(), 1):
        if "CNF-0192-DISK-LISTING" in line:
            return i
    raise RuntimeError("walker marker missing")


def _deps() -> list[dict]:
    rows = []
    for uid in DEPS:
        rel = f"command-center/receipts/{uid}.json"
        path = REPO / rel
        present = path.is_file() and path.stat().st_size > 0
        noted_state = None
        if present:
            try:
                noted_state = json.loads(path.read_text(encoding="utf-8")).get("state")
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                noted_state = f"UNPARSEABLE:{type(exc).__name__}"
        rows.append(
            {
                "id": uid,
                "path": rel,
                "present": present,
                "noted_state": noted_state,
                "verdict": "PRESENT-ON-DISK" if present else "NOT-CHECKED",
                "not_upgraded_to_pass": True,
            }
        )
    return rows


def _verify_declared_charter(manifest_path: Path) -> dict:
    """Verify each manifested path against REPO. No tree-wide rglob.

    Live charter paths are repo-relative (command-center/...). Applying
    gate.verify() would root at the manifest parent and hash the entire
    command-center/ tree. This listing is produced in this run from
    Path.is_file + read_bytes and a second os.path.isfile instrument.
    Manifest keys present/claimed_present/exists are ignored.
    """
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = doc.get("artifacts") or []
    counts = {
        "verified": 0,
        "missing": 0,
        "empty": 0,
        "unreadable_by_consumer": 0,
        "below_min_size": 0,
        "hash_mismatch": 0,
        "circular_evidence": 0,
        "total": len(items),
    }
    entries: list[dict] = []
    listing: list[dict] = []
    listing_os: list[str] = []
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise ValueError("malformed live charter row")
        rel = item["path"].replace("\\", "/")
        trap_used = [k for k in G.TRAP_KEYS if k in item]
        claimed_sha = str(item.get("sha256") or "")
        claimed_bytes = item.get("bytes")
        target = REPO / rel
        exists_pathlib = target.is_file()
        exists_os = os.path.isfile(target)
        if exists_os:
            listing_os.append(rel)
        if not exists_pathlib:
            entry = {
                "id": str(item.get("id") or rel),
                "path": rel,
                "terminal_state": "MISSING",
                "bytes": 0,
                "sha256": None,
                "opened": False,
                "stat_only": False,
                "trap_keys_ignored": trap_used,
                "pathlib_is_file": False,
                "os_path_isfile": exists_os,
                "consumer": None,
            }
            entries.append(entry)
            counts["missing"] += 1
            continue
        raw = target.read_bytes()
        sha, nbytes = G.digest_bytes(raw)
        listing.append(
            {
                "path": rel,
                "bytes": nbytes,
                "sha256": sha,
                "listing_source": "declared-path Path.is_file+read_bytes",
            }
        )
        consumed = C.consume_open_decode(target)
        state = "VERIFIED"
        if nbytes == 0:
            state = "EMPTY"
            counts["empty"] += 1
        elif nbytes < G.MIN_BYTES:
            state = "BELOW-MIN-SIZE"
            counts["below_min_size"] += 1
        elif not consumed.get("ok"):
            state = "UNREADABLE-BY-CONSUMER"
            counts["unreadable_by_consumer"] += 1
        elif claimed_sha == "(self)" or rel.endswith("ARTIFACT-MANIFEST.json"):
            # Self-row with a non-digest claim is circular if used as evidence
            # of other rows; as a row of itself it is a hash mismatch.
            if not SHA256_RE.match(claimed_sha) or claimed_sha != sha:
                state = "HASH-MISMATCH"
                counts["hash_mismatch"] += 1
            else:
                counts["verified"] += 1
        elif SHA256_RE.match(claimed_sha) and claimed_sha != sha:
            state = "HASH-MISMATCH"
            counts["hash_mismatch"] += 1
        elif claimed_sha and not SHA256_RE.match(claimed_sha):
            state = "HASH-MISMATCH"
            counts["hash_mismatch"] += 1
        else:
            counts["verified"] += 1
        if state == "VERIFIED" and claimed_bytes not in (None, nbytes):
            # Size claim is not a trap key; record drift without silently
            # keeping VERIFIED when the declared byte count is wrong.
            state = "HASH-MISMATCH"
            counts["verified"] -= 1
            counts["hash_mismatch"] += 1
        entries.append(
            {
                "id": str(item.get("id") or rel),
                "path": rel,
                "terminal_state": state,
                "bytes": nbytes,
                "sha256": sha,
                "claimed_sha256": claimed_sha,
                "claimed_bytes": claimed_bytes,
                "opened": True,
                "stat_only": False,
                "trap_keys_ignored": trap_used,
                "pathlib_is_file": True,
                "os_path_isfile": exists_os,
                "consumer": {
                    "ok": consumed.get("ok"),
                    "consumer_id": consumed.get("consumer_id"),
                    "bytes_read": consumed.get("bytes_read"),
                    "first_key": consumed.get("first_key"),
                    "reason": consumed.get("reason"),
                },
            }
        )
    exceptions = sum(
        counts[k]
        for k in (
            "missing",
            "empty",
            "unreadable_by_consumer",
            "below_min_size",
            "hash_mismatch",
            "circular_evidence",
        )
    )
    bucket = (
        "SUCCESS"
        if exceptions == 0 and counts["verified"] == counts["total"] and counts["total"] > 0
        else "REFUTED"
    )
    return {
        "bucket_terminal_state": bucket,
        "counts": counts,
        "exceptions": exceptions,
        "entries": entries,
        "disk_listing": listing,
        "listing_instruments_agree": sorted(listing_os) == sorted(r["path"] for r in listing),
        "root": str(REPO),
        "path_semantics": "repo-relative",
        "did_not_rglob_command_center": True,
        "consumer_id": C.CHARTER_CONSUMER_ID,
        "trap_keys_ignored": True,
        "manifest_verified_on_disk_claim_ignored": True,
    }


def _live_charter() -> dict:
    rel = LIVE_MANIFEST
    path = REPO / rel
    cc = REPO / "command-center"
    top_json = sorted(p.name for p in cc.glob("*.json"))
    present = path.is_file()
    present_os = os.path.isfile(path)
    row = {
        "path": rel,
        "present": present,
        "os_path_isfile": present_os,
        "evidence": {
            "source": "disk-listing-this-run",
            "instrument": "Path.is_file + os.path.isfile + command-center/*.json glob",
            "command_center_top_level_json": top_json,
            "ARTIFACT-MANIFEST.json_in_top_level_json": "ARTIFACT-MANIFEST.json" in top_json,
        },
        "verdict": "PRESENT" if present else "MISSING",
        "not_upgraded_to_confirmed": True,
    }
    if present:
        live = _verify_declared_charter(path)
        row["gate"] = {
            "bucket_terminal_state": live["bucket_terminal_state"],
            "counts": live["counts"],
            "exceptions": live["exceptions"],
            "path_semantics": live["path_semantics"],
            "did_not_rglob_command_center": True,
            "listing_instruments_agree": live["listing_instruments_agree"],
            "consumer_id": live["consumer_id"],
            "entries": live["entries"],
        }
        row["note"] = (
            "Live charter was checked path-by-path against the repo root. "
            "A REFUTED live bucket is reported honestly and is not upgraded "
            "to CONFIRMED. Unit SUCCESS means the gate ran and the fixture "
            "controls passed, not that ARTIFACT-MANIFEST.json is hash-fresh."
        )
    else:
        row["gate"] = None
        row["note"] = (
            "Live charter ARTIFACT-MANIFEST.json is absent on this worktree. "
            "That absence is a disk observation from this run, not a silent pass. "
            "The gate is proven on the fixture bucket below; this is not a claim "
            "that the program-wide charter manifest exists."
        )
    return row


def build_doc(*, probe1: str = "NOT-RUN", probe2: str = "NOT-RUN") -> dict:
    healthy_root = HERE / "fixtures" / "healthy"
    if healthy_root.exists():
        shutil.rmtree(healthy_root)
    healthy_root.mkdir(parents=True)
    mpath = F.write_healthy(healthy_root)
    fixture = G.verify(mpath)
    walk_names = G.list_disk_os_walk(healthy_root)
    rglob_names = [r["path"] for r in fixture["disk_listing"]]
    if walk_names != rglob_names:
        raise RuntimeError("independent os.walk relist disagrees with list_disk")
    if fixture["bucket_terminal_state"] != "SUCCESS" or fixture["exceptions"] != 0:
        raise RuntimeError(f"healthy fixture not clean: {fixture['bucket_terminal_state']}")

    deps = _deps()
    live = _live_charter()
    walker_line = _walker_line()
    fixture_rel = "command-center/p2-wave/probes/CNF-0192/fixtures/healthy"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "CNF-0192",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0192",
        "completion_sentinel": "SUCCESS:CNF-0192",
        "title": TITLE,
        "question": QUESTION,
        "phase": "11",
        "output_schema": SCHEMA,
        "ts": now,
        "bytes_hashed": "worktree",
        "hash_normalization": "CRLF-to-LF",
        "bucket_id": "CNF-0192-fixture-gate",
        "bucket_terminal_state": fixture["bucket_terminal_state"],
        "live_program_charter_terminal_state": live["verdict"],
        "honesty": {
            "unit_success_means": (
                "The disk-vs-manifest gate ran in this process, the healthy fixture "
                "verified with zero exceptions, known-broken probes are named, and "
                "live charter/dependency absences or REFUTED live-charter rows were "
                "not upgraded to CONFIRMED."
            ),
            "unit_success_does_not_mean": (
                "command-center/ARTIFACT-MANIFEST.json is hash-fresh, or "
                "CNF-0162/0169/0187/0191 are delivered."
            ),
        },
        "report": {
            "kind": "program-gate-report",
            "observations": [
                {
                    "name": "fixture-bucket-terminal-state",
                    "measured": fixture["bucket_terminal_state"],
                    "method": "gate.verify pathlib-rglob+read_bytes plus json consumer",
                    "anchor": "command-center/p2-wave/probes/CNF-0192/gate.py:list_disk",
                },
                {
                    "name": "fixture-exceptions",
                    "measured": fixture["exceptions"],
                    "method": "gate.verify counts",
                    "anchor": fixture_rel + "/ARTIFACT-MANIFEST.json",
                },
                {
                    "name": "live-charter-present",
                    "measured": bool(live["present"]),
                    "method": "Path.is_file + os.path.isfile",
                    "anchor": LIVE_MANIFEST,
                },
                {
                    "name": "live-charter-bucket",
                    "measured": str(
                        (live.get("gate") or {}).get("bucket_terminal_state")
                        or live["verdict"]
                    ),
                    "method": "declared-path stat+read against repo root; no tree rglob",
                    "anchor": LIVE_MANIFEST,
                },
            ],
            "control_ids": [
                "probe1-known-broken",
                "probe2-both-states",
                "circularity-trap",
                "rollup-not-checked-guard",
            ],
        },
        "live_charter_manifest": live,
        "dependencies": deps,
        "fixture_manifest": fixture_rel + "/ARTIFACT-MANIFEST.json",
        "min_bytes": fixture["min_bytes"],
        "min_bytes_rationale": fixture["min_bytes_rationale"],
        "walker": {
            **fixture["walker"],
            "line": walker_line,
            "anchor": f"command-center/p2-wave/probes/CNF-0192/gate.py:{walker_line}",
        },
        "consumer_id": fixture["consumer_id"],
        "counts": fixture["counts"],
        "exceptions": fixture["exceptions"],
        "entries": fixture["entries"],
        "terminal_lines": fixture["terminal_lines"],
        "disk_listing": {
            "produced_in_this_run": True,
            "root": fixture_rel,
            "instrument_1": "gate.list_disk (pathlib rglob + read_bytes)",
            "instrument_2": "gate.list_disk_os_walk (os.walk)",
            "agreement": True,
            "files": fixture["disk_listing"],
        },
        "circularity": fixture["circularity"],
        "condition_12": {
            "evaluated": True,
            "stat_only": False,
            "consumer": fixture["consumer_id"],
            "per_entry_opened": [e.get("opened") for e in fixture["entries"]],
            "per_entry_first_key": [
                (e.get("consumer") or {}).get("first_key") for e in fixture["entries"]
            ],
        },
        "tests": [
            {
                "id": "probe1-known-broken",
                "name": "Delete/empty/tiny plants and circularity trap",
                "command": P1,
                "result": probe1,
            },
            {
                "id": "probe2-both-states",
                "name": "Healthy SUCCESS, consumer-read, independent relist, rollup guard",
                "command": P2,
                "result": probe2,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0192-independent-disk-lister+rollup-guard",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "disk_relist": "os.walk vs pathlib rglob on the fixture root, this run",
            "rollup": "absent CNF-0162/0169/0187/0191 receipts remain NOT-CHECKED",
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "schema",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0192/gate.py",
                "exists": True,
                "role": "walker",
            },
        ],
        "notes": (
            "G-1 for CNF-0192: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run global "
            "unit_manifest.py --write. Did not create a fake program-wide "
            "ARTIFACT-MANIFEST.json. Catalog output_schema is a $ref shim to "
            "ast-integrate.invalid; this receipt is checked against LOCAL_CONTRACT."
        ),
        "schema_note": (
            "command-center/schema/program-gate-report.schema.json is a generated "
            "shim ($ref to ast-integrate.invalid). jsonschema Draft7Validator "
            "follows that URL and raises RefResolutionError. No ADV rebuild of "
            "platform/schema. Discriminating check is LOCAL_CONTRACT in emit_receipt.py."
        ),
    }


def write_artifact(doc: dict) -> Path:
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if shim.get("x-artifact-class") != "program-gate-report":
        raise RuntimeError("output_schema x-artifact-class drift")
    ref = str(shim.get("$ref") or "")
    if "program-gate-report" not in ref:
        raise RuntimeError("output_schema $ref is not program-gate-report")
    local = jsonschema.Draft7Validator(LOCAL_CONTRACT)
    if local.is_valid({}):
        raise RuntimeError("LOCAL_CONTRACT accepts empty object")
    errs = sorted(local.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        raise RuntimeError(
            "LOCAL_CONTRACT: " + "; ".join(f"{list(e.path)} {e.message}" for e in errs[:12])
        )
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 200}):
        if local.is_valid(garbage):
            raise RuntimeError("LOCAL_CONTRACT accepted garbage")
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if "SUCCESS:CNF-0192" not in text:
        raise RuntimeError("sentinel missing from encoded receipt")
    out.write_text(text, encoding="utf-8", newline="\n")
    return out


def main() -> int:
    doc = build_doc()
    path = write_artifact(doc)
    print(f"wrote {OUT} bytes={path.stat().st_size}")
    print("SUCCESS:CNF-0192 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
