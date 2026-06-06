# Deep-Research Literature Workflow

A reusable, **lawful** end-to-end pipeline for evidence-grounded literature research. It takes a
research question, finds and resolves the relevant papers, classifies access **honestly**, downloads
only genuinely open-access PDFs, summarizes from legally-available metadata, walks the citation graph,
and feeds the resolved DOIs/entities into the ToolUniverse + RDKit + drug-discovery skills to produce
a documented, cited report.

The retrieval layer is the **Scholarly Access MCP** (code at
`C:/Users/Prekzursil/source/agent-skills-toolchain/tools/scholarly-access-mcp/`; its `README.md` is
the canonical contract). That server is the compliant replacement for a Sci-Hub MCP: it routes only to
legitimate open-access and rights-holder-entitled sources, and a hard policy gate (`policy.py`) makes
shadow-library / paywall-bypass retrieval impossible rather than merely discouraged.

> **Status note:** the MCP server is config-wired and loads at the next Claude Code restart. Nothing in
> this document has been verified in-session; the verification claims below ("22 offline policy tests +
> 10 live end-to-end checks pass; 8 tools listed over MCP stdio") are the server's own frozen test
> record, not a fresh in-session run.

---

## 1. When to use this workflow

- You need a thorough, **cited** literature review or topic deep-dive, not a single factoid.
- You want access classification you can trust (downloadable OA vs. read-only-on-publisher vs.
  paywalled) so a downstream report never mislabels a paywalled paper as "open access".
- You will hand the resolved DOIs / drug / target / disease entities to ToolUniverse, RDKit, or the
  drug-discovery skills for DDI / ADMET / target / mechanism work.
- You want a multi-agent (ultracode) loop to fan out resolution, adversarially verify access
  classification, and synthesize a final report.

For a single factoid, skip the pipeline and call `paper_resolve` (or `paper_access_status`) once.

---

## 2. The MCP tools this workflow uses

All retrieval goes through the eight Scholarly Access MCP tools (spec dot-name -> MCP underscore-name):

| spec | MCP tool | role in this workflow |
|---|---|---|
| `paper.resolve` | `paper_resolve(identifier)` | DOI/PMID/arXiv/title -> canonical metadata + normalized ids (doi, pmid, arxiv, openalex) + confidence |
| `paper.fetch_metadata` | `paper_fetch_metadata(identifier)` | adds abstract + references where legally available |
| `paper.find_oa_pdf` | `paper_find_oa_pdf(identifier or doi or arxiv)` | a legal OA PDF url (allowlisted host) + license + per-candidate evidence (including any DENIED shadow url) |
| `paper.access_status` | `paper_access_status(identifier or doi or arxiv)` | category + provenance: `oa_pdf`, `free_to_read_not_redistributable`, `subscription`, `unavailable`, `unknown` |
| `paper.citation_graph` | `paper_citation_graph(identifier or doi, limit)` | references + citing works from Semantic Scholar / OpenAlex |
| `paper.download_oa_pdf` | `paper_download_oa_pdf(url, dest_dir, filename, license, source)` | hard-gated download -> path + sha256 + bytes + license/source |
| `paper.summarize` | `paper_summarize(identifier or doi)` | structured digest from legally-available metadata/abstract (the agent writes the prose) |
| `paper.batch_resolve` | `paper_batch_resolve(identifiers[])` | table of access status + OA links + metadata + unresolved items |

Legitimate sources only: Crossref, OpenAlex, Unpaywall, Europe PMC, arXiv, Semantic Scholar (keyless),
CORE (keyed), DOAJ, PubMed/NCBI E-utilities, Zenodo, institutional repositories, OA publishers, and the
Elsevier entitled-fulltext API (valid key only). Keys are read by env-var **name** only
(`UNPAYWALL_EMAIL`, `CORE_API_KEY`, `NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` — keyless works —,
`ELSEVIER_API_KEY`); the server auto-loads `~/.tooluniverse/.env`, and the process environment wins.

---

## 3. End-to-end flow

1. **Frame the research question.** Disambiguate the subject (gene vs. drug vs. disease vs. CS topic),
   fix the scope, and write down what a "complete" answer must contain.
2. **Search / resolve seeds.** Turn the question into a seed set of identifiers (titles, DOIs, PMIDs,
   arXiv ids). Resolve them with `paper_resolve`, or resolve a whole list at once with
   `paper_batch_resolve` to get a status table plus the items that did not resolve.
3. **Lawful access check.** For each resolved paper call `paper_access_status`. Honor the category:
   - `oa_pdf` -> eligible for download in the next step.
   - `free_to_read_not_redistributable` -> **cite the landing page only; never circumvent.**
   - `subscription` -> cite metadata only.
   - `unavailable` / `unknown` -> record as such; do not fabricate a link.
4. **Find + download OA PDFs (where available).** For `oa_pdf` items, `paper_find_oa_pdf` returns an
   allowlisted url + license + per-candidate evidence (it surfaces any DENIED shadow url so you can see
   what was refused). Pass that exact url/license/source to `paper_download_oa_pdf`, which re-checks the
   host against the OA allowlist and verifies the bytes are a real `%PDF` before writing
   path + sha256 + bytes.
5. **Summarize.** `paper_summarize` returns a structured digest built only from legally-available
   metadata/abstract; the agent writes the actual prose from that digest (and from downloaded OA full
   text where present).
6. **Extract citations.** `paper_citation_graph` returns references + citing works (Semantic Scholar /
   OpenAlex). Feed high-signal neighbors back into step 2 to expand the corpus until coverage saturates.
7. **Feed entities into ToolUniverse / RDKit / drug-discovery skills.** The resolved DOIs and the drug
   / target / disease entities pulled from the corpus become inputs to DDI, ADMET, target, mechanism,
   and structure tools (section 6).
8. **Documented report.** Synthesize a cited report: claim -> evidence (DOI + access category + license
   + sha256 for downloaded PDFs) -> evidence grade. Mislabeling access is a defect; every paywalled or
   read-only source is cited, never bypassed.

### ASCII pipeline diagram

```
                         +-----------------------------+
                         |  (1) Research question      |
                         |      + disambiguation       |
                         +--------------+--------------+
                                        |
                                        v
                         +-----------------------------+
                         |  (2) Search / resolve seeds |
                         |  paper_resolve /            |
                         |  paper_batch_resolve        |
                         +--------------+--------------+
                                        |
                                        v
                         +-----------------------------+
                         |  (3) Lawful access check    |
                         |  paper_access_status        |
                         +------+-------+-------+-------+
                                |       |       |
              oa_pdf            |       |       |  free_to_read / subscription /
                                v       |       |  unavailable / unknown
            +---------------------------+--+    |
            | (4) paper_find_oa_pdf        |    |  (cite only; NO bypass)
            |     paper_download_oa_pdf    |    |
            |     -> path + sha256 + bytes |    |
            +--------------+---------------+    |
                           |                    |
                           +----------+---------+
                                      |
                                      v
                         +-----------------------------+
                         |  (5) paper_summarize        |
                         |  +  (6) paper_citation_graph|<--- expand corpus
                         |        references + citing  |     (loop to step 2)
                         +--------------+--------------+
                                        |
                                        v
                         +-----------------------------+
                         |  (7) DOIs / drug / target / |
                         |      disease entities ->    |
                         |  ToolUniverse + RDKit +     |
                         |  drug-discovery skills      |
                         |  (DDI / ADMET / target)     |
                         +--------------+--------------+
                                        |
                                        v
                         +-----------------------------+
                         |  (8) Documented cited report|
                         |  claim -> evidence (DOI +   |
                         |  access cat + license +     |
                         |  sha256) -> evidence grade  |
                         +-----------------------------+
```

---

## 4. How an ultracode multi-agent loop participates

The pipeline maps cleanly onto a fan-out / verify / synthesize loop:

- **Fan-out resolve & triage.** Split the seed identifier list across worker agents. Each worker calls
  `paper_resolve` / `paper_batch_resolve` + `paper_access_status` over its slice and returns a partial
  table (id, normalized ids, confidence, access category, provenance). This parallelizes the slowest
  network-bound step.
- **Adversarial verify of access classification.** A second, independent reviewer agent re-runs
  `paper_access_status` (and `paper_find_oa_pdf` evidence) on a sample of each worker's "oa_pdf" claims
  and challenges them: is the host actually on the OA allowlist? Did `find_oa_pdf` surface a DENIED
  shadow url that a worker wrongly treated as a hit? Any "oa_pdf" that cannot be independently
  reproduced is demoted to `unknown`. This is the key guard against a worker optimistically upgrading a
  `free_to_read_not_redistributable` or `subscription` paper to downloadable.
- **Download under the gate.** Only verified `oa_pdf` items proceed to `paper_download_oa_pdf`. The
  server's own `%PDF` + allowlist gate is the final backstop; an agent cannot talk it into fetching a
  pirate url (it raises `PermissionError`).
- **Synthesize.** A synthesizer agent merges the verified tables, calls `paper_summarize` +
  `paper_citation_graph` on the accepted corpus, expands neighbors, and writes the cited report. A
  completeness-critic pass checks the report against the step-1 "what a complete answer must contain"
  checklist before declaring done.

File-disjoint workers should use isolated worktrees or scoped writes so parallel agents do not
contaminate a shared output directory.

---

## 5. RDKit and the literature corpus

RDKit consumes the **chemical entities** surfaced by the corpus rather than the papers themselves:

- From summaries and metadata, extract compound names / SMILES / InChI / identifiers mentioned in the
  retrieved papers.
- Use RDKit to canonicalize structures, compute descriptors and fingerprints, check substructure /
  similarity across the compound set, and prepare ligands for the drug-discovery skills.
- Feed the canonical structures forward to ADMET prediction and docking/scoring steps, keeping each
  structure traceable back to its source DOI + access category so the final report can cite where a
  molecule came from.

---

## 6. How ToolUniverse consumes the findings

The resolved DOIs and extracted entities (drug, gene/protein target, disease) are the bridge into
ToolUniverse's 120+ biomedical tools and the matching skills:

- **DOIs / PMIDs -> deeper literature.** Hand the corpus to `tooluniverse-literature-deep-research` /
  `scientific-thinking-literature-review` for citation-network expansion and T1-T4 evidence grading that
  complements the access-classified corpus produced here.
- **Drug entities -> DDI.** Feed drug names/identifiers to `tooluniverse-drug-drug-interaction` to check
  interactions among the drugs discussed in the literature.
- **Compounds -> ADMET.** Feed RDKit-canonicalized structures to `tooluniverse-admet-prediction` for
  absorption/distribution/metabolism/excretion/toxicity profiles.
- **Target / disease entities -> target & mechanism.** Route gene/protein targets to
  `tooluniverse-target-research` / `tooluniverse-drug-target-validation` and mechanisms to
  `tooluniverse-drug-mechanism-research`, with disease associations via
  `tooluniverse-gene-disease-association`.
- **Back-reference.** Each ToolUniverse result is cited back to the originating DOI so the documented
  report keeps a clean chain from claim -> paper (with honest access category) -> tool output.

Every entity that enters ToolUniverse / RDKit traces to a paper whose access was classified honestly by
this pipeline — paywalled and read-only sources are cited, never bypassed, on the way in.

---

## 7. Concrete example run (real tested DOIs)

Research question: *"Map a small evidence base around reproducibility and a landmark ML architecture,
classify access honestly, download what is genuinely OA, and stage entities for downstream tools."*

1. **Resolve seeds** (tested invocations):
   - `paper_resolve("10.1371/journal.pmed.0020124")` -> resolved; title *"Why Most Published Research
     Findings Are False"*.
   - `paper_resolve("1706.03762")` -> resolved; arXiv *"Attention Is All You Need"*.
2. **Access check:**
   - `paper_access_status(doi="10.1371/journal.pone.0000308")` -> `oa_pdf` with a PLOS OA url.
   - `paper_access_status(doi="10.1056/NEJMoa2034577")` -> `subscription` /
     `free_to_read_not_redistributable`. **Not downloaded, no bypass — cite only.**
3. **Find + download an OA PDF:**
   - `paper_find_oa_pdf(arxiv="1706.03762")` -> allowlisted arXiv OA url + license, then
     `paper_download_oa_pdf(url=...)` -> ~2.1 MB PDF written with its sha256.
4. **Refusal proof (the lawful gate):**
   - `paper_download_oa_pdf("https://sci-hub.se/...")` -> **REFUSED (`PermissionError`)** — demonstrates
     the hard policy gate rejecting an off-allowlist / shadow url.
5. **Summarize + expand:** `paper_summarize` on the accepted items for structured digests, then
   `paper_citation_graph` on the arXiv paper to pull references + citing works and expand the corpus.
6. **Downstream staging:** the PLOS and arXiv DOIs (plus any drug/target/disease entities extracted from
   their abstracts) are handed to the ToolUniverse / RDKit / drug-discovery skills per sections 5-6; the
   NEJM paper is cited from metadata only.

---

## 8. Limitations

- Title resolution uses a similarity threshold; a too-vague title may be reported unresolved.
- `free_to_read_not_redistributable` items are intentionally **not** downloaded — open the landing page.
- Citation-graph depth depends on Semantic Scholar / OpenAlex coverage for a given DOI.
- A missing API key means that source is skipped (never an error), so OA discovery is best-effort across
  the configured sources.

---

## 9. Safety / access policy (hard, enforced — not advisory)

Enforced in `policy.py`, not merely documented:

- **No** Sci-Hub / LibGen / SciDownl / scihub.py / shadow library / mirror scraping, ever.
- **No** paywall bypass; **no** fake "open access" classification; **no** silent fallback to
  unauthorized sources.
- `paper_download_oa_pdf` only fetches a url whose host is on the OA allowlist **and** whose bytes are a
  real `%PDF`; anything else is refused with `PermissionError`.
- Access categories are honest: `oa_pdf` = downloadable OA at a legit source; `free_to_read_not_
  redistributable` = readable on a publisher/PMC page but not legally fetchable (cite, do not
  circumvent); `subscription` = paywalled (cite only); `unavailable` = no legit full text;
  `unknown` = could not determine.

---

## 10. Tested invocation block

```text
# Resolve (tested)
paper_resolve("10.1371/journal.pmed.0020124")   # -> "Why Most Published Research Findings Are False"
paper_resolve("1706.03762")                      # -> arXiv "Attention Is All You Need"

# Honest access classification (tested)
paper_access_status(doi="10.1371/journal.pone.0000308")  # -> oa_pdf, PLOS OA url
paper_access_status(doi="10.1056/NEJMoa2034577")         # -> subscription / free_to_read_not_redistributable (NOT downloaded)

# Find + download a genuine OA PDF (tested)
paper_find_oa_pdf(arxiv="1706.03762")            # -> allowlisted OA url + license
paper_download_oa_pdf(url=...)                    # -> ~2.1 MB PDF + sha256

# Lawful-gate refusal (tested)
paper_download_oa_pdf("https://sci-hub.se/...")  # -> REFUSED (PermissionError)
```

Frozen test record for the server (not an in-session run): 22 offline policy tests + 10 live
end-to-end checks pass; 8 tools listed over MCP stdio. The server is config-wired and loads at the
next Claude Code restart.
