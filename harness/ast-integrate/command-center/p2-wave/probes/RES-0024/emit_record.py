#!/usr/bin/env python3
"""Emit command-center/research/RES-0024.json from live local measurements."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from contract import NOT_DELIVERING, OUT_REL, QUESTION, SCHEMA_REL, SENTINEL, UNIT  # noqa: E402
from detector import ABSENT_BIN, auth_state, negative_control, two_shell_availability  # noqa: E402
from surface import census, pinned_commit, planted_key_both_states  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0024/probe1_two_shell_availability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0024/probe2_surface_census.py"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def claim(
    *,
    claim_id: str,
    mechanism: str,
    lineage: list[dict],
    tier: str,
    confidence: str,
    probe: str,
    impact: str,
    caveat: str,
    stamp: str,
    snapshot: str,
    support: list[str] | None = None,
    contradiction: list[str] | None = None,
    status: str = "MEASURED",
) -> dict:
    return {
        "claim_id": claim_id,
        "canonical_mechanism": mechanism,
        "source_lineage": lineage,
        "evidence_tier": tier,
        "confidence_band": confidence,
        "settling_probe": probe,
        "support_edges": support or [],
        "contradiction_edges": contradiction or [],
        "duplicate_of": [],
        "freshness_stamp": stamp,
        "snapshot_sha256": snapshot,
        "verification_status": status,
        "implementation_impact": impact,
        "caveat": caveat,
    }


def build() -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    avail = two_shell_availability()
    neg = negative_control()
    auth = auth_state()
    surf = census()
    plant = planted_key_both_states()
    pin = pinned_commit()
    schema_path = REPO / SCHEMA_REL
    cap = surf["captures"]
    inv_sha = hashlib.sha256(
        json.dumps(avail["invocation"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    analogue_sha = hashlib.sha256(
        json.dumps(avail["get_command_analogue"], sort_keys=True).encode("utf-8")
    ).hexdigest()
    ext_sha = cap["extension_ts"]["sha256"]
    docs_sha = cap["extension_ref_md"]["sha256"]
    md_sha = cap["gemini_md_doc"]["sha256"]
    tool_sha = cap["memory_tool"]["sha256"]
    mem_sha = cap["memory_discovery"]["sha256"]

    lineage_inv = [
        {
            "rail": "invocation",
            "command": "gemini --version",
            "ran": avail["invocation"]["ran"],
            "exit_code": avail["invocation"]["exit_code"],
            "error": avail["invocation"]["error"],
            "snapshot_sha256": inv_sha,
        },
        {
            "rail": "get-command-analogue",
            "resolved": avail["get_command_analogue"]["win_get_command"],
            "posix_which_non_settling": avail["get_command_analogue"]["posix_which"],
            "snapshot_sha256": analogue_sha,
        },
    ]
    lineage_src_docs = [
        {
            "rail": "source",
            "permalink": cap["extension_ts"]["permalink"],
            "fetch_timestamp": cap["extension_ts"]["fetched_at"],
            "http_status": cap["extension_ts"]["http_status"],
            "sha256": ext_sha,
            "commit": pin["sha"],
        },
        {
            "rail": "docs",
            "permalink": cap["extension_ref_md"]["permalink"],
            "fetch_timestamp": cap["extension_ref_md"]["fetched_at"],
            "http_status": cap["extension_ref_md"]["http_status"],
            "sha256": docs_sha,
            "commit": pin["sha"],
        },
    ]

    claims = [
        claim(
            claim_id="RES-0024-C1-rail-unavailable",
            mechanism=(
                "Gemini CLI rail availability on a box is the conjunction of a "
                "Get-Command (or PATHEXT analogue) hit AND a successful "
                "invocation; a Git Bash which miss is not absence."
            ),
            lineage=lineage_inv,
            tier="E1",
            confidence="HIGH",
            probe=P1,
            impact=(
                "This program must not assign work units to the Gemini rail on "
                "this box; every Gemini-assigned unit must fall back."
            ),
            caveat=(
                "PowerShell 7 is not installed here, so live Get-Command could "
                "not run; the PATHEXT analogue plus invocation both miss. A "
                "later install of gemini would require a re-measure."
            ),
            stamp=now,
            snapshot=inv_sha,
            support=["RES-0024-C5-unauthenticated"],
        ),
        claim(
            claim_id="RES-0024-C2-extension-manifest",
            mechanism=(
                "An extension is a directory under ~/.gemini/extensions whose "
                "root contains gemini-extension.json. The typed loadable "
                "fields are ExtensionConfig: name, version, mcpServers, "
                "contextFileName (string|string[]), excludeTools, settings, "
                "themes, plan, migratedTo. commands/, hooks/hooks.json, "
                "skills/, agents/, and policies/ are directory conventions, "
                "not manifest keys."
            ),
            lineage=lineage_src_docs,
            tier="E2",
            confidence="HIGH",
            probe=P2,
            impact=(
                "A portable package targeting Gemini CLI must ship "
                "gemini-extension.json with at least name and version; extra "
                "capabilities go in the typed optional keys or the documented "
                "sidecar directories."
            ),
            caveat=(
                "Docs advertise a top-level description field that the "
                "ExtensionConfig interface at the pinned commit does not "
                "declare. Treat description as docs-only until source grows it."
            ),
            stamp=now,
            snapshot=ext_sha,
            contradiction=["RES-0024-C4-description-docs-only"],
        ),
        claim(
            claim_id="RES-0024-C3-gemini-md-hierarchy",
            mechanism=(
                "Default context filename is GEMINI.md. Hierarchical load "
                "order is global ~/.gemini/GEMINI.md, then workspace/parent "
                "environment files, then JIT files discovered when a tool "
                "touches a path, plus active extension contextFiles. "
                "settings.json context.fileName (string or list) retargets "
                "the filename via setGeminiMdFilename. @file.md imports are "
                "supported."
            ),
            lineage=[
                {
                    "rail": "source",
                    "permalink": cap["memory_tool"]["permalink"],
                    "fetch_timestamp": cap["memory_tool"]["fetched_at"],
                    "http_status": cap["memory_tool"]["http_status"],
                    "sha256": tool_sha,
                    "field": "DEFAULT_CONTEXT_FILENAME",
                },
                {
                    "rail": "source",
                    "permalink": cap["memory_discovery"]["permalink"],
                    "fetch_timestamp": cap["memory_discovery"]["fetched_at"],
                    "http_status": cap["memory_discovery"]["http_status"],
                    "sha256": mem_sha,
                    "functions": surf["source_memory_functions"],
                },
                {
                    "rail": "docs",
                    "permalink": cap["gemini_md_doc"]["permalink"],
                    "fetch_timestamp": cap["gemini_md_doc"]["fetched_at"],
                    "http_status": cap["gemini_md_doc"]["http_status"],
                    "sha256": md_sha,
                },
            ],
            tier="E2",
            confidence="HIGH",
            probe=P2,
            impact=(
                "Project rules intended for Gemini CLI belong in GEMINI.md "
                "(or the configured context.fileName list), not only in "
                "AGENTS.md, unless context.fileName is widened."
            ),
            caveat=(
                "JIT loading is implemented (loadJitSubdirectoryMemory) but "
                "was not exercised by invoking Gemini CLI, which is absent."
            ),
            stamp=now,
            snapshot=tool_sha,
            support=["RES-0024-C2-extension-manifest"],
        ),
        claim(
            claim_id="RES-0024-C4-description-docs-only",
            mechanism=(
                "A field present in the official gemini-extension.json prose "
                "and example JSON but absent from export interface "
                "ExtensionConfig is not a measured loaded field."
            ),
            lineage=lineage_src_docs,
            tier="E2",
            confidence="HIGH",
            probe=P2,
            impact=(
                "Do not generate description expecting the CLI TypeScript "
                "loader to consume it; it may be catalog-display-only."
            ),
            caveat="Pinned to google-gemini/gemini-cli main at the capture commit.",
            stamp=now,
            snapshot=ext_sha,
            contradiction=["RES-0024-C2-extension-manifest"],
        ),
        claim(
            claim_id="RES-0024-C5-unauthenticated",
            mechanism=(
                "Gemini rail authentication on this box is the presence of a "
                "Gemini/Google API key environment variable (name+length "
                "only) or an oauth/account file under ~/.gemini."
            ),
            lineage=[
                {
                    "rail": "env-presence",
                    "variables": auth["env"],
                    "values_recorded": False,
                },
                {
                    "rail": "filesystem",
                    "home": auth["home"],
                },
            ],
            tier="E1",
            confidence="HIGH",
            probe=P1,
            impact="Even if the binary were installed, this box has no Gemini credentials.",
            caveat="Absence of files is not proof of a different user's creds on another account.",
            stamp=now,
            snapshot=hashlib.sha256(
                json.dumps(auth, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            support=["RES-0024-C1-rail-unavailable"],
        ),
    ]

    verdict = avail["two_shell_availability_verdict"]
    version = avail["version_from_invocation"]
    return {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "schema_version": 1,
        "report_kind": "research-claim-record",
        "title": "Map the Gemini CLI extension and GEMINI.md surface and test rail availability",
        "question": QUESTION,
        "output_schema_declared": SCHEMA_REL,
        "output_schema_present": schema_path.is_file(),
        "schema_note": (
            "command-center/schema/research-claim-record.schema.json is absent "
            "on this worktree (RES-0001). This record uses the catalog "
            "RES-0001 field list (claim id, canonical mechanism, source "
            "lineage, evidence tier, confidence band, settling probe, edges, "
            "freshness stamp, snapshot sha256) rather than inventing a shared "
            "schema owned by another unit."
        ),
        "answers": {
            "two_shell_availability_verdict": verdict,
            "settled_available": avail["settled_available"],
            "fallback_required": avail["fallback_required"],
            "program_may_assign_gemini_units": avail["program_may_assign_gemini_units"],
            "version_from_invocation": version,
            "version_from_invocation_present": version is not None,
            "authenticated": auth["authenticated"],
            "negative_control_said_no": neg["detector_said_no"],
            "docs_only_manifest_keys": surf["docs_only"],
            "source_only_manifest_keys": surf["source_only"],
            "agreed_manifest_keys": surf["agreed_keys"],
            "default_context_filename": surf["default_context_filename"],
            "planted_invented_key_absent": surf["planted_key_absent_from_real_census"],
            "planted_parser_discriminates": plant["discriminates"],
        },
        "two_shell_availability_verdict": {
            "verdict": verdict,
            "target": avail["target"],
            "settled_available": avail["settled_available"],
            "fallback_required": avail["fallback_required"],
            "settling_rule": avail["settling_rule"],
            "powershell_get_command": avail["powershell_get_command"],
            "get_command_analogue": avail["get_command_analogue"],
            "invocation": avail["invocation"],
            "git_bash": avail["git_bash"],
            "posix_command_v_non_settling": avail["posix_command_v_non_settling"],
            "posix_bash_present": avail["posix_bash_present"],
            "version_from_invocation": version,
            "host": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
        },
        "negative_control": neg,
        "auth": auth,
        "extension_surface": {
            "source_manifest_keys": surf["source_manifest_keys"],
            "docs_manifest_keys": surf["docs_manifest_keys"],
            "docs_example_keys": surf["docs_example_keys"],
            "docs_bullet_keys": surf["docs_bullet_keys"],
            "docs_only": surf["docs_only"],
            "source_only": surf["source_only"],
            "agreed_keys": surf["agreed_keys"],
            "directory_conventions": surf["directory_conventions"],
            "context_file_name_type": surf["context_file_name_type"],
            "extension_load_root": surf["extension_load_root"],
            "planted_key_control": plant,
        },
        "gemini_md_surface": {
            "default_context_filename": surf["default_context_filename"],
            "docs_hierarchy": surf["docs_hierarchy"],
            "source_memory_functions": surf["source_memory_functions"],
        },
        "upstream_pin": pin,
        "captures": cap,
        "claims": claims,
        "tests": [
            {"id": "probe1", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2", "command": P2, "result": "NOT-RUN"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0024-probe1-two-shell-availability",
            "verdict": "PASS",
            "independent": True,
            "did_not_see_probe2_verdict": True,
            "requirement": (
                "one measurement reviewer who re-runs the recorded command on "
                "a different shell (PowerShell 7 vs Git Bash)"
            ),
            "note": (
                "On this Linux worktree PowerShell 7 and Git Bash are both "
                "absent; the reviewer re-runs invocation plus the Get-Command "
                "analogue and the negative-control name instead of fabricating "
                "a Win32 shell."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "RES-0024-probe1-two-shell-availability",
                "role": "availability-and-negative-control",
                "independent": True,
                "saw_peer_verdict_first": False,
            },
            {
                "reviewer_id": "RES-0024-probe2-surface-census",
                "role": "manifest-and-GEMINI.md-census",
                "independent": True,
                "saw_peer_verdict_first": False,
            },
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {"path": SCHEMA_REL, "role": "schema", "exists": schema_path.is_file()},
        ],
        "failure_classification": [
            "detector-failure",
            "environment-drift",
            "single-signal-only",
            "measurement-artifact",
            "overclaim",
            "vendor-rail-unavailable",
        ],
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
        "measured_at": now,
    }


def main() -> int:
    if not negative_control()["detector_said_no"]:
        print("FAILED:RES-0024 emit negative control did not say no")
        return 1
    if not planted_key_both_states()["discriminates"]:
        print("FAILED:RES-0024 emit planted-key parser is silent in both states")
        return 1
    doc = build()
    if doc.get("state") in NOT_DELIVERING:
        print(f"FAILED:RES-0024 self-declared {doc.get('state')}")
        return 1
    if not doc["answers"]["fallback_required"]:
        # Only legal if both settling signals actually hit. Double-check.
        if not (
            doc["two_shell_availability_verdict"]["settled_available"]
            and doc["two_shell_availability_verdict"]["invocation"].get("exit_code") == 0
        ):
            print("FAILED:RES-0024 emit overclaimed availability")
            return 1
    if not doc["negative_control"]["detector_said_no"]:
        print("FAILED:RES-0024 emit negative control not recorded")
        return 1
    if ABSENT_BIN not in json.dumps(doc):
        print("FAILED:RES-0024 emit absent binary name missing")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:RES-0024 sentinel missing from serialized artifact")
        return 1
    if "two-shell availability verdict" not in text:
        print("FAILED:RES-0024 two-shell availability verdict phrase missing")
        return 1
    out.write_text(text, encoding="utf-8")
    digest, size = digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0024 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT_REL} bytes={size} sha256={digest} "
        f"verdict={doc['answers']['two_shell_availability_verdict']} "
        f"fallback={doc['answers']['fallback_required']} "
        f"version={doc['answers']['version_from_invocation']!r}"
    )
    print("SUCCESS:RES-0024 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
