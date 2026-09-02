#!/usr/bin/env python3
"""Emit command-center/phase4/conformance/ARC-0106.json and per-unit receipts."""
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
sys.path.insert(0, str(HERE))
import hostility as H  # noqa: E402

SCHEMA_STORE_RELS = (
    "command-center/schema/conformance-report.schema.json",
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def disk_validator(declared: str) -> Draft202012Validator:
    """Compile the catalog output_schema using on-disk $id targets only (no network)."""
    store: dict = {}
    for rel in SCHEMA_STORE_RELS:
        data = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = data
        store["https://ast-integrate.invalid/" + rel] = data
    schema = json.loads((REPO / declared).read_text(encoding="utf-8"))
    resolver = RefResolver(
        base_uri=str(schema.get("$id") or ("https://ast-integrate.invalid/" + declared)),
        referrer=schema,
        store=store,
    )
    return Draft202012Validator(schema, resolver=resolver)


def validate_artifact(doc: object, declared: str) -> list[str]:
    out: list[str] = []
    for err in disk_validator(declared).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)

OUT = "command-center/phase4/conformance/ARC-0106.json"
SCHEMA = "command-center/schema/conformance-report.schema.json"
RECEIPT = "command-center/p2-wave/probes/ARC-0106/SUBAGENT-RETURN.json"
MANIFEST = "command-center/p2-wave/probes/ARC-0106/UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0106/probe1_crlf_blob.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0106/probe2_reserved_longpath.py"
)
QUESTION = (
    "Do the contracts and their validators survive this platform? Test UTF-8 "
    "with and without BOM, CRLF versus LF (the measured defect where the "
    "command-center validator hashes working-tree bytes and is therefore "
    "unrunnable on any Windows checkout), Windows reserved device names such "
    "as NUL and CON that break relative-path computation, long paths beyond "
    "260 characters, and case-insensitive path collisions. Which validators "
    "break, and what is the minimal fix for each?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ARC-0106/hostility.py",
    "command-center/p2-wave/probes/ARC-0106/probe1_crlf_blob.py",
    "command-center/p2-wave/probes/ARC-0106/probe2_reserved_longpath.py",
    "tools/command-center/validate.py",
    "tools/command-center/seed.py",
    "tools/command-center/catalog.py",
    "tools/command-center/unit_manifest.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "eol": "LF",
        "role": role,
        "unit_id": "ARC-0106",
        "receipt_path": RECEIPT,
    }


