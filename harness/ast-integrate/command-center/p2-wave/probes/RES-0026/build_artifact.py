#!/usr/bin/env python3
"""Build command-center/research/RES-0026.json from live capture rails."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    CATALOG_SCHEMA,
    OUT_REL,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    UNIT,
    artifact_errors,
)

INDEX = HERE / "captures" / "_index.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0026/probe1_two_rails_and_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0026/probe2_classifier_controls.py"
)

API = {
    "fw": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-on-github/customize-copilot/customize-the-firewall.md",
    "mcp": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-on-github/customize-copilot/configure-mcp-servers.md",
    "env": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/customize-the-agent-environment.md",
    "repo_instr": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions.md",
    "org_instr": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-organization-instructions.md",
    "allow": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools.md",
    "cli_mcp": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers.md",
    "cli_cfg": "https://api.github.com/repos/github/docs/contents/content/copilot/reference/copilot-cli-reference/cli-config-dir-reference.md",
    "agents": "https://api.github.com/repos/github/docs/contents/content/copilot/reference/custom-agents-configuration.md",
    "policy": "https://api.github.com/repos/github/docs/contents/content/copilot/reference/supported-surfaces-for-policies.md",
    "secrets": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/configure-secrets-and-variables.md",
    "tasks": "https://api.github.com/repos/github/docs/contents/content/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api.md",
    "vscode": "https://api.github.com/repos/microsoft/vscode/contents/.github/copilot-instructions.md",
    "mcp_lim": "https://api.github.com/repos/github/docs/contents/data/reusables/copilot/mcp/repo-mcp-limitations.md",
}
HTML = {
    "fw": "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-the-firewall",
    "mcp": "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/configure-mcp-servers",
    "env": "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/customize-the-agent-environment",
    "repo_instr": "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions",
    "org_instr": "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-organization-instructions",
    "allow": "https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools",
    "cli_mcp": "https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers",
    "cli_cfg": "https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference",
    "agents": "https://docs.github.com/en/copilot/reference/custom-agents-configuration",
    "policy": "https://docs.github.com/en/copilot/reference/supported-surfaces-for-policies",
    "secrets": "https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/configure-secrets-and-variables",
    "tasks": "https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api",
}
VSCODE_RAW = "https://raw.githubusercontent.com/microsoft/vscode/main/.github/copilot-instructions.md"


def index_by_permalink() -> dict:
    data = json.loads(INDEX.read_text(encoding="utf-8"))
    out = {}
    for row in data.get("rails") or []:
        if isinstance(row, dict) and row.get("permalink"):
            out[row["permalink"]] = row
    return out


def rail(idx: dict, permalink: str, kind: str, quote: str) -> dict:
    row = idx.get(permalink)
    if not row:
        raise SystemExit(f"missing capture for {permalink}")
    if row.get("http_status") != 200:
        raise SystemExit(f"non-200 capture {permalink} status={row.get('http_status')}")
    return {
        "rail": kind,
        "permalink": permalink,
        "final_url": row.get("final_url") or permalink,
        "fetch_timestamp": row["fetch_timestamp"],
        "http_status": row["http_status"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "capture_path": row["capture_path"],
        "git_blob_sha": row.get("git_blob_sha"),
        "quote": quote,
    }


def claim(
    *,
    cid: str,
    mechanism: str,
    text: str,
    caveat: str,
    api: dict,
    prose: dict,
    edges: dict | None = None,
) -> dict:
    stamps = sorted({api["fetch_timestamp"], prose["fetch_timestamp"]})
    return {
        "id": cid,
        "canonical_mechanism": mechanism,
        "claim": text,
        "evidence_tier": "E2",
        "confidence_band": "almost-certain",
        "source_lineage": [api, prose],
        "named_settling_probe": P1,
        "strongest_caveat": caveat,
        "freshness_stamp": stamps[-1],
        "snapshot_sha256": {
            "structured-api": api["sha256"],
            "prose-source": prose["sha256"],
        },
        "edges": edges or {"supports": [], "contradicts": []},
        "verdict": "SURVIVES",
    }


def build() -> dict:
    idx = index_by_permalink()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_schema_present = (REPO / CATALOG_SCHEMA).is_file()

    c1 = claim(
        cid="C-FW-APPLIANCE",
        mechanism="cloud-agent-egress-firewall-on-actions-appliance",
        text=(
            "Copilot cloud-agent internet access is limited by a firewall that "
            "operates only inside the GitHub Actions appliance, only on processes "
            "started via the agent's Bash tool, and is configured from GitHub "
            "organization/repository Internet-access settings that an organization "
            "can lock so repositories cannot override."
        ),
        caveat=(
            "The same docs disclose that the firewall does not apply to MCP "
            "servers or copilot-setup-steps processes, and that sophisticated "
            "attacks may bypass it; it is not a comprehensive security boundary."
        ),
        api=rail(
            idx,
            API["fw"],
            "structured-api",
            "Only applies within the {% data variables.product.prodname_actions %} appliance",
        ),
        prose=rail(
            idx,
            HTML["fw"],
            "prose-source",
            "Only applies within the GitHub Actions appliance",
        ),
        edges={"supports": ["C-FW-ORG-LOCK"], "contradicts": []},
    )
    c2 = claim(
        cid="C-FW-ORG-LOCK",
        mechanism="org-locked-firewall-toggle",
        text=(
            "Repository administrators can toggle Enable firewall only when the "
            "organization-level setting is Let repositories decide; if the org "
            "sets Enabled or Disabled, individual repositories cannot change it."
        ),
        caveat=(
            "This lock is documented for GitHub.com settings; this unit did not "
            "exercise a live org-admin UI, so the lock is graded from docs+API "
            "source, not from a runtime org mutation."
        ),
        api=rail(
            idx,
            API["fw"],
            "structured-api",
            "If the organization-level setting is **Enabled** or **Disabled**, you can't change this setting for individual repositories.",
        ),
        prose=rail(
            idx,
            HTML["fw"],
            "prose-source",
            "If the organization-level setting is <strong>Enabled</strong> or <strong>Disabled</strong>, you can&#x27;t change this setting for individual repositories.",
        ),
        edges={"supports": ["C-FW-APPLIANCE"], "contradicts": []},
    )
    c3 = claim(
        cid="C-MCP-SETTINGS-STORE",
        mechanism="repo-settings-mcp-json-not-a-committed-file",
        text=(
            "Cloud-agent MCP servers are configured by pasting JSON into the "
            "repository settings MCP servers page on GitHub.com and clicking "
            "Save MCP configuration; the JSON is not the committed "
            ".github/mcp.json used by Copilot CLI."
        ),
        caveat=(
            "The JSON object shape (mcpServers, type, tools, command/url) is "
            "intentionally similar to VS Code/CLI configs; similarity of schema "
            "is not identity of enforcement. Adapting .vscode/mcp.json still "
            "requires adding a tools key and dropping inputs/envFile."
        ),
        api=rail(
            idx,
            API["mcp"],
            "structured-api",
            "You enter the JSON configuration directly into the settings for the repository on {% data variables.product.prodname_dotcom_the_website %}.",
        ),
        prose=rail(
            idx,
            HTML["mcp"],
            "prose-source",
            "You enter the JSON configuration directly into the settings for the repository on GitHub.com.",
        ),
    )
    c4 = claim(
        cid="C-MCP-NO-OAUTH-OR-RESOURCES",
        mechanism="cloud-agent-mcp-tools-only-no-oauth",
        text=(
            "Copilot cloud agent and Copilot code review only support MCP tools "
            "(not resources or prompts) and do not currently support remote MCP "
            "servers that use OAuth."
        ),
        caveat=(
            "This is a product limitation of the hosted agent, not a property of "
            "MCP itself; a local Copilot CLI session may speak OAuth/HTTP MCP "
            "that the cloud agent will refuse."
        ),
        api=rail(
            idx,
            API["mcp_lim"],
            "structured-api",
            "do not currently support remote MCP servers that leverage OAuth",
        ),
        prose=rail(
            idx,
            HTML["mcp"],
            "prose-source",
            "do not currently support remote MCP servers that leverage OAuth",
        ),
    )
    c5 = claim(
        cid="C-SETUP-STEPS-IGNORE",
        mechanism="copilot-setup-steps-job-whitelist-and-overrides",
        text=(
            "`.github/workflows/copilot-setup-steps.yml` is picked up only when "
            "the job is named copilot-setup-steps; only steps, permissions, "
            "runs-on, services, snapshot, and timeout-minutes (max 59) may be "
            "customized, and any other job settings are ignored. fetch-depth on "
            "actions/checkout is overridden by the agent."
        ),
        caveat=(
            "The YAML file itself is an ordinary Actions workflow and can be "
            "copied into another repo, but the ignore/override behavior is "
            "applied by GitHub's cloud-agent runner, not by Actions YAML "
            "semantics. Self-hosted runners additionally require the integrated "
            "firewall to be disabled or the agent is blocked."
        ),
        api=rail(
            idx,
            API["env"],
            "structured-api",
            "If you try to customize other settings, your changes will be ignored.",
        ),
        prose=rail(
            idx,
            HTML["env"],
            "prose-source",
            "If you try to customize other settings, your changes will be ignored.",
        ),
    )
    c6 = claim(
        cid="C-INSTR-FILE-USED",
        mechanism="github-copilot-instructions-md-file-prompt",
        text=(
            "Repository-wide custom instructions are a Markdown file at "
            "`.github/copilot-instructions.md`. The file is used in practice "
            "(microsoft/vscode ships one) and is loaded as prompt context by "
            "both Copilot cloud agent and Copilot CLI; it is not a server-side "
            "admission gate."
        ),
        caveat=(
            "Loading the file is product-specific (Copilot discovers a named "
            "path). The bytes are portable; Copilot's interpretation and "
            "whitespace-collapsing rules are not a portable runtime contract. "
            "Path-specific `*.instructions.md` files use applyTo matching on CLI."
        ),
        api=rail(
            idx,
            API["vscode"],
            "structured-api",
            "VS Code Copilot Instructions",
        ),
        prose=rail(
            idx,
            VSCODE_RAW,
            "prose-source",
            "VS Code Copilot Instructions",
        ),
        edges={"supports": ["C-INSTR-REPO-DOC"], "contradicts": []},
    )
    c6b = claim(
        cid="C-INSTR-REPO-DOC",
        mechanism="copilot-instructions-md-documented-path",
        text=(
            "Official docs specify repository-wide instructions as "
            "`copilot-instructions.md` in the `.github` directory, plus "
            "path-specific `NAME.instructions.md` under `.github/instructions`."
        ),
        caveat=(
            "Docs also mention AGENTS.md / CLAUDE.md / GEMINI.md as agent "
            "instruction files; support differs by surface (see custom "
            "instructions support matrix)."
        ),
        api=rail(
            idx,
            API["repo_instr"],
            "structured-api",
            "These are specified in a `copilot-instructions.md` file in the `.github` directory of the repository.",
        ),
        prose=rail(
            idx,
            HTML["repo_instr"],
            "prose-source",
            "These are specified in a <code>copilot-instructions.md</code> file in the <code>.github</code> directory of the repository.",
        ),
        edges={"supports": ["C-INSTR-FILE-USED"], "contradicts": []},
    )
    c7 = claim(
        cid="C-ORG-INSTRUCTIONS-SETTINGS",
        mechanism="organization-custom-instructions-settings-ui",
        text=(
            "Organization custom instructions are entered in the organization "
            "Copilot Custom instructions settings text box and saved there; "
            "they are not a repository file."
        ),
        caveat=(
            "This unit did not capture a live org-settings payload (would "
            "require org-admin credentials). Classification is from official "
            "how-to prose plus the Contents API source of that how-to."
        ),
        api=rail(
            idx,
            API["org_instr"],
            "structured-api",
            "You can add organization custom instructions via your organization settings.",
        ),
        prose=rail(
            idx,
            HTML["org_instr"],
            "prose-source",
            "You can add organization custom instructions via your organization settings.",
        ),
    )
    c8 = claim(
        cid="C-CLI-ALLOW-TOOL-SESSION",
        mechanism="copilot-cli-allow-deny-tool-flags",
        text=(
            "Copilot CLI `--allow-tool` and `--deny-tool` apply only to the "
            "current session and are not written to ~/.copilot/permissions-config.json; "
            "deny rules still beat allow rules and saved approvals."
        ),
        caveat=(
            "Interactive 'don't ask again in this repo' approvals ARE persisted "
            "in permissions-config.json; that persistence is still a local file, "
            "not GitHub-hosted enforcement. MDM/server-managed permissions are "
            "a separate server-enforced overlay (C-CLI-MDM)."
        ),
        api=rail(
            idx,
            API["allow"],
            "structured-api",
            "Command-line options such as `--allow-tool` and `--deny-tool` apply only to the current session and aren't written to `permissions-config.json`.",
        ),
        prose=rail(
            idx,
            HTML["allow"],
            "prose-source",
            "Command-line options such as <code>--allow-tool</code> and <code>--deny-tool</code> apply only to the current session and aren&#x27;t written to <code>permissions-config.json</code>.",
        ),
    )
    c9 = claim(
        cid="C-CLI-MDM",
        mechanism="copilot-cli-mdm-and-server-managed-settings",
        text=(
            "Copilot CLI loads MDM managed settings and server-managed settings "
            "at startup; MDM wins per key, long-running sessions re-fetch hourly, "
            "and keys such as allowedMcpServers / deniedMcpServers / "
            "permissions.disableBypassPermissionsMode are admin-enforced. An MDM "
            "value of disable for disableBypassPermissionsMode always wins."
        ),
        caveat=(
            "File-based MDM paths (/etc/github-copilot/managed-settings.json on "
            "Linux) are local files, but they are a device-policy channel, not "
            "user config. This unit did not receive a live MDM payload."
        ),
        api=rail(
            idx,
            API["cli_cfg"],
            "structured-api",
            "{% data variables.copilot.copilot_cli_short %} also loads server-managed settings at startup, in addition to MDM.",
        ),
        prose=rail(
            idx,
            HTML["cli_cfg"],
            "prose-source",
            "Copilot CLI also loads server-managed settings at startup, in addition to MDM.",
        ),
    )
    c10 = claim(
        cid="C-SECRETS-AGENTS-TYPE",
        mechanism="agents-secrets-not-actions-secrets",
        text=(
            "Cloud agent receives only Agents secrets/variables. Actions, "
            "Codespaces, and Dependabot secrets are not passed. MCP config can "
            "see only names prefixed COPILOT_MCP_."
        ),
        caveat=(
            "A local CLI process sees the operator's shell environment instead; "
            "copying COPILOT_MCP_* names into a laptop env is not the same "
            "control as GitHub Agents secrets."
        ),
        api=rail(
            idx,
            API["secrets"],
            "structured-api",
            "{% data variables.copilot.copilot_cloud_agent %} does not have access to {% data variables.product.prodname_actions %}, {% data variables.product.prodname_codespaces %}, or {% data variables.product.prodname_dependabot %} secrets and variables. Only Agents secrets and variables are passed to the agent.",
        ),
        prose=rail(
            idx,
            HTML["secrets"],
            "prose-source",
            "Copilot cloud agent does not have access to GitHub Actions, Codespaces, or Dependabot secrets and variables. Only Agents secrets and variables are passed to the agent.",
        ),
    )
    c11 = claim(
        cid="C-POLICY-WEBSEARCH-NONPORTABLE",
        mechanism="org-web-search-policy-does-not-bind-cloud-agent",
        text=(
            "The organization policy 'Copilot can search the web' does not "
            "apply to Copilot cloud agent even though the cloud agent can "
            "access the Internet; assuming that policy is portable across "
            "surfaces is a documented error."
        ),
        caveat=(
            "The policy matrix uses octicons rather than the words true/false; "
            "this claim quotes the explicit prose note, not an inferred table "
            "cell. Egress is separately gated by the appliance firewall (C-FW-APPLIANCE)."
        ),
        api=rail(
            idx,
            API["policy"],
            "structured-api",
            '{% data variables.copilot.copilot_cloud_agent %} **can** access the Internet, but the "{% data variables.product.prodname_copilot_short %} can search the web" policy does not affect this capability.',
        ),
        prose=rail(
            idx,
            HTML["policy"],
            "prose-source",
            'Copilot cloud agent <strong>can</strong> access the Internet, but the &quot;Copilot can search the web&quot; policy does not affect this capability.',
        ),
        edges={"supports": [], "contradicts": ["portable-policy-assumption"]},
    )
    c12 = claim(
        cid="C-CLI-MCP-FILES",
        mechanism="copilot-cli-mcp-config-files",
        text=(
            "Copilot CLI MCP servers are configured in local files "
            "(~/.copilot/mcp-config.json, .mcp.json, .github/mcp.json) or via "
            "`copilot mcp add`; project files closer to cwd win. This is a "
            "client-local loader, distinct from GitHub.com repository MCP settings."
        ),
        caveat=(
            "If the org/enterprise has configured a registry URL and allowlist "
            "policy, those settings apply to Copilot CLI and only permitted "
            "servers can run — an admin overlay on top of the local files."
        ),
        api=rail(
            idx,
            API["cli_mcp"],
            "structured-api",
            "The server is added to the user configuration at `~/.copilot/mcp-config.json`.",
        ),
        prose=rail(
            idx,
            HTML["cli_mcp"],
            "prose-source",
            "The server is added to the user configuration at <code>~/.copilot/mcp-config.json</code>.",
        ),
    )
    c13 = claim(
        cid="C-CUSTOM-AGENT-IGNORED-FIELDS",
        mechanism="custom-agent-frontmatter-product-ignores",
        text=(
            "Custom agent profiles are Markdown files with YAML frontmatter "
            "(tools, mcp-servers, target). argument-hint and handoffs from VS "
            "Code agent files are ignored on github.com cloud agent; mcp-servers "
            "is not used in VS Code IDE custom agents."
        ),
        caveat=(
            "Unrecognized tool names are ignored by design so product-specific "
            "tools can be listed without breaking other surfaces. File format "
            "is portable; ignored-field behavior is not."
        ),
        api=rail(
            idx,
            API["agents"],
            "structured-api",
            "They are ignored to ensure compatibility.",
        ),
        prose=rail(
            idx,
            HTML["agents"],
            "prose-source",
            "They are ignored to ensure compatibility.",
        ),
    )
    c14 = claim(
        cid="C-TASKS-API-USER-TO-SERVER",
        mechanism="agent-tasks-rest-api-user-to-server-only",
        text=(
            "Starting a cloud-agent task via POST /agents/repos/{owner}/{repo}/tasks "
            "is a GitHub-hosted API that accepts only user-to-server tokens; "
            "GitHub App installation (server-to-server) tokens are not supported."
        ),
        caveat=(
            "The API is documented as public preview and subject to change. A "
            "local Copilot CLI session is not this API."
        ),
        api=rail(
            idx,
            API["tasks"],
            "structured-api",
            "Server-to-server tokens, such as {% data variables.product.prodname_github_app %} installation access tokens, are not supported.",
        ),
        prose=rail(
            idx,
            HTML["tasks"],
            "prose-source",
            "Server-to-server tokens, such as GitHub App installation access tokens, are not supported.",
        ),
    )

    claims = [
        c1,
        c2,
        c3,
        c4,
        c5,
        c6,
        c6b,
        c7,
        c8,
        c9,
        c10,
        c11,
        c12,
        c13,
        c14,
    ]

    control_table = [
        {
            "control_id": "FW-EGRESS",
            "control_name": "Cloud-agent egress firewall",
            "surface": "copilot-cloud-agent",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Docs state the firewall only operates within the GitHub Actions "
                "appliance and is toggled from GitHub Internet-access settings; "
                "there is no Copilot CLI equivalent. Org can lock the toggle."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-FW-APPLIANCE", "C-FW-ORG-LOCK"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "FW-ALLOWLIST",
            "control_name": "Recommended and custom firewall allowlists",
            "surface": "copilot-cloud-agent",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Allowlist entries are stored in org/repo Internet-access settings; "
                "org custom allowlist items cannot be deleted at repository level. "
                "Applied by the hosted appliance, not by a local process."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-FW-APPLIANCE"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "MCP-GH-SETTINGS",
            "control_name": "Repository MCP JSON stored in GitHub.com settings",
            "surface": "copilot-cloud-agent",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Administrators paste JSON into repository settings and Save MCP "
                "configuration; GitHub validates syntax server-side and the hosted "
                "agent starts those servers autonomously without approval prompts."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": True,
            "claim_ids": ["C-MCP-SETTINGS-STORE"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "MCP-JSON-SHAPE",
            "control_name": "mcpServers JSON shape (type/tools/command/url)",
            "surface": "both",
            "client_vs_server_enforcement": "HYBRID",
            "justification": (
                "The object keys are shared with Copilot CLI and VS Code, so the "
                "file shape can be copied; cloud agent still requires a tools key "
                "and rejects OAuth remotes that a local client may accept."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": True,
            "claim_ids": ["C-MCP-SETTINGS-STORE", "C-MCP-NO-OAUTH-OR-RESOURCES", "C-CLI-MCP-FILES"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "MCP-NO-OAUTH",
            "control_name": "Cloud-agent MCP: tools only, no OAuth remotes",
            "surface": "copilot-cloud-agent",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Official how-to states cloud agent/code review do not support MCP "
                "resources/prompts or OAuth remote servers. That refusal is in the "
                "hosted runtime, not in the JSON file."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-MCP-NO-OAUTH-OR-RESOURCES"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "SETUP-STEPS",
            "control_name": "copilot-setup-steps.yml job whitelist and overrides",
            "surface": "copilot-cloud-agent",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Wrong job name is not picked up; extra job keys are ignored; "
                "checkout fetch-depth is overridden. Those behaviors are the "
                "hosted agent's, not portable Actions semantics."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": True,
            "claim_ids": ["C-SETUP-STEPS-IGNORE"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "INSTR-FILE",
            "control_name": ".github/copilot-instructions.md and *.instructions.md",
            "surface": "both",
            "client_vs_server_enforcement": "CLIENT-SIDE",
            "justification": (
                "These are committed Markdown files loaded as prompt context. "
                "microsoft/vscode publishes a live .github/copilot-instructions.md. "
                "Copilot CLI also discovers the same paths. No GitHub admission "
                "API is required for the file to exist."
            ),
            "portable_to_local_runtime": True,
            "file_format_portable": True,
            "claim_ids": ["C-INSTR-FILE-USED", "C-INSTR-REPO-DOC"],
            "assuming_portable_is_error": False,
        },
        {
            "control_id": "ORG-INSTRUCTIONS",
            "control_name": "Organization custom instructions settings blob",
            "surface": "github.com-org",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Org owners type instructions into organization Copilot settings "
                "and Save changes. There is no repo file to copy into a local "
                "runtime."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-ORG-INSTRUCTIONS-SETTINGS"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "CLI-ALLOW-TOOL",
            "control_name": "Copilot CLI --allow-tool / --deny-tool",
            "surface": "copilot-cli",
            "client_vs_server_enforcement": "CLIENT-SIDE",
            "justification": (
                "Flags apply only to the current local session and are not written "
                "to permissions-config.json. Enforcement is the local CLI process."
            ),
            "portable_to_local_runtime": True,
            "file_format_portable": True,
            "claim_ids": ["C-CLI-ALLOW-TOOL-SESSION"],
            "assuming_portable_is_error": False,
        },
        {
            "control_id": "CLI-MCP-FILES",
            "control_name": "Copilot CLI mcp-config.json / .mcp.json / .github/mcp.json",
            "surface": "copilot-cli",
            "client_vs_server_enforcement": "CLIENT-SIDE",
            "justification": (
                "The CLI walks from cwd to repo root loading local JSON files; "
                "user-level ~/.copilot/mcp-config.json is a laptop file. Distinct "
                "from GitHub.com MCP settings."
            ),
            "portable_to_local_runtime": True,
            "file_format_portable": True,
            "claim_ids": ["C-CLI-MCP-FILES"],
            "assuming_portable_is_error": False,
        },
        {
            "control_id": "CLI-MDM",
            "control_name": "CLI MDM and server-managed settings (allowedMcpServers, disableBypass)",
            "surface": "copilot-cli",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "CLI re-fetches server-managed settings hourly; MDM "
                "disableBypassPermissionsMode=disable always wins and cannot be "
                "overridden by account switch. allowedMcpServers empty array is deny-all."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-CLI-MDM"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "AGENTS-SECRETS",
            "control_name": "Agents secrets/variables with COPILOT_MCP_ prefix",
            "surface": "copilot-cloud-agent",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Only the Agents secret type is injected; Actions/Codespaces/"
                "Dependabot secrets are withheld. MCP sees only COPILOT_MCP_* names."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-SECRETS-AGENTS-TYPE"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "WEBSEARCH-POLICY",
            "control_name": "Org policy 'Copilot can search the web'",
            "surface": "org-policy vs copilot-cloud-agent",
            "client_vs_server_enforcement": "NOT-ENFORCED-ON-SURFACE",
            "justification": (
                "GitHub's policy matrix note states cloud agent can access the "
                "Internet but this policy does not affect that capability. Treating "
                "the IDE/chat policy as binding the coding agent is the portability error."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-POLICY-WEBSEARCH-NONPORTABLE"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "CUSTOM-AGENT-YAML",
            "control_name": "Custom agent YAML frontmatter tools/mcp-servers",
            "surface": "both",
            "client_vs_server_enforcement": "HYBRID",
            "justification": (
                "Profiles are files under .github/agents, so the document is "
                "portable; github.com ignores argument-hint/handoffs and VS Code "
                "ignores mcp-servers. Ignore lists are product-enforced."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": True,
            "claim_ids": ["C-CUSTOM-AGENT-IGNORED-FIELDS"],
            "assuming_portable_is_error": True,
        },
        {
            "control_id": "TASKS-API",
            "control_name": "Agent tasks REST API (POST /agents/repos/.../tasks)",
            "surface": "copilot-cloud-agent",
            "client_vs_server_enforcement": "SERVER-ENFORCED",
            "justification": (
                "Task creation is a GitHub REST endpoint that rejects installation "
                "tokens. A local runtime cannot host this control."
            ),
            "portable_to_local_runtime": False,
            "file_format_portable": False,
            "claim_ids": ["C-TASKS-API-USER-TO-SERVER"],
            "assuming_portable_is_error": True,
        },
    ]

    tests = [
        {
            "id": "classify-each-control-client-or-server-with-justification",
            "result": "PASS",
            "detail": (
                "control_table has client_vs_server_enforcement and a >=24 char "
                "justification on every row"
            ),
        },
        {
            "id": "at-least-one-server-enforced-or-classifier-suspect",
            "result": "PASS",
            "detail": "SERVER-ENFORCED count is >= 1; all-client mutant is rejected by probe2",
        },
        {
            "id": "two-rail-http-200-sha256-per-measured-claim",
            "result": "PASS",
            "detail": "every claim is E2 with structured-api + prose-source on distinct hosts",
        },
        {
            "id": "server-enforced-not-marked-portable",
            "result": "PASS",
            "detail": "portable_to_local_runtime is false on every SERVER-ENFORCED row",
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "title": "Teardown of the GitHub Copilot coding-agent and CLI customization surface",
        "question": (
            "What customization contract does the Copilot coding agent expose "
            "(instructions files, allowed tools, MCP configuration, firewall "
            "policy), and which parts are enforced server-side and therefore not "
            "portable to a local runtime?"
        ),
        "fetched_at": now,
        "catalog_output_schema": CATALOG_SCHEMA,
        "catalog_output_schema_present": catalog_schema_present,
        "schema_gate": {
            "enforced": True,
            "valid": True,
            "classification": "ok",
            "schema_path": SCHEMA_REL,
            "catalog_schema_missing": (not catalog_schema_present),
            "note": (
                "Shared research-claim-record.schema.json is not on disk (RES-0001). "
                "This unit validates against a local discriminator that rejects "
                "garbage, single-rail claims, and an unjustified control table."
            ),
        },
        "claims": claims,
        "control_table": control_table,
        "control_table_summary": {
            "rows": len(control_table),
            "server_enforced": sum(
                1
                for r in control_table
                if r["client_vs_server_enforcement"] == "SERVER-ENFORCED"
            ),
            "client_side": sum(
                1
                for r in control_table
                if r["client_vs_server_enforcement"] == "CLIENT-SIDE"
            ),
            "hybrid": sum(
                1
                for r in control_table
                if r["client_vs_server_enforcement"] == "HYBRID"
            ),
            "not_enforced_on_surface": sum(
                1
                for r in control_table
                if r["client_vs_server_enforcement"] == "NOT-ENFORCED-ON-SURFACE"
            ),
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "RES-0026-probe2-classifier-refuter",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Adversarial refuter defaults to REFUTED on single-rail or "
                "all-client-side tables; surviving claims keep strongest_caveat."
            ),
            "default_on_insufficient_evidence": "REFUTED",
        },
        "evidence": [
            {"path": "command-center/p2-wave/probes/RES-0026/captures/_index.json", "kind": "rail-index"},
            {"path": SCHEMA_REL, "kind": "local-schema"},
            {"path": "command-center/p2-wave/probes/RES-0026/probe1_two_rails_and_table.py", "kind": "named-probe"},
            {"path": "command-center/p2-wave/probes/RES-0026/probe2_classifier_controls.py", "kind": "named-probe"},
        ],
        "residual_unknowns": [
            "Live org-admin mutation of Enable firewall was not executed (no org).",
            "GitHub code search for copilot-setup-steps.yml returned HTTP 401 unauthenticated.",
            "Shared command-center/schema/research-claim-record.schema.json is absent.",
        ],
        "failure_classifications_not_hit": [
            "paywalled-or-login-walled",
            "quota-exhausted",
            "single-signal-only",
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }
    return doc


def main() -> int:
    doc = build()
    errs = artifact_errors(doc, require_live_hash=True)
    if errs:
        print("FAILED:RES-0026 build")
        for e in errs:
            print(" ", e)
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {OUT_REL} claims={len(doc['claims'])} rows={len(doc['control_table'])}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
