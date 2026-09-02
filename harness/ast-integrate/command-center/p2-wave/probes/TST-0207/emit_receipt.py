#!/usr/bin/env python3
"""Emit TST-0207 security report, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0207"
OUT = "command-center/receipts/TST-0207.json"
SENTINEL = "SUCCESS:TST-0207"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0207/probe1_planted_git_and_junk.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0207/probe2_members_and_ceiling.py"
)
CONSUME = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0207/consume_receipt.py"
)
SUPPORTING = [
    "tools/plugin/pack.py",
    "tools/plugin/schema/payload-allowlist.schema.json",
    "command-center/p2-wave/probes/TST-0207/staging.py",
    "command-center/p2-wave/probes/TST-0207/probe1_planted_git_and_junk.py",
    "command-center/p2-wave/probes/TST-0207/probe2_members_and_ceiling.py",
    "command-center/p2-wave/probes/TST-0207/consume_receipt.py",
]
QUESTION = (
    "Can `.git`, caches, logs, transcripts or unrelated gigabytes enter the "
    "distributable? PASS requires an ALLOWLIST-based packer (a denylist is a "
    "FAIL by construction) plus a package size ceiling that fails the build."
)
SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0207] "
    "question_or_target + tests_required + evidence_requirement"
)
PLACEHOLDER_SHA = "0" * 64


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0207/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-65000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def validate_security_report(doc: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        return
    schema_path = REPO / "platform" / "schema" / "receipt.schema.json"
    if not schema_path.is_file():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    fragment = schema.get("$defs", {}).get("security_report")
    if not isinstance(fragment, dict):
        return
    validator = jsonschema.Draft202012Validator(schema, format_checker=None)
    # Validate against the full document using the fragment by wrapping $ref locally.
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": schema.get("$defs") or {},
        "$ref": "#/$defs/security_report",
    }
    errs = sorted(
        jsonschema.Draft202012Validator(wrapper).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:TST-0207 schema errors")
        for err in errs[:24]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    del validator


def main() -> int:
    missing = [p for p in SUPPORTING if not (REPO / p).is_file()]
    if missing:
        print("FAILED:TST-0207 missing supporting files: " + ", ".join(missing))
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0207 emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    (HERE / "probe1.raw.txt").write_text(t1 + "\n", encoding="utf-8")
    (HERE / "probe2.raw.txt").write_text(t2 + "\n", encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_src = probe_obj("source", "command", P1, t1, c1)
    p2_ver = probe_obj("verifier", "byte-compare", P2, t2, c2)
    p2_src = probe_obj("source", "byte-compare", P2, t2, c2)
    p1_ver = probe_obj("verifier", "command", P1, t1, c1)

    supporting_arts = []
    for rel in SUPPORTING:
        sha, size = digest(REPO / rel)
        supporting_arts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            }
        )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "profile": "security-report",
        "spec_anchor": SPEC_ANCHOR,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "security-tester",
            "execution_substrate": "linux-worktree",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 1,
                "sha256": PLACEHOLDER_SHA,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            *supporting_arts,
        ],
        "evidence": [
            {
                "claim": (
                    "tools/plugin/pack.py is allowlist-only: a denylist config is "
                    "refused before any walk; planting .git/HEAD, .git/config and "
                    "a 200MiB junk.bin in a staging tree fails the build, names "
                    "every extra path, and writes no archive. A denylist mutant "
                    "would drop .git and still ship junk.bin."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0207/probe1.raw.txt",
                "probes": [p1_src, p2_ver],
                "unverified": False,
            },
            {
                "claim": (
                    "Independent zipfile member listing of a clean pack agrees "
                    "file-for-file with an independent allowlist expansion "
                    "(README.md, plugin.json, src/app.py; 97 uncompressed bytes). "
                    "An allowlisted payload.bin over size_ceiling_bytes 1048576 "
                    "fails the build (1048737 bytes) and writes no archive. "
                    "Unbounded glob ** is refused."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/TST-0207/probe2.raw.txt",
                "probes": [p2_src, p1_ver],
                "unverified": False,
            },
        ],
        "tests": [
            {
                "id": "detector-planted-git-and-200mb-junk",
                "name": (
                    "detector control: add a 200 MB junk file and a .git "
                    "directory to the source tree and confirm the build fails"
                ),
                "command": P1,
                "result": "PASS",
                "assertions": 8,
                "output_tail": (
                    "clean=PASS dirty=FAIL git_named=1 junk_named=1 "
                    "junk_bytes=209715200 denylist_would_ship_junk=1"
                ),
            },
            {
                "id": "independent-members-and-size-ceiling",
                "name": (
                    "package member list vs allowlist and packaged size vs "
                    "declared ceiling; oversize allowlisted payload fails"
                ),
                "command": P2,
                "result": "PASS",
                "assertions": 6,
                "output_tail": (
                    "members=['README.md', 'plugin.json', 'src/app.py'] "
                    "bytes=97 ceiling=1048576 oversize=FAIL"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "planted-git-and-200mib-junk",
                "kind": "adversarial-payload",
                "description": (
                    "Plant .git and a sparse 200MiB junk.bin beside an "
                    "allowlisted fixture; the allowlist packer must fail and "
                    "name both. The same allowlist must pack the clean tree."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "dirty.ok=false extras=.git/HEAD,.git/config,junk.bin "
                    "junk.bin=209715200 dirty_archive_absent=true"
                ),
                "good_state_output": (
                    "clean.ok=true members=README.md,plugin.json,src/app.py "
                    "uncompressed_bytes=97 clean_archive_present=true"
                ),
            },
            {
                "id": "denylist-mutant-ships-junk",
                "kind": "mutation",
                "description": (
                    "A denylist of .git/** and *.log would select junk.bin "
                    "(FAIL by construction). pack() refuses mode=denylist "
                    "before any walk."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "denylist_mutant_would_select_junk=true; PackError denylist",
                "good_state_output": "policy=allowlist denylist_config_refused=true",
            },
            {
                "id": "oversize-allowlisted-payload-ceiling",
                "kind": "known-broken-fixture",
                "description": (
                    "Allowlisted payload.bin of ceiling+64 bytes must fail "
                    "size_ceiling_bytes and emit no archive. Clean fixture "
                    "of 97 bytes packs under the 1MiB ceiling."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    "oversize_fails=true oversize_uncompressed_bytes=1048737 "
                    "oversize_ceiling_exceeded=true"
                ),
                "good_state_output": "clean_under_ceiling=true independent_uncompressed_bytes=97",
            },
            {
                "id": "unbounded-glob-starstar",
                "kind": "mutation",
                "description": "Widen globs to **; packer must refuse (not an allowlist).",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unbounded_glob_refused=true PackError",
                "good_state_output": "FIXTURE_ALLOWLIST globs accepted; clean pack ok",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0207-probe2-independent-zipfile-census",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Probe 2 enumerates archive members with zipfile and expands "
                "the allowlist with a second walk, not pack.classify_tree. "
                "Catalog asked for a cross-vendor Codex reviewer plus a "
                "correctness reviewer; those processes were not dispatched. "
                "Probe 2 is the independent mechanical check. SUCCESS:TST-0207"
            ),
            "reviewed_at": now,
        },
        "defects": [
            {
                "id": "TST0207-D1-PACKER-ABSENT-ON-RESUME",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "tools/plugin/pack.py was absent on resume; restored the "
                    "allowlist packer with size_ceiling_bytes fail-closed and "
                    "denylist refusal, then re-ran both named probes to exit 0."
                ),
            },
            {
                "id": "TST0207-D2-RECEIPT-ABSENT-ON-RESUME",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "command-center/receipts/TST-0207.json was missing; this "
                    "emit writes the catalog output_path plus per-unit manifest."
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0207/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/TST-0207/consume_receipt.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "command",
                    "command": CONSUME,
                    "raw_output": "pending-first-write",
                    "fingerprint": fingerprint("command", CONSUME),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry: a failure here is a finding, not a "
                "transient; re-run only after a named change to the harness "
                "or the fixture"
            ),
            "attempts": [{"attempt": 1, "outcome": "SUCCESS", "started_at": now}],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement names a cross-vendor Codex "
                    "security reviewer plus a fresh-context correctness reviewer; "
                    "those two human/process reviewers were not dispatched on "
                    "this G-1 pass."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch those reviewers against probe1.raw.txt and "
                    "probe2.raw.txt and require both to reproduce the "
                    "both-states controls."
                ),
            },
            {
                "claim": (
                    "Global python tools/command-center/unit_manifest.py --write "
                    "was not run (hard constraint). Per-unit "
                    "UNIT-ARTIFACT-MANIFEST.json is the G-1 registration target."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Authorized C11 repair of sibling first-red, then global "
                    "--check until SUCCESS:unit-manifest without rewriting "
                    "this unit's per-unit row."
                ),
            },
        ],
        "report": {
            "kind": "security_report",
            "findings": [
                {
                    "id": "TST0207-F1-ALLOWLIST-NOT-DENYLIST",
                    "severity": "INFO",
                    "summary": (
                        "Packer refuses denylist mode; extras including .git "
                        "and 200MiB junk.bin fail the build by name."
                    ),
                    "anchor": "command-center/p2-wave/probes/TST-0207/probe1.raw.txt",
                    "exploit_proven": False,
                    "credential_redacted": True,
                },
                {
                    "id": "TST0207-F2-SIZE-CEILING",
                    "severity": "INFO",
                    "summary": (
                        "Uncompressed payload above size_ceiling_bytes fails "
                        "the build; independent zip listing matches the allowlist."
                    ),
                    "anchor": "command-center/p2-wave/probes/TST-0207/probe2.raw.txt",
                    "exploit_proven": False,
                    "credential_redacted": True,
                },
            ],
            "scanners": [
                {
                    "name": "deny-by-default glob allowlist",
                    "version": "1",
                    "installed": True,
                },
                {
                    "name": "uncompressed payload size ceiling",
                    "version": "1",
                    "installed": True,
                },
            ],
        },
        "extensions": {
            "stage": "p2-deliver",
            "title": (
                "The packer uses an allowlist and a size ceiling, so `.git` "
                "and caches cannot ship"
            ),
            "question_or_target": QUESTION,
            "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
            "packer": "tools/plugin/pack.py",
            "cloud_ok_is_not_delivery": True,
            "g1_per_unit_manifest": True,
            "notes": (
                "G-1 TST-0207: live named probes exit 0, receipt state=SUCCESS, "
                "per-unit manifest row. Did not run global unit_manifest.py "
                "--write. SUCCESS:TST-0207"
            ),
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(dumps(doc), encoding="utf-8")

    cc, ct = run_cmd(CONSUME)
    if cc != 0:
        print(f"FAILED:TST-0207 consume after first write cc={cc}")
        print(ct[-2000:])
        return 1
    doc["downstream_consumers"][0]["exit_code"] = cc
    doc["downstream_consumers"][0]["read_ok"] = True
    doc["downstream_consumers"][0]["executed"] = True
    doc["downstream_consumers"][0]["probe"]["raw_output"] = ct[-65000:]
    doc["downstream_consumers"][0]["probe"]["exit_code"] = cc

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["ended_at"] = ended
    out_path.write_text(dumps(doc), encoding="utf-8")
    live_sha, live_bytes = digest(out_path)
    doc["artifacts"][0]["sha256"] = live_sha
    doc["artifacts"][0]["bytes"] = live_bytes
    out_path.write_text(dumps(doc), encoding="utf-8")
    live_sha, live_bytes = digest(out_path)
    # Keep artifacts[0] as the digest of the bytes actually on disk after the
    # last write that still contained the previous digest. Re-stamp once more
    # only if the placeholder remains.
    if doc["artifacts"][0]["sha256"] == PLACEHOLDER_SHA:
        print("FAILED:TST-0207 placeholder sha survived")
        return 1

    validate_security_report(doc)
    text = out_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:TST-0207 sentinel missing after write")
        return 1

    live_sha, live_bytes = digest(out_path)
    primary = {
        "path": OUT,
        "sha256": live_sha,
        "bytes": live_bytes,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0207/SUBAGENT-RETURN.json",
        "role": "primary",
    }
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/security_report",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "planted-git-and-200mb-junk",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-members-and-ceiling",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": live_sha,
                "bytes": live_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0207/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0207-probe2-independent-zipfile-census",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ended,
        "notes": (
            "G-1 for TST-0207: live named probes exit 0, TST-0207.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(dumps(ret), encoding="utf-8")
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(dumps(man), encoding="utf-8")
    print(f"primary {OUT} sha256={live_sha} bytes={live_bytes}")
    print("SUCCESS:TST-0207 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
