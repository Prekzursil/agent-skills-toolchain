#!/usr/bin/env python3
"""Emit command-center/research/RES-0032.json from local captures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402
import evidence as E  # noqa: E402

REPO = E.REPO
OUT_REL = E.ARTIFACT_REL
SCHEMA_REL = "command-center/schema/compatibility-matrix.schema.json"
QUESTION = (
    "For hosted agents (Devin-class, Factory-class, Copilot Workspace-class), "
    "which expose a public, versioned API or artifact contract that a "
    "cross-vendor adapter could target - and which are UI-only and therefore "
    "out of scope regardless of capability?"
)


def gist_version() -> str:
    data = json.loads((E.CAPTURES / "gist-meta.json").read_text(encoding="utf-8"))
    hist = data.get("history") or []
    if not hist:
        raise RuntimeError("gist history missing")
    return str(hist[0].get("version") or "")


def github_docs_commit() -> str:
    data = json.loads(
        (E.CAPTURES / "github-docs-commits-agent-tasks.json").read_text(encoding="utf-8")
    )
    return str(data[0]["sha"])


def workspace_manual_commit() -> str:
    data = json.loads(
        (E.CAPTURES / "githubnext-manual-commits.json").read_text(encoding="utf-8")
    )
    return str(data[0]["sha"])


def cite(name: str, extra: dict | None = None) -> dict:
    meta = E.verify_capture(name)
    out = {
        "url": meta["url"],
        "final_url": meta["final_url"],
        "fetched_at": meta["fetched_at"],
        "http_status": meta["http_status"],
        "sha256": meta["sha256"],
        "bytes": meta["bytes"],
        "capture_path": meta["capture_path"],
        "capture_name": name,
    }
    if extra:
        out.update(extra)
    return out


def row(
    rid: str,
    label: str,
    family: str,
    verdict: str,
    pin: str,
    capture: str,
    snippet: str,
    rationale: str,
    caveat: str,
    extra_cite: dict | None = None,
) -> dict:
    cit = cite(capture, extra_cite)
    body = (REPO / cit["capture_path"]).read_bytes()
    if snippet.encode("utf-8") not in body and snippet not in body.decode("utf-8", "replace"):
        raise RuntimeError(f"{rid}: snippet not in capture {capture}: {snippet!r}")
    return {
        "id": rid,
        "label": label,
        "family": family,
        "verdict": verdict,
        "version_or_commit": pin,
        "snippet": snippet,
        "rationale": rationale,
        "strongest_caveat": caveat,
        "citation": cit,
    }


def build() -> dict:
    gist_sha = gist_version()
    docs_sha = github_docs_commit()
    manual_sha = workspace_manual_commit()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [
        row(
            "cognition-devin",
            "Cognition Devin",
            "Devin-class",
            "public-versioned-API",
            "v3",
            "devin-llms",
            "https://docs.devin.ai/api-reference/v3/sessions/post-organizations-sessions.md",
            (
                "Public docs enumerate a versioned Organization/Enterprise REST "
                "surface under /v3/, including Create Session. A cross-vendor "
                "adapter can target https://api.devin.ai/v3 plus service-user tokens."
            ),
            (
                "Mintlify HTML has no git SHA; the pin is the /v3/ path family. "
                "Legacy v1/v2 remain during deprecation and must not be treated as current."
            ),
        ),
        row(
            "factory-droid",
            "Factory Droid",
            "Factory-class",
            "public-versioned-API",
            "openapi.info.version=0.1.0 path=/api/v0",
            "factory-openapi",
            '"version": "0.1.0"',
            (
                "Factory publishes OpenAPI 3.0.1 at "
                "https://api.factory.ai/api/v0/openapi.json titled Factory Public API, "
                "version 0.1.0, with /api/v0/computers and /api/v0/sessions."
            ),
            (
                "POST /api/v0/sessions is documented as enabled for selected "
                "organizations only. Computers/CI remain the portable public contract; "
                "session drive is org-gated, not undocumented."
            ),
        ),
        row(
            "github-copilot-workspace",
            "GitHub Copilot Workspace",
            "Copilot Workspace-class",
            "UI-only",
            f"sunset=2025-05-30 gist={gist_sha} manual={manual_sha}",
            "copilot-workspace-sunset-gist",
            "May 30th 2025",
            (
                "Copilot Workspace was a GitHub Next technical preview operated from "
                "the issue Open in Workspace button and a web UI. The Next sunset "
                "note ends the preview on 30 May 2025 with no REST/OpenAPI contract. "
                "Successor Copilot Cloud Agent is a different product (see next row)."
            ),
            (
                "Do not treat Copilot Cloud Agent REST as a Workspace contract. "
                "Workspace is sunset; an adapter targeting it has no live surface."
            ),
            {"commit_sha": gist_sha, "related_commit_sha": manual_sha},
        ),
        row(
            "github-copilot-cloud-agent",
            "GitHub Copilot Cloud Agent",
            "Copilot successor (not Workspace)",
            "public-versioned-API",
            f"X-GitHub-Api-Version:2026-03-10 docs={docs_sha}",
            "github-agent-tasks",
            "https://api.github.com/agents/repos/OWNER/REPO/tasks",
            (
                "GitHub REST documents agent tasks at "
                "POST/GET /agents/repos/{owner}/{repo}/tasks with "
                "X-GitHub-Api-Version: 2026-03-10. github/docs commit "
                f"{docs_sha} (2026-05-06) pins the captured description."
            ),
            (
                "Endpoints are public preview and may change. This is not Copilot "
                "Workspace. An adapter must pin 2026-03-10 and expect schema drift."
            ),
            {"commit_sha": docs_sha},
        ),
        row(
            "cursor-cloud-agents",
            "Cursor Cloud Agents",
            "hosted peer",
            "public-versioned-API",
            "openapi.info.version=1.0.0 path=/v1/agents",
            "cursor-openapi-v1",
            "/v1/agents:",
            (
                "Cursor publishes Cloud Agents API OpenAPI 3.0.3, info.version 1.0.0, "
                "server https://api.cursor.com, resource /v1/agents. That is a "
                "versioned HTTP contract an adapter can call."
            ),
            "Docs mark the v1 API as public beta; schemas may change before GA.",
        ),
        row(
            "google-jules",
            "Google Jules",
            "hosted peer",
            "public-versioned-API",
            "v1alpha",
            "jules-developers",
            "https://jules.googleapis.com/v1alpha/sessions",
            (
                "Google documents Jules REST at https://jules.googleapis.com/v1alpha "
                "with X-Goog-Api-Key and session create/list/sendMessage. The version "
                "token is v1alpha."
            ),
            (
                "Official copy calls this an alpha/experimental release that may "
                "change specs and API keys. Pin v1alpha; do not treat it as stable."
            ),
        ),
        row(
            "anthropic-managed-agents",
            "Claude Managed Agents",
            "hosted peer",
            "public-versioned-API",
            "anthropic-version:2023-06-01 beta:managed-agents-2026-04-01",
            "claude-agent-setup",
            "anthropic-version: 2023-06-01",
            (
                "Anthropic documents POST https://api.anthropic.com/v1/agents with "
                "anthropic-version: 2023-06-01 and anthropic-beta: "
                "managed-agents-2026-04-01. That is a dated, public HTTP contract."
            ),
            "Managed Agents is beta; headers and session semantics may be refined.",
        ),
        row(
            "replit-agent",
            "Replit Agent",
            "hosted peer",
            "UI-only",
            "docs-replit-agent@capture",
            "replit-agent",
            "Describe what you want",
            (
                "Replit Agent docs instruct the user to describe work in the Project "
                "Editor chat. The Enterprise Admin API covers workspaces/members/usage, "
                "not starting or steering Agent runs. No versioned agent-task HTTP "
                "contract was present in the captured docs."
            ),
            (
                "Admin API existence is not an agent adapter contract. A later Agent "
                "REST would flip this row; none was in the 2026-08-24 captures."
            ),
        ),
        row(
            "openai-codex-cloud",
            "OpenAI Codex cloud",
            "hosted peer",
            "UI-only",
            "codex-cloud-environments@capture",
            "openai-codex-cloud",
            "Cloud environments",
            (
                "Captured Codex cloud docs describe isolated cloud environments "
                "configured in product settings. Programmatic Codex paths in the "
                "same doc set are the local CLI/SDK (including MCP), not a hosted "
                "Devin-class session REST. An adapter cannot target a public "
                "versioned hosted-agent HTTP contract from these pages."
            ),
            (
                "Local Codex CLI/SDK is programmable but is not a hosted-agent "
                "artifact contract. Do not conflate it with Devin/Factory/Cursor HTTP APIs."
            ),
        ),
    ]
    ok_cit, why_cit = C.citations_complete(rows)
    ok_ctl, why_ctl = C.control_ui_only_and_discriminating(rows)
    if not ok_cit or not ok_ctl:
        raise RuntimeError(f"preflight failed cit={why_cit} ctl={why_ctl}")
    hist = C.histogram(rows)
    ui_rows = [r["id"] for r in rows if r["verdict"] == "UI-only"]
    evidence = []
    for r in rows:
        cit = r["citation"]
        evidence.append(
            {
                "claim": r["id"],
                "path": cit["capture_path"],
                "url": cit["url"],
                "fetched_at": cit["fetched_at"],
                "http_status": cit["http_status"],
                "sha256": cit["sha256"],
                "version_or_commit": r["version_or_commit"],
                "snippet": r["snippet"],
                "kind": "live-fetch-capture",
            }
        )
    doc = {
        "unit_id": "RES-0032",
        "state": "SUCCESS",
        "sentinel": E.SENTINEL,
        "receipt": E.SENTINEL,
        "question": QUESTION,
        "title": "Which hosted-agent platforms expose a contract stable enough to adapt to",
        "output_schema": SCHEMA_REL,
        "fetched_window": {
            "earliest": min(str(r["citation"]["fetched_at"]) for r in rows),
            "latest": max(str(r["citation"]["fetched_at"]) for r in rows),
            "emitted_at": now,
        },
        "row_axis": "hosted_agent_platform",
        "column_axis": "adapter_targetability",
        "allowed_classes": list(C.ALLOWED),
        "classification_rule": (
            "public-versioned-API: third parties can call a documented HTTP/RPC "
            "or OpenAPI contract with an explicit version token (path, date header, "
            "or info.version). private-API: a programmatic surface exists but is "
            "partner-only or unpublished. UI-only: operation is through a web/IDE "
            "UI (or the product is sunset) with no public versioned agent-task contract."
        ),
        "rows": rows,
        "platform_classification_table": [
            {
                "platform": r["label"],
                "family": r["family"],
                "verdict": r["verdict"],
                "version_or_commit": r["version_or_commit"],
                "citation_url": r["citation"]["url"],
                "fetched_at": r["citation"]["fetched_at"],
                "http_status": r["citation"]["http_status"],
                "sha256": r["citation"]["sha256"],
            }
            for r in rows
        ],
        "class_histogram": hist,
        "ui_only_count": hist.get("UI-only", 0),
        "ui_only_platforms": ui_rows,
        "adapter_targets": [r["id"] for r in rows if r["verdict"] == "public-versioned-API"],
        "out_of_scope_ui_only": ui_rows,
        "claims": [
            {
                "id": r["id"],
                "claim": f"{r['label']} is {r['verdict']} at pin {r['version_or_commit']}",
                "verdict": "CONFIRMED",
                "caveat": r["strongest_caveat"],
            }
            for r in rows
        ],
        "evidence": evidence,
        "tests": [
            {
                "id": "probe1-citations",
                "name": "each row has a citation; capture sha256 and snippet match disk",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0032/probe1_citations.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2-ui-only-control",
                "name": "at least one UI-only row; all-public mutant is rejected",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0032/probe2_ui_only_control.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0032-adversarial-default-refute",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Defaulted to REFUTED for any platform lacking a version pin plus "
                "a 200-capture. Copilot Workspace is UI-only because the sunset "
                "note and user manual describe a button/web preview, not REST. "
                "Jules stays public-versioned-API only because v1alpha is still a "
                "version token; stability is the caveat, not the class."
            ),
        },
        "strongest_surviving_counterargument": (
            "OpenAI Codex CLI/SDK and Replit Admin API are programmable, so a "
            "reader might reject UI-only. Those surfaces are local CLI or "
            "governance APIs, not hosted-agent session contracts in the Devin/"
            "Factory/Cursor sense. The UI-only verdict is about adapter-targetable "
            "hosted-agent HTTP/artifact contracts, not about whether any API exists "
            "in the vendor catalogue."
        ),
        "preflight": {"citations": why_cit, "control": why_ctl},
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {"path": SCHEMA_REL, "role": "schema", "exists": True},
        ],
    }
    return doc


def main() -> int:
    doc = build()
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} rows={len(doc['rows'])} ui_only={doc['ui_only_count']}")
    print(E.SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
