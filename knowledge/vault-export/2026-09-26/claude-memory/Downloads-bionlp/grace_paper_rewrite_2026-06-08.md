---
name: grace-paper-rewrite-2026-06-08
description: GRACE main.pdf was fabricated vs real system; rewriting .tex to the true
  arithmetic 9-model ensemble. Ground-truth numbers + task state.
metadata:
  node_type: memory
  type: project
  originSessionId: 7d868df4-f868-4a58-acac-c022173b11b4
permalink: main/claude-memory/downloads-bionlp/grace-paper-rewrite-2026-06-08
---

GRACE @ IberLEF 2026 Track 1 paper task (started 2026-06-08). User asked to "improve/perfectionize `FINAL/main.pdf` with strict rigidity (ultracode)".

**Discovery:** `main.pdf` (Jun 8, no .tex source in repo) describes a system that DOES NOT EXIST in the code/data — a *geometric* 4-model role-based ensemble (Anchor/Specialist/Logic/Generalist), focal loss, SWA, multi-sample dropout, Optuna sweeps, bootstrap tests, dev F1 **0.8193**/0.7874, MajorClaim 0.6250, 4-class macro incl. None. Cross-checked against `modal_ensemble.py`, `modal_sweep.py`, `ensemble_results.json`, and the user's own `report/report_data.json` (the source the truthful DOCX/PPTX were built from) — all four agree and contradict the PDF. User confirmed (AskUserQuestion): **rewrite the paper to the REAL system**; reconstruct `.tex` from the PDF (no LaTeX locally → user compiles on Overleaf CEUR template); **drop the other-team standings table**.

**REAL SYSTEM (ground truth — every number reproducible from `FINAL/`):**
- 9 encoders × 3 seeds (42/100/2026) = 27 runs on Modal **A10G**; torch 2.4.1 / transformers 4.48.0.
- Sentence-level 4-class (None/Premise/Claim/MajorClaim); input `prev_sentence [SEP] sentence`; spaCy `es_core_news_sm`; **max_len 192 (uniform)**; batch 16.
- Loss = **weighted CE** (inverse-freq weights, MajorClaim weight forced **10.0**) — NOT focal. AdamW wd 0.05, dual LR (body 1e-5 / head 1e-4), cosine + 100 warmup, label smoothing 0.15.
- Two-stage: P1 ≤15 epochs + early-stop patience 4 → best epoch on dev; P2 full-fit train+dev (best+1 epochs) → blind logits.
- Decode: argmax then override to MajorClaim if `p[MajorClaim] > 0.50` (the ONLY real post-processing).
- Fusion = **arithmetic mean of softmax probs** across models & seeds (NOT geometric, no weights). Configs: greedy-4 0.7426, top3 0.7416, **all9 0.7434 (SUBMITTED, zero-peek)**. Best single mDeBERTa-v3 0.7046 (+3.9 pts).
- Metric = **3-class strict macro-F1** (Premise/Claim/MajorClaim) via exact-span official scorer; NO None class.

**Dataset (real):** train 350 docs (Premise 1536/Claim 666/MajorClaim 64 = 2266 ents); dev 50 docs (218/99/9 = 326 ents, 705 sentences); blind 2474 docs / 26640 sentences. all9 dev per-class: Premise F1 0.9095, Claim 0.8500, MajorClaim 0.4706 (P.50/R.444, tp4/fp4/fn5). Blind all9 submission: 11752 entities (Premise 7872/Claim 3717/MajorClaim 163), 0 offset mismatches.

**Official TEST 36.83 (Subtask-1) is NOT in any repo file** — only in main.pdf + external leaderboard. Report headline = dev **0.743**. Flag 36.83 + rank (PDF claims 4th overall/2nd Subtask-1) for user to confirm vs official site. 13 real figures in `FINAL/report/figures/`. Authoritative facts: `FINAL/paper/FACTS.md`. See [[grace_kaggle_workflow]].

**DONE (2026-06-08):** Rewrote → `FINAL/paper/main.tex` (CEUR ceurart) + `references.bib` (13 real refs) + 4 figures. Verified by a 5-lens adversarial workflow (numbers/fabrication/consistency/latex/quality) → all numbers accurate, fix list applied. Compiled locally with **tectonic** (`scoop install tectonic`); needed 2 local build aids in `paper/`: patched `ceurart.cls` (skips pdfx — XeTeX can't) + stub `fontawesome5.sty` (XeTeX OTF crash) + `$env:SOURCE_DATE_EPOCH`. Corrected 6-page PDF now replaces `FINAL/main.pdf` (643KB). **Overleaf camera-ready:** upload ONLY main.tex+references.bib+figures/ to CEUR template (NOT the patched cls/stub). **Still TODO for user:** real author names (placeholders in main.tex ~L24-26); confirm 36.83+rank vs official site.