"""Closed primitive vocabulary and dual-rail needle extractors for RES-0031."""
from __future__ import annotations

from typing import Any

from captures_lib import by_id, concat_text, load_metas

VENDORS = ("cline", "roo", "windsurf")
PLANTED_UNIQUE = "custom-modes"
CATALOG_SENTINEL = (
    "SUCCESS:RES-0031 in the receipt AND a printed three-way intersection "
    "plus the three unique-feature sets it was derived from"
)

# Each primitive names independent rails: a structured file (source / GitHub
# Contents-equivalent raw blob) and a prose docs page. A vendor scores E2 only
# when BOTH rails hit. E3 (one rail) may be listed as presence but is excluded
# from the citable intersection.
PRIMITIVES: list[dict[str, Any]] = [
    {
        "id": "workspace-rules",
        "label": "Workspace-scoped instruction/rules files",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-storage-paths.ts", "cline-docs-cline-rules.mdx"],
                    "needles": [".clinerules"],
                },
                "prose": {
                    "captures": ["docs-cline-rules"],
                    "needles": [".clinerules/"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-custom-instructions.ts"],
                    "needles": [".roo/rules/"],
                },
                "prose": {
                    "captures": ["docs-roo-custom-instructions"],
                    "needles": [".roo/rules/"],
                },
            },
            "windsurf": {
                # Windsurf editor source is closed. Official docs are prose-only
                # here; do not promote this cell to E2.
                "structured": {"captures": [], "needles": []},
                "prose": {
                    "captures": ["docs-windsurf-memories"],
                    "needles": [".devin/rules"],
                },
            },
        },
    },
    {
        "id": "global-rules",
        "label": "User-global rules directory or file",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-storage-paths.ts"],
                    "needles": ['resolveDocumentsExtensionPath("Rules")'],
                },
                "prose": {
                    "captures": ["docs-cline-rules"],
                    "needles": ["Documents/Cline/Rules"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-custom-instructions.ts"],
                    "needles": [
                        "getRooDirectoriesForCwd",
                        ".roo/rules/",
                    ],
                },
                "prose": {
                    "captures": ["docs-roo-custom-instructions"],
                    "needles": ["~/.roo/rules/"],
                },
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {
                    "captures": ["docs-windsurf-memories"],
                    "needles": ["global_rules.md"],
                },
            },
        },
    },
    {
        "id": "agents-md",
        "label": "AGENTS.md workspace instruction file",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-storage-paths.ts"],
                    "needles": ['AGENTS_RULES_FILE_NAME = "AGENTS.md"'],
                },
                "prose": {
                    "captures": ["docs-cline-rules"],
                    "needles": ["AGENTS.md"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-custom-instructions.ts"],
                    "needles": ['"AGENTS.md"', "AGENT.md"],
                },
                "prose": {
                    "captures": ["docs-roo-custom-instructions"],
                    "needles": ["AGENTS.md"],
                },
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {
                    "captures": ["docs-windsurf-memories"],
                    "needles": ["AGENTS.md"],
                },
            },
        },
    },
    {
        "id": "mcp-json-mcpservers",
        "label": "JSON MCP config keyed by mcpServers",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-mcp-config-loader.ts"],
                    "needles": ["mcpServers"],
                },
                "prose": {
                    "captures": ["docs-cline-mcp"],
                    "needles": ["mcpServers"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-McpHub.ts"],
                    "needles": ["mcpServers: z.record"],
                },
                "prose": {
                    "captures": ["docs-roo-mcp"],
                    "needles": ["mcpServers"],
                },
            },
            "windsurf": {
                "structured": {
                    "captures": ["ghmcp-install-windsurf.md"],
                    "needles": ["mcpServers", "mcp_config.json"],
                },
                "prose": {
                    "captures": ["docs-windsurf-mcp"],
                    "needles": ["mcpServers", "mcp_config.json"],
                },
            },
        },
    },
    {
        "id": "mcp-stdio",
        "label": "stdio/local MCP transport (command + args)",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-mcp-types.ts"],
                    "needles": ['type: "stdio"', "command: string"],
                },
                "prose": {
                    "captures": ["docs-cline-mcp"],
                    "needles": ["Local (STDIO)", "command</code> + <code>args"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-McpHub.ts"],
                    "needles": ['"stdio"', "StdioClientTransport"],
                },
                "prose": {
                    "captures": ["docs-roo-mcp"],
                    "needles": ["STDIO Transport"],
                },
            },
            "windsurf": {
                "structured": {
                    "captures": ["ghmcp-install-windsurf.md"],
                    "needles": ['"command": "docker"'],
                },
                "prose": {
                    "captures": ["docs-windsurf-mcp"],
                    "needles": ["stdio"],
                },
            },
        },
    },
    {
        "id": "mcp-remote-http",
        "label": "Remote HTTP/SSE MCP transport",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-mcp-types.ts"],
                    "needles": ['type: "streamableHttp"', "url: string"],
                },
                "prose": {
                    "captures": ["docs-cline-mcp"],
                    "needles": ["streamableHttp"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-McpHub.ts"],
                    "needles": ["streamable-http", "url"],
                },
                "prose": {
                    "captures": ["docs-roo-mcp"],
                    "needles": ["Streamable HTTP"],
                },
            },
            "windsurf": {
                "structured": {
                    "captures": ["ghmcp-install-windsurf.md"],
                    "needles": ["serverUrl", "Streamable HTTP"],
                },
                "prose": {
                    "captures": ["docs-windsurf-mcp"],
                    "needles": ["serverUrl"],
                },
            },
        },
    },
    {
        "id": "project-mcp-config",
        "label": "Workspace-level MCP JSON (shareable in-repo)",
        "rails": {
            "cline": {
                "structured": {"captures": [], "needles": []},
                "prose": {
                    "captures": ["docs-cline-mcp"],
                    "needles": ["~/.cline/mcp.json"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-McpHub.ts"],
                    "needles": [".roo/mcp.json"],
                },
                "prose": {
                    "captures": ["docs-roo-mcp"],
                    "needles": [".roo/mcp.json"],
                },
            },
            "windsurf": {
                "structured": {
                    "captures": ["ghmcp-install-windsurf.md"],
                    "needles": ["no per-project support"],
                },
                "prose": {"captures": [], "needles": []},
            },
        },
        "absent_if_needle": {
            "windsurf": True,
        },
    },
    {
        "id": "skills",
        "label": "SKILL.md progressive-disclosure skills",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-user-instruction-config-loader.ts"],
                    "needles": ['SKILL_FILE_NAME = "SKILL.md"'],
                },
                "prose": {
                    "captures": ["docs-cline-skills"],
                    "needles": ["SKILL.md"],
                },
            },
            "roo": {
                "structured": {
                    "captures": ["roo-skills.ts"],
                    "needles": ["SKILL.md"],
                },
                "prose": {
                    "captures": ["docs-roo-skill"],
                    "needles": ["SKILL.md"],
                },
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {
                    "captures": ["docs-windsurf-memories"],
                    "needles": ["Skills"],
                },
            },
        },
    },
    {
        "id": "hooks",
        "label": "Lifecycle hooks directory",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-storage-paths.ts"],
                    "needles": ['HOOKS_CONFIG_DIRECTORY_NAME = "hooks"'],
                },
                "prose": {
                    "captures": ["docs-cline-hooks"],
                    "needles": ["Hooks"],
                },
            },
            "roo": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
        },
    },
    {
        "id": "custom-modes",
        "label": "User-defined agent modes with tool groups (.roomodes)",
        "rails": {
            "cline": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
            "roo": {
                "structured": {
                    "captures": ["roo-CustomModesManager.ts"],
                    "needles": ["customModes", "rules-{slug}"],
                },
                "prose": {
                    "captures": ["docs-roo-custom-modes"],
                    "needles": [".roomodes"],
                },
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
        },
    },
    {
        "id": "mode-specific-rules",
        "label": "Rules directories scoped to a mode slug",
        "rails": {
            "cline": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
            "roo": {
                "structured": {
                    "captures": ["roo-custom-instructions.ts"],
                    "needles": [".roo/rules-${mode}/"],
                },
                "prose": {
                    "captures": ["docs-roo-custom-instructions"],
                    "needles": [".roo/rules-{modeSlug}/"],
                },
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
        },
    },
    {
        "id": "first-class-memories",
        "label": "Auto-generated persistent memories (product primitive, not markdown methodology)",
        "rails": {
            "cline": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
            "roo": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {
                    "captures": ["docs-windsurf-memories"],
                    "needles": ["~/.codeium/windsurf/memories/"],
                },
            },
        },
    },
    {
        "id": "memory-bank-methodology",
        "label": "Cline Memory Bank (rules+markdown methodology, not a first-class memory API)",
        "rails": {
            "cline": {
                "structured": {"captures": [], "needles": []},
                "prose": {
                    "captures": ["docs-cline-memory-bank"],
                    "needles": ["Memory Bank"],
                },
            },
            "roo": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
        },
    },
    {
        "id": "cross-vendor-rule-import",
        "label": "Auto-detect peer-vendor rule files (.cursorrules / .windsurfrules)",
        "rails": {
            "cline": {
                "structured": {
                    "captures": ["cline-docs-cline-rules.mdx"],
                    "needles": [".windsurfrules", ".cursorrules"],
                },
                "prose": {
                    "captures": ["docs-cline-rules"],
                    "needles": ["Windsurf Rules"],
                },
            },
            "roo": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
            "windsurf": {
                "structured": {"captures": [], "needles": []},
                "prose": {"captures": [], "needles": []},
            },
        },
    },
]


