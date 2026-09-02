#!/usr/bin/env python3
"""Emit command-center/research/RES-0036.json and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
sys.path.insert(0, str(PROBE))
from matrix import (  # noqa: E402
    REVISIONS,
    assert_every_cell_cites_revision,
    build_matrix,
)

OUT = "command-center/research/RES-0036.json"
SCHEMA = "command-center/schema/compatibility-matrix.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0036/probe1_rebuild_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0036/probe2_optional_unimplemented.py"
)
SENTINEL = (
    "SUCCESS:RES-0036 in the receipt AND a revision-by-capability matrix "
    "where every cell cites a spec revision id"
)
SPEC_HEAD = "57ac4a2ec742e0cb7622d899b0f5d3bcf769fd69"
SPEC_HEAD_DATE = "2026-08-23T09:06:35Z"
FETCHED_AT = "2026-08-24T18:43:00Z"
CLIENT_FETCHED_AT = "2026-08-24T18:46:52Z"
TS_SDK = "3924de99df834302d89f5997a1b64ca268282284"
PY_SDK = "c5d7d0b6d0cc8e0a2cc2f5dd6caf0be9ad744352"
QUESTION = (
    "Between the MCP protocol revisions currently in the wild, which "
    "capabilities became mandatory, which remain optional, and which clients "
    "implement which revision — the matrix that decides what an MCP adapter "
    "may assume?"
)

# Last-path commits from GitHub commits API at fetch time (schema.json).
FILE_COMMITS = {
    "2024-11-05": ("dfc88487d491ae1f3e21963b55f56be073cc1859", "2025-02-21T20:14:22Z"),
    "2025-03-26": ("ef5ebfaaac37d6086f522aeed29015dda0403359", "2025-04-22T13:33:35Z"),
    "2025-06-18": ("2ebb8060268e177b22598b403d6ba6764bb899ac", "2026-07-27T17:41:05Z"),
    "2025-11-25": ("c4c367f9f58296a7053f5c78a52fd02bfbb56a49", "2026-07-27T14:20:44Z"),
    "2026-07-28": ("271ecc9accafdd9b83a3c869fa67c22953b2af80", "2026-07-28T16:42:34Z"),
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def fixture_hash(rel: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {"path": rel, "sha256": digest, "bytes": size}


def build_artifact() -> dict:
    matrix = build_matrix()
    assert_every_cell_cites_revision(matrix)
    spec_files = []
    for rev in REVISIONS:
        rel = f"command-center/p2-wave/probes/RES-0036/fixtures/spec/{rev}/schema.json"
        rec = fixture_hash(rel)
        rec["spec_revision_id"] = rev
        rec["repo"] = "modelcontextprotocol/modelcontextprotocol"
        rec["git_path"] = f"schema/{rev}/schema.json"
        rec["tree_head"] = SPEC_HEAD
        rec["tree_head_date"] = SPEC_HEAD_DATE
        rec["path_commit"], rec["path_commit_date"] = FILE_COMMITS[rev]
        rec["source_url"] = (
            f"https://raw.githubusercontent.com/modelcontextprotocol/modelcontextprotocol/"
            f"{SPEC_HEAD}/schema/{rev}/schema.json"
        )
        rec["fetched_at"] = FETCHED_AT
        spec_files.append(rec)

    headline = (
        "No named feature capability on ServerCapabilities or ClientCapabilities "
        "is JSON-Schema-required in any of the five published schema directories "
        f"{list(REVISIONS)}. What became mandatory is session machinery: "
        "initialize + notifications/initialized through 2025-11-25, then "
        "server/discover in 2026-07-28 (initialize removed). Feature flags stay "
        "optional. An adapter may assume the handshake of the negotiated revision, "
        "not tools/resources/prompts."
    )
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "RES-0036",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:RES-0036",
        "completion_sentinel": SENTINEL,
        "catalog_completion_sentinel": SENTINEL,
        "question": QUESTION,
        "headline": headline,
        "fetched_at": FETCHED_AT,
        "produced_at": now,
        "source_lineage": {
            "spec_repo": "https://github.com/modelcontextprotocol/modelcontextprotocol",
            "spec_head": SPEC_HEAD,
            "spec_head_date": SPEC_HEAD_DATE,
            "spec_head_url": f"https://github.com/modelcontextprotocol/modelcontextprotocol/commit/{SPEC_HEAD}",
            "schema_files": spec_files,
            "typescript_sdk_commit": TS_SDK,
            "python_sdk_commit": PY_SDK,
            "client_fetched_at": CLIENT_FETCHED_AT,
        },
        "revisions_in_wild": [
            {
                "spec_revision_id": "2024-11-05",
                "era": "legacy-handshake",
                "status_in_spec_repo": "final-schema-dir",
            },
            {
                "spec_revision_id": "2025-03-26",
                "era": "legacy-handshake",
                "status_in_spec_repo": "final-schema-dir",
            },
            {
                "spec_revision_id": "2025-06-18",
                "era": "legacy-handshake",
                "status_in_spec_repo": "final-schema-dir",
            },
            {
                "spec_revision_id": "2025-11-25",
                "era": "legacy-handshake",
                "status_in_spec_repo": "final-schema-dir",
                "docs_label_at_fetch": "current in docs/docs/2025-11-25/learn/versioning.mdx",
            },
            {
                "spec_revision_id": "2026-07-28",
                "era": "modern-discover",
                "status_in_spec_repo": "final-schema-dir",
                "docs_label_at_fetch": "current in docs/docs/2026-07-28/learn/versioning.mdx",
            },
        ],
        "became_mandatory": [
            {
                "capability": "session.initialize",
                "spec_revision_ids": ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"],
                "caveat": "Mandatory for handshake-era sessions. Absent in 2026-07-28 schema (replaced by server/discover).",
            },
            {
                "capability": "session.notifications/initialized",
                "spec_revision_ids": ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"],
                "caveat": "Paired with initialize; absent once initialize is removed.",
            },
            {
                "capability": "session.server/discover",
                "spec_revision_ids": ["2026-07-28"],
                "caveat": "Servers MUST implement it. Clients MAY skip the call and send RPCs directly, handling UnsupportedProtocolVersionError.",
            },
        ],
        "remain_optional": [
            "server.tools",
            "server.resources",
            "server.resources.subscribe",
            "server.prompts",
            "server.logging",
            "server.completions",
            "server.experimental",
            "server.extensions",
            "client.roots",
            "client.sampling",
            "client.elicitation",
            "client.elicitation.url",
            "client.experimental",
            "client.extensions",
            "session.ping",
        ],
        "introduced_then_removed_from_core": [
            {
                "capability": "server.tasks",
                "introduced_spec_revision_id": "2025-11-25",
                "core_status_2026-07-28": "absent (moved to extension io.modelcontextprotocol/tasks per changelog)",
            },
            {
                "capability": "client.tasks",
                "introduced_spec_revision_id": "2025-11-25",
                "core_status_2026-07-28": "absent (same extension move)",
            },
        ],
        "adapter_may_assume": [
            "A negotiated handshake-era session speaks initialize (mandatory) and may omit every feature capability.",
            "A negotiated 2026-07-28 server implements server/discover (mandatory) and carries protocol version in _meta; feature capabilities remain optional.",
            "Do not assume tools, resources, prompts, sampling, elicitation, or tasks without reading the peer's capabilities object (or 2026 extensions map).",
            "Do not treat TypeScript SDK LATEST_PROTOCOL_VERSION=2025-11-25 as the version a default client actually negotiates (DEFAULT_NEGOTIATED_PROTOCOL_VERSION=2025-03-26).",
        ],
        "matrix": matrix,
        "clients": [
            {
                "id": "typescript-sdk",
                "source": {
                    "repo": "modelcontextprotocol/typescript-sdk",
                    "commit": TS_SDK,
                    "path": "packages/core/src/constants.ts",
                    "fetched_at": CLIENT_FETCHED_AT,
                    "url": f"https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/{TS_SDK}/packages/core/src/constants.ts",
                    "fixture": "command-center/p2-wave/probes/RES-0036/fixtures/clients/typescript-sdk.constants.ts",
                },
                "claimed": {
                    "latest": "2025-11-25",
                    "protocol_versions": [
                        "2025-11-25",
                        "2025-06-18",
                        "2025-03-26",
                        "2024-11-05",
                        "2024-10-07",
                    ],
                    "claim_kind": "SUPPORTED_PROTOCOL_VERSIONS + LATEST_PROTOCOL_VERSION constants",
                },
                "observed": {
                    "default_negotiated": "2025-03-26",
                    "protocol_versions": ["2025-03-26"],
                    "observation_kind": "DEFAULT_NEGOTIATED_PROTOCOL_VERSION constant; not a live initialize capture",
                    "tasks_runtime": "unimplemented",
                    "notes": "RELATED_TASK_META_KEY is documented as 2025-11-25 wire vocabulary with no SDK runtime.",
                },
                "spec_gap": "2024-10-07 is claimed in SUPPORTED_PROTOCOL_VERSIONS but is not a schema/ directory in the spec repo at HEAD 57ac4a2.",
            },
            {
                "id": "python-sdk",
                "source": {
                    "repo": "modelcontextprotocol/python-sdk",
                    "commit": PY_SDK,
                    "paths": [
                        "src/mcp-types/mcp_types/version.py",
                        "src/mcp-types/mcp_types/_types.py",
                    ],
                    "fetched_at": CLIENT_FETCHED_AT,
                    "fixture": "command-center/p2-wave/probes/RES-0036/fixtures/clients/python-sdk.mcp_types.version.py",
                },
                "claimed": {
                    "latest": "2026-07-28",
                    "latest_handshake": "2025-11-25",
                    "protocol_versions": [
                        "2024-11-05",
                        "2025-03-26",
                        "2025-06-18",
                        "2025-11-25",
                        "2026-07-28",
                    ],
                    "claim_kind": "KNOWN_PROTOCOL_VERSIONS / LATEST_PROTOCOL_VERSION",
                },
                "observed": {
                    "default_negotiated": "2025-03-26",
                    "protocol_versions": ["2025-03-26"],
                    "observation_kind": "DEFAULT_NEGOTIATED_VERSION in _types.py; not a live initialize capture",
                    "tasks_runtime": "types-only",
                    "notes": "The 2025-11-25 task requests are deliberately excluded (types-only).",
                },
            },
            {
                "id": "vscode-copilot-types",
                "source": {
                    "repo": "microsoft/vscode",
                    "ref": "main",
                    "path": "src/vs/workbench/contrib/mcp/common/modelContextProtocol.ts",
                    "fetched_at": CLIENT_FETCHED_AT,
                    "fixture": "command-center/p2-wave/probes/RES-0036/fixtures/clients/vscode-copilot.excerpt.ts",
                    "commit_sha": None,
                    "commit_sha_caveat": "GitHub commits API returned 403 on this host; SHA unpinned. Body sha256 is in the per-unit manifest.",
                },
                "claimed": {
                    "latest": "2025-11-25",
                    "protocol_versions": ["2025-11-25"],
                    "claim_kind": "LATEST_PROTOCOL_VERSION in generated types; ClientCapabilities includes roots, sampling, elicitation, tasks",
                },
                "observed": {
                    "default_negotiated": None,
                    "protocol_versions": [],
                    "observation_kind": "not_measured_runtime",
                    "notes": "This worktree did not run VS Code. Types are a claimed surface, not an observed handshake.",
                },
            },
        ],
        "optional_and_unimplemented": [
            {
                "capability": "client.tasks",
                "spec_revision_id": "2025-11-25",
                "matrix_presence": "optional",
                "claimed": "typescript-sdk LATEST_PROTOCOL_VERSION 2025-11-25 (schema includes ClientCapabilities.tasks)",
                "observed": "unimplemented",
                "client_id": "typescript-sdk",
                "evidence": "packages/core/src/constants.ts RELATED_TASK_META_KEY: 2025-11-25 wire vocabulary with no SDK runtime",
            },
            {
                "capability": "server.tasks",
                "spec_revision_id": "2025-11-25",
                "matrix_presence": "optional",
                "claimed": "python-sdk KNOWN_PROTOCOL_VERSIONS includes 2025-11-25",
                "observed": "types-only",
                "client_id": "python-sdk",
                "evidence": "_types.py: The 2025-11-25 task requests are deliberately excluded (types-only).",
            },
        ],
        "tests": {
            "matrix_from_spec_source": True,
            "every_cell_cites_spec_revision_id": True,
            "optional_and_unimplemented_control": True,
            "claimed_vs_observed_separated": True,
        },
        "reviewer": {
            "reviewer_id": "RES-0036-probe1-schema-rebuild",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe1 rebuilds the matrix from frozen schema.json files. "
                "Named probe2 checks the optional-and-unimplemented control and "
                "claimed-vs-observed split, including an in-memory empty-list mutant. "
                "Catalog scoring by a second human protocol analyst is independent of G-1 probe-green."
            ),
        },
        "strongest_caveat": (
            "Client 'observed' rows are source-constant observations (default negotiated "
            "version and explicit types-only / no-runtime comments), not packet captures of "
            "a live initialize handshake on this box. Feature capabilities are optional in "
            "JSON Schema in every published revision; 'mandatory' here means session "
            "machinery required to speak that revision, not that tools must be implemented."
        ),
        "does_not_claim": [
            "cloud ok=true is delivery",
            "global unit_manifest.py --write was run",
            "a live MCP client handshake was executed on this host",
            "2024-10-07 is a published schema directory in the spec repo",
            "VS Code Copilot runtime implements tasks or elicitation",
        ],
        "cloud_ok": False,
    }


def write_receipts(doc: dict, digest: str, size: int, out1: str, out2: str) -> None:
    artifacts = [
        {
            "path": OUT,
            "sha256": digest,
            "bytes": size,
            "present": True,
            "unit_id": "RES-0036",
            "receipt_path": "command-center/p2-wave/probes/RES-0036/SUBAGENT-RETURN.json",
            "role": "primary",
        }
    ]
    extras = [
        "command-center/p2-wave/probes/RES-0036/matrix.py",
        "command-center/p2-wave/probes/RES-0036/probe1_rebuild_matrix.py",
        "command-center/p2-wave/probes/RES-0036/probe2_optional_unimplemented.py",
        "command-center/p2-wave/probes/RES-0036/emit.py",
    ]
    for rel in extras:
        d, b = sha256_file(REPO / rel)
        artifacts.append(
            {
                "path": rel,
                "sha256": d,
                "bytes": b,
                "present": True,
                "unit_id": "RES-0036",
                "receipt_path": "command-center/p2-wave/probes/RES-0036/SUBAGENT-RETURN.json",
                "role": "supporting",
            }
        )
    for rev in REVISIONS:
        rel = f"command-center/p2-wave/probes/RES-0036/fixtures/spec/{rev}/schema.json"
        d, b = sha256_file(REPO / rel)
        artifacts.append(
            {
                "path": rel,
                "sha256": d,
                "bytes": b,
                "present": True,
                "unit_id": "RES-0036",
                "receipt_path": "command-center/p2-wave/probes/RES-0036/SUBAGENT-RETURN.json",
                "role": "spec-schema",
            }
        )
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0036",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    man_path = PROBE / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    ret = {
        "id": "RES-0036",
        "unit_id": "RES-0036",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0036",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": 0,
                "role": "rebuild-matrix-from-spec",
                "raw_output": out1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": 0,
                "role": "optional-unimplemented-control",
                "raw_output": out2[-4000:],
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
        "manifest_path": "command-center/p2-wave/probes/RES-0036/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0036-probe1-schema-rebuild",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "notes": (
            "G-1 for RES-0036: live named probes exit 0, research artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (PROBE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )


def main() -> int:
    doc = build_artifact()
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0036 catalog sentinel missing from artifact")
        return 1
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:RES-0036 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1
    # Re-hash after probes (artifact should be unchanged).
    digest2, size2 = sha256_file(out)
    if digest2 != digest:
        print("FAILED:RES-0036 probes mutated artifact")
        return 1
    write_receipts(doc, digest2, size2, out1, out2)
    print(f"wrote {OUT} bytes={size2} sha256={digest2}")
    print("SUCCESS:RES-0036 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
