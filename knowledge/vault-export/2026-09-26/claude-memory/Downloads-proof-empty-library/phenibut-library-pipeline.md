---
name: phenibut-library-pipeline
description: How the phenibut research library at proof_empty/_library is built and
  deduplicated
metadata:
  node_type: memory
  type: project
  originSessionId: 3fb11978-54f5-4f83-9ad7-c3f1b51436b9
permalink: main/claude-memory/downloads-proof-empty-library/phenibut-library-pipeline
---

User maintains a **phenibut / psychopharmacology research library** of DOI-named open-access PDFs at `C:\Users\Prekzursil\Downloads\proof_empty\_library` (filenames = DOI with `/`→`_`, e.g. `10.1002_dta.3547.pdf`). As of 2026-06-10 it holds ~378 PDFs.

Pipeline (scripts in `proof_empty\.phenibut_fetch\`): discover via **OpenAlex + Europe PMC + Crossref + arXiv** (phenibut synonyms incl. fenibut, β-phenyl-GABA, 4-amino-3-phenylbutyric acid, Noofen, Anvifen, фенибут) → relevance-filter to phenibut-FOCUSED (synonym in title/abstract; bare "phenyl-GABA" is ambiguous = other analogs) → resolve OA PDFs via **Unpaywall** + EuropePMC `fullTextPDF` → download + validate (PyMuPDF) → **dedup by normalized DOI key AND content sha256** against existing files.

Constraints: only legitimate OA (no sci-hub). Wiley/Elsevier OA PDFs are Cloudflare-bot-blocked (use the user's browser); python-requests gets challenged where `curl` passes. `phenibut_NOT_downloaded_wishlist.csv` lists focused papers with no free full text.

`academia_mcp` (IlyaGusev) is installed (Python 3.12) and registered user-scope — it covers arXiv/Semantic Scholar/etc but **cannot** access academia.edu.