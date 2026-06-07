---
name: biomedical-paper-triage
---

# Biomedical Paper Triage

Turn a raw list of biomedical papers (DOIs, PMIDs, arXiv ids, or titles) into a defensible, ranked shortlist. Pairs with the `consensus-tooluniverse-research` evidence-grading scheme (T1-T4 x human / animal / in-vitro) so the shortlist carries both a triage rank and an evidence tier.

## When to use

- You ran a search (PubMed, Consensus, a colleague's bibliography) and got back 20-200 candidate papers and need to decide which 10-20 to actually read.
- You must justify inclusion/exclusion for a mini-review or grant background and want recency, study-type, citation-signal, and access reasons recorded per paper.
- You want to avoid wasting time queuing papers that turn out to be paywalled, retracted, or non-redistributable.
- You need an access-honest list to hand to the `consensus-tooluniverse-research` workflow for evidence grading and download.

## The MCP tools it uses

It primarily uses three tools (spec dot-name -> MCP underscore-name):

- `paper.batch_resolve` -> `paper_batch_resolve(identifiers[])` : resolve a whole list at once into a table of canonical metadata, normalized ids (doi, pmid, arxiv, openalex), access status, OA links, and a list of unresolved items. This is the workhorse for the first pass.
- `paper.access_status` -> `paper_access_status(identifier|doi|arxiv)` : confirm or refine the honest access category for a single paper when the batch result is `unknown` or you need provenance.
- `paper.citation_graph` -> `paper_citation_graph(identifier|doi, limit)` : pull references and citing works from Semantic Scholar / OpenAlex to derive a citation signal and to discover high-impact neighbors worth adding to the pool.

Supporting tools when you need them: `paper.resolve` (single id sanity check), `paper.fetch_metadata` (abstract + references for closer study-type reading), `paper.find_oa_pdf` and `paper.download_oa_pdf` (only after triage, only for `oa_pdf` items at allowlisted hosts), and `paper.summarize` (structured digest from legally-available metadata).

## Access categories (honest)

- `oa_pdf` : downloadable OA at a legit source.
- `subscription` : paywalled. Cite only.
- `unavailable` : no available full text exists.
- `unknown` : access could not be determined; run `paper_access_status` to refine.

## Workflow steps

1. Gather the candidate identifiers into a single list (DOIs, PMIDs, arXiv ids, or titles). Deduplicate obvious repeats.
2. Run `paper_batch_resolve(identifiers)` to get one table: canonical title, year, normalized ids, access status, OA link, and the unresolved set.
3. For any item with status `unknown`, call `paper_access_status` on its best id to get an honest category and provenance. Triage unresolved items separately (often title typos or non-indexed preprints).
4. Derive a citation signal: for the top candidates by relevance/recency, call `paper_citation_graph(doi, limit)` and record citing-work count plus any high-impact neighbors that should join the pool.
5. Infer study type from metadata/abstract (`paper_fetch_metadata` when the title is ambiguous) and map it to an evidence tier using the paired `consensus-tooluniverse-research` T1-T4 x human / animal / in-vitro scheme (e.g. RCT / systematic review = higher human-tier; cell-line only = in-vitro tier).
6. Score and rank each paper across five axes: relevance to the question, recency, study-type strength, citation signal, and availability. Keep availability as a tag, not a hard filter, unless the user wants only readable papers.
7. Produce the ranked, access-tagged shortlist (rank, title, year, ids, study type, evidence tier, citation signal, access category, one-line reason). Hand `oa_pdf` items to download only after the shortlist is approved.

## Concrete examples

- Resolve a known landmark: `paper_resolve("10.1371/journal.pmed.0020124")` returns the resolved record titled "Why Most Published Research Findings Are False".
- Confirm openly downloadable: `paper_access_status(doi="10.1371/journal.pone.0000308")` returns `oa_pdf` with a PLOS OA url, so this paper sits high on the availability axis.
- Citation neighbors: `paper_citation_graph(doi="10.1371/journal.pmed.0020124", limit=25)` returns references and citing works to compute citation signal and surface high-impact additions.

## Limitations

- Triage scores are heuristic; a low rank is a reading-priority signal, not a quality verdict. A human reviews the final shortlist.
- Citation counts depend on Semantic Scholar / OpenAlex coverage and lag for very recent or niche work.
- Study-type inference from titles/abstracts can be wrong; verify before assigning a high evidence tier.
- `unknown` and `unavailable` items are surfaced, not silently dropped; decide their fate explicitly.

## Tested invocation

```
paper_batch_resolve(["10.1371/journal.pmed.0020124", "10.1371/journal.pone.0000308", "10.1056/NEJMoa2034577"])
# -> table: each id resolved with canonical title, normalized ids, and access status
#    (PLOS Medicine + PLOS ONE = oa_pdf; NEJM = subscription / free_to_read_not_redistributable)

paper_access_status(doi="10.1371/journal.pone.0000308")
# -> { category: "oa_pdf", oa_url: "<PLOS OA url>", provenance: ... }

paper_citation_graph(doi="10.1371/journal.pmed.0020124", limit=25)
# -> references + citing works for the citation-signal axis
```
