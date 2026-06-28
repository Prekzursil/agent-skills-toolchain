"""MCP server exposing lawful scholarly-access tools over stdio.

Spec names use dots (`paper.resolve`); MCP tool names use underscores
(`paper_resolve`) for client compatibility. The mapping is 1:1 and documented.

NO Sci-Hub / LibGen / SciDownl / shadow libraries. NO paywall bypass. See policy.py.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import logic, policy

mcp = FastMCP("scholarly-access")


@mcp.tool()
def paper_resolve(identifier: str) -> dict[str, object]:
    """Resolve a DOI / PMID / arXiv ID / title to canonical metadata + normalized identifiers
    (doi, pmid, arxiv, openalex) with a source-confidence score. Spec: paper.resolve."""
    return logic.resolve(identifier)


@mcp.tool()
def paper_fetch_metadata(identifier: str) -> dict[str, object]:
    """Fetch title, authors, year, journal, abstract (if legally available) and a reference
    list for a DOI / PMID / arXiv / title. Spec: paper.fetch_metadata."""
    return logic.fetch_metadata(identifier)


@mcp.tool()
def paper_find_oa_pdf(
    identifier: str = "", doi: str = "", arxiv: str = ""
) -> dict[str, object]:
    """Find a LEGAL open-access PDF URL for a paper (Unpaywall / OpenAlex / arXiv / Semantic
    Scholar / CORE / DOAJ). Returns the URL only if its host is on the OA allowlist; lists
    evidence for every candidate (including any shadow-library URL it DENIED). Never returns a
    Sci-Hub/LibGen link. Spec: paper.find_oa_pdf."""
    return logic.find_oa_pdf(identifier=identifier, doi=doi, arxiv=arxiv)


@mcp.tool()
def paper_access_status(
    identifier: str = "", doi: str = "", arxiv: str = ""
) -> dict[str, object]:
    """Classify access honestly: 'oa_pdf' (downloadable OA), 'free_to_read_not_redistributable'
    (readable on a page but not legally fetchable — cite, don't circumvent), 'subscription'
    (paywalled), 'unavailable', or 'unknown' — with provenance. Spec: paper.access_status."""
    return logic.access_status(identifier=identifier, doi=doi, arxiv=arxiv)


@mcp.tool()
def paper_citation_graph(
    identifier: str = "", doi: str = "", limit: int = 50
) -> dict[str, object]:
    """References + citing-works from legal metadata APIs (Semantic Scholar / OpenAlex).
    Spec: paper.citation_graph."""
    return logic.citation_graph(identifier=identifier, doi=doi, limit=limit)


@mcp.tool()
def paper_download_oa_pdf(
    url: str,
    dest_dir: str = "",
    filename: str = "",
    license: str = "",
    source: str = "",
) -> dict[str, object]:
    """Download a legal OA PDF. HARD-GATED: the URL must be on the OA allowlist (typically one
    returned by paper.find_oa_pdf) and the bytes must be a real %PDF; otherwise it refuses.
    Never constructs URLs, never falls back to an unauthorized mirror. Records path + sha256 +
    license/source. Spec: paper.download_oa_pdf."""
    try:
        return logic.download_oa_pdf(
            url, dest_dir=dest_dir, filename=filename, license=license, source=source
        )
    except PermissionError as e:
        return {
            "ok": False,
            "refused": True,
            "reason": str(e),
            "policy": policy.POLICY_BANNER,
        }


@mcp.tool()
def paper_summarize(identifier: str = "", doi: str = "") -> dict[str, object]:
    """Return a structured digest (title/authors/year/venue/abstract/access-status/identifiers)
    from legally-available metadata only, for the agent to turn into a prose summary.
    Spec: paper.summarize."""
    return logic.summarize(identifier=identifier, doi=doi)


@mcp.tool()
def paper_batch_resolve(identifiers: list[str]) -> dict[str, object]:
    """Resolve a list of identifiers/titles; returns a table of access status, OA links,
    metadata, and the unresolved items. Spec: paper.batch_resolve."""
    return logic.batch_resolve(identifiers)


def _load_env_file() -> None:
    """Best-effort load of ~/.tooluniverse/.env so existing keys are inherited out-of-the-box.
    Machine/process environment ALWAYS wins (setdefault). Keys are read by NAME only; never logged."""
    import os

    envf = os.path.expanduser(
        os.environ.get("SCHOLARLY_ENV_FILE", "~/.tooluniverse/.env")
    )
    if os.path.exists(envf):
        try:
            for line in open(envf, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    _ = os.environ.setdefault(
                        k.strip(), v.strip().strip('"').strip("'")
                    )
        except OSError:
            pass


def main() -> None:
    _load_env_file()
    mcp.run()


if __name__ == "__main__":  # pragma: no cover -- module entrypoint
    main()
