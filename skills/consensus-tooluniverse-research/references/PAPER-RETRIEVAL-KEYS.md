# Paper-Retrieval API Keys — what to add, what it unlocks, where it goes

**Problem this solves:** the first harvest auto-downloaded **125 / 345 open-access PDFs**; **220 were
OA-but-bot-walled** (publisher Cloudflare 403s) and the keyless EuropePMC-XML fallback captured 0. API keys
to OA-aggregator and rate-limited services let a **keyed v2 downloader** recover a large share of those 220
**without ever touching paywalls** (OA-only discipline is unchanged).

## Where keys go (secure — never in chat, never committed)
- **ToolUniverse keys** → `C:\Users\Prekzursil\.tooluniverse\.env` (this path is gitignored by TU's design).
- **Pipeline keys** (CORE/Semantic Scholar/NCBI for the downloader) → the same `.env`, or the workspace
  `.env` (already in `.gitignore`). The scripts read them from the environment; absent keys are skipped
  gracefully (no crash, just lower yield).
- Format: `KEY_NAME=value`, one per line. Tell me only the **names** you added, not the values.

## Ranked by impact on "get the 220 blocked papers"

| Rank | Service | env var | Unlocks | Free? / where |
|---|---|---|---|---|
| 1 | **CORE** | `CORE_API_KEY` | Largest OA aggregator (300M+); a **download API** that serves repository copies publishers bot-wall. Biggest single recovery of the 220. | Free — register at core.ac.uk/services/api |
| 2 | **Semantic Scholar** | `SEMANTIC_SCHOLAR_API_KEY` | `openAccessPdf` URLs + lifts the keyless 403/429 throttle (it powers Consensus itself). | Free — request at semanticscholar.org/product/api |
| 3 | **NCBI / Entrez** | `NCBI_API_KEY` | 3→10 req/s to PubMed/PMC; makes the PMC-OA-package PDF route reliable + **fixes the XML fallback**. | Free — NCBI account → API key |
| 4 | **Unpaywall** | `UNPAYWALL_EMAIL` | OA discovery (already used — just your email). | Free (email) — already set |

## Also valuable (beyond raw downloading)

| Service | env var | Unlocks |
|---|---|---|
| **OpenAI** *or* **Azure OpenAI** | `OPENAI_API_KEY` / `AZURE_OPENAI_API_KEY` | ToolUniverse **agentic** tools: `advanced_literature_search_agent` (12+ DBs in one call), `Tool_Finder` (semantic tool search), output-summarization hooks. |
| **scite** | `SCITE_API_KEY` | Citation **stance** (`scite_get_tallies`: supporting / contrasting / mentioning) — the verify-against-primary-sources step. |
| **Gemini** / **OpenRouter** | `GEMINI_API_KEY` / `OPENROUTER_API_KEY` | Alternative LLM providers for the agentic tools. |
| **FDA** | `FDA_API_KEY` | Higher openFDA rate (adverse events, labels) — overdose/pharmacovigilance work. |
| **UMLS** | `UMLS_API_KEY` | Medical terminology normalization. |
| **BioGRID**, **HuggingFace** | `BIOGRID_API_KEY`, `HF_TOKEN` | Interactions DB; HF-hosted TU tool packs / embedding search. |

## NOT needed / out of scope
- **Sci-Hub / LibGen / any paywall bypass** — never. "Available" = legally open-access.
- **Elsevier / Wiley / Springer TDM keys** — only if you have *institutional entitlement*; they grant
  text-mining of *subscribed* content, which is access-dependent and not OA. Skip unless you specifically
  have an institutional account; OA-only discipline still applies.

## What I'll do once the keys are in `.env`
1. Build `resolve_and_download_v2.py` — adds **CORE** + **Semantic Scholar `openAccessPdf`** + **NCBI-keyed
   PMC/Entrez** download tiers, and fixes the EuropePMC-XML bug, all reading keys from env.
2. Re-run **only the 220 blocked** papers (resumable — clears `downloaded:"blocked"` and retries them).
3. Report the new funnel; fold the keyed tiers + this doc into the `consensus-tooluniverse-research` skill.

## Runtime notes (2026-06-06 — what actually worked)
**Configured** (in `~/.tooluniverse/.env` AND machine-wide Windows env, all users, no rotation):
UNPAYWALL_EMAIL · CORE_API_KEY · ELSEVIER_API_KEY · DOAJ_ID/DOAJ_API_KEY · ZENODO_TOKEN ·
SPRINGER_API_KEY (+SPRINGER_META_API_KEY) · SEMANTIC_SCHOLAR_API_KEY · NCBI_API_KEY · FDA_API_KEY · UMLS_API_KEY.

- **Elsevier** ✅ — biggest contributor; entitled full-text PDFs via `api.elsevier.com/content/article/doi/<DOI>` (`X-ELS-APIKey`, `Accept: application/pdf`).
- **CORE** ✅ — works; thin for very recent psych/med papers (`downloadUrl` often null).
- **Semantic Scholar** ⚠️ — the provided **key returns 403** (invalid/inactive); the **keyless** endpoint returns 200 with `openAccessPdf`, so SS runs **keyless** (lower rate, 1.1s spacing). Re-issue the key if you want higher throughput.
- **Springer** ✅ — valid, but the OA API only covers **Springer/Nature** journals (`10.1007`/`10.1038`/`10.1186`); non-Springer DOIs correctly return no OA record.
- **NCBI** — keys the PMC OA-package route. **FDA/UMLS** — domain tools (overdose/terminology), read by ToolUniverse as `FDA_API_KEY`/`UMLS_API_KEY`.
- Pipeline today = `resolve_and_download.py` (v1 keyless) + `resolve_and_download_v2.py` (CORE/Elsevier/Zenodo/DOAJ) + `resolve_v3_extra_sources.py` (SS-keyless/Springer/NCBI-PMC). Optional cleanup: merge into one `resolve_keyed.py`.
