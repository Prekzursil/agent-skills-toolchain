#!/usr/bin/env python3
"""FastMCP surface for keyless SureChEMBL patent structure search."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from patent_api import PatentInputError, PatentSearchError, SureChEMBLClient

mcp = FastMCP("patent-search")


def _error_result(exc: PatentInputError | PatentSearchError) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "error",
        "error_type": "invalid_input" if isinstance(exc, PatentInputError) else "provider_error",
        "error": str(exc),
    }


@mcp.tool()
def patent_substructure_search(
    smiles: str,
    structure_limit: int = 25,
    patent_limit: int = 50,
    wait_seconds: int = 20,
) -> dict[str, Any]:
    """Find patents containing structures that include a query SMILES as a substructure.

    This performs a real SureChEMBL substructure search, resolves matched chemical IDs to
    patent documents, and returns both chemical and patent hits. The keyless provider runs
    searches asynchronously. If the bounded wait expires, the response is ``pending`` and
    includes a ``search_id`` for ``patent_structure_search_results``. Limits are 1..100 and
    wait_seconds is 0..60. Results support FTO/prior-art triage but are not legal opinions.
    """
    try:
        with SureChEMBLClient() as client:
            return client.search_patents_by_substructure(
                smiles,
                structure_limit=structure_limit,
                patent_limit=patent_limit,
                wait_seconds=wait_seconds,
            )
    except (PatentInputError, PatentSearchError) as exc:
        return _error_result(exc)


@mcp.tool()
def patent_structure_search_results(
    search_id: str,
    structure_limit: int = 25,
    patent_limit: int = 50,
    wait_seconds: int = 10,
) -> dict[str, Any]:
    """Continue a pending SureChEMBL structure search and return its patent hits.

    Pass the UUID returned by ``patent_substructure_search``. The call waits at most
    ``wait_seconds`` (0..60), then returns either another ``pending`` envelope or the complete
    matched-structure and patent result set. Limits are 1..100.
    """
    try:
        with SureChEMBLClient() as client:
            return client.continue_substructure_search(
                search_id,
                structure_limit=structure_limit,
                patent_limit=patent_limit,
                wait_seconds=wait_seconds,
            )
    except (PatentInputError, PatentSearchError) as exc:
        return _error_result(exc)


@mcp.tool()
def patent_metadata(
    patent_id: str,
    include_abstract: bool = True,
    include_claims: bool = False,
    text_char_limit: int = 6_000,
) -> dict[str, Any]:
    """Fetch normalized SureChEMBL metadata for one patent publication.

    ``patent_id`` must use SureChEMBL UCID form (for example ``WO-2020096695-A1``). Returns
    titles, dates, family ID, parties, CPC/IPCR classifications, recent legal events and PDF
    metadata. Abstract and claims text are optional and bounded to 500..20000 characters.
    Legal-event data must be verified with the relevant patent office before an FTO decision.
    """
    try:
        with SureChEMBLClient() as client:
            return client.patent_metadata(
                patent_id,
                include_abstract=include_abstract,
                include_claims=include_claims,
                text_char_limit=text_char_limit,
            )
    except (PatentInputError, PatentSearchError) as exc:
        return _error_result(exc)


def main() -> None:  # pragma: no cover - stdio entrypoint
    mcp.run()


if __name__ == "__main__":  # pragma: no cover - stdio entrypoint
    main()
