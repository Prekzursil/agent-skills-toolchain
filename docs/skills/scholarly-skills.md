# Scholarly Skills

scholarly-retrieval server (code at `tools/scholarly-access-mcp/`, `README.md` canonical).

`paper_download_oa_pdf`
> only fetches a URL whose host is on the OA allowlist AND whose bytes are a real `%PDF`. Sources are
> limited to Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar (keyless), CORE (keyed),
> DOAJ, PubMed/NCBI E-utilities, Zenodo, institutional repositories, OA publishers, and the Elsevier
> entitled-fulltext API (valid key only). Items classified `free_to_read_not_redistributable` are cited,

> **Access categories (honest):** `oa_pdf` = downloadable OA at a legit source; `free_to_read_not_redistributable`
> paywalled (cite only); `unavailable` = no legit full text; `unknown` = could not determine.

> **Status:** config wired, loads at CC restart. The MCP surface itself is verified (22 offline policy
> tests + 10 live end-to-end checks pass; 8 tools listed over MCP stdio). These five skills are documented
> against that frozen, tested tool contract.

## The 8 MCP tools (spec dot-name → MCP underscore-name)

| spec | MCP tool | what |
|---|---|---|
| `paper.resolve` | `paper_resolve` | DOI/PMID/arXiv/title → canonical metadata + normalized ids + confidence |
| `paper.fetch_metadata` | `paper_fetch_metadata` | + abstract + references (where legally available) |
| `paper.find_oa_pdf` | `paper_find_oa_pdf` | a OA PDF url (allowlisted host) + license + per-candidate evidence |
| `paper.access_status` | `paper_access_status` | access category + provenance |
| `paper.citation_graph` | `paper_citation_graph` | references + citing works from Semantic Scholar / OpenAlex |
| `paper.summarize` | `paper_summarize` | structured digest from legally-available metadata/abstract |
| `paper.batch_resolve` | `paper_batch_resolve` | table of access status + OA links + metadata + unresolved items |

---

## 1. scholarly-literature-review

**Purpose:** Build a cited, evidence-graded literature review from a topic or a seed set of papers

**Trigger phrases:** "literature review on …", "survey the research on …", "summarize the key papers about …",
"review the evidence for …", "build a reading list with citations".

**MCP tools it uses:** `paper_batch_resolve` (seed set → access table), `paper_resolve` /
`paper_fetch_metadata` (per-paper metadata + abstract + references), `paper_citation_graph` (expand the
corpus), `paper_summarize` (per-paper digest), `paper_find_oa_pdf` + `paper_download_oa_pdf` (pull OA full
text where legal).

**Example:**
- `paper_resolve("10.1371/journal.pmed.0020124")` → resolved, title "Why Most Published Research Findings
  Are False"; then `paper_citation_graph(doi="10.1371/journal.pmed.0020124", limit=25)` to fan out, and
  `paper_summarize` on each resolved item.

**Expected output:** A structured review (themes, key findings, gaps) with one citation per claim, each
tagged by access category, and a list of which sources were downloadable as OA PDF vs cite-only. The agent
writes the prose; the MCP supplies only legally-available text.

---

## 2. oa-pdf-retrieval

honestly that no full text exists.

**Trigger phrases:** "get the PDF for …", "download this paper", "find an open-access copy of …",
"is there a full text for this DOI", "fetch the OA version".

**MCP tools it uses:** `paper_resolve` (normalize the id), `paper_access_status` (classify first),
`paper_find_oa_pdf` (allowlisted candidate url + license + evidence), `paper_download_oa_pdf` (gated fetch
→ path + sha256 + bytes).

**Example:**
- `paper_find_oa_pdf(arxiv="1706.03762")` → an arXiv OA url, then `paper_download_oa_pdf(url, dest_dir, ...)`
  → ~2.1MB PDF + sha256.

**Expected output:** For a OA paper: a saved PDF path, sha256, byte count, license, and source. For a
`subscription` / `free_to_read_not_redistributable` / `unavailable` paper: NO download — the access category,

