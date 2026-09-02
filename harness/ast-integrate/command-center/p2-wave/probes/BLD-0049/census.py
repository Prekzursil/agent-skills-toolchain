"""Production concatenation-site census for BLD-0049.

Does not patch A2. Records PRESENT/UNFENCED or ABSENT-SITE. A FENCED
production claim requires the fence markers at the cited line, not a
comment that the bytes are untrusted.
"""
from __future__ import annotations

from pathlib import Path

from fence import BEGIN

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

INGRESSES = (
    {
        "id": "fetched-web-pages",
        "catalog_name": "fetched web pages",
        "search": "http/html fetch concatenated into a prompt",
        "production_site": None,
        "snippet": None,
    },
    {
        "id": "mcp-tool-results",
        "catalog_name": "MCP tool results",
        "search": "MCP tool result text concatenated into a prompt",
        "production_site": None,
        "snippet": None,
    },
    {
        "id": "marketplace-package-descriptions",
        "catalog_name": "marketplace package descriptions and READMEs",
        "search": "marketplace description field copied into generated JSON",
        "production_site": "command-center/p2-wave/probes/ARC-0010/generator.py:220",
        "snippet": '"description": entry["description"],',
    },
    {
        "id": "imported-workflow-definitions",
        "catalog_name": "imported workflow definitions",
        "search": "workflow stages copied into generated blueprint JSON",
        "production_site": "command-center/p2-wave/probes/ARC-0010/generator.py:238",
        "snippet": '"stages": entry["stages"],',
    },
    {
        "id": "council-transcripts-and-participant-artifacts",
        "catalog_name": "council transcripts and participant artifacts",
        "search": "council preset roles copied into generated JSON (no transcript runtime)",
        "production_site": "command-center/p2-wave/probes/ARC-0010/generator.py:245",
        "snippet": '"roles": entry["roles"],',
    },
    {
        "id": "pr-and-issue-bodies",
        "catalog_name": "PR and issue bodies",
        "search": "PR/issue body concatenated into a prompt",
        "production_site": None,
        "snippet": None,
    },
    {
        "id": "repository-supplied-agent-config",
        "catalog_name": "repository-supplied agent config",
        "search": "skill instructions concatenated into generated SKILL.md",
        "production_site": "command-center/p2-wave/probes/ARC-0010/generator.py:183",
        "snippet": 'f"{entry[\'instructions\']}\\n\\n"',
    },
)

HATCH_MUTANT = {
    "path": "command-center/p2-wave/probes/ARC-0016/hatch.py:82",
    "snippet": "out[rel] = data + opaques[rid].encode(\"utf-8\")",
    "note": "Mutant hatch, not the typed generator. Unfenced passthrough of opaque_body.",
}

SIBLINGS = (
    {
        "unit_id": "CNL-0100",
        "artifact_path": "command-center/design/council/CNL-0100-prompt-injection-through-participant-artifacts-and-transcr.md",
    },
    {
        "unit_id": "WFA-0158",
        "artifact_path": "command-center/foundry/WFA-0158-prompt-injection-quarantine-for-ingested-third-party.json",
    },
    {
        "unit_id": "CNF-0114",
        "artifact_path": "command-center/confirmation/CNF-0114-prompt-injection-defence.json",
    },
)


def parse_site(site: str) -> tuple[str, int]:
    path, _, line = site.rpartition(":")
    return path, int(line)


def line_text(rel: str, line: int) -> str:
    text = (REPO / rel).read_text(encoding="utf-8")
    rows = text.splitlines()
    if line < 1 or line > len(rows):
        raise IndexError(f"{rel}:{line} out of range n={len(rows)}")
    return rows[line - 1]


def site_has_fence(rel: str, line: int) -> bool:
    body = (REPO / rel).read_text(encoding="utf-8")
    # Fence construct, not a prose mention. The cited line plus neighbours.
    rows = body.splitlines()
    lo = max(0, line - 4)
    hi = min(len(rows), line + 3)
    window = "\n".join(rows[lo:hi])
    return BEGIN in window


def sibling_rows() -> list[dict]:
    out = []
    for s in SIBLINGS:
        p = REPO / s["artifact_path"]
        out.append({**s, "present": p.is_file() and p.stat().st_size > 0})
    return out


def census() -> list[dict]:
    rows = []
    for spec in INGRESSES:
        site = spec["production_site"]
        if not site:
            rows.append(
                {
                    "id": spec["id"],
                    "catalog_name": spec["catalog_name"],
                    "search": spec["search"],
                    "production_concatenation": "ABSENT",
                    "production_fencing": "ABSENT-SITE",
                    "production_site": None,
                    "snippet": None,
                    "instrument_fencing": "FENCED",
                    "instrument_site": "command-center/p2-wave/probes/BLD-0049/fence.py:29",
                }
            )
            continue
        rel, line = parse_site(site)
        got = line_text(rel, line)
        if spec["snippet"] not in got:
            raise RuntimeError(f"anchor drift {site}: {got!r}")
        fenced = site_has_fence(rel, line)
        rows.append(
            {
                "id": spec["id"],
                "catalog_name": spec["catalog_name"],
                "search": spec["search"],
                "production_concatenation": "PRESENT",
                "production_fencing": "FENCED" if fenced else "UNFENCED",
                "production_site": site,
                "snippet": got.strip(),
                "instrument_fencing": "FENCED",
                "instrument_site": "command-center/p2-wave/probes/BLD-0049/fence.py:29",
            }
        )
    return rows
