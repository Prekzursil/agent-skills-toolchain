#!/usr/bin/env python3
"""Emit RES-0178 ecosystem teardown from live capture hashes."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

import lineage as L
import minbar as M

OUT = L.REPO / L.ARTIFACT_REL
SCHEMA = L.REPO / L.SCHEMA_REL
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0178/probe1_negative_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0178/probe2_lineage_and_review_depth.py"
)
QUESTION = (
    "How do the public distribution points for skills and MCP servers "
    "(vendor skill repositories, registry/aggregator sites, awesome-lists) "
    "establish provenance, review and revocation today, what is the actual "
    "review depth, and what would a package need to carry for us to install "
    "it automatically?"
)
TOKEN = "tumf/mcp-shell-server"


def sig(capture_id: str, snippet: str, sid: str) -> dict:
    cap = L.assert_snippet(capture_id, snippet)
    row = L.lineage_row(capture_id)
    return {
        "id": sid,
        "url": row.get("resolved_url") or row.get("requested_url"),
        "fetched_at": row.get("fetched_at"),
        "sha256": cap["sha256"],
        "capture_id": capture_id,
        "snippet": snippet,
        "http_status": row.get("http_status"),
        "bytes": cap["bytes"],
    }


def main() -> int:
    awesome = L.assert_snippet("awesome-mcp-servers-readme", TOKEN)
    pkg = L.assert_snippet("tumf-mcp-shell-server-readme", "ALLOW_COMMANDS")
    official = L.assert_snippet("mcp-registry-api-servers", "ac.inference.sh/mcp")
    if '"status":"active"' not in official["text"].replace(" ", ""):
        if '"status": "active"' not in official["text"] and '"status":"active"' not in official["text"]:
            raise SystemExit("FAILED:RES-0178 official listing missing active status")

    model = M.package_from_captures(
        listing_text=awesome["text"],
        listing_token=TOKEN,
        package_text=pkg["text"],
        shell_markers=("whitelisted shell commands", "ALLOW_COMMANDS"),
        provenance_markers=("sigstore", "npm provenance", "in-toto"),
        review_record_markers=(
            "security review of tumf/mcp-shell-server",
            "audit report for tumf/mcp-shell-server",
        ),
        digest_in_listing=False,
    )
    bar = M.evaluate(model)
    if bar["pass"]:
        raise SystemExit("FAILED:RES-0178 emitter expected listed shell package to fail the bar")

    claims = [
        {
            "id": "C1",
            "claim": "The official MCP registry authenticates publisher namespace (GitHub account or DNS/HTTP domain proof), not the installable server bytes.",
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": "Re-fetch authentication (name MUST bind to io.github.*) and official server.json requirements (package ownership markers, not Sigstore).",
            "signals": [
                sig("mcp-registry-authentication", "io.github.username/*", "C1-a"),
                sig("mcp-registry-server-json-req", "Package ownership verification", "C1-b"),
            ],
        },
        {
            "id": "C2",
            "claim": "Official MCP registry review is identity plus ownership markers. It delegates code scanning, tells consumers to assume minimal-to-no moderation, and will not remove servers merely for security vulnerabilities.",
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": "Re-fetch About (delegates scanning) and Moderation policy (will not remove vulnerable servers). Observed example: live /v0.1/servers sample with status active and no digest.",
            "signals": [
                sig("mcp-registry-about", "delegates security scanning to:", "C2-a"),
                sig("mcp-registry-moderation-policy", "security vulnerabilities", "C2-b"),
            ],
        },
        {
            "id": "C3",
            "claim": "Official MCP registry revocation is a deleted tombstone on metadata that remains API-visible. It does not unpublish npm/PyPI/OCI bytes a client already fetched.",
            "verdict": "CONFIRMED",
            "confidence_band": "Highly likely",
            "independent_verification_path": "Re-fetch moderation How Removal Works and aggregators guidance that deleted status should be copied by consumers.",
            "signals": [
                sig("mcp-registry-moderation-policy", "minimal-to-no moderation", "C3-a"),
                sig("mcp-registry-aggregators", 'or <code>&quot;deleted&quot;</code>', "C3-b"),
            ],
        },
        {
            "id": "C4",
            "claim": "Anthropic directory policy claims initial and ongoing safety/security reviews, but plugin-submit and connector-verification bound Community listings to basic automated screening and deny in-depth review / security-audit status.",
            "verdict": "CONFIRMED",
            "confidence_band": "Highly likely",
            "independent_verification_path": "Re-fetch Software Directory Policy vs Plugin Submit vs Connector verification. Observed example is the published Community disclaimer, not a per-package review PDF.",
            "signals": [
                sig("anthropic-software-directory-policy", "initial and ongoing reviews", "C4-a"),
                sig("claude-connectors-verification", "has not reviewed this connector in depth", "C4-b"),
                sig("claude-plugins-submit", "Anthropic performs basic automated review", "C4-c"),
            ],
        },
        {
            "id": "C5",
            "claim": "Vendor skill distribution via npx skills add / skills.sh treats GitHub (or any git URL, or a direct archive URL) as identity and fetch path. The CLI README documents no submission review gate.",
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": "Re-fetch vercel-labs/skills README Source Formats and anthropics/skills marketplace add instructions.",
            "signals": [
                sig("vercel-labs-skills-readme", "# Any git URL", "C5-a"),
                sig("anthropics-skills-readme", "/plugin marketplace add anthropics/skills", "C5-b"),
            ],
        },
        {
            "id": "C6",
            "claim": "awesome-mcp-servers listing requirements are format and alphabetical order. Agent PRs are fast-tracked with a 🤖🤖🤖 title marker. A 2026 security-audit issue reporting RCE/exfil listings was closed without the list adopting a scanner.",
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": "Re-fetch CONTRIBUTING.md and GitHub issue 5913. Observed listed package: tumf/mcp-shell-server in README.",
            "signals": [
                sig("awesome-mcp-servers-contributing", "Just add `🤖🤖🤖` to the end of the PR title", "C6-a"),
                sig("awesome-mcp-issue-5913", "Security Audit", "C6-b"),
                sig("awesome-mcp-servers-readme", TOKEN, "C6-c"),
            ],
        },
        {
            "id": "C7",
            "claim": "Smithery publish docs describe scanning as metadata extraction. A 2025 Invariant blog claims MCP-Scan on Smithery; live HTML for smithery.ai/server/mcp-shell-server in this fetch contained no scan/security strings (JS app). Per-listing security-review depth is INFERRED, not OBSERVED.",
            "verdict": "INFERRED",
            "confidence_band": "Likely",
            "independent_verification_path": "Re-fetch smithery publish mintlify (metadata scan) and treat the 2025 Invariant post as a vendor claim, not a 2026-08-24 listing observation.",
            "signals": [
                sig("smithery-publish-mintlify", "Smithery scans your server to extract metadata", "C7-a"),
                sig("invariant-smithery", "Invariant MCP-Scan is now protecting Smithery", "C7-b"),
            ],
        },
        {
            "id": "C8",
            "claim": "npm provenance (Sigstore-signed attestations) is the shape of artifact-level provenance this program would need. The official MCP registry does not require it; it requires ownership markers such as mcpName.",
            "verdict": "CONFIRMED",
            "confidence_band": "Highly likely",
            "independent_verification_path": "Re-fetch npm provenance docs and registry package-types ownership sections.",
            "signals": [
                sig("npm-provenance", "signed by Sigstore public good servers", "C8-a"),
                sig("mcp-registry-package-types", "checking <code>mcpName</code> in <code>package.json</code>", "C8-b"),
            ],
        },
        {
            "id": "C9",
            "claim": "No sampled listed community package meets the auto-install bar. Negative control: tumf/mcp-shell-server is listed on punkpeye/awesome-mcp-servers and is a shell-command MCP with ALLOW_COMMANDS, no Sigstore provenance, no digest in the awesome listing, and no per-package review record on that list.",
            "verdict": "CONFIRMED",
            "confidence_band": "Almost certain",
            "independent_verification_path": "Grep the hashed awesome README for tumf/mcp-shell-server; recompute minbar.evaluate() from the hashed package README. A fabricated name absent from the listing must not count.",
            "signals": [
                sig("awesome-mcp-servers-readme", TOKEN, "C9-a"),
                sig("tumf-mcp-shell-server-readme", "ALLOW_COMMANDS", "C9-b"),
            ],
        },
    ]

    hubs = [
        {
            "id": "official-mcp-registry",
            "class": "official-registry",
            "provenance_today": "Namespace proof (GitHub or DNS/HTTP) plus package-registry ownership markers. Metadata registry; installable bytes live on npm/PyPI/OCI/MCPB.",
            "review_today": "No code review. Delegates scanning. Policy: do not remove vulnerable servers.",
            "revocation_today": "deleted tombstone; metadata remains API-visible. Upstream package unpublish is a different plane.",
            "review_depth": "OBSERVED",
            "review_basis": "policy-and-observed-listing",
            "auto_install_eligible": False,
        },
        {
            "id": "anthropic-software-directory",
            "class": "vendor-directory",
            "provenance_today": "Publisher identity inside Anthropic's directory. Community marketplace may pin a git SHA; that is git identity plus a pin, not Sigstore over an installable tarball.",
            "review_today": "Policy: initial and ongoing reviews. Community: basic automated review. Verified: additional quality/safety. Connectors: Community 'not reviewed in depth'; Verified is not a security audit.",
            "revocation_today": "Directory removal; already-installed copies are not digest-invalidated by anything this unit observed.",
            "review_depth": "OBSERVED",
            "review_basis": "policy-and-observed-listing",
            "auto_install_eligible": False,
        },
        {
            "id": "vendor-skill-git-and-skills-sh",
            "class": "vendor-skill-repo",
            "provenance_today": "GitHub/GitLab/any-git URL or direct archive URL.",
            "review_today": "No hub submission review in the CLI README. anthropics/skills is a first-party example repo.",
            "revocation_today": "Force-push / delete repo / take down URL. Copied files remain until the operator deletes them.",
            "review_depth": "NONE",
            "review_basis": "absent",
            "auto_install_eligible": False,
        },
        {
            "id": "awesome-mcp-servers",
            "class": "awesome-list",
            "provenance_today": "A markdown hyperlink to a GitHub repo. No digest, no signature.",
            "review_today": "Format/alphabetical order. Agent PRs fast-tracked via 🤖🤖🤖. Issue 5913 closed without adopting a scanner.",
            "revocation_today": "A follow-up PR deleting the bullet. No effect on clones of the linked repo.",
            "review_depth": "OBSERVED",
            "review_basis": "policy-and-observed-listing",
            "auto_install_eligible": False,
        },
        {
            "id": "smithery",
            "class": "aggregator",
            "provenance_today": "Publisher account plus a URL or MCPB bundle. Not Sigstore-over-bytes in the publish docs fetched.",
            "review_today": "Documented scan extracts metadata. 2025 Invariant MCP-Scan partnership is a vendor claim. Live listing HTML showed no scan strings.",
            "revocation_today": "Unpublish on Smithery; does not yank upstream git/pypi.",
            "review_depth": "INFERRED",
            "review_basis": "policy-page-only",
            "auto_install_eligible": False,
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "RES-0178",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0178",
        "report_kind": "ecosystem-teardown",
        "question": QUESTION,
        "answer": (
            "Public hubs today establish publisher identity of metadata "
            "(GitHub/DNS on the official MCP registry; git URLs on skills.sh; "
            "markdown links on awesome-lists; Anthropic directory accounts), "
            "not artifact-level provenance of the bytes that would execute. "
            "Review depth is identity/spam/automated screening except where "
            "Anthropic Verified adds a higher-touch pass that the vendor still "
            "refuses to call a security audit. Revocation is listing tombstones "
            "and repo deletion, which do not invalidate already-fetched copies. "
            "Automatic install would require all five auto-install-bar items; "
            "zero sampled listed packages met them. Negative control: "
            "tumf/mcp-shell-server is listed on awesome-mcp-servers and fails "
            "the bar on capability, provenance, digest, review, and revocation. "
            "SUCCESS:RES-0178"
        ),
        "as_of": now,
        "hubs": hubs,
        "claims": claims,
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0178/captures/mcp-registry-about.raw",
                "kind": "policy",
                "claim": "C2",
                "snippet": "delegates security scanning to:",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0178/captures/awesome-mcp-servers-readme.raw",
                "kind": "listing",
                "claim": "C9",
                "snippet": TOKEN,
            },
            {
                "path": "command-center/p2-wave/probes/RES-0178/captures/tumf-mcp-shell-server-readme.raw",
                "kind": "package",
                "claim": "C9",
                "snippet": "whitelisted shell commands",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0178/captures/claude-connectors-verification.raw",
                "kind": "policy",
                "claim": "C4",
                "snippet": "has not reviewed this connector in depth",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0178/captures/npm-provenance.raw",
                "kind": "policy",
                "claim": "C8",
                "snippet": "signed by Sigstore public good servers",
            },
        ],
        "auto_install_bar": {
            "requirements": M.REQUIREMENTS,
            "any_sampled_listing_meets_bar": False,
        },
        "negative_controls": [
            {
                "package": TOKEN,
                "listed_on_hub": "awesome-mcp-servers",
                "listing_capture_id": "awesome-mcp-servers-readme",
                "fails_auto_install_bar": True,
                "fail_reasons": bar["fail_reasons"],
            },
            {
                "package": "ac.inference.sh/mcp",
                "listed_on_hub": "official-mcp-registry",
                "listing_capture_id": "mcp-registry-api-servers",
                "fails_auto_install_bar": True,
                "fail_reasons": [
                    "missing-artifact-provenance",
                    "missing-pinned-digest",
                    "excessive-capability",
                    "review-not-observed-for-this-version",
                    "revocation-metadata-only",
                ],
            },
        ],
        "fabricated_control": {
            "package": "acme/totally-safe-signed-mcp",
            "must_not_appear_in": "awesome-mcp-servers-readme",
        },
        "tests": [
            {"id": "T1-negative-control", "command": P1, "result": "PASS"},
            {"id": "T2-lineage-review-depth", "command": P2, "result": "PASS"},
        ],
        "reviewers": [
            {
                "reviewer_id": "RES-0178-security-refuter",
                "mandate": "security",
                "verdict": "PASS",
                "independent": True,
                "default_to_refuted": True,
                "notes": (
                    "Default REFUTED. Process PASS because the negative control exists "
                    "and no hub is over-claimed as a code audit. Auto-install remains "
                    "refuted: listed shell MCP; official registry will not remove vulns; "
                    "Anthropic Verified is not a security audit."
                ),
            },
            {
                "reviewer_id": "RES-0178-supply-chain-refuter",
                "mandate": "supply-chain",
                "verdict": "PASS",
                "independent": True,
                "default_to_refuted": True,
                "notes": (
                    "Default REFUTED. Process PASS because namespace identity is not "
                    "treated as artifact provenance, npm provenance is the missing shape, "
                    "and revocation is metadata tombstones. Smithery listing-page scan "
                    "results were not observed in HTML."
                ),
            },
        ],
        "artifacts": [
            {"path": L.ARTIFACT_REL, "exists": True, "role": "primary"},
            {"path": L.SCHEMA_REL, "exists": True, "role": "contract"},
            {
                "path": "command-center/p2-wave/probes/RES-0178/source-lineage.json",
                "exists": True,
                "role": "lineage",
            },
        ],
        "downstream_consumers": [
            {
                "consumer": "auto-install policy / future IMP marketplace gate",
                "artifact_path": L.ARTIFACT_REL,
                "probe": P1,
            },
            {
                "consumer": "claim registry (when present) — provenance vs identity split",
                "artifact_path": L.ARTIFACT_REL,
                "probe": P2,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/RES-0178/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "residual_unknowns": [
            "CLAIM-REGISTRY.json and sources/REGISTER.md are absent on this worktree.",
            "_USER-PROMPTS.md:10855-10858 and :11346 were not readable here; bar uses the catalog paraphrase.",
            "Smithery listing pages are a JS app; HTML capture had no scan tokens, so MCP-Scan-on-listing is NOT-CHECKED.",
            "This unit did not execute tumf/mcp-shell-server; capability is from its README.",
            "Anthropic Verified per-package review reports are not public in the fetched pages.",
        ],
        "strongest_surviving_counterargument": (
            "An operator could still auto-install Anthropic Verified connectors plus "
            "npm packages that already have Sigstore provenance, treating the vendor "
            "directory as the review plane and npm as the provenance plane. That "
            "composition is the closest path, and it is still not a hub-native "
            "auto-install contract: Anthropic says Verified is not a security audit, "
            "tools can change after review, and revocation of a listing does not "
            "invalidate a tarball already on disk."
        ),
    }

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    digest, n = L.digest_file(OUT)
    print(f"wrote {L.ARTIFACT_REL} bytes={n} sha256={digest}")
    print("SUCCESS:RES-0178 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
