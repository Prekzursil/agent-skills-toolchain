---
title: ChatGPT-Pro deep-research reply verified + prompt/dossier updated (2026-07-11)
type: note
permalink: main/phenibut/verifications/chat-gpt-pro-deep-research-reply-verified-prompt-dossier-updated-2026-07-11
tags:
- verification
- phenibut
- chatgpt-deep-research
- high-confidence
- citations
---

Adversarial verification (workflow wf_d463c3ee, 7 agents) of a ChatGPT-Pro Deep-Research reply run on the PRE-rewrite `CHATGPT_PRO_PROMPT.md`.

## Verdict
- **Citation integrity: excellent.** All ~25 load-bearing citations resolved to real papers/records — **0 hallucinated DOIs/PMIDs**.
- **One misattribution:** the reply pinned S/R α2δ Ki 39/23 µM + neuropathic-pain (CCI) data to **Dambrova 2008 (PMID 18275958)**; those are actually **Zvejniece 2015 (PMID 26234470)**. Dambrova 2008 = GABA-B binding (R=92, racemate=177 µM) + acute tail-flick, with S **inactive**. (Dossier §11 already flags this Dambrova/anchor confusion.)
- **Novelty thin:** only **2 of 23 venues** were genuinely new; all 4 "corrections" were already the program's stated position. The run also **could not read its attachments** (literature+reasoning, not corpus-grounded).

## Verified new facts folded into the program
- **GABA-B heterotetramer negative allostery** — Shen 2026, Nat Commun `10.1038/s41467-026-70640-8`, PMID 41862465 (PMC13168656). Native neuronal GABA-B is a hetero-*tetramer*; one heterodimer asymmetrically restrains the other. → treat the **tetramer, not the isolated heterodimer**, as the receptor unit for active-state MD (N2) and the FEP-vs-Ki reconciliation. Added to `PROGRAM_DOSSIER.md` §9 + `CHATGPT_PRO_PROMPT.md`.
- **2 new backlog venues** (`PROGRAM_DOSSIER.md` §8): (1) proteome-wide target/transport deconvolution (TPP/CETSA + transportome CRISPR); (2) GABA-B mechanosensitivity/membrane-state dependence (Huo 2025, Nat Commun `10.1038/s41467-025-64811-2`, GABA-independent mechanical activation).
- **Cerebellar sc-eQTL instruments** for the deferred CACNA2D2→anxiety colocalisation: Castonguay 2026 cerebellar single-cell cis-eQTL atlas (Nat Genet `10.1038/s41588-026-02544-8`; Zenodo `10.5281/zenodo.17102593`) + SingleBrain (`10.1038/s41588-026-02541-x`). Both verified real.

## Public-DB status (VERIFIED, corrects "phenibut absent from public DBs")
- ChEMBL: racemate **CHEMBL315818** (ATC N06BX22; 41 activity rows, all unmapped HTS/AC50, no single-protein target); R-phenibut **CHEMBL53073** (stereo-defined, InChIKey `DAFOCGYVTAOKAJ-VIFPVBQESA-N`). BindingDB R-phenibut `50007119`.
- Absent from BindingDB (racemate CID 14113 has no BindingDB xref) and IUPHAR/GtoPdb (API 404; baclofen present as control). So "no curated single-protein target affinity in public DBs" holds; the "absent from ChEMBL" wording is the error.

## Prompt + upload bundle
- `docs/CHATGPT_PRO_PROMPT.md` was **rewritten 2026-07-11** (not by me) into a self-contained job: 15-file attachment manifest + readability gate, source-integrity/instruction firewall, evidence-lane authority order, novelty gate; embeds the corrected baseline. Verified accurate. Updated it with the heterotetramer constraint + an "already-adopted venues" novelty-gate exclusion.
- Upload bundle built: `Downloads/phenibut_chatgpt_upload_2026-07-11.zip` — 15 core files + EN manuscript PDF + manifest. `AI_CONVERSATIONS_CORPUS.md` assembled = exactly 85 SOURCE blocks (59 ChatGPT + 26 Gemini).

Relates to [[phenibut-affinity-anchors-verified-zvejniece-2015-not-volgograd]] and the causal-genetics cis-MR extension (0/36 causal).