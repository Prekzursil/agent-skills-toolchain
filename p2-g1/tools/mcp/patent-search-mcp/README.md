# Patent search MCP

A small keyless FastMCP server for chemical patent discovery and freedom-to-operate (FTO)
triage. It searches the SureChEMBL patent chemistry index with a query SMILES, resolves the
matched chemical structures to patent publications, and retrieves normalized patent metadata,
abstracts, claims, classifications, parties, family IDs, and recent legal events.

This closes a specific discovery gap: looking up a PubChem CID and following its known links is
not a novelty or substructure search. This MCP starts from the molecular graph and asks which
structures extracted from patent documents contain it.

## Tools

| Tool | Purpose |
|---|---|
| `patent_substructure_search(smiles, structure_limit?, patent_limit?, wait_seconds?)` | Start a true SureChEMBL substructure search and resolve chemical hits to patents. Returns `complete` or a bounded `pending` result. |
| `patent_structure_search_results(search_id, ...)` | Continue an asynchronous search using the UUID from a `pending` response. |
| `patent_metadata(patent_id, include_abstract?, include_claims?, text_char_limit?)` | Fetch and normalize one SureChEMBL publication in UCID form, such as `WO-2020096695-A1`. |

The search flow is:

```text
query SMILES
  -> SureChEMBL asynchronous substructure search
  -> matched SureChEMBL chemical IDs
  -> patents associated with those structures
  -> metadata/claims retrieval for selected publications
```

Search responses retain both the matched structures and patent documents so callers can audit
how a patent entered the result set. The provider may cap very broad structure searches; narrow
the query or divide it into meaningful scaffolds when `matched_structure_total` is very large.

## Install and run

Python 3.11 or newer is required. No API key, account file, or environment variable is used.

```powershell
cd tools/mcp/patent-search-mcp
uv sync --extra test
uv run python server.py
```

Without `uv`:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python server.py
```

The server uses stdio transport. A Codex registration can point directly at the project:

```toml
[mcp_servers.patent-search]
command = "uv"
args = [
  "run",
  "--directory",
  "C:/path/to/agent-skills-toolchain/tools/mcp/patent-search-mcp",
  "python",
  "server.py",
]
enabled = true
```

There is deliberately no `env` or `env_vars` block: the MCP calls the public SureChEMBL API at
`https://www.surechembl.org/api/` and never reads credential or account files.

## Typical FTO triage workflow

1. Call `patent_substructure_search` with the smallest meaningful scaffold or complete product
   SMILES. Start with modest limits so broad scaffolds do not dominate the result set.
2. If the response is `pending`, pass its `search_id` to
   `patent_structure_search_results`; do not start the same search again.
3. Rank the returned publications by structural relevance, date, applicant, and jurisdiction.
4. Call `patent_metadata(..., include_claims=true)` on the short list. Increase
   `text_char_limit` when the claims were truncated.
5. Review family members, prosecution history, current legal status, claim construction, and the
   countries where making, using, selling, offering, or importing is contemplated.

Every result includes an FTO caveat. SureChEMBL uses automated text/image extraction, so false
positives and false negatives are possible. A structure appearing anywhere in a patent is not
the same as the structure being covered by an enforceable claim. Generic/Markush claims may not
be enumerated as exact extracted structures. Legal events can be incomplete or stale. Treat this
server as a high-recall lead generator, not a legal opinion, and verify material findings in
official patent-office registers with qualified counsel.

## API behavior and safety

- The base URL is fixed in code; tool inputs cannot redirect requests to another host.
- SMILES, UUIDs, patent IDs, result limits, wait times, and text limits are validated at the MCP
  boundary.
- Calls use bounded HTTP timeouts and bounded search polling. A long-running provider search
  returns `pending` rather than holding an MCP call indefinitely.
- Provider errors are returned as structured `provider_error` envelopes without dumping large
  response bodies.
- Unit tests use `httpx.MockTransport`; the test suite requires no network access.
- SureChEMBL's API requires an undocumented `StructureSearchRequest` JSON root wrapper. The
  client locks that behavior with a regression test.

Provider documentation:

- [SureChEMBL API documentation](https://chembl.gitbook.io/surechembl/api/api-documentation)
- [SureChEMBL API examples](https://chembl.gitbook.io/surechembl/api/examples)
- [SureChEMBL service](https://www.surechembl.org/)

## Validation

Run all checks from this directory:

```powershell
uv run python -c "import asyncio, server; print([t.name for t in asyncio.run(server.mcp.list_tools())])"
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
```

An optional live smoke call can use a narrow structure and low limits. Do not make live provider
calls part of the unit test suite.
