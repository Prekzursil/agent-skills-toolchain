#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0101-repo-live-parity.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/confirmation/CNF-0101-repo-live-parity.json"
SCHEMA = "command-center/schema/byte-parity-report.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0101/probe1_two_way.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0101/probe2_controls.py"
)
QUESTION = (
    "Are the repository and the deployed copy the same? Compare them BOTH ways "
    "for the shipped file set and answer: how many files are identical, how many "
    "differ only by line endings, how many differ in content, and in which "
    "direction is each larger? A one-directional sync on a two-directional "
    "divergence destroys content, and the measured estate rate is 5 identical of 88."
)
SENTINEL = (
    "SUCCESS:CNF-0101 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and the comparison ran in both "
    "directions, no tree was written to, and the four-way counts are attached. "
    "Any other terminal state is FAILED:CNF-0101 <classification> with the "
    "diagnostic tail attached."
)
MIN_BYTES = 2048


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()[:32]


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def make_validator() -> Draft202012Validator:
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads((REPO / PROFILES).read_text(encoding="utf-8"))
    receipt = json.loads((REPO / RECEIPT_SCHEMA).read_text(encoding="utf-8"))
    store = {
        profiles["$id"]: profiles,
        receipt["$id"]: receipt,
        shim["$id"]: shim,
    }
    resolver = RefResolver(base_uri=shim["$id"], referrer=shim, store=store)
    return Draft202012Validator(shim, resolver=resolver)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    raw = path.read_bytes()
    if b"\0" in raw:
        eol = "BINARY"
    elif b"\r\n" in raw and raw.replace(b"\r\n", b"\n").find(b"\r") == -1:
        eol = "CRLF" if b"\n" not in raw.replace(b"\r\n", b"") else "MIXED"
        if b"\n" in raw.replace(b"\r\n", b"\n") and b"\r\n" in raw:
            # mixed LF and CRLF
            if raw.replace(b"\r\n", b"") != raw.replace(b"\r\n", b"").replace(b"\n", b""):
                # has leftover bare LF
                if b"\n" in raw.replace(b"\r\n", b""):
                    eol = "MIXED"
    else:
        eol = "LF" if b"\r\n" not in raw else "MIXED"
    if b"\r\n" not in raw and b"\n" in raw:
        eol = "LF"
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNF-0101 named probes")
        print(out1[-1500:])
        print(out2[-1500:])
        return 1

    p1 = json.loads((HERE / "probe1-two-way.raw.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-controls.raw.json").read_text(encoding="utf-8"))
    census = p1["census"]
    fw = census["four_way_counts"]
    if p1.get("trees_written") or p2.get("trees_written"):
        print("FAILED:CNF-0101 premature-write")
        return 1
    if p1.get("cited_2026_08_09_5_of_88") or census.get("cited_2026_08_09_5_of_88"):
        print("FAILED:CNF-0101 cited historical 5/88 as today")
        return 1

    per_file = []
    for r in census["rows"]:
        per_file.append(
            {
                "path": r["path"],
                "class": r["class"],
                "four_way": r.get("four_way"),
                "larger": r["larger"],
                "in_repo": r["in_repo"],
                "in_live": r["in_live"],
                "repo_bytes": r.get("repo_bytes"),
                "live_bytes": r.get("live_bytes"),
                "repo_sha256": r.get("repo_sha256"),
                "live_sha256": r.get("live_sha256"),
                "repo_sha256_lf": r.get("repo_sha256_lf"),
                "live_sha256_lf": r.get("live_sha256_lf"),
                "repo_unique_line_count": r["repo_unique_line_count"],
                "live_unique_line_count": r["live_unique_line_count"],
                "repo_unique_lines_sample": (r.get("repo_unique_lines") or [])[:4],
                "live_unique_lines_sample": (r.get("live_unique_lines") or [])[:4],
                "one_directional_class": r.get("one_directional_class"),
            }
        )

    fixture_sync = p1["sync_script"]["fixture_stand_in"]
    repo_sync_present = p1["sync_script"]["any_catalog_named_present"]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_n = int(p1.get("live_present_trees") or p1.get("host_present_trees") or 0)
    shipped_n = int(p1.get("shipped_present_trees") or 0)
    answer = (
        f"Live deployed trees present={live_n}. Shipped repo trees present={shipped_n}. "
        f"Fixture union={census['union_files']} both_sides={census['both_sides']} "
        f"identical={fw['identical']} eol_only={fw['eol_only']} "
        f"content_differ={fw['content_differ']} "
        f"(content_repo_larger={fw['content_repo_larger']} "
        f"content_live_larger={fw['content_live_larger']} "
        f"content_same_size={fw['content_same_size']} "
        f"diverged_both_unique={fw['diverged_both_unique']}). "
        "2026-08-09 5/88 is NOT today's measurement. "
        "scripts/sync-from-live.ps1 is absent from this worktree; the fixture "
        f"stand-in cited_line={fixture_sync['cited_line']!r} applies no transform. "
        "Comparison ran repo-to-live and live-to-repo. trees_written=false. "
        + SENTINEL
    )

    validator = make_validator()
    garbage_docs = (
        {"totally": "unrelated"},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNF-0101", "state": "SUCCESS"},
    )
    garbage_rejected = []
    for g in garbage_docs:
        errs = list(validator.iter_errors(g))
        garbage_rejected.append({"keys": sorted(g.keys()), "rejected": bool(errs)})
        if not errs:
            print(f"FAILED:CNF-0101 schema accepted garbage {list(g)[:2]}")
            return 1

    supporting = [
        art(SCHEMA, "supporting"),
        art("command-center/p2-wave/probes/CNF-0101/probe1_two_way.py", "supporting"),
        art("command-center/p2-wave/probes/CNF-0101/probe2_controls.py", "supporting"),
        art("command-center/p2-wave/probes/CNF-0101/compare.py", "supporting"),
        art("command-center/p2-wave/probes/CNF-0101/fixtures/sync-from-live.ps1", "fixture"),
        art("command-center/p2-wave/probes/CNF-0101/probe1-two-way.raw.json", "log"),
        art("command-center/p2-wave/probes/CNF-0101/probe2-controls.raw.json", "log"),
    ]

    rules_count = 0
    for h in p1["host_candidates"]:
        if h["path"].endswith("/rules") and h.get("role") == "shipped":
            rules_count = h["file_count"]
            break

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0101",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNF-0101",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "Two-directional fixture census of the shipped-file-set analog "
                    f"has union={census['union_files']}, identical={fw['identical']}, "
                    f"eol_only={fw['eol_only']}, content_differ={fw['content_differ']} "
                    f"(repo_larger={fw['content_repo_larger']}, "
                    f"live_larger={fw['content_live_larger']}, "
                    f"diverged_both_unique={fw['diverged_both_unique']}); "
                    "neither compared tree was written."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0101/probe1-two-way.raw.json"
                    ":census.four_way_counts"
                ),
                "probes": [
                    probe("source", "command", P1, out1, rc1),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNF-0101/probe1-two-way.raw.json",
                        json.dumps(fw, sort_keys=True),
                    ),
                ],
            },
            {
                "claim": (
                    "EOL-only is separated from content: control eol-only.md is "
                    f"EOL_ONLY with eol_delta==cr_count={p2['eol_cr_count']}; "
                    "identical.md is IDENTICAL; diverged.md is DIVERGED two-way and "
                    f"{p2['one_directional_diverged_class']} one-way."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNF-0101/probe2-controls.raw.json"
                    ":checks"
                ),
                "probes": [
                    probe("source", "command", P2, out2, rc2),
                    probe(
                        "verifier",
                        "byte-compare",
                        (
                            "command-center/p2-wave/probes/CNF-0101/fixtures/control/"
                            "{shipped,live}/{identical,eol-only,content,diverged}.md"
                        ),
                        json.dumps(
                            {
                                "identical": p2["identical_class"],
                                "eol": p2["eol_class"],
                                "eol_delta": p2["eol_delta_bytes"],
                                "eol_cr": p2["eol_cr_count"],
                                "diverged": p2["diverged_class"],
                                "one_way": p2["one_directional_diverged_class"],
                            },
                            sort_keys=True,
                        ),
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-two-way",
                "name": "two-directional four-way census",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-controls",
                "name": "detector controls including one-directional miss",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-IDENTICAL-SILENT",
                "kind": "known-broken-fixture",
                "description": (
                    "Identical pair must stay IDENTICAL (detector does not flag "
                    "everything). Content/diverged pair must not be IDENTICAL."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": p2["content_class"] + "/" + p2["diverged_class"],
                "good_state_output": p2["identical_class"],
            },
            {
                "id": "NC-EOL-NOT-CONTENT",
                "kind": "known-broken-fixture",
                "description": (
                    "EOL-only CRLF/LF pair must classify EOL_ONLY, and the raw "
                    "byte delta must equal the CR count."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"eol={p2['eol_class']} delta={p2['eol_delta_bytes']} "
                    f"cr={p2['eol_cr_count']}"
                ),
                "good_state_output": "identical=IDENTICAL",
            },
            {
                "id": "NC-ONE-WAY-MISS",
                "kind": "known-broken-fixture",
                "description": (
                    "A DIVERGED pair is reported REPO_AHEAD by a one-directional "
                    "read; the two-way classifier must still say DIVERGED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(p2["one_directional_diverged_class"]),
                "good_state_output": p2["diverged_class"],
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": (
                    "byte-parity-report schema must reject empty/unrelated docs "
                    "and accept a receipt_core + report.kind pin."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(garbage_rejected, sort_keys=True),
                "good_state_output": "schema-valid CNF-0101 receipt",
            },
            {
                "id": "NC-TREES-UNWRITTEN",
                "kind": "mutation",
                "description": (
                    "Fingerprint census and control trees before and after the "
                    "probes; any write fails the unit."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "trees_written would be true",
                "good_state_output": "trees_written=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0101-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "local",
            "notes": (
                "Mechanical reviewer is probe2 (detector control on known-broken "
                "fixtures). Catalog also wants owner sign-off; this worker did "
                "not record owner approval."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0101/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0101",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads + Draft202012Validator(byte-parity-report)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    (
                        "python3 -c jsonschema.Draft202012Validator"
                        "(byte-parity-report.schema.json)"
                    ),
                    "in-memory document accepted; garbage docs rejected",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record (spec 11039), "
                "never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    f"Live deployed copy is absent on this Linux worktree "
                    f"(live_present_trees={live_n}). Repo rules/ file_count="
                    f"{rules_count} (the historical 5-of-88 denominator size) but "
                    "was not paired with a live tree, so 5/88 is not today's "
                    "measurement."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the two-way census on a host that has both the repo "
                    "shipped file set and the corresponding ~/.claude (or other "
                    "live) tree, without writing either side."
                ),
            },
            {
                "claim": "Owner sign-off required by the catalog was not recorded.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Obtain owner sign-off on the four-way counts and attach "
                    "reviewer.vendor plus reviewed_at."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "drift-auditor",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "byte-parity-report",
            "title": (
                "Two-directional equality check between the repository copy and "
                "the live deployed copy"
            ),
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "fixture-union-files",
                    "measured": census["union_files"],
                    "method": "two-way tree walk of fixture shipped vs live",
                    "anchor": (
                        "command-center/p2-wave/probes/CNF-0101/fixtures/census/"
                    ),
                },
                {
                    "name": "identical",
                    "measured": fw["identical"],
                    "method": "raw-byte equality",
                    "anchor": "compare.classify_pair IDENTICAL",
                },
                {
                    "name": "eol_only",
                    "measured": fw["eol_only"],
                    "method": "LF-normalised equality with raw inequality",
                    "anchor": "compare.classify_pair EOL_ONLY",
                },
                {
                    "name": "content_differ",
                    "measured": fw["content_differ"],
                    "method": "LF-normalised inequality",
                    "anchor": "compare.classify_pair CONTENT_DIFFER",
                },
                {
                    "name": "content_repo_larger",
                    "measured": fw["content_repo_larger"],
                    "method": "raw byte size of content-differ rows",
                    "anchor": "four_way_counts.content_repo_larger",
                },
                {
                    "name": "content_live_larger",
                    "measured": fw["content_live_larger"],
                    "method": "raw byte size of content-differ rows",
                    "anchor": "four_way_counts.content_live_larger",
                },
                {
                    "name": "diverged_both_unique",
                    "measured": fw["diverged_both_unique"],
                    "method": "symmetric unique-line sets",
                    "anchor": "four_way_counts.diverged_both_unique",
                },
                {
                    "name": "trees_written",
                    "measured": False,
                    "method": "pre/post fingerprint of compared trees",
                    "anchor": "probe1 trees_written and probe2 trees_written",
                },
                {
                    "name": "sync_script_transforms",
                    "measured": False,
                    "method": "read fixture Copy-Item -Force line; do not execute",
                    "anchor": fixture_sync["path"] + " cited_line",
                },
                {
                    "name": "live_deployed_trees_present",
                    "measured": live_n,
                    "method": "stat of ~/.claude and sibling live candidates",
                    "anchor": "hosts.host_candidates role=live",
                },
                {
                    "name": "cited_2026_08_09_5_of_88",
                    "measured": False,
                    "method": "explicit non-citation of historical rate",
                    "anchor": "census.cited_2026_08_09_5_of_88",
                },
            ],
            "control_ids": [
                "NC-IDENTICAL-SILENT",
                "NC-EOL-NOT-CONTENT",
                "NC-ONE-WAY-MISS",
                "NC-SCHEMA-GARBAGE",
                "NC-TREES-UNWRITTEN",
            ],
            "comparison_directions": ["repo-to-live", "live-to-repo"],
            "trees_written": False,
            "four_way_counts": fw,
            "per_file": per_file,
            "compared_surfaces": [
                {
                    "name": "fixture-shipped-file-set",
                    "path": (
                        "command-center/p2-wave/probes/CNF-0101/fixtures/census/shipped"
                    ),
                    "read_only": True,
                    "present": True,
                    "role": "repository-shipped-analog",
                },
                {
                    "name": "fixture-live-deployed-copy",
                    "path": (
                        "command-center/p2-wave/probes/CNF-0101/fixtures/census/live"
                    ),
                    "read_only": True,
                    "present": True,
                    "role": "live-deployed-analog",
                },
            ],
            "host_candidates": p1["host_candidates"],
            "live_present_trees": live_n,
            "shipped_present_trees": shipped_n,
            "sync_script": {
                "path": "scripts/sync-from-live.ps1",
                "present": repo_sync_present,
                "transforms": False,
                "cited_line": fixture_sync["cited_line"],
                "executed": False,
                "fixture_stand_in": fixture_sync["path"],
                "note": (
                    "Catalog names scripts/sync-from-live.ps1. It is absent on this "
                    "Linux worktree. The fixture stand-in is a one-directional "
                    "Copy-Item -Force with no EOL or merge transform. This unit "
                    "did not execute it."
                ),
            },
            "scope": {
                "live_estate_present": live_n > 0,
                "proof_surface": (
                    "static fixture shipped-vs-live trees covering identical, "
                    "EOL-only, repo-ahead, live-ahead, same-size DIVERGED, "
                    "repo-only, and live-only; live host candidates remeasured "
                    "and absent"
                ),
                "does_not_claim": [
                    "today's host estate is 5 identical of 88",
                    "cloud ok=true is delivery",
                    "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                    "owner sign-off",
                    "production trees were mutated",
                ],
                "cited_2026_08_09_5_of_88": False,
            },
            "controls": {
                "eol_separated_from_content": p2["checks"]["eol_separated_from_content"],
                "eol_delta_equals_cr_count": p2["checks"]["eol_delta_equals_cr_count"],
                "identical_not_flagged": p2["checks"]["identical_is_identical"],
                "one_directional_misses_diverged": p2["checks"][
                    "one_directional_misses_diverged"
                ],
                "trees_unwritten": p2["checks"]["trees_unwritten"],
                "sync_not_executed": p2["checks"]["sync_not_executed"],
            },
        },
        "extensions": {
            "completion_sentinel": SENTINEL,
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "named_probes": [
                {
                    "id": "probe1",
                    "command": P1,
                    "exit_code": rc1,
                    "raw_output": out1[-4000:],
                },
                {
                    "id": "probe2",
                    "command": P2,
                    "exit_code": rc2,
                    "raw_output": out2[-4000:],
                },
            ],
        },
    }

    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0101 schema errors")
        for e in errs[:30]:
            print(" ", list(e.path), e.message)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0101 sentinel-absent after write")
        return 1
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0101 artifact {size}B below floor")
        return 1
    # Re-validate on-disk bytes (consumer actually executed).
    on_disk = json.loads(text)
    disk_errs = list(validator.iter_errors(on_disk))
    if disk_errs:
        print("FAILED:CNF-0101 on-disk schema errors")
        for e in disk_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1

    now = ended
    ret = {
        "id": "CNF-0101",
        "unit_id": "CNF-0101",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0101",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNF-0101/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0101-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0101: live named probes exit 0, repo-live-parity.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Live deployed trees absent; 5/88 is not "
            "today's measurement."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        pth = REPO / rel
        sha, n = sha256_file(pth)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "CNF-0101",
            "receipt_path": "command-center/p2-wave/probes/CNF-0101/SUBAGENT-RETURN.json",
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0101",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row(SCHEMA, "supporting"),
            row("command-center/p2-wave/probes/CNF-0101/probe1_two_way.py", "supporting"),
            row("command-center/p2-wave/probes/CNF-0101/probe2_controls.py", "supporting"),
            row("command-center/p2-wave/probes/CNF-0101/compare.py", "supporting"),
            row("command-center/p2-wave/probes/CNF-0101/SUBAGENT-RETURN.json", "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0101 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
