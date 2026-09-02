"""WFA-0023 marketplace sweep engine.

Evidence A: parse each registry index against its declared schema (or a
reconstructed schema when the declared URL is unreachable). Per-pack
metadata is taken only from index fields, never from prose.

Evidence B: fetch package manifests as HTTP bytes and compare them to the
index claims. An index row is a claim, not a receipt.

This unit never installs, executes, or auto-loads bundled agent config.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CAPTURES = HERE / "captures"
PACKS = HERE / "packs"
FIXTURES = HERE / "fixtures"
UNDECLARED = "UNDECLARED-IN-INDEX"

_install_calls: list[str] = []


def record_install_attempt(cmd: str) -> None:
    _install_calls.append(cmd)
    raise RuntimeError(f"WFA-0023 forbids install: {cmd}")


def install_attempts() -> list[str]:
    return list(_install_calls)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_str(v: Any) -> bool:
    return isinstance(v, str) and v.strip() != ""


def validate_claude_marketplace(doc: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return {"ok": False, "errors": ["root-not-object"], "schema": "reconstructed-claude-marketplace"}
    for key in ("name", "owner", "plugins"):
        if key not in doc:
            errors.append(f"missing:{key}")
    owner = doc.get("owner")
    if not isinstance(owner, dict) or not _is_str(owner.get("name")):
        errors.append("owner.name-missing")
    plugins = doc.get("plugins")
    if not isinstance(plugins, list):
        errors.append("plugins-not-array")
        plugins = []
    bad = 0
    for i, plug in enumerate(plugins):
        if not isinstance(plug, dict):
            bad += 1
            errors.append(f"plugins[{i}]-not-object")
            continue
        if "name" not in plug or "source" not in plug:
            bad += 1
            errors.append(f"plugins[{i}].missing:name-or-source")
            continue
        src = plug["source"]
        if not (_is_str(src) or isinstance(src, dict)):
            bad += 1
            errors.append(f"plugins[{i}].source-bad-type")
    return {
        "ok": not errors,
        "errors": errors[:40],
        "plugin_count": len(plugins),
        "plugin_count": len(plugins),
        "malformed_plugin_rows": bad,
        "schema": "reconstructed-claude-marketplace",
    }


def validate_cline_catalog(doc: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return {"ok": False, "errors": ["root-not-object"], "schema": "reconstructed-cline-catalog"}
    for key in ("version", "generatedAt", "entries"):
        if key not in doc:
            errors.append(f"missing:{key}")
    entries = doc.get("entries")
    if not isinstance(entries, list):
        errors.append("entries-not-array")
        entries = []
    for i, ent in enumerate(entries):
        if not isinstance(ent, dict):
            errors.append(f"entries[{i}]-not-object")
            continue
        for key in ("id", "type", "name"):
            if key not in ent:
                errors.append(f"entries[{i}].missing:{key}")
                break
    return {
        "ok": not errors,
        "errors": errors[:40],
        "entry_count": len(entries),
        "schema": "reconstructed-cline-catalog",
    }


def validate_mcp_page(doc: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return {"ok": False, "errors": ["root-not-object"], "schema": "mcp-server.schema.json+$page"}
    servers = doc.get("servers")
    if not isinstance(servers, list):
        errors.append("servers-not-array")
        servers = []
    for i, row in enumerate(servers):
        srv = row.get("server") if isinstance(row, dict) else None
        if not isinstance(srv, dict):
            errors.append(f"servers[{i}].server-missing")
            continue
        for key in ("name", "description", "version"):
            if not _is_str(srv.get(key)):
                errors.append(f"servers[{i}].missing:{key}")
        declared = srv.get("$schema")
        if declared and not (
            isinstance(declared, str)
            and declared.startswith("https://static.modelcontextprotocol.io/schemas/")
        ):
            errors.append(f"servers[{i}].unexpected-$schema")
    return {
        "ok": not errors,
        "errors": errors[:40],
        "server_count": len(servers),
        "schema": "mcp-server.schema.json+$page",
    }


def index_field(plug: dict[str, Any], key: str) -> Any:
    if key not in plug:
        return UNDECLARED
    val = plug.get(key)
    if val is None or val == "":
        return UNDECLARED
    return val


def publisher_from_index(plug: dict[str, Any], marketplace_owner: str | None) -> Any:
    author = plug.get("author")
    if isinstance(author, dict) and _is_str(author.get("name")):
        return author["name"]
    if _is_str(author):
        return author
    if marketplace_owner:
        return {
            "inherited_marketplace_owner": marketplace_owner,
            "per_pack_author": UNDECLARED,
        }
    return UNDECLARED


def source_pin(plug: dict[str, Any]) -> dict[str, Any]:
    src = plug.get("source")
    if _is_str(src):
        return {"kind": "relative-path", "path": src, "ref": UNDECLARED, "sha": UNDECLARED}
    if isinstance(src, dict):
        return {
            "kind": src.get("source") or src.get("type") or "object",
            "url": src.get("url"),
            "path": src.get("path"),
            "ref": src.get("ref") or UNDECLARED,
            "sha": src.get("sha") or UNDECLARED,
        }
    return {"kind": UNDECLARED, "ref": UNDECLARED, "sha": UNDECLARED}


def last_release_from_index(plug: dict[str, Any]) -> dict[str, Any]:
    for key in ("lastRelease", "last_release", "releasedAt", "updatedAt", "publishedAt"):
        if key in plug and plug[key]:
            return {"calendar_date": plug[key], "basis": key}
    pin = source_pin(plug)
    if pin.get("ref") != UNDECLARED or pin.get("sha") != UNDECLARED:
        return {
            "calendar_date": None,
            "basis": "source-pin-not-calendar-date",
            "pin": pin,
        }
    return {"calendar_date": None, "basis": UNDECLARED}


def classify_workflow(name: str, description: str, extra: str = "") -> str:
    blob = f"{name} {description} {extra}".lower()
    if any(w in blob for w in ("workflow", "agent", "orchestrat", "pipeline", "skill")):
        return "workflow-shaped"
    if "mcp" in blob:
        return "mcp"
    return "plugin"


def extract_claude_packs(doc: dict[str, Any], marketplace_id: str) -> list[dict[str, Any]]:
    owner = ""
    if isinstance(doc.get("owner"), dict):
        owner = str(doc["owner"].get("name") or "")
    rows = []
    for plug in doc.get("plugins") or []:
        if not isinstance(plug, dict):
            continue
        name = plug.get("name")
        desc = plug.get("description") if isinstance(plug.get("description"), str) else ""
        rows.append(
            {
                "marketplace": marketplace_id,
                "name": name,
                "publisher": publisher_from_index(plug, owner),
                "license_from_index": index_field(plug, "license"),
                "version_from_index": index_field(plug, "version"),
                "category_from_index": index_field(plug, "category"),
                "homepage_from_index": index_field(plug, "homepage"),
                "permission_from_index": index_field(plug, "permissions"),
                "source": source_pin(plug),
                "last_release_from_index": last_release_from_index(plug),
                "kind": classify_workflow(str(name or ""), desc, str(plug.get("category") or "")),
                "metadata_source": "index-fields-only",
            }
        )
    return rows


def extract_cline_packs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    catalog_time = doc.get("generatedAt")
    rows = []
    for ent in doc.get("entries") or []:
        if not isinstance(ent, dict):
            continue
        author = ent.get("author")
        pub: Any = UNDECLARED
        if isinstance(author, dict) and _is_str(author.get("name")):
            pub = author["name"]
        elif _is_str(author):
            pub = author
        install = ent.get("install") if isinstance(ent.get("install"), dict) else {}
        rows.append(
            {
                "marketplace": "cline-marketplace",
                "name": ent.get("id") or ent.get("name"),
                "display_name": ent.get("name"),
                "type_from_index": ent.get("type"),
                "publisher": pub,
                "license_from_index": index_field(ent, "license"),
                "version_from_index": index_field(ent, "version"),
                "permission_from_index": {
                    "install_command": install.get("command"),
                    "install_args": install.get("args"),
                    "env": install.get("env"),
                },
                "last_release_from_index": {
                    "calendar_date": None,
                    "catalog_generatedAt": catalog_time,
                    "basis": "catalog-timestamp-not-per-pack-date"
                    if catalog_time
                    else UNDECLARED,
                },
                "kind": classify_workflow(
                    str(ent.get("name") or ""),
                    str(ent.get("description") or ""),
                    str(ent.get("type") or ""),
                ),
                "homepage_from_index": index_field(ent, "homepage"),
                "metadata_source": "index-fields-only",
            }
        )
    return rows


def extract_mcp_packs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in doc.get("servers") or []:
        if not isinstance(row, dict):
            continue
        srv = row.get("server") or {}
        meta = row.get("_meta") or {}
        official = meta.get("io.modelcontextprotocol.registry/official") or {}
        headers: list[Any] = []
        for remote in srv.get("remotes") or []:
            if isinstance(remote, dict):
                headers.extend(remote.get("headers") or [])
        secret_headers = [
            h.get("name")
            for h in headers
            if isinstance(h, dict) and (h.get("isSecret") or h.get("isRequired"))
        ]
        rows.append(
            {
                "marketplace": "mcp-official-registry",
                "name": srv.get("name"),
                "publisher": (srv.get("repository") or {}).get("url") or UNDECLARED,
                "license_from_index": index_field(srv, "license"),
                "version_from_index": srv.get("version") or UNDECLARED,
                "declared_schema": srv.get("$schema"),
                "permission_from_index": {
                    "remotes": srv.get("remotes"),
                    "packages": srv.get("packages"),
                    "secret_or_required_headers": secret_headers,
                },
                "last_release_from_index": {
                    "calendar_date": official.get("updatedAt") or official.get("publishedAt"),
                    "basis": "registry-_meta",
                    "isLatest": official.get("isLatest"),
                    "status": official.get("status"),
                },
                "kind": "mcp",
                "metadata_source": "index-fields-only",
            }
        )
    return rows


def extract_smithery_packs(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for srv in doc.get("servers") or []:
        if not isinstance(srv, dict):
            continue
        rows.append(
            {
                "marketplace": "smithery",
                "name": srv.get("qualifiedName") or srv.get("displayName"),
                "publisher": srv.get("owner") or UNDECLARED,
                "license_from_index": UNDECLARED,
                "version_from_index": UNDECLARED,
                "permission_from_index": {
                    "remote": srv.get("remote"),
                    "isDeployed": srv.get("isDeployed"),
                },
                "last_release_from_index": {
                    "calendar_date": srv.get("createdAt"),
                    "basis": "createdAt-not-release-date",
                },
                "kind": "mcp",
                "metadata_source": "index-fields-only",
            }
        )
    return rows


def prose_must_not_fill(plug: dict[str, Any]) -> dict[str, Any]:
    license_field = index_field(plug, "license")
    desc = plug.get("description") or ""
    mentions_mit = bool(re.search(r"\bMIT\b", desc, re.I))
    return {
        "license_from_index": license_field,
        "description_mentions_mit": mentions_mit,
        "did_not_promote_prose_to_license": license_field == UNDECLARED,
        "control_ok": mentions_mit and license_field == UNDECLARED,
    }


def compare_claim_to_receipt(
    index_entry: dict[str, Any], receipt: dict[str, Any]
) -> dict[str, Any]:
    notes: list[dict[str, Any]] = []

    def check(field: str, claim: Any, got: Any) -> None:
        claim_u = UNDECLARED if claim in (None, "", UNDECLARED) else claim
        got_u = UNDECLARED if got in (None, "") else got
        if claim_u == UNDECLARED:
            notes.append(
                {
                    "field": field,
                    "kind": "index-silent-receipt-present"
                    if got_u != UNDECLARED
                    else "both-undeclared",
                    "claim": claim_u,
                    "receipt": got_u,
                }
            )
            return
        if claim_u != got_u:
            notes.append(
                {
                    "field": field,
                    "kind": "claim-not-receipt",
                    "claim": claim_u,
                    "receipt": got_u,
                }
            )
        else:
            notes.append(
                {
                    "field": field,
                    "kind": "claim-matches-receipt",
                    "claim": claim_u,
                    "receipt": got_u,
                }
            )

    iauth = index_entry.get("author")
    if isinstance(iauth, dict):
        iauth = iauth.get("name")
    rauth = receipt.get("author")
    if isinstance(rauth, dict):
        rauth = rauth.get("name")
    check("name", index_entry.get("name"), receipt.get("name"))
    check(
        "version",
        index_entry.get("version")
        if "version" in index_entry
        else index_field(index_entry, "version"),
        receipt.get("version"),
    )
    check(
        "license",
        index_entry.get("license")
        if "license" in index_entry
        else index_field(index_entry, "license"),
        receipt.get("license"),
    )
    check("author", iauth, rauth)
    material = [m for m in notes if m["kind"] == "claim-not-receipt"]
    matches = [m for m in notes if m["kind"] == "claim-matches-receipt"]
    if material:
        verdict = "CLAIM-NOT-RECEIPT"
    elif matches:
        verdict = "CLAIMS-MATCH-RECEIPT"
    else:
        verdict = "INDEX-SILENT"
    return {
        "verdict": verdict,
        "material_mismatches": material,
        "all_field_notes": notes,
        "index_is_claim_not_receipt": True,
    }


def permission_surface(receipt: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    blob = json.dumps(receipt, sort_keys=True).lower()
    if extra:
        blob += json.dumps(extra, sort_keys=True).lower()
    flags: list[str] = []
    tools = receipt.get("allowedTools") or receipt.get("allowed_tools") or []
    for t in tools:
        tl = str(t).lower()
        if "bash" in tl or tl.strip() == "*":
            flags.append(f"unrestricted-tool:{t}")
    hooks = receipt.get("hooks")
    if hooks:
        flags.append("hooks-present")
        dumped = json.dumps(hooks)
        if "pretooluse" in dumped.lower():
            flags.append("pretooluse-hook")
    if receipt.get("mcpServers") or (extra and extra.get("mcp.json")):
        flags.append("mcp-servers")
    if "bearer" in blob or "personal_access_token" in blob or "github_personal_access_token" in blob:
        flags.append("credential-material-in-manifest")
    if "npx" in blob and "-y" in blob:
        flags.append("install-time-remote-code-npx-y")
    if "cat ~/.ssh" in blob or "evil.example" in blob:
        flags.append("exfil-or-secret-read")
    bundled: list[str] = []
    if extra:
        for k in (".claude", ".codex", "hooks", "AGENTS.md", "mcp.json"):
            if extra.get(k):
                bundled.append(k)
                flags.append(f"bundled-agent-config:{k}")
    excessive = any(
        f.startswith("unrestricted-tool")
        or f
        in {
            "pretooluse-hook",
            "exfil-or-secret-read",
            "credential-material-in-manifest",
        }
        for f in flags
    )
    return {
        "flags": flags,
        "excessive": excessive,
        "bundled_agent_config": bundled,
        "installed": False,
        "auto_loaded": False,
        "policy": "report-never-install-never-autoload",
    }


def refuse_install() -> dict[str, Any]:
    return {
        "packages_installed": [],
        "install_attempts": install_attempts(),
        "live_client_modified": False,
    }


def load_official() -> dict[str, Any]:
    return load_json(CAPTURES / "claude-plugins-official.marketplace.json")


def load_community() -> dict[str, Any]:
    return load_json(CAPTURES / "claude-community.marketplace.json")


def load_cline() -> dict[str, Any]:
    return load_json(CAPTURES / "cline.catalog.json")


def load_mcp() -> dict[str, Any]:
    return load_json(CAPTURES / "mcp-registry.servers-page.json")


def load_smithery() -> dict[str, Any]:
    return load_json(CAPTURES / "smithery.servers-page.json")


def sample_pack_receipts() -> list[dict[str, Any]]:
    samples = []

    def add(
        pack_id: str,
        marketplace: str,
        index_name: str,
        plugin_file: str,
        extra_files: dict[str, str] | None = None,
    ) -> None:
        receipt = load_json(PACKS / plugin_file)
        extra: dict[str, Any] = {}
        if extra_files:
            for label, fname in extra_files.items():
                p = PACKS / fname
                extra[label] = (
                    json.loads(p.read_text(encoding="utf-8"))
                    if p.suffix == ".json"
                    else p.read_text(encoding="utf-8")[:400]
                )
        samples.append(
            {
                "pack_id": pack_id,
                "marketplace": marketplace,
                "index_name": index_name,
                "receipt": receipt,
                "extra": extra,
            }
        )

    add("feature-dev", "claude-plugins-official", "feature-dev", "feature-dev.plugin.json")
    add("code-review", "claude-plugins-official", "code-review", "code-review.plugin.json")
    add(
        "github",
        "claude-plugins-official",
        "github",
        "github.plugin.json",
        {"mcp.json": "github.mcp.json"},
    )
    add(
        "42crunch-api-security-testing",
        "claude-plugins-official",
        "42crunch-api-security-testing",
        "42crunch.plugin.json",
    )
    add("gitkraken", "claude-plugins-official", "gitkraken", "gitkraken.plugin.json")
    add("0x", "claude-plugins-community", "0x", "0x.plugin.json")
    return samples


def index_entry_for(name: str, marketplace: str) -> dict[str, Any]:
    if marketplace == "claude-plugins-official":
        doc = load_official()
        for p in doc["plugins"]:
            if p.get("name") == name:
                return p
    if marketplace == "claude-plugins-community":
        doc = load_community()
        for p in doc["plugins"]:
            if p.get("name") == name:
                return p
    raise KeyError(f"{marketplace}:{name}")


def run_evidence_a() -> dict[str, Any]:
    official = load_official()
    community = load_community()
    cline = load_cline()
    mcp = load_mcp()
    smithery = load_smithery()
    schema_fetch = load_json(CAPTURES / "declared-schema-fetch.json")
    official_packs = extract_claude_packs(official, "claude-plugins-official")
    community_packs = extract_claude_packs(community, "claude-plugins-community")
    cline_packs = extract_cline_packs(cline)
    mcp_packs = extract_mcp_packs(mcp)
    smithery_packs = extract_smithery_packs(smithery)
    return {
        "declared_schema_fetch": schema_fetch,
        "validations": {
            "claude-plugins-official": validate_claude_marketplace(official),
            "claude-plugins-community": validate_claude_marketplace(community),
            "cline-marketplace": validate_cline_catalog(cline),
            "mcp-official-registry": validate_mcp_page(mcp),
            "smithery": {
                "ok": isinstance(smithery.get("servers"), list),
                "page_totalCount": (smithery.get("pagination") or {}).get("totalCount"),
                "schema": "observed-smithery-list-page",
                "note": "No $schema on list page; pagination.totalCount is an index claim.",
            },
        },
        "pack_counts": {
            "claude-plugins-official": len(official_packs),
            "claude-plugins-community": len(community_packs),
            "cline-marketplace": len(cline_packs),
            "mcp-official-registry-page": len(mcp_packs),
            "smithery-page": len(smithery_packs),
            "smithery-declared-total": (smithery.get("pagination") or {}).get("totalCount"),
        },
        "packs": official_packs + cline_packs + mcp_packs + smithery_packs,
        "community_packs": community_packs,
        "prose_control": prose_must_not_fill(
            {
                "description": "Licensed under MIT. Version 9.9.9.",
                "name": "control",
                "source": "./x",
            }
        ),
    }


def run_evidence_b() -> dict[str, Any]:
    comparisons = []
    for sample in sample_pack_receipts():
        entry = index_entry_for(sample["index_name"], sample["marketplace"])
        cmp_ = compare_claim_to_receipt(entry, sample["receipt"])
        perms = permission_surface(sample["receipt"], sample.get("extra"))
        comparisons.append(
            {
                "pack_id": sample["pack_id"],
                "marketplace": sample["marketplace"],
                "index_name": sample["index_name"],
                "receipt_name": sample["receipt"].get("name"),
                "receipt_license": sample["receipt"].get("license") or UNDECLARED,
                "receipt_version": sample["receipt"].get("version") or UNDECLARED,
                "comparison": cmp_,
                "permission_surface": perms,
                "fetched_bytes_only": True,
                "installed": False,
            }
        )
    planted_match = compare_claim_to_receipt(
        load_json(FIXTURES / "pack_match" / "index_entry.json"),
        load_json(FIXTURES / "pack_match" / "plugin.json"),
    )
    planted_mis = compare_claim_to_receipt(
        load_json(FIXTURES / "pack_mismatch" / "index_entry.json"),
        load_json(FIXTURES / "pack_mismatch" / "plugin.json"),
    )
    planted_ex = permission_surface(load_json(FIXTURES / "pack_excessive" / "plugin.json"))
    return {
        "live_samples": comparisons,
        "planted": {
            "match": planted_match,
            "mismatch": planted_mis,
            "excessive": planted_ex,
        },
        "install": refuse_install(),
    }
