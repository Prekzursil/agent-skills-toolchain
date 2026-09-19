# OWNER-ADJUDICATION-PACKET — CC-0023

**Built for CC-0023** · 58 algorithmically unresolvable option-id references
batched into 12 foundation questions (7 ref-bearing + 5 session policies).

Rules (from catalog + `_USER-PROMPTS.md` owner interaction):
- Ask **one foundation-level question at a time**.
- Each question carries recommendation, strongest tradeoff, default if unanswered.
- **Only a recorded owner answer with a timestamp counts as evidence.**
- Inferred / majority / most-likely / LLM classification → **DEFERRED + impact**.
- Do **not** silently rewrite ambiguous `M-NN` tokens.

Census: `command-center/option-id/CC-0023-UNRESOLVED-REFS.json`
Ledger: `command-center/option-id/OWNER-ADJUDICATION-LEDGER.json`

---

## 1. OQ-CC23-01 — Leave F-B-02 mention tokens in 17-DECISION-LOG.md untouched?

**Covers:** doc17-mentions (10 refs)

**Recommendation:** (a) Leave all 10 mention tokens verbatim; append-only REMEDIATED row (already done by CC-0022 for tense/namespace). Never blind-rewrite.

**Strongest tradeoff:** Rewriting mention tokens destroys the historical evidence of the collision claim itself.

**Default if unanswered:** DEFERRED: leave mentions untouched; no rewrite.

**Impact if DEFERRED:** 10 mention tokens stay ambiguous-looking to naive greps; CC-0021 use-vs-mention gate already excludes 17-DECISION-LOG paths.

---

## 2. OQ-CC23-02 — How should the 16 unsettled refs in 16-GRILL-QUEUE-PHASE2.md resolve?

**Covers:** doc16-unsettled (16 refs)

**Recommendation:** (b) Author of doc 16 maps each operational cite to option-universe-M or architecture-mech; finding-write-up mentions stay as mentions.

**Strongest tradeoff:** Batching saves owner time but a wrong namespace on an operational cite is silent data loss (LLM classifier: 86% accurate, 100% of errors = data loss).

**Default if unanswered:** DEFERRED: no rewrite of any doc-16 M-NN token.

**Impact if DEFERRED:** 16 refs remain algorithmically unresolved; downstream rewrite lanes must not touch doc 16.

---

## 3. OQ-CC23-03 — Which namespace do the 11 unsettled BLOCKS: fields in doc 18 mean?

**Covers:** doc18-blocks-unsettled (11 refs)

**Recommendation:** (b) Author of 18-OPEN-UNKNOWNS-AND-PROBES.md answers one BLOCKS: field at a time; do not infer from adjacent settled MECH-16/17.

**Strongest tradeoff:** Adjacency inference (M-16 settled MECH ⇒ nearby M-18 is MECH-18) is exactly the near-collision trap called out in OPTION-ID-RESOLUTION §7c.

**Default if unanswered:** DEFERRED: BLOCKS: fields stay bare M-NN.

**Impact if DEFERRED:** 11 blocker edges stay namespace-ambiguous; executors must not treat them as selected option IDs or MECH IDs.

---

## 4. OQ-CC23-04 — Which namespace for the 5 unsettled refs in 19-SUBSTANCE-AUDIT-OPTIONS.md?

**Covers:** doc19-unsettled (5 refs)

**Recommendation:** (b) Author of doc 19 maps each unsettled cite; apply only after timestamped answer.

**Strongest tradeoff:** Substance-audit prose mixes option and mechanism vocabulary; a wrong rewrite flips audit conclusions.

**Default if unanswered:** DEFERRED: no rewrite in doc 19 unsettled cites.

**Impact if DEFERRED:** 5 refs stay unresolved; substance-audit consumers must treat bare M-NN as ambiguous.

---

## 5. OQ-CC23-05 — Resolve the 2 unsettled refs in diagrams/07-option-dependency-map.md?

**Covers:** diagrams-unsettled (2 refs)

**Recommendation:** (a) Prefer option-universe-M when the diagram edge is an option dependency.

**Strongest tradeoff:** Diagram edges look option-like but may cite mechanisms.

**Default if unanswered:** DEFERRED: diagram tokens unchanged.

**Impact if DEFERRED:** 2 diagram refs remain ambiguous.

---

