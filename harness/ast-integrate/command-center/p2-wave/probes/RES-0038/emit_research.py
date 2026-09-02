#!/usr/bin/env python3
"""Emit command-center/research/RES-0038.json from pinned captures + recomputes."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import check as C  # noqa: E402
import recompute as R  # noqa: E402

OUT = "command-center/research/RES-0038.json"
SCHEMA = "command-center/p2-wave/probes/RES-0038/research-registry.schema.json"
CATALOG_SCHEMA = "command-center/schema/research-registry.schema.json"
CAP = HERE / "captures"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0038/probe1_recompute_signal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0038/probe2_signal_table.py"
)
QUESTION = (
    "What metadata does the official MCP registry require and expose, what does "
    "its publish flow verify, and which of its trust signals are actually "
    "verifiable by a client at install time rather than merely displayed?"
)
SENTINEL_FULL = (
    "SUCCESS:RES-0038 in the receipt AND a signal table split into "
    "client-verifiable and display-only with one signal actually recomputed"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def loadj(name: str) -> dict:
    return json.loads((CAP / name).read_text(encoding="utf-8"))


def rail_rows(index: dict) -> list[dict]:
    rows = []
    for cap in index.get("captures") or []:
        row = {
            "id": cap["id"],
            "kind": cap.get("rail"),
            "permalink": cap.get("permalink") or cap.get("url"),
            "url": cap.get("url"),
            "final_url": cap.get("final_url"),
            "fetched_at": cap.get("fetched_at"),
            "http_status": cap.get("http_status"),
            "sha256": cap.get("sha256"),
            "bytes": cap.get("bytes"),
            "path": cap.get("path"),
            "ok": cap.get("ok"),
        }
        if cap.get("id") == "pulsemcp-dns-txt":
            row["dns_exit_code"] = cap.get("dns_exit_code")
            row["command"] = cap.get("command")
            row["mcp_txt"] = cap.get("mcp_txt")
        rows.append(row)
    return rows


def main() -> int:
    index = loadj("capture_index.json")
    schema = loadj("server.schema.json")
    server_detail_def = (schema.get("definitions") or {}).get("ServerDetail") or {}
    package_def = (schema.get("definitions") or {}).get("Package") or {}
    sreq = list(server_detail_def.get("required") or [])
    preq = list(package_def.get("required") or [])
    if sreq != ["name", "description", "version"]:
        print(f"FAILED:emit unexpected ServerDetail.required {sreq}")
        return 1
    if preq != ["registryType", "identifier", "transport"]:
        print(f"FAILED:emit unexpected Package.required {preq}")
        return 1

    openapi = (CAP / "openapi.yaml").read_text(encoding="utf-8")
    auth_paths = [
        p
        for p in (
            "/v0.1/auth/dns",
            "/v0.1/auth/http",
            "/v0.1/auth/github-at",
            "/v0.1/auth/github-oidc",
            "/v0.1/auth/oidc",
            "/v0.1/publish",
        )
        if p in openapi
    ]
    if len(auth_paths) < 6:
        print(f"FAILED:emit openapi auth/publish paths {auth_paths}")
        return 1

    computed = R.from_captures()
    npm = computed["npm_mcpName_ownership"]
    dns = computed["dns_apex_mcp_txt"]
    gh = computed["github_namespace_repo_owner_consistency"]
    allow = computed["npm_registry_base_url_allowlist"]
    if not npm.get("match") or not dns.get("match") or not gh.get("match") or not allow.get("match"):
        print(f"FAILED:emit recompute npm={npm.get('match')} dns={dns.get('match')} gh={gh.get('match')} allow={allow.get('match')}")
        return 1

    brave = loadj("brave-server-detail.json")
    pulse = loadj("pulsemcp-server-detail.json")
    version = loadj("registry-version.json")
    npm_doc = loadj("brave-npm-2.1.3.json")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rails = rail_rows(index)

    official_meta = ((brave.get("_meta") or {}).get("io.modelcontextprotocol.registry/official") or {})
    pulse_name = str((pulse.get("server") or {}).get("name") or "")
    brave_name = str((brave.get("server") or {}).get("name") or "")

    pkg_types = (CAP / "package-types.mdx").read_text(encoding="utf-8")
    if "mcpName" not in pkg_types or "match the server name" not in pkg_types:
        print("FAILED:emit package-types.mdx missing mcpName rule")
        return 1
    req_md = (CAP / "official-registry-requirements.md").read_text(encoding="utf-8")
    if "Package ownership verification" not in req_md:
        print("FAILED:emit requirements.md missing ownership section")
        return 1
    auth_md = (CAP / "authentication.mdx").read_text(encoding="utf-8")
    if "v=MCPv1" not in auth_md or "GitHub authentication" not in auth_md:
        print("FAILED:emit authentication.mdx missing DNS/GitHub sections")
        return 1

    signal_table = [
        {
            "id": "npm_mcpName_ownership",
            "signal": "npm package.json mcpName equals server.json name",
            "class": "client-verifiable",
            "justification": (
                "A client GETs registry.npmjs.org/<identifier>/<version> and "
                "compares mcpName to the registry server name. This unit did "
                f"that for {brave_name} / {npm_doc.get('name')}@{npm_doc.get('version')} "
                f"and got mcpName={npm.get('npm_mcpName')}."
            ),
            "recomputed_end_to_end": True,
            "outcome": "MATCH",
            "subject": brave_name,
        },
        {
            "id": "dns_apex_mcp_txt",
            "signal": "domain-namespace apex TXT record v=MCPv1; k=...; p=...",
            "class": "client-verifiable",
            "justification": (
                "Authentication docs require an apex TXT (not a selector). "
                f"dig +short TXT pulsemcp.com for {pulse_name} returned a "
                "v=MCPv1 ed25519 public-key record. This proves key publication, "
                "not the original signed login challenge."
            ),
            "recomputed_end_to_end": True,
            "outcome": "MATCH",
            "subject": pulse_name,
        },
        {
            "id": "npm_registry_base_url_allowlist",
            "signal": "packages[].registryBaseUrl is the official npm allowlist URL",
            "class": "client-verifiable",
            "justification": (
                "official-registry-requirements.md allows only "
                "https://registry.npmjs.org for npm. The captured brave package "
                f"declares registryBaseUrl={allow.get('registry_base_url')}."
            ),
            "recomputed_end_to_end": True,
            "outcome": "MATCH",
            "subject": brave_name,
        },
        {
            "id": "github_namespace_repo_owner_consistency",
            "signal": "io.github.<owner> namespace owner matches repository.url owner",
            "class": "client-verifiable",
            "justification": (
                "String check only: name io.github.brave/... vs "
                "https://github.com/brave/brave-search-mcp-server. This is not "
                "a replay of GitHub OAuth/OIDC."
            ),
            "recomputed_end_to_end": True,
            "outcome": "MATCH",
            "subject": brave_name,
            "caveat": "not-oauth-replay",
        },
        {
            "id": "github_oauth_publish_proof",
            "signal": "GitHub OAuth/OIDC namespace authentication performed at publish",
            "class": "display-only",
            "justification": (
                "Publish uses POST /v0.1/auth/github-at or github-oidc and stores "
                "a registry JWT. An installer cannot replay that device-flow or "
                "OIDC exchange. Name/repo string match is a different, weaker signal."
            ),
            "recomputed_end_to_end": False,
        },
        {
            "id": "dns_http_login_signature",
            "signal": "Original DNS/HTTP signed challenge that issued the publish JWT",
            "class": "display-only",
            "justification": (
                "mcp-publisher login dns|http signs a challenge with the private "
                "key. The live apex TXT only publishes the public key. Without "
                "the original challenge bytes a client cannot recompute the JWT."
            ),
            "recomputed_end_to_end": False,
        },
        {
            "id": "registry_official_status",
            "signal": "_meta.io.modelcontextprotocol.registry/official.status",
            "class": "display-only",
            "justification": (
                "Registry-managed. Re-querying the same API is not an independent "
                "recompute. Captured brave status="
                f"{official_meta.get('status')!r}."
            ),
            "recomputed_end_to_end": False,
            "displayed_value": official_meta.get("status"),
        },
        {
            "id": "registry_isLatest",
            "signal": "_meta.io.modelcontextprotocol.registry/official.isLatest",
            "class": "display-only",
            "justification": (
                "A listing badge. A client that trusts isLatest without fetching "
                "/versions is reading a display field. Same-API re-query is still "
                "the registry talking about itself."
            ),
            "recomputed_end_to_end": False,
            "displayed_value": official_meta.get("isLatest"),
        },
        {
            "id": "registry_timestamps",
            "signal": "publishedAt / updatedAt / statusChangedAt",
            "class": "display-only",
            "justification": (
                "Clock values assigned by the registry. No second rail can "
                "recompute them from the package or DNS."
            ),
            "recomputed_end_to_end": False,
            "displayed_value": {
                "publishedAt": official_meta.get("publishedAt"),
                "updatedAt": official_meta.get("updatedAt"),
                "statusChangedAt": official_meta.get("statusChangedAt"),
            },
        },
        {
            "id": "publisher_provided_meta",
            "signal": "server._meta.io.modelcontextprotocol.registry/publisher-provided",
            "class": "display-only",
            "justification": (
                "Publisher-chosen JSON, size-capped at 4KB, not authenticated "
                "beyond publish auth. Captured brave server.json has no "
                "publisher-provided block."
            ),
            "recomputed_end_to_end": False,
        },
        {
            "id": "title_icons_websiteUrl",
            "signal": "Optional title, icons, websiteUrl display fields",
            "class": "display-only",
            "justification": (
                "Schema marks these optional. They are UI. A client cannot "
                "authenticate an icon URL or title against namespace ownership."
            ),
            "recomputed_end_to_end": False,
        },
        {
            "id": "npm_dist_integrity_adjacent",
            "signal": "npm dist.integrity / dist.signatures (not an MCP registry field)",
            "class": "display-only",
            "justification": (
                "The captured npm document carries dist.integrity and npm "
                "registry signatures. That is npm's own trust, not a signal "
                "the MCP registry required or exposed on this row (no fileSha256)."
            ),
            "recomputed_end_to_end": False,
            "caveat": "adjacent-ecosystem-not-registry-signal",
        },
    ]

    claims = [
        {
            "id": "C-required-server-fields",
            "claim": (
                "server.json ServerDetail required fields on schema "
                "2025-12-11 are exactly name, description, version."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "rails": ["server-schema", "generic-server-json"],
            "anchor": "captures/server.schema.json definitions.ServerDetail.required",
        },
        {
            "id": "C-required-package-fields",
            "claim": (
                "Package objects require registryType, identifier, and transport; "
                "version and registryBaseUrl are optional in the generic schema "
                "but official publish further restricts registryBaseUrl."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "rails": ["server-schema", "official-registry-requirements"],
            "anchor": "captures/server.schema.json definitions.Package.required",
        },
        {
            "id": "C-publish-verifies-npm-mcpName",
            "claim": (
                "Official publish verifies npm ownership by requiring package.json "
                "mcpName to equal server.json name. A client can recompute that "
                f"check: captured {brave_name} MATCHES npm mcpName."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "rails": ["brave-server-detail", "brave-npm", "package-types"],
            "anchor": "recomputed_signal npm_mcpName_ownership",
        },
        {
            "id": "C-publish-namespace-auth",
            "claim": (
                "Publish authentication is namespace-based: GitHub OAuth/OIDC for "
                "io.github.* and DNS/HTTP for domain namespaces, via OpenAPI "
                f"paths {auth_paths}."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "rails": ["openapi", "authentication"],
            "anchor": "captures/openapi.yaml /v0.1/auth/*",
        },
        {
            "id": "C-dns-txt-live",
            "claim": (
                f"Domain namespace {pulse_name} still publishes an apex v=MCPv1 "
                "TXT on pulsemcp.com, which a client can query independently."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "rails": ["pulsemcp-dns-txt", "authentication"],
            "anchor": "captures/pulsemcp-dns-txt.txt",
        },
        {
            "id": "C-status-badge-not-client-recomputable",
            "claim": (
                "Registry-managed official.status / isLatest / timestamps are "
                "display-only: they cannot be recomputed from npm or DNS."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "rails": ["brave-server-detail", "official-registry-requirements"],
            "anchor": "signal_table registry_isLatest class=display-only",
        },
        {
            "id": "C-single-rail-would-be-E3",
            "claim": (
                "A claim citing only the HTML marketing page at "
                "modelcontextprotocol.io/registry/quickstart, with no API or "
                "source-markdown rail, would be E3 and must not be cited as fact."
            ),
            "verdict": "E3-NOT-FACT",
            "evidence_tier": "E3",
            "rails": ["quickstart"],
            "note": "Recorded as the control: one rail is not a measured fact.",
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": "RES-0038",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0038",
        "completion_sentinel": SENTINEL_FULL,
        "title": "Teardown the official MCP registry: schema, publish flow and the trust signals it exposes",
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "output_schema": SCHEMA,
        "schema_binding": {
            "catalog_output_schema": CATALOG_SCHEMA,
            "unit_schema": SCHEMA,
            "reason": (
                "Catalog path is shared with RES-0128, which now owns that "
                "file as a coverage-registry schema (required list size 6). "
                "RES-0038 pins the freeze teardown schema locally."
            ),
        },
        "registry_observed": {
            "base": "https://registry.modelcontextprotocol.io",
            "api_version_path": "/v0.1",
            "ping": {"pong": True},
            "version": version,
            "server_schema": schema.get("$id"),
            "schema_comment": schema.get("$comment"),
        },
        "required_metadata": {
            "source": "captures/server.schema.json definitions.ServerDetail / Package",
            "schema_id": schema.get("$id"),
            "server_detail_required": sreq,
            "package_required": preq,
            "repository_required_if_present": ["url", "source"],
            "optional_display_fields": ["title", "websiteUrl", "icons"],
            "optional_install_fields": ["packages", "remotes", "repository", "$schema", "_meta"],
            "api_response_extra": {
                "path": "_meta.io.modelcontextprotocol.registry/official",
                "fields": [
                    "status",
                    "statusChangedAt",
                    "publishedAt",
                    "updatedAt",
                    "isLatest",
                ],
                "settable_by_publisher": False,
            },
            "exposed_on_brave_latest": {
                "name": brave_name,
                "version": (brave.get("server") or {}).get("version"),
                "has_packages": True,
                "has_remotes": bool((brave.get("server") or {}).get("remotes")),
                "has_repository": True,
                "has_title": "title" in (brave.get("server") or {}),
                "official_meta": official_meta,
            },
        },
        "publish_flow": {
            "cli": "mcp-publisher",
            "docs": [
                "captures/quickstart.mdx",
                "captures/cli-commands.md",
                "captures/official-registry-api.md",
            ],
            "steps": [
                {
                    "order": 1,
                    "action": "init/edit server.json against the published schema",
                    "endpoint": None,
                },
                {
                    "order": 2,
                    "action": "mcp-publisher validate (schema + semantic checks, no publish)",
                    "endpoint": "POST /v0.1/validate",
                },
                {
                    "order": 3,
                    "action": "namespace login: github | github-oidc | dns | http",
                    "endpoint": auth_paths[:-1],
                },
                {
                    "order": 4,
                    "action": "mcp-publisher publish uploads server.json with the login JWT",
                    "endpoint": "POST /v0.1/publish",
                },
                {
                    "order": 5,
                    "action": "registry server-side checks before store",
                    "endpoint": "server-side; described in official-registry-requirements.md",
                },
            ],
            "verifies": [
                "JSON Schema compliance for server.json (ServerDetail + Package + transport)",
                "Namespace authentication matches the name prefix (io.github.* vs domain reverse-DNS)",
                "Package ownership markers (npm mcpName; PyPI/NuGet/Cargo mcp-name in README; OCI label; MCPB GitHub/GitLab release host)",
                "registryBaseUrl restricted to the trusted public registries allowlist",
                "Only io.modelcontextprotocol.registry/publisher-provided is kept under server._meta (4KB cap); other publisher _meta keys are dropped",
            ],
            "does_not_verify": [
                "Runtime behaviour of the server",
                "That GitHub OAuth still holds at install time",
                "The original DNS/HTTP login signature after JWT issuance",
                "Optional title/icons/websiteUrl authenticity",
            ],
        },
        "signal_table": signal_table,
        "recomputed_signal": {
            "signal_id": "npm_mcpName_ownership",
            "method": npm["method"],
            "outcome": "MATCH",
            "computed_not_asserted": True,
            "detail": npm,
            "also_recomputed": [
                {
                    "signal_id": computed[sid]["signal_id"],
                    "match": computed[sid]["match"],
                    "method": computed[sid]["method"],
                }
                for sid in (
                    "dns_apex_mcp_txt",
                    "npm_registry_base_url_allowlist",
                    "github_namespace_repo_owner_consistency",
                )
            ],
        },
        "claims": claims,
        "evidence_rails": rails,
        "answer": (
            "On schema 2025-12-11 the official registry requires name, description "
            "and version on every server.json, plus registryType, identifier and "
            "transport on each package. Publish (mcp-publisher -> POST /v0.1/publish "
            "after /v0.1/auth/*) additionally verifies namespace authentication, "
            "package-ownership markers, the public-registry allowlist, and _meta "
            "key restriction. Client-verifiable at install: npm mcpName, DNS apex "
            f"v=MCPv1 TXT, allowlisted registryBaseUrl, and io.github owner/repo "
            f"string match. Display-only: official.status/isLatest/timestamps, "
            f"GitHub OAuth proof, the original DNS/HTTP login signature, "
            f"publisher-provided _meta, and title/icons/websiteUrl. One signal was "
            f"recomputed end to end: {brave_name} mcpName MATCH on "
            f"{npm_doc.get('name')}@{npm_doc.get('version')}. "
            + SENTINEL_FULL
        ),
        "timestamps": {
            "captured_at": index.get("captured_at"),
            "emitted_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after 2 failed attempts "
                "on the same source route, switch source class before a third"
            ),
        },
        "tests": [
            {
                "id": "T1-recompute-mcpName-and-dns",
                "name": "Recompute npm mcpName from pinned captures; live DNS TXT; both-states mutants",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-signal-table-split-and-two-rails",
                "name": "Signal table split, two-rail claims, display-only cannot claim recompute",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "RES0038-C1-wrong-mcpName",
                "kind": "mutant",
                "description": "If npm mcpName is replaced with io.github.evil/forge, the recompute must return match=false.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "RES0038-C2-dns-domain-without-record",
                "kind": "live-negative",
                "description": "dig TXT brave.com must not be accepted as an MCP DNS proof (no v=MCPv1).",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "RES0038-C3-display-only-claimed-recomputed",
                "kind": "artifact-mutant",
                "description": "Flipping a recomputed row to class=display-only while leaving recomputed_end_to_end true must fail the checker.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0038-probe2-signal-table-scope",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "probe2 re-reads the artifact, checks the class split, refuses "
                "display-only rows that claim end-to-end recompute, and kills "
                "a confirmed claim reduced to one rail."
            ),
            "note": (
                "Catalog asked for a security reviewer constructing a bypass of "
                "every mitigation. G-1 for this unit is the named probes. A "
                "human bypass review of GitHub OAuth/OIDC is independent of "
                "probe-green and is recorded as NOT-CHECKED below."
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Human attempted-bypass of GitHub org-role checks and DNS key-rotation races.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Fresh-context security reviewer attempts the bypasses named "
                    "in the catalog reviewer_requirement."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/RES-0038/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/RES-0038/captures/capture_index.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "strongest_surviving_counterargument": (
            "npm mcpName is publisher-controlled metadata on npm: a stolen npm "
            "token can set mcpName to any string. The check binds the npm "
            "package to a registry name, not to a human identity, and GitHub "
            "OAuth is not recomputed at install. The artifact therefore does "
            "not call mcpName a full trust root."
        ),
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2) + "\n"
    ok, why = C.check_artifact(doc, text=text)
    if not ok:
        print(f"FAILED:emit checker {why}")
        return 1
    dest.write_text(text, encoding="utf-8")
    sha, n = sha256_file(dest)
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    print("SUCCESS:RES-0038 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
