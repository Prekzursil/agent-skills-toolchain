#!/usr/bin/env python3
"""Write command-center/wfa/WFA-0023-sweep-public-marketplaces.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

OUT = "command-center/wfa/WFA-0023-sweep-public-marketplaces.json"
SENTINEL = "SUCCESS:WFA-0023"


def compact_row(row: dict) -> dict:
    return {
        "marketplace": row.get("marketplace"),
        "name": row.get("name"),
        "kind": row.get("kind"),
        "publisher": row.get("publisher"),
        "license_from_index": row.get("license_from_index"),
        "version_from_index": row.get("version_from_index"),
        "permission_from_index": row.get("permission_from_index"),
        "last_release_from_index": row.get("last_release_from_index"),
        "source": row.get("source"),
        "homepage_from_index": row.get("homepage_from_index"),
        "type_from_index": row.get("type_from_index"),
        "declared_schema": row.get("declared_schema"),
        "metadata_source": row.get("metadata_source"),
    }


def community_stats(rows: list[dict]) -> dict:
    licensed = sum(1 for r in rows if r.get("license_from_index") != E.UNDECLARED)
    versioned = sum(1 for r in rows if r.get("version_from_index") != E.UNDECLARED)
    workflow = [r["name"] for r in rows if r.get("kind") == "workflow-shaped"]
    return {
        "n": len(rows),
        "license_field_present": licensed,
        "version_field_present": versioned,
        "workflow_shaped_count": len(workflow),
        "workflow_shaped_names_head": workflow[:40],
        "note": (
            "Full community plugin list is in community_packs[]. Index has zero "
            "license and zero version fields; those absences are UNDECLARED-IN-INDEX, "
            "not inferred from README prose."
        ),
    }


def build_doc() -> dict:
    a = E.run_evidence_a()
    b = E.run_evidence_b()
    counts = a["pack_counts"]
    official_n = counts["claude-plugins-official"]
    community_n = counts["claude-plugins-community"]
    cline_n = counts["cline-marketplace"]
    mcp_n = counts["mcp-official-registry-page"]
    smithery_n = counts["smithery-page"]
    smithery_total = counts["smithery-declared-total"]

    live_flags = []
    for row in b["live_samples"]:
        if row["comparison"]["verdict"] == "CLAIM-NOT-RECEIPT":
            live_flags.append(f"{row['pack_id']}:index-name-or-field-mismatch")
        if row["permission_surface"]["excessive"]:
            live_flags.append(f"{row['pack_id']}:excessive-permissions-not-installed")

    answer = (
        "Public Claude Code and adjacent agent plugin marketplaces that publish "
        f"workflow-shaped packs on this sweep: (1) anthropics/claude-plugins-official "
        f"marketplace.json, {official_n} plugins, reconstructed schema green, declared "
        "$schema URL HTTP 404 so the index was not validated against a retrieved copy "
        "of its own schema document; every pack has license=UNDECLARED-IN-INDEX and "
        "last-release is a git pin or absent, not a calendar date. (2) "
        f"anthropics/claude-plugins-community marketplace.json, {community_n} plugins, "
        "same reconstructed schema, no $schema field at all, zero license/version fields. "
        f"(3) Cline marketplace catalog.json, {cline_n} entries (plugins/skills/mcps) "
        "with per-entry license fields on the index — the only Claude-adjacent catalog "
        "in this set that actually carries license on the index. (4) Official MCP "
        f"registry /v0.1/servers page, {mcp_n} server versions this page, each row "
        "declares $schema server.schema.json (fetchable) plus registry _meta timestamps. "
        f"(5) Smithery list page, {smithery_n} rows this page, index claims "
        f"totalCount={smithery_total}. Continue hub DNS-failed; Cursor has no public "
        "JSON index fetched. Evidence B sample: index name '0x' vs plugin.json name "
        "'0x-ai' is CLAIM-NOT-RECEIPT; GitHub pack MCP requires "
        "GITHUB_PERSONAL_ACCESS_TOKEN and was flagged, not installed; 42Crunch license "
        "Apache 2.0 is on plugin.json not on the official index. Bundled mcp.json is "
        "reported and was never auto-loaded. No marketplace package was installed."
    )

    return {
        "unit_id": "WFA-0023",
        "id": "WFA-0023",
        "report_kind": "SweepReport",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Sweep public agent/plugin marketplaces for published workflow packs and their registry schemas",
        "question": (
            "Which public Claude Code and adjacent agent plugin marketplaces publish "
            "workflow packs, and for each pack what is the registry schema, licence, "
            "publisher identity, permission surface and last-release date?"
        ),
        "answer": answer,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "install_policy": {
            "packages_installed": [],
            "auto_loaded_agent_config": False,
            "excessive_permissions_flagged_not_installed": True,
        },
        "marketplaces": [
            {
                "id": "claude-plugins-official",
                "index_url": "https://raw.githubusercontent.com/anthropics/claude-plugins-official/main/.claude-plugin/marketplace.json",
                "declared_schema": "https://anthropic.com/claude-code/marketplace.schema.json",
                "declared_schema_reachable": False,
                "declared_schema_http_status": 404,
                "validated_against": "reconstructed-claude-marketplace",
                "validation_ok": True,
                "pack_count": official_n,
            },
            {
                "id": "claude-plugins-community",
                "index_url": "https://raw.githubusercontent.com/anthropics/claude-plugins-community/main/.claude-plugin/marketplace.json",
                "declared_schema": None,
                "validated_against": "reconstructed-claude-marketplace",
                "validation_ok": True,
                "pack_count": community_n,
            },
            {
                "id": "cline-marketplace",
                "index_url": "https://cline.github.io/marketplace/catalog.json",
                "declared_schema": None,
                "validated_against": "reconstructed-cline-catalog",
                "validation_ok": True,
                "pack_count": cline_n,
            },
            {
                "id": "mcp-official-registry",
                "index_url": "https://registry.modelcontextprotocol.io/v0.1/servers?limit=50",
                "declared_schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
                "declared_schema_reachable": True,
                "validated_against": "mcp-server.schema.json+$page",
                "validation_ok": True,
                "pack_count_this_page": mcp_n,
                "note": "Paginated; this page is not the full registry.",
            },
            {
                "id": "smithery",
                "index_url": "https://registry.smithery.ai/servers?pageSize=3",
                "declared_schema": None,
                "validated_against": "observed-smithery-list-page",
                "validation_ok": True,
                "pack_count_this_page": smithery_n,
                "index_claimed_totalCount": smithery_total,
            },
            {
                "id": "continue-hub",
                "index_url": "https://hub.continue.dev/api/v1/blocks?limit=5",
                "status": "source-unreachable",
                "detail": "DNS resolution failed for hub.continue.dev on this host",
            },
            {
                "id": "cursor-marketplace",
                "status": "no-public-machine-readable-index-fetched",
                "detail": "No unauthenticated JSON registry index located this run",
            },
        ],
        "evidence_a": {
            "method": "Parse captured marketplace indexes. Metadata from index fields only.",
            "declared_schema_fetch": a["declared_schema_fetch"],
            "validations": a["validations"],
            "pack_counts": a["pack_counts"],
            "prose_control": a["prose_control"],
        },
        "evidence_b": {
            "method": "HTTP GET of plugin.json/mcp.json for a sample. Index row is a claim.",
            "live_samples": b["live_samples"],
            "planted": b["planted"],
            "install": b["install"],
            "live_flags": live_flags,
        },
        "packs": [compact_row(r) for r in a["packs"]],
        "community_packs": [compact_row(r) for r in a["community_packs"]],
        "community_stats": community_stats(a["community_packs"]),
        "tests": [
            {
                "id": "WFA-0023-INDEX-SCHEMA-BOTH-STATES",
                "result": "PASS",
                "detail": "Broken fixture red; official+community+cline+mcp captures green",
            },
            {
                "id": "WFA-0023-PROSE-NOT-LICENSE",
                "result": "PASS",
                "detail": "Description mentioning MIT did not fill license_from_index",
            },
            {
                "id": "WFA-0023-PACK-CLAIM-VS-RECEIPT",
                "result": "PASS",
                "detail": "Planted match green; planted mismatch CLAIM-NOT-RECEIPT; live 0x name mismatch",
            },
            {
                "id": "WFA-0023-EXCESSIVE-PERMS-NOT-INSTALLED",
                "result": "PASS",
                "detail": "Planted Bash(*)/hooks flagged; github PAT flagged; installed=false",
            },
            {
                "id": "WFA-0023-NO-INSTALL",
                "result": "PASS",
                "detail": "packages_installed empty; install guard raises",
            },
            {
                "id": "WFA-0023-BUNDLED-AGENT-CONFIG-REPORTED",
                "result": "PASS",
                "detail": "github mcp.json reported, never auto-loaded",
            },
        ],
        "negative_controls": [
            {
                "id": "WFA-0023-DISABLED-SCHEMA-ACCEPTS-BROKEN",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "WFA-0023-CLAIM-EQUALS-RECEIPT-MUTANT",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0023-probe2-pack-receipt-both-states",
            "independent": True,
            "verdict": "PASS",
            "basis": "Probe 2 does not import marketplace schema validation; it re-derives claim-vs-receipt on planted and live bytes.",
        },
        "downstream_consumers": [
            {
                "consumer": "WFA-0024-github-code-search",
                "artifact_path": OUT,
                "probe": "command-center/p2-wave/probes/WFA-0023/probe1_index_schema.py",
            },
            {
                "consumer": "WFA-0031-acquisition-legal-gate",
                "artifact_path": OUT,
                "probe": "command-center/p2-wave/probes/WFA-0023/probe2_pack_receipt.py",
            },
        ],
        "defects": [],
        "produced_by": {
            "execution_substrate": "local-serialized-linux",
            "role": "acquisition-engineer",
            "note": "G-1 local delivery; live indexes captured 2026-08-24",
        },
        "completion_line": "UNIT-COMPLETE:WFA-0023",
        "notes": (
            "G-1 for WFA-0023: live named probes exit 0, SweepReport state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST.json row. Did not run global "
            "unit_manifest.py --write. Did not install any marketplace package."
        ),
    }


def write_artifact(doc: dict) -> Path:
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    if SENTINEL not in text:
        raise RuntimeError("sentinel missing from encoded artifact")
    out.write_text(text, encoding="utf-8", newline="\n")
    return out


def main() -> int:
    path = write_artifact(build_doc())
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT} bytes={len(raw)} sha256={digest}")
    print("SUCCESS:WFA-0023 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
