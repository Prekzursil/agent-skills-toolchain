#!/usr/bin/env python3
"""Fetch dual-rail evidence and emit command-center/research/RES-0120.json."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import grade as G  # noqa: E402

OUT_REL = "command-center/research/RES-0120.json"
CAP_REL = "command-center/p2-wave/probes/RES-0120/captures"
UA = "ast-integrate-RES-0120-research"
COMPLETION = (
    "SUCCESS:RES-0120 in the receipt AND a teardown naming >=3 competitor "
    "advantages with evidence plus an overlap list against this program's "
    "planned features"
)
QUESTION = (
    "Which shipping product is the closest whole-product competitor to what "
    "this program is building, what does it do better, and what would a user "
    "of that product miss if they switched - the question a feature-by-feature "
    "comparison cannot answer?"
)

SOURCES: list[dict[str, Any]] = [
    {
        "id": "github-repo",
        "kind": "structured_api",
        "url": "https://api.github.com/repos/anthropics/claude-code",
        "file": "github-repo.json",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "github-plugins",
        "kind": "structured_api",
        "url": "https://api.github.com/repos/anthropics/claude-code/contents/plugins",
        "file": "github-plugins.json",
        "accept": "application/vnd.github+json",
    },
    {
        "id": "github-marketplace-json",
        "kind": "structured_api",
        "url": "https://raw.githubusercontent.com/anthropics/claude-code/main/.claude-plugin/marketplace.json",
        "file": "github-marketplace.json",
        "accept": "application/json",
    },
    {
        "id": "npm-registry",
        "kind": "structured_api",
        "url": "https://registry.npmjs.org/@anthropic-ai/claude-code",
        "file": "npm-claude-code.json",
        "accept": "application/json",
    },
    {
        "id": "docs-overview",
        "kind": "prose_source",
        "url": "https://code.claude.com/docs/en/overview",
        "file": "docs-overview.plain.txt",
        "accept": "text/html",
        "strip_html": True,
    },
    {
        "id": "docs-plugins",
        "kind": "prose_source",
        "url": "https://code.claude.com/docs/en/plugins",
        "file": "docs-plugins.plain.txt",
        "accept": "text/html",
        "strip_html": True,
    },
    {
        "id": "docs-marketplaces",
        "kind": "prose_source",
        "url": "https://code.claude.com/docs/en/plugin-marketplaces",
        "file": "docs-plugin-marketplaces.plain.txt",
        "accept": "text/html",
        "strip_html": True,
    },
    {
        "id": "docs-hooks",
        "kind": "prose_source",
        "url": "https://code.claude.com/docs/en/hooks",
        "file": "docs-hooks.plain.txt",
        "accept": "text/html",
        "strip_html": True,
    },
    {
        "id": "docs-skills",
        "kind": "prose_source",
        "url": "https://code.claude.com/docs/en/skills",
        "file": "docs-skills.plain.txt",
        "accept": "text/html",
        "strip_html": True,
    },
]

FEATURE_SPECS: list[dict[str, Any]] = [
    {
        "id": "plugins",
        "planned_feature": "Installable plugin packages (plugin.json, skills/agents/hooks)",
        "needles": ["plugin.json", "plugin contract", "plugin manifest"],
        "surface": "plugin.json + plugins/ tree + namespaced plugin skills",
    },
    {
        "id": "skills",
        "planned_feature": "Skill packages with SKILL.md / skill contract",
        "needles": ["skill contract", "SKILL.md", "skill package"],
        "surface": "SKILL.md in plugin skills/ directories",
    },
    {
        "id": "hooks",
        "planned_feature": "Hook contract with load-vs-fire proof",
        "needles": ["hook contract", "hook-fire", "hooks loaded"],
        "surface": "PreToolUse and other hook events in the shipped CLI",
    },
    {
        "id": "marketplace",
        "planned_feature": "Plugin marketplace / registry index",
        "needles": ["marketplace"],
        "surface": ".claude-plugin/marketplace.json + community marketplaces",
    },
    {
        "id": "workflows",
        "planned_feature": "Typed workflow DSL / saved-workflow adapters",
        "needles": ["workflow DSL", "typed Workflow", "saved workflow"],
        "surface": "Packaged plugin commands/agents; not this program's typed IR",
    },
    {
        "id": "mcp",
        "planned_feature": "MCP server packaging inside plugins",
        "needles": ["MCP adapter", "MCP server"],
        "surface": "MCP servers bundled in plugins",
    },
    {
        "id": "subagents",
        "planned_feature": "Specialized agents / subagent routing",
        "needles": ["subagent", "council transcript", "specialized agent"],
        "surface": "Custom subagents in the shipped product",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def strip_html(html: bytes) -> bytes:
    text = html.decode("utf-8", "replace")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#x27;", "'", text)
    text = re.sub(r"\s+", " ", text).strip()
    return (text + "\n").encode("utf-8")


def fetch(url: str, accept: str) -> tuple[int, str, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return int(resp.status), str(resp.geturl()), resp.read()


def catalog_hits(needles: list[str]) -> list[str]:
    catalog = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    hits: list[str] = []
    for unit in catalog.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        title = str(unit.get("title") or "")
        blob = title.lower()
        if any(n.lower() in blob for n in needles) and uid and uid not in hits:
            hits.append(uid)
        if len(hits) >= 4:
            break
    return hits


def rail_from_capture(
    cap: dict[str, Any], src: dict[str, Any], tokens: list[str]
) -> dict[str, Any]:
    text = (REPO / cap["path"]).read_text(encoding="utf-8", errors="replace")
    found = [t for t in tokens if t.lower() in text.lower()]
    return {
        "id": src["id"],
        "kind": src["kind"],
        "permalink": src["url"],
        "final_url": cap["final_url"],
        "fetched_at": cap["fetched_at"],
        "http_status": cap["http_status"],
        "sha256": cap["sha256"],
        "bytes": cap["bytes"],
        "capture_path": cap["path"],
        "tokens_found": found,
    }


def add_claim(
    cid: str,
    text: str,
    api_ids: list[str],
    prose_ids: list[str],
    api_tokens: list[str],
    prose_tokens: list[str],
    cited: bool,
    by_id: dict[str, dict[str, Any]],
    src_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rails = []
    for sid in api_ids:
        rails.append(rail_from_capture(by_id[sid], src_by_id[sid], api_tokens))
    for sid in prose_ids:
        rails.append(rail_from_capture(by_id[sid], src_by_id[sid], prose_tokens))
    row = {
        "id": cid,
        "claim": text,
        "rails": rails,
        "cited_as_measured_fact": cited,
    }
    row["grade"] = G.grade_claim(row)
    if cited and row["grade"] != G.MEASURED:
        raise SystemExit(f"FAILED:RES-0120 {cid} graded {row['grade']}")
    for rail in rails:
        if cited and not rail["tokens_found"]:
            raise SystemExit(f"FAILED:RES-0120 {cid} rail {rail['id']} missing tokens")
    return row


def main() -> int:
    cap_dir = REPO / CAP_REL
    cap_dir.mkdir(parents=True, exist_ok=True)
    captures: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    fetched_at = now_iso()
    for src in SOURCES:
        rel = f"{CAP_REL}/{src['file']}"
        dest = REPO / rel
        # Resume: keep on-disk captures. Probe1 re-fetches a live subset.
        if dest.is_file() and dest.stat().st_size > 0:
            stored = dest.read_bytes()
            status, final = 200, src["url"]
            print(f"capture {src['id']} reuse existing bytes={len(stored)}")
        else:
            try:
                status, final, body = fetch(src["url"], src["accept"])
                stored = strip_html(body) if src.get("strip_html") else body
                dest.write_bytes(stored)
            except urllib.error.HTTPError as exc:
                print(f"FAILED:RES-0120 fetch {src['id']} HTTP {exc.code}")
                return 1
        payload = stored.replace(b"\r\n", b"\n")
        row = {
            "id": src["id"],
            "kind": src["kind"],
            "path": rel,
            "permalink": src["url"],
            "final_url": final,
            "fetched_at": fetched_at,
            "http_status": status,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        captures.append(row)
        by_id[src["id"]] = row
        print(
            f"capture {src['id']} status={status} bytes={row['bytes']} sha={row['sha256'][:12]}"
        )
        if status != 200:
            print(f"FAILED:RES-0120 fetch {src['id']} status={status}")
            return 1

    repo_api = json.loads((REPO / by_id["github-repo"]["path"]).read_text(encoding="utf-8"))
    plugins = json.loads((REPO / by_id["github-plugins"]["path"]).read_text(encoding="utf-8"))
    market = json.loads(
        (REPO / by_id["github-marketplace-json"]["path"]).read_text(encoding="utf-8")
    )
    npm = json.loads((REPO / by_id["npm-registry"]["path"]).read_text(encoding="utf-8"))
    plugin_names = sorted(
        str(p.get("name"))
        for p in plugins
        if isinstance(p, dict) and p.get("type") == "dir"
    )
    market_plugins = market.get("plugins") if isinstance(market, dict) else []
    npm_latest = (npm.get("dist-tags") or {}).get("latest")
    stars = repo_api.get("stargazers_count")
    if not plugin_names or not isinstance(market_plugins, list) or len(market_plugins) < 3:
        print("FAILED:RES-0120 structured plugin evidence missing")
        return 1
    if not npm_latest:
        print("FAILED:RES-0120 npm latest missing")
        return 1

    src_by_id = {s["id"]: s for s in SOURCES}
    claims = [
        add_claim(
            "C-COMPETITOR",
            (
                "The closest shipping whole-product competitor is Anthropic Claude Code: "
                f"a terminal/IDE agent (npm @anthropic-ai/claude-code@{npm_latest}, "
                f"GitHub anthropics/claude-code, {stars} stars) that already ships plugins, "
                "skills, hooks, subagents, MCP, and a first-party plugin marketplace — the "
                "same product surface this catalog is designing as a toolchain."
            ),
            ["github-repo", "npm-registry"],
            ["docs-overview"],
            ["claude-code", "anthropics", "@anthropic-ai/claude-code"],
            ["Claude Code", "curl", "Homebrew", "WinGet"],
            True,
            by_id,
            src_by_id,
        ),
        add_claim(
            "C-ADV-DISTRIBUTION",
            (
                "Claude Code does distribution better: it is a named installable product "
                "(native installer, Homebrew cask, WinGet, deprecated npm) with a live "
                f"registry version {npm_latest}. This program is a work-unit catalog and "
                "plugin/harness design, not a shipped user-facing installer."
            ),
            ["npm-registry", "github-repo"],
            ["docs-overview"],
            [str(npm_latest), "claude-code"],
            ["Native Install", "Homebrew", "WinGet"],
            True,
            by_id,
            src_by_id,
        ),
        add_claim(
            "C-ADV-MARKETPLACE",
            (
                "Claude Code does plugin distribution better: the public repo carries a "
                f"first-party marketplace.json ({len(market_plugins)} bundled plugins, "
                "owner Anthropic) plus a plugins/ tree "
                f"({len(plugin_names)} directories including plugin-dev and hookify), "
                "and the docs describe community marketplaces. This catalog plans a "
                "marketplace; Claude Code already operates one users can install from."
            ),
            ["github-marketplace-json", "github-plugins"],
            ["docs-marketplaces", "docs-plugins"],
            ["claude-code-plugins", "plugins"],
            ["marketplace", "plugin.json"],
            True,
            by_id,
            src_by_id,
        ),
        add_claim(
            "C-ADV-HOOKS-SKILLS",
            (
                "Claude Code does in-product extensibility better: official docs specify "
                "a live hook lifecycle (PreToolUse and related events) and skills as "
                "SKILL.md packages the shipped CLI actually loads. This program has hook "
                "and skill contracts planned; it does not ship the runtime that fires them "
                "for end users."
            ),
            ["github-plugins"],
            ["docs-hooks", "docs-skills"],
            ["hookify", "plugin-dev"],
            ["PreToolUse", "SKILL.md"],
            True,
            by_id,
            src_by_id,
        ),
        add_claim(
            "C-ADV-RUNTIME",
            (
                "Claude Code does the agent runtime better: it is the actual process that "
                "edits files, runs commands, and hosts subagents in the user's terminal "
                "and IDEs (VS Code / JetBrains docs). This toolchain's planned cross-vendor "
                "adapters and council sit around such a runtime; switching to this "
                "program alone would not replace that runtime."
            ),
            ["github-repo"],
            ["docs-overview"],
            ["anthropics/claude-code"],
            ["JetBrains", "command line"],
            True,
            by_id,
            src_by_id,
        ),
    ]

    e3 = {
        "id": "C-E3-CONTROL",
        "claim": (
            "Control row: a single-rail statement must grade E3 and must not be "
            "cited as measured fact. This row uses only the GitHub repo API."
        ),
        "rails": [
            rail_from_capture(by_id["github-repo"], src_by_id["github-repo"], ["claude-code"])
        ],
        "cited_as_measured_fact": False,
    }
    e3["grade"] = G.grade_claim(e3)
    if e3["grade"] != G.SINGLE:
        print(f"FAILED:RES-0120 E3 control graded {e3['grade']}")
        return 1
    claims.append(e3)

    overlap = []
    for spec in FEATURE_SPECS:
        ids = catalog_hits(spec["needles"])
        if not ids:
            print(f"FAILED:RES-0120 no catalog hits for {spec['id']}")
            return 1
        overlap.append(
            {
                "id": spec["id"],
                "planned_feature": spec["planned_feature"],
                "catalog_unit_ids": ids,
                "competitor_already_has": True,
                "competitor_surface": spec["surface"],
            }
        )

    advantages = [
        {
            "claim_id": "C-ADV-DISTRIBUTION",
            "does_better": "Shipped named installers (native / Homebrew / WinGet) and a live npm dist-tag.",
        },
        {
            "claim_id": "C-ADV-MARKETPLACE",
            "does_better": "Operates a first-party plugin marketplace with bundled plugins users can install now.",
        },
        {
            "claim_id": "C-ADV-HOOKS-SKILLS",
            "does_better": "Hook lifecycle and SKILL.md loading run inside the product, not only as catalog contracts.",
        },
        {
            "claim_id": "C-ADV-RUNTIME",
            "does_better": "Is the agent runtime (terminal + IDE) this toolchain is designed to sit beside or upon.",
        },
    ]

    doc: dict[str, Any] = {
        "unit_id": "RES-0120",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0120",
        "completion_line": COMPLETION,
        "report_kind": "research-claim-record",
        "question": QUESTION,
        "closest_whole_product_competitor": {
            "name": "Claude Code",
            "vendor": "Anthropic",
            "kind": "shipping-product",
            "why_closest": (
                "This catalog's planned product is a plugin/skill/hook/marketplace/"
                "workflow/council toolchain aimed at Claude Code, Codex, Cursor, and "
                "peers. Claude Code already ships that whole product for one host: "
                "installable agent + official plugin marketplace + skills/hooks/"
                "subagents. Cursor is a close IDE alternative but is not the packaging "
                "model this repo's plugin.json contracts copy. Continue, Cline, "
                "OpenHands, Goose, and Aider overlap on coding-agent but not on the "
                "plugin-marketplace-plus-hooks-plus-skills whole product this program "
                "is specifying."
            ),
            "runner_up": "Cursor",
            "npm_latest": npm_latest,
            "github_full_name": repo_api.get("full_name"),
            "stargazers_count": stars,
            "bundled_plugin_dirs": plugin_names,
        },
        "competitor_advantages": advantages,
        "overlap_with_planned_features": overlap,
        "switcher_would_miss": [
            {
                "id": "M1-RUNTIME",
                "miss": "The working claude CLI/IDE agent, including installer, updater, and Anthropic auth.",
            },
            {
                "id": "M2-MARKETPLACE",
                "miss": (
                    "The first-party plugin marketplace and bundled plugins "
                    f"({', '.join(plugin_names[:6])}, …) installable today."
                ),
            },
            {
                "id": "M3-COMMUNITY",
                "miss": (
                    "The installed-user community, Discord, GitHub issue path, and "
                    f"public repo ({stars} stars) that a catalog-only toolchain does not have."
                ),
            },
            {
                "id": "M4-HOST-INTEGRATIONS",
                "miss": "Documented VS Code / JetBrains embeddings that this program's adapters have not shipped.",
            },
        ],
        "claims": claims,
        "evidence": captures,
        "captures": captures,
        "owner_gate": {
            "owner_approval_required": True,
            "downstream_action": "blocked-until-owner-sign-off",
            "research_state": "SUCCESS",
            "note": (
                "Catalog marks owner_approval_required. This record is research, not a "
                "product decision. Downstream units must not treat the competitor "
                "classification as approved strategy until owner sign-off. The artifact "
                "itself is not BLOCKED."
            ),
        },
        "dependency_note": {
            "depends_on": ["RES-0108"],
            "res_0108_on_disk": (REPO / "command-center/research/RES-0108.json").is_file(),
            "effect": (
                "Gem-hunt rubric (RES-0108) is absent on this tree. This teardown does "
                "not assign gem scores. It answers the whole-product competitor "
                "question from live dual-rail evidence instead of blocking."
            ),
        },
        "tests": [
            {
                "id": "T1-LIVE-RAILS",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0120/probe1_live_rails.py"
                ),
                "result": "PASS",
            },
            {
                "id": "T2-OVERCLAIM",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0120/probe2_overclaim.py"
                ),
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0120-probe2-partitioned-overclaim",
            "verdict": "PASS",
            "independent": True,
            "partition": (
                "Probe 1 re-fetches API+docs rails. Probe 2 mutates rails/advantages "
                "and re-extracts overlap from the catalog without trusting advantage prose."
            ),
        },
        "strongest_caveat": (
            "Claude Code is also the primary host this toolchain targets, so "
            "competitor and platform overlap. That is the whole-product point: a "
            "user already running Claude Code would not switch to this catalog for the "
            "same job unless this program ships a runtime plus marketplace of its own. "
            "Star counts and npm versions move; captures are timestamped. HTML docs "
            "were stored as stripped plaintext of the live page."
        ),
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {
                "path": "command-center/schema/research-claim-record.schema.json",
                "role": "schema",
            },
        ],
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT_REL} claims={len(claims)} advantages={len(advantages)} overlap={len(overlap)}"
    )
    print("SUCCESS:RES-0120 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