def domain_payload(doc: dict[str, Any] | None) -> dict[str, Any]:
    """Domain fields live under report (receipt_core). Top-level is a fallback."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    merged = dict(report)
    for key in (
        "intersection",
        "unique_sets",
        "cells",
        "feature_sets",
        "presence_any_rail",
        "printed",
    ):
        if key not in merged and key in doc:
            merged[key] = doc[key]
    return merged


def _rail_hits(index: dict, spec: dict) -> bool:
    captures = list(spec.get("captures") or [])
    needles = list(spec.get("needles") or [])
    if not captures or not needles:
        return False
    blob = concat_text(index, captures)
    return all(n in blob for n in needles)


def _rail_record(index: dict, spec: dict, kind: str) -> dict | None:
    captures = list(spec.get("captures") or [])
    if not captures or not _rail_hits(index, spec):
        return None
    first = index[captures[0]]
    return {
        "kind": kind,
        "capture_id": first["id"],
        "permalink": first.get("permalink") or first.get("url"),
        "url": first.get("url"),
        "fetched_at": first.get("fetched_at"),
        "http_status": first.get("http_status"),
        "sha256": first.get("sha256"),
        "needles": list(spec.get("needles") or []),
    }


def extract(index: dict | None = None) -> dict[str, Any]:
    if index is None:
        index = by_id(load_metas())
    cells = []
    e2_sets: dict[str, set[str]] = {v: set() for v in VENDORS}
    present_sets: dict[str, set[str]] = {v: set() for v in VENDORS}
    for prim in PRIMITIVES:
        pid = prim["id"]
        for vendor in VENDORS:
            rails = (prim.get("rails") or {}).get(vendor) or {}
            structured = _rail_record(index, rails.get("structured") or {}, "structured")
            prose = _rail_record(index, rails.get("prose") or {}, "prose")
            n_rails = int(structured is not None) + int(prose is not None)
            forced_absent = bool((prim.get("absent_if_needle") or {}).get(vendor))
            if forced_absent and structured is not None:
                verdict = "ABSENT"
                tier = "E2"
            elif n_rails >= 2:
                verdict = "PRESENT"
                tier = "E2"
                e2_sets[vendor].add(pid)
                present_sets[vendor].add(pid)
            elif n_rails == 1:
                verdict = "PRESENT"
                tier = "E3"
                present_sets[vendor].add(pid)
            else:
                verdict = "ABSENT"
                tier = "E4"
            cells.append(
                {
                    "primitive_id": pid,
                    "label": prim["label"],
                    "vendor": vendor,
                    "verdict": verdict,
                    "evidence_tier": tier,
                    "rail_count": n_rails,
                    "rails": [r for r in (structured, prose) if r],
                }
            )
    return {
        "cells": cells,
        "e2_sets": {k: sorted(v) for k, v in e2_sets.items()},
        "present_sets": {k: sorted(v) for k, v in present_sets.items()},
        "index": index,
    }