## 6. OQ-CC23-06 — Are wave1 REGISTER.md M-1/M-3 a fourth namespace (mission grades)?

**Covers:** wave1-mission-grades (2 refs)

**Recommendation:** (a) Yes — declare MG-1/MG-3 (or keep single-digit M-N as mission grades) distinct from family-M and MECH-.

**Strongest tradeoff:** Collapsing mission grades into family-M invents option cards that do not exist.

**Default if unanswered:** DEFERRED: leave M-1/M-3; do not rewrite to M-01/MECH-01.

**Impact if DEFERRED:** Fourth namespace stays undeclared in live prose; CC-0021 registry already declares MG-N provisionally from census.

---

## 7. OQ-CC23-07 — Confirm scratch _sa_*/_verify_*/_p1floor_* refs are out of scope?

**Covers:** scratch-tooling (12 refs)

**Recommendation:** (a) Out of scope — do not adjudicate scratch tooling tokens.

**Strongest tradeoff:** Ignoring scratch refs risks a later false 'fully resolved' claim.

**Default if unanswered:** DEFERRED: scratch tooling remains out of rewrite scope.

**Impact if DEFERRED:** 12 scratch refs stay unresolved and explicitly non-blocking.

---

## 8. OQ-CC23-08 — Standing rule for the M-18 near-collision (benchmark vs certification)?

**Covers:** session policy (0 direct refs)

**Recommendation:** (c) Never auto-resolve M-18; require an explicit author answer naming option M-18 (benchmark harness) or MECH-18 (certification harness).

**Strongest tradeoff:** Both readings are plausible in almost any sentence — mis-resolution produces no visible error.

**Default if unanswered:** DEFERRED: M-18 stays unresolved wherever bare.

**Impact if DEFERRED:** Near-collision remains the highest-risk ambiguous token.

---

## 9. OQ-CC23-09 — Default when the owner never answers a foundation question?

**Covers:** session policy (0 direct refs)

**Recommendation:** (a) Record DEFERRED + impact; continue independent work; never LLM-guess.

**Strongest tradeoff:** Deferred ambiguity slows executors vs inventing a wrong namespace.

**Default if unanswered:** DEFERRED applies to every unanswered ref (this question's own default).

**Impact if DEFERRED:** All unanswered refs stay DEFERRED — the honest blocked state.

---

## 10. OQ-CC23-10 — Ban LLM / majority / most-likely classification as settlement evidence?

**Covers:** session policy (0 direct refs)

**Recommendation:** (a) Ban. Only timestamped owner/author answers count.

**Strongest tradeoff:** Slower closure vs measured 86%-accurate classifier with 100% lossful errors.

**Default if unanswered:** Ban stands (catalog evidence_requirement).

**Impact if DEFERRED:** No classifier settlement path; packet stays owner-gated.

---

## 11. OQ-CC23-11 — Authorize any silent rewrite of ambiguous M-NN tokens without an answer?

**Covers:** session policy (0 direct refs)

**Recommendation:** (a) No. Zero unattributed id changes.

**Strongest tradeoff:** Cleaner docs vs irreversible namespace corruption.

**Default if unanswered:** No silent rewrites authorized.

**Impact if DEFERRED:** Source docs 16/18/19 keep bare tokens until answered.

---

## 12. OQ-CC23-12 — Where must every recorded answer be durable?

**Covers:** session policy (0 direct refs)

**Recommendation:** (a) OWNER-DECISIONS.md CC-0023 section + option-id/OWNER-ADJUDICATION-LEDGER.json.

**Strongest tradeoff:** Dual write vs single generated OWNER-DECISIONS overwrite risk.

**Default if unanswered:** Ledger + OWNER-DECISIONS section remain the durability targets.

**Impact if DEFERRED:** Durability paths stay declared; answers still absent.

---

## Answer sheet (empty until owner speaks)

| question | owner answer | answered_at |
|---|---|---|
| OQ-CC23-01 | — | — |
| OQ-CC23-02 | — | — |
| OQ-CC23-03 | — | — |
| OQ-CC23-04 | — | — |
| OQ-CC23-05 | — | — |
| OQ-CC23-06 | — | — |
| OQ-CC23-07 | — | — |
| OQ-CC23-08 | — | — |
| OQ-CC23-09 | — | — |
| OQ-CC23-10 | — | — |
| OQ-CC23-11 | — | — |
| OQ-CC23-12 | — | — |