---

## 3. citation-mapping

**Purpose:** Map the references and citing works around a paper to trace influence, find related work, or
seed a snowball search — using only available metadata APIs.

**Trigger phrases:** "what cites this paper", "show the references of …", "map the citation network around …",
"find papers that build on …", "snowball from this DOI".

**MCP tools it uses:** `paper_resolve` (anchor the id), `paper_citation_graph` (references + citing works from
Semantic Scholar / OpenAlex), `paper_batch_resolve` (resolve the neighbors into an access table),
`paper_fetch_metadata` (pull references where the citation graph is thin).

**Example:**
- `paper_resolve("1706.03762")` → arXiv "Attention Is All You Need"; then
  `paper_citation_graph(doi=..., limit=50)` for references + citing works, and `paper_batch_resolve([...])`
  on the neighbor ids to get their access status and OA links.

**Expected output:** A two-sided citation map (references / citing works) with normalized ids
(doi, pmid, arxiv, openalex), each neighbor tagged with access category and any OA link. Note: depth depends
on Semantic Scholar / OpenAlex coverage for the DOI.

---

## 4. biomedical-paper-triage

**Purpose:** Rapidly triage a batch of biomedical papers (PMID/DOI lists) — resolve, classify access, pull
abstracts, and grade evidence — leaning on the PubMed/Europe PMC/Unpaywall stack.

**Trigger phrases:** "triage these PMIDs", "screen this batch of biomedical papers", "which of these are
open access", "pull abstracts for this PubMed list", "grade the evidence for these studies".

**MCP tools it uses:** `paper_batch_resolve` (PMID/DOI list → access + OA table + unresolved),
`paper_fetch_metadata` (abstract + references via Europe PMC / PubMed), `paper_access_status` (per-item
honest category), `paper_summarize` (structured per-paper digest).

**Example:**
- `paper_batch_resolve(["10.1371/journal.pone.0000308", "10.1056/NEJMoa2034577"])` →
  the PLOS item resolves `oa_pdf` (PLOS OA url); the NEJM item resolves `subscription` /

**Expected output:** A triage table — title, normalized ids, access category, OA link (if any), abstract
availability — plus per-paper structured digests and a flagged list of unresolved or cite-only items.
Evidence grading is written by the agent from legally-available abstracts/metadata.

---

## 5. drug-discovery-literature-bridge

**Purpose:** Bridge a drug / target / mechanism question to the supporting literature — resolve the relevant
papers, map their citation neighborhood, and assemble a cited evidence packet that feeds downstream
drug-discovery analysis.

**Trigger phrases:** "find the literature behind this target", "evidence for this drug's mechanism",
"papers supporting this drug-target link", "cite the studies for this pathway", "build an evidence packet
for this compound".

**MCP tools it uses:** `paper_resolve` / `paper_batch_resolve` (anchor the seed papers), `paper_fetch_metadata`
(abstract + references), `paper_citation_graph` (expand mechanism/target evidence), `paper_summarize`
(per-paper digest), `paper_find_oa_pdf` + `paper_download_oa_pdf` (pull OA full text where legal).

**Example:**
- `paper_resolve("Why Most Published Research Findings Are False")` to confirm a methodology caveat, then
  for the mechanism papers: `paper_batch_resolve([...DOIs...])` → access table, `paper_citation_graph` per
  key DOI to surface follow-up studies, and `paper_summarize` on each to extract the target/mechanism claim.

**Expected output:** A cited evidence packet — seed papers + citation-expanded neighbors, each with access
category and OA link, structured mechanism/target claims, and any legally-downloaded OA PDFs (path + sha256).
The packet is the literature
bridge into the broader drug-discovery toolchain.

---

## Safety / access policy (restated)

(`paper_download_oa_pdf("https://sci-hub.se/...")` → PermissionError). When a paper is not legally
access control.