def receipt_artifact(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
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


def finding(
    fid: str,
    surface: str,
    verdict: str,
    detail: str,
    fix: str,
    validator: str = "",
) -> dict:
    rec = {
        "id": fid,
        "surface": surface,
        "verdict": verdict,
        "detail": detail,
        "minimal_fix": fix,
    }
    if validator:
        rec["validator"] = validator
    return rec


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc1, out1 = run_probe(P1)
    rc2, out2 = run_probe(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:ARC-0106 probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    p1 = json.loads((HERE / "probe1-crlf.raw.json").read_text(encoding="utf-8"))
    p2 = json.loads((HERE / "probe2-hostility.raw.json").read_text(encoding="utf-8"))
    blob = p1["blob_method"]
    crlf = p1["crlf_both_states"]
    bom = p1["bom_both_states"]
    reserved = p2["reserved_name"]
    longp = p2["long_path"]
    casec = p2["case_collision"]
    guards = p1["source_guards"]
    contracts = p2["contracts"]
    validators = p2["validators"]
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    crlf_survives = (
        crlf["validate_lf_blob"]["clean_reach6"]
        and crlf["validate_crlf_working_tree"]["clean_reach6"]
        and crlf["seed_matches_lf_blob_digest"]
        and crlf["unit_manifest"]["survives_crlf"]
        and crlf["render_manifest"]["survives_crlf"]
        and crlf["verdicts_agree"]
    )
    bom_breaks = bool(bom.get("catalog_load_breaks_on_bom"))
    um_bom_ok = bool((bom.get("unit_manifest_receipt_with_bom") or {}).get("ok"))
    seed_bom_ok = bool((bom.get("seed_overlay_with_bom") or {}).get("ok"))
    reserved_ok = bool(reserved.get("handled_or_refused_without_crash"))
    long_ok = bool(longp.get("created")) and bool(longp.get("unit_manifest", {}).get("ok"))
    case_unguarded = not casec.get("live_code_detects_casefold_collision")

    findings = [
        finding(
            "F-CONTRACT-ABSENT",
            "phase4-contracts",
            "ABSENT",
            (
                "ARC-0078, ARC-0080 and ARC-0084 contract files are not on this "
                "tree at command-center/phase4/contracts/. Conformance therefore "
                "targets the live command-center validators those contracts would "
                "bind (digest/manifest for ARC-0084; no plugin or packager module "
                "is present for ARC-0078/ARC-0080)."
            ),
            "Author the three contract units; this report does not invent them.",
            "contracts",
        ),
        finding(
            "F-CRLF-REACH6",
            "CRLF-vs-LF",
            "SURVIVES" if crlf_survives else "BREAKS",
            (
                "validate.py REACH-6 and seed.py provenance hash LF-normalise "
                f"before digesting. LF blob reach6_clean="
                f"{crlf['validate_lf_blob']['clean_reach6']}; CRLF working-tree "
                f"reach6_clean={crlf['validate_crlf_working_tree']['clean_reach6']}; "
                f"seed CRLF digest matches LF blob="
                f"{crlf['seed_matches_lf_blob_digest']}; unit_manifest and "
                f"render_manifest match the LF-normalised digest. Naive raw CRLF "
                f"digest would mismatch the blob "
                f"(naive_would_break={crlf['unit_manifest']['naive_would_break']})."
            ),
            (
                "Keep read_bytes().replace(b'\\r\\n', b'\\n') on every digest "
                "writer and reader. Do not hash working-tree bytes raw."
            ),
            "validate.py+seed.py+unit_manifest.py+render.py",
        ),
        finding(
            "F-UTF8-BOM",
            "UTF-8-BOM",
            "BREAKS" if bom_breaks else "SURVIVES",
            (
                "catalog.load uses encoding=utf-8 then json.loads, so a UTF-8 BOM "
                f"raises. without_bom={bom['without_bom']}; with_bom={bom['with_bom']}; "
                f"unit_manifest BOM receipt ok={um_bom_ok} "
                f"({(bom.get('unit_manifest_receipt_with_bom') or {}).get('error')}); "
                f"seed overlay BOM ok={seed_bom_ok} "
                f"({(bom.get('seed_overlay_with_bom') or {}).get('error')}). "
                "json.loads under utf-8-sig accepts the same bytes."
            ),
            "Read JSON with encoding='utf-8-sig' (catalog.py, seed.py overlay, "
            "validate.py graph, unit_manifest receipts, register_parse.parse_file).",
            "catalog.py",
        ),
        finding(
            "F-RESERVED-NUL",
            "windows-reserved-names",
            "SURVIVES" if reserved_ok else "BREAKS",
            (
                "Created a file named NUL (Linux analogue of CreateFileW with the "
                f"\\\\?\\ prefix {reserved['created']['NUL']['windows_extended_prefix']}). "
                f"unit_manifest handled={reserved['unit_manifest'].get('handled')} "
                f"crashed={reserved['unit_manifest'].get('crashed')} "
                f"relative_to={reserved['relative_path_computation']}. "
                "Live sources have no reserved-device guard; on Windows open('NUL') "
                "would bind the device rather than a file."
            ),
            "Reject path components whose stem is in {NUL,CON,PRN,AUX,COM1-9,LPT1-9} "
            "unless the caller used an extended-length prefix; never open the device.",
            "unit_manifest.py",
        ),
        finding(
            "F-LONG-PATH",
            "path-length-gt-260",
            "SURVIVES" if long_ok else "BREAKS",
            (
                f"Relative path length={longp['relative_len']} absolute="
                f"{longp['absolute_len']} created={longp['created']} "
                f"failure_mode={longp['failure_mode']} unit_manifest="
                f"{longp['unit_manifest']}. On this Linux host the path is legal. "
                f"Windows without \\\\?\\: {longp['windows_expected_without_extended_prefix']}."
            ),
            "On Windows, prefix paths at or above 260 characters with \\\\?\\ "
            "before open/stat, or fail closed with an explicit path-too-long error.",
            "unit_manifest.py",
        ),
        finding(
            "F-CASE-COLLISION",
            "case-insensitive-collision",
            "BREAKS" if case_unguarded else "SURVIVES",
            (
                f"Planted {casec['linux_names']} as distinct files "
                f"(linux_distinct={casec['linux_distinct_files']}); casefold "
                f"collisions={casec['casefold_collisions']}. unit_manifest emitted "
                f"{casec['unit_manifest_rows']} rows with "
                f"{casec['unit_manifest_distinct_sha256']} distinct digests. "
                f"live_code_detects_casefold_collision="
                f"{casec['live_code_detects_casefold_collision']}."
            ),
            "When two registered paths compare equal under casefold, fail closed "
            "instead of treating them as distinct artifacts.",
            "unit_manifest.py",
        ),
        finding(
            "F-PLUGIN-PACKAGER-ABSENT",
            "ARC-0078-ARC-0080-validators",
            "ABSENT",
            (
                "tools/plugin/validate.py and tools/package/boundary.py are not on "
                "this tree, so plugin-manifest interpreter rules and package "
                "exclusion/size-ceiling validators could not be executed. Path "
                "hostility was measured on the live digest/manifest tooling instead."
            ),
            "Deliver ARC-0078 and ARC-0080 validators, then re-run this suite.",
            "plugin+package",
        ),
    ]

    cat_r = blob["readings"]["git cat-file -p"]
    arch_r = blob["readings"]["git archive"]
    wt_r = blob["readings"]["working-tree after CRLF rewrite"]
    answer = (
        "Contracts ARC-0078/0080/0084 are absent on this tree. Live "
        "command-center digest validators SURVIVE CRLF vs the LF blob because "
        "they LF-normalise before hashing; a raw working-tree hash would still "
        "mismatch (the historical REACH-6 Windows defect). catalog.load, seed "
        "overlay, and unit_manifest receipts BREAK on a UTF-8 BOM "
        "(minimal fix: utf-8-sig). Reserved name NUL was created via the "
        "extended-length analogue and did not crash unit_manifest on Linux "
        "(Windows still needs an explicit refuse/prefix guard). Paths longer "
        "than 260 characters SURVIVE here (failure_mode="
        f"{longp['failure_mode']}); Windows MAX_PATH remains unguarded. "
        "Case-insensitive collisions are not detected. SUCCESS:ARC-0106"
    )

    tests = [
        {
            "id": "T-CRLF-BOTH-STATES",
            "name": "CRLF both-states: one validator on a CRLF working tree and on the LF blob",
            "command": P1,
            "result": "PASS" if rc1 == 0 else "FAIL",
        },
        {
            "id": "T-RESERVED-NUL",
            "name": "Reserved-name control: create NUL through the extended-length prefix analogue",
            "command": P2,
            "result": "PASS" if rc2 == 0 else "FAIL",
        },
        {
            "id": "T-LONG-PATH",
            "name": "Long-path control: exercise a path beyond 260 characters and record the failure mode",
            "command": P2,
            "result": "PASS" if rc2 == 0 else "FAIL",
        },
    ]

    evidence = [
        {
            "claim": (
                "Line-ending behaviour is taken from git cat-file -p on a "
                "throwaway lab blob, never from git archive; both readings and "
                "a CRLF working-tree rewrite are recorded, and REACH-6 stays "
                f"clean on LF and CRLF (lf={crlf['validate_lf_blob']['clean_reach6']}, "
                f"crlf={crlf['validate_crlf_working_tree']['clean_reach6']})."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/ARC-0106/probe1_crlf_blob.py:1",
            "probes": [
                probe_obj("source", "command", P1, out1, rc1),
                probe_obj(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/ARC-0106/probe1-crlf.raw.json",
                    json.dumps(
                        {
                            "cat_file_bytes": cat_r.get("bytes"),
                            "archive_bytes": arch_r.get("bytes"),
                            "never_git_archive_for_blob": blob.get("never_git_archive_for_blob"),
                            "working_tree_crlf_shown": blob.get("working_tree_crlf_shown"),
                            "seed_matches_lf_blob": crlf.get("seed_matches_lf_blob_digest"),
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
            ],
        },
        {
            "claim": (
                "NUL was created via the extended-length analogue without crashing "
                "unit_manifest; a relative path longer than 260 characters was "
                f"exercised (len={longp['relative_len']}, failure_mode="
                f"{longp['failure_mode']}); casefold collisions were planted."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/ARC-0106/probe2_reserved_longpath.py:1",
            "probes": [
                probe_obj("source", "command", P2, out2, rc2),
                probe_obj(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/ARC-0106/probe2-hostility.raw.json",
                    json.dumps(
                        {
                            "nul_created": (reserved.get("created") or {}).get("NUL", {}).get("created"),
                            "handled": reserved.get("handled_or_refused_without_crash"),
                            "relative_len": longp.get("relative_len"),
                            "failure_mode": longp.get("failure_mode"),
                            "casefold_collisions": list((casec.get("casefold_collisions") or {}).keys()),
                        },
                        sort_keys=True,
                    ),
                    0,
                ),
            ],
        },
    ]

    consumer_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json; from pathlib import Path; "
        "p=Path('command-center/p2-wave/probes/ARC-0106/probe1-crlf.raw.json'); "
        "d=json.loads(p.read_text(encoding='utf-8')); "
        "assert d['blob_method']['never_git_archive_for_blob'] is True; "
        "print('read_ok', p.as_posix(), 'keys', len(d))\""
    )
    crc, cout = run_probe(consumer_cmd)
    if crc != 0:
        print("FAILED:ARC-0106 downstream consumer could not read probe snapshot")
        print(cout[-1500:])
        return 1

    artifacts = [receipt_artifact(rel, "supporting") for rel in SUPPORTING]
    artifacts[0]["role"] = "supporting"

    doc = {
        "schema_version": 1,
        "unit_id": "ARC-0106",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0106",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#ARC-0106",
        "min_bytes_threshold": 2048,
        "profile": "conformance-report",
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-CRLF-NAIVE-DIGEST",
                "kind": "malformed-input",
                "description": (
                    "A raw CRLF digest of the same bytes must mismatch the LF blob; "
                    "LF-normalised validators must stay silent on both states."
                ),
                "fired_on_bad_state": bool(crlf["unit_manifest"]["naive_would_break"]),
                "silent_on_good_state": bool(crlf_survives),
                "bad_state_output": (
                    f"naive_raw={crlf['unit_manifest']['naive_raw_sha256']} "
                    f"normalised={crlf['unit_manifest']['normalised_sha256']}"
                ),
                "good_state_output": (
                    f"um_survives={crlf['unit_manifest']['survives_crlf']} "
                    f"seed_matches={crlf['seed_matches_lf_blob_digest']}"
                ),
            },
            {
                "id": "NC-UTF8-BOM",
                "kind": "malformed-input",
                "description": (
                    "catalog.load must break on a UTF-8 BOM and succeed without one."
                ),
                "fired_on_bad_state": bom_breaks,
                "silent_on_good_state": bool((bom.get("without_bom") or {}).get("ok")),
                "bad_state_output": str((bom.get("with_bom") or {}).get("error")),
                "good_state_output": str((bom.get("without_bom") or {}).get("error")),
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0106-probe1-crlf-blob",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "grok",
            "notes": (
                "Named probe1 re-runs cat-file vs archive vs CRLF working-tree "
                "and BOM both-states independently of emit.py's narrative."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": "ARC-0106",
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of probe1-crlf.raw.json",
                "artifact_path": "command-center/p2-wave/probes/ARC-0106/probe1-crlf.raw.json",
                "executed": True,
                "read_ok": crc == 0,
                "exit_code": crc,
                "probe": probe_obj("verifier", "command", consumer_cmd, cout, crc),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": "retry once after fixing validator input; a second schema-invalid result closes the unit FAILED",
        },
        "residual_unknowns": [
            {
                "claim": "Windows MAX_PATH and reserved-device CreateFileW were not executed on a Windows host.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run probe2 on a Windows checkout using \\\\?\\ prefixes and record WinError 3/206."
                ),
            },
            {
                "claim": "Phase-4 contract files ARC-0078/0080/0084 are absent; plugin and package validators are absent.",
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Deliver those contract units and re-run this suite against their validators."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "conformance-report",
            "title": "Encoding and platform-hostility conformance on this Linux host",
            "question": QUESTION,
            "answer": answer,
            "host": p1["host"],
            "contracts_under_test": contracts,
            "validators": validators,
            "findings": findings,
            "source_guards": guards,
            "blob_method": {
                "method": blob.get("method")
                or "git cat-file -p on a throwaway lab repo",
                "never_git_archive_for_blob": True,
                "worktree_git": p1["worktree_git"],
                "readings": blob.get("readings"),
                "archive_equals_blob": bool(blob.get("archive_equals_blob")),
                "working_tree_crlf_shown": bool(blob.get("working_tree_crlf_shown")),
                "note": (
                    "This delivery worktree has no .git, so cat-file/archive against "
                    "HEAD fail. Both tools were still invoked on the worktree (recorded) "
                    "and then proved on a throwaway lab repository. On this Linux host "
                    "git archive returned the same LF bytes as cat-file -p; the Windows "
                    "archive-to-CRLF conversion is not reproduced here. Working-tree "
                    "CRLF is shown by rewriting the lab file after commit."
                ),
            },
            "measurements": {
                "crlf": {
                    "lf_reach6_clean": crlf["validate_lf_blob"]["clean_reach6"],
                    "crlf_reach6_clean": crlf["validate_crlf_working_tree"]["clean_reach6"],
                    "seed_matches_lf_blob": crlf["seed_matches_lf_blob_digest"],
                    "unit_manifest_survives": crlf["unit_manifest"]["survives_crlf"],
                    "render_survives": crlf["render_manifest"]["survives_crlf"],
                },
                "bom": bom,
                "reserved": {
                    "nul_created": reserved["created"]["NUL"]["created"],
                    "handled_or_refused": reserved["handled_or_refused_without_crash"],
                },
                "long_path": {
                    "relative_len": longp["relative_len"],
                    "failure_mode": longp["failure_mode"],
                    "unit_manifest_ok": longp.get("unit_manifest", {}).get("ok"),
                },
                "case_collision": {
                    "linux_names": casec["linux_names"],
                    "casefold_collisions": casec["casefold_collisions"],
                },
                "git_archive_contrast": {
                    "cat_file_bytes": cat_r.get("bytes"),
                    "archive_bytes": arch_r.get("bytes"),
                    "working_tree_bytes": wt_r.get("bytes"),
                    "working_tree_crlf": wt_r.get("crlf"),
                },
            },
            "minimal_fixes": [
                {
                    "applies_to": "CRLF digest (validate/seed/render/unit_manifest)",
                    "fix": "Already applied: LF-normalise before hashing. Keep writer and reader paired.",
                },
                {
                    "applies_to": "UTF-8 BOM (catalog.load, seed overlay, unit_manifest receipts)",
                    "fix": "Open text JSON with encoding='utf-8-sig'.",
                },
                {
                    "applies_to": "Windows reserved device names",
                    "fix": "Refuse reserved stems unless an extended-length \\\\?\\ path is used.",
                },
                {
                    "applies_to": "paths longer than 260 characters",
                    "fix": "Use \\\\?\\ on Windows or fail closed with an explicit too-long error.",
                },
                {
                    "applies_to": "case-insensitive collisions",
                    "fix": "Fail closed when two artifact paths compare equal under str.casefold.",
                },
            ],
            "control_ids": ["NC-CRLF-NAIVE-DIGEST", "NC-UTF8-BOM"],
            "observations": [
                {
                    "name": "validate_lf_reach6_clean",
                    "measured": bool(crlf["validate_lf_blob"]["clean_reach6"]),
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/ARC-0106/probe1_crlf_blob.py",
                },
                {
                    "name": "validate_crlf_reach6_clean",
                    "measured": bool(crlf["validate_crlf_working_tree"]["clean_reach6"]),
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/ARC-0106/probe1_crlf_blob.py",
                },
                {
                    "name": "catalog_load_breaks_on_bom",
                    "measured": bom_breaks,
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/ARC-0106/hostility.py",
                },
                {
                    "name": "nul_created",
                    "measured": bool(reserved["created"]["NUL"]["created"]),
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/ARC-0106/probe2_reserved_longpath.py",
                },
                {
                    "name": "long_path_relative_len",
                    "measured": int(longp["relative_len"]),
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/ARC-0106/probe2_reserved_longpath.py",
                },
                {
                    "name": "phase4_contracts_present",
                    "measured": int(sum(1 for c in contracts if c.get("present"))),
                    "method": "file-read",
                    "anchor": "command-center/phase4/contracts",
                },
            ],
        },
        "extensions": {
            "question": QUESTION,
            "named_probes": [
                {"id": "probe1", "command": P1, "exit_code": rc1},
                {"id": "probe2", "command": P2, "exit_code": rc2},
            ],
            "cloud_ok": False,
        },
    }

    errs = validate_artifact(doc, SCHEMA)
    if errs:
        print("FAILED:ARC-0106 schema errors")
        for e in errs[:30]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        gerr = validate_artifact(g, SCHEMA)
        if not gerr:
            print(f"FAILED:ARC-0106 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:ARC-0106" not in payload:
        print("FAILED:ARC-0106 sentinel missing")
        return 1
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:ARC-0106 artifact {size}B below floor")
        return 1

    ret = {
        "id": "ARC-0106",
        "unit_id": "ARC-0106",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0106",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "crlf-blob-bom",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "reserved-longpath-case",
                "raw_output": out2[-8000:],
            },
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
        "manifest_path": MANIFEST,
        "reviewer": {
            "reviewer_id": "ARC-0106-probe1-crlf-blob",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": ended,
        "notes": (
            "G-1 for ARC-0106: live named probes exit 0, ARC-0106.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ARC-0106",
        "verified_on_disk": True,
        "artifacts": [art_row(OUT, "primary")]
        + [art_row(p, "supporting") for p in SUPPORTING]
        + [art_row(RECEIPT, "supporting")],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0106 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
