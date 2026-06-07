"""MCP server exposing scholarly-access tools over stdio.

All sources enabled: OA repositories, Sci-Hub, LibGen, SciDownl, direct-DOI fetch.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import logic, policy

mcp = FastMCP("scholarly-access")


@mcp.tool()
def paper_resolve(identifier: str) -> dict:
    """Resolve a DOI / PMID / arXiv ID / title to canonical metadata + normalized identifiers
    with a source-confidence score."""
    return logic.resolve(identifier)


@mcp.tool()
def paper_fetch_metadata(identifier: str) -> dict:
    """Fetch title, authors, year, journal, abstract and reference list for a paper."""
    return logic.fetch_metadata(identifier)


@mcp.tool()
def paper_find_oa_pdf(identifier: str = "", doi: str = "", arxiv: str = "") -> dict:
    """Find a PDF URL for a paper. Searches OA sources, Sci-Hub mirrors, LibGen,
    publisher pages, and direct DOI resolution. Returns the best URL found."""
    return logic.find_oa_pdf(identifier=identifier, doi=doi, arxiv=arxiv)


@mcp.tool()
def paper_access_status(identifier: str = "", doi: str = "", arxiv: str = "") -> dict:
    """Classify access: 'oa_pdf' (downloadable), 'free_to_read_not_redistributable',
    'subscription', 'unavailable', or 'unknown' — with provenance."""
    return logic.access_status(identifier=identifier, doi=doi, arxiv=arxiv)


@mcp.tool()
def paper_citation_graph(identifier: str = "", doi: str = "", limit: int = 50) -> dict:
    """References + citing works from metadata APIs (Semantic Scholar / OpenAlex)."""
    return logic.citation_graph(identifier=identifier, doi=doi, limit=limit)


@mcp.tool()
def paper_download_oa_pdf(url: str, dest_dir: str = "", filename: str = "", license: str = "", source: str = "") -> dict:
    """Download a PDF from any URL. Verifies the response is a real PDF file.
    Records path + sha256 + license/source."""
    try:
        return logic.download_oa_pdf(url, dest_dir=dest_dir, filename=filename, license=license, source=source)
    except PermissionError as e:
        return {"ok": False, "refused": True, "reason": str(e)}


@mcp.tool()
def paper_summarize(identifier: str = "", doi: str = "") -> dict:
    """Structured digest: title/authors/year/venue/abstract/access-status/identifiers."""
    return logic.summarize(identifier=identifier, doi=doi)


@mcp.tool()
def paper_batch_resolve(identifiers: list[str]) -> dict:
    """Resolve a list of identifiers/titles; returns access status, PDF links, and metadata."""
    return logic.batch_resolve(identifiers)


def _load_env_file() -> None:
    """Load ~/.tooluniverse/.env so existing keys are inherited."""
    import os
    envf = os.path.expanduser(os.environ.get("SCHOLARLY_ENV_FILE", "~/.tooluniverse/.env"))
    if os.path.exists(envf):
        try:
            for line in open(envf, encoding="utf-8"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except OSError:
            pass


def main() -> None:
    _load_env_file()
    mcp.run()


if __name__ == "__main__":
    main()
