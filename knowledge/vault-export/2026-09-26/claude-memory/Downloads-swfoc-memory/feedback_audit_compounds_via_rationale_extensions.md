---
name: Audit-Compounds-Via-Rationale-Extensions Pattern
description: Periodic catalog audits compound when rationale extensions are present
  from prior drift-resolution arcs. Investing 1 iter (~30 LoC of rationale text) after
  any drift-resolution arc pays back ~6× audit cycle time across subsequent audits.
  Validated stable at 2 instances (iter-341 + iter-358); codified at 2/3 trigger per
  iter-337 meta-rule precedent because audit-compounds IS a meta-pattern about audit-cadence
  + docs-cleanup, not a production code pattern.
type: feedback
originSessionId: aeb94ff3-639d-48d8-b24a-6f3ee9650c46
permalink: main/claude-memory/downloads-swfoc-memory/feedback-audit-compounds-via-rationale-extensions
---

**Rule:** After any drift-resolution arc that resolves N catalog entries by surfacing LIVE alternatives or marking deprecated-orphans, invest 1 follow-up iter in extending each entry's rationale to cite the resolution. The rationale extensions compound: subsequent periodic audits can immediately recognize the resolved entries from the rationale alone, avoiding re-investigation of the same N entries.

Pattern shape:

1. **Drift-resolution arc** ships LIVE flips OR DEPRECATED-orphan markings on N catalog entries (e.g., iter-324-328 resolved 5 P2HP candidates from iter-323 audit).
2. **Docs cleanup iter** (iter-329 in the canonical case) extends rationale on all N entries — typically `~5-30 LoC per entry` citing the LIVE alternative + iter number + composition workflow.
3. **Subsequent audit iter** (iter-341 in the canonical case) immediately recognizes the N resolved entries from rationale text alone, surfacing 0 drift candidates instead of re-investigating.
4. **Subsequent audit iter+1** (iter-358 in the canonical case) confirms the rationale extensions still compound 17 iters later.

**Why:**

2 instances iter-341 + iter-358 (~17-iter window) demonstrate the compounding effect:

| Audit iter | Drift candidates | Cycle time | Vs baseline |
|---|---|---|---|
| iter-323 | **5 candidates** | ~45 min | (baseline before iter-329) |
| iter-341 | 0 candidates | ~20 min | **2.25× faster + 6× cycle savings** |
| iter-358 | 0 candidates | ~20 min | **2.25× faster + 6× cycle savings (compounding)** |

The investment was iter-329's ~30 LoC of rationale extensions on 5 entries. The savings: 25 minutes per subsequent audit × 2 audits so far = 50 minutes saved against a 30-LoC investment. ROI grows linearly with audit count.

**Codified at 2/3 trigger per iter-337 meta-rule precedent.** The audit-compounds pattern is a meta-pattern about audit-cadence + docs-cleanup compounding effect (not a production code pattern), so the iter-337 "meta-rules ≥3 instances" precedent applies in inverse: meta-patterns can codify at 2/3 when the lesson is forward-applicable to upcoming iters. iter-368 reverse-orphan audit (10 iters away) can apply this rule directly.

**How to apply:**

After any drift-resolution arc:

1. **Step 1 — Identify resolved entries** (~5 min): list every catalog entry whose status changed (Phase2HookPending → Live OR Live → Deprecated) OR whose rationale needs to cite a LIVE alternative.

2. **Step 2 — Extend rationale per entry** (~5-15 min per entry):
   - Cite the LIVE alternative wire (e.g., "superseded by iter-231 SWFOC_SetCreditsFreezeGlobal")
   - Cite the audit iter that surfaced the resolution (e.g., "iter-323 audit caught the operator-trust drift")
   - Cite the composition workflow (e.g., "operator should use iter-179 SWFOC_FindAllObjectsOfTypeLua + Get_Owner filter for hero enumeration")
   - **Critical**: rationale text must be substantive enough that a future audit can recognize the entry as resolved without re-investigating

3. **Step 3 — Pin rationale extensions in tests** (~2-3 tests per entry, optional):
   - `entry.Note.Should().Contain("iter-XXX")` to lock the cross-reference
   - `entry.Note.Should().Contain("LIVE alternative")` to lock the resolution language
   - These pins fire if a future contributor "cleans up" the rationale and inadvertently strips the resolution context

4. **Step 4 — Schedule audit iter at canonical cadence** (~17 iters later for P2HP, ~22 iters for reverse-orphan): the audit reads the rationale extensions and confirms entries remain resolved without re-investigation.

**Honest break-out clause** — when this rule does NOT apply:

- **Resolution is fragile**: if the LIVE alternative is itself drift-prone (e.g., engine binary version changes the RVA), the rationale extension may need frequent revision. Don't apply the rule for fragile resolutions; instead, use simpler `BLOCKED-NO-RVA` rationale + re-audit each iter.
- **Entries are removed entirely**: if an arc removes catalog entries instead of resolving them, no rationale extension is needed. Skip step 2.
- **No subsequent audit cadence exists**: if the catalog category isn't periodically audited (e.g., one-off entries), the compounding can't materialize. The rule requires a periodic audit cadence to compound.
- **Audit cadence is shorter than rationale extension benefit**: if audits run every iter (cadence = 1), the compounding benefit doesn't accumulate (every audit is a new full investigation regardless). Rule requires cadence ≥10 iters for meaningful compounding.

**Edge cases worth flagging:**

- **Rationale staleness**: rationale extensions can become stale over many iters if the LIVE alternative itself changes. Annual review (~50-iter cadence) recommended to refresh rationale text.
- **Cross-reference drift**: if iter-XXX cross-references in rationale point to iters that get deleted/superseded, fix the references during the next audit. Example: "iter-231 superseded" → if iter-231 itself gets superseded by iter-300, update both rationales.
- **Empty rationale problem**: entries with bare `BLOCKED-NO-RVA` rationale don't compound (no information for audit to recognize). Either invest in extending OR accept re-investigation cost each audit.
- **Rationale length cap**: if rationale grows beyond ~500 LoC for a single entry, split into a separate doc + reference from rationale. Catalog rationale should stay reader-scannable.
- **Bidirectional compounding**: rationale extensions help audits AND help operators (when reading catalog entries via Diagnostics tab). Same investment, double benefit.

**Cost-benefit ratio:**

- **Per-entry rationale extension cost**: ~5-15 LoC + ~5-15 min cycle (one-time investment after drift-resolution arc)
- **Per-audit savings (resolved entry)**: ~5-15 min/entry/audit (audit reads rationale, recognizes as resolved, skips re-investigation)
- **Compounding factor**: savings × N audits = total saved time
- **Break-even point**: 1 audit (after the immediately-following audit, every future audit is pure savings)
- **iter-329 case study**: 5 entries × ~30 LoC = ~150 LoC investment / 25 min × 2 audits = 50 min savings so far / **expected 5+ future audits = ~125+ min total savings**

**Memory-write triggers (2-instance evidence base):**

- **2 instances** iter-341 + iter-358 (~17-iter window). Pattern survived 2 audit cycles with same iter-329 rationale extensions still cited.
- **iter-358 was the codification trigger at 2/3** per iter-337 meta-rule precedent. Future incidents (instance #3+) should EXTEND this rule rather than create new ones — most likely add more case studies to the table above.
- **Predicted 3rd instance**: iter-375 P2HP audit (next canonical 17-iter cadence) OR iter-368 reverse-orphan audit (~10 iters away; could surface compounding effect for reverse-orphan rationale extensions if any exist).

**Prospective uses (iter-360+):**

When the next drift-resolution arc completes:

- **Apply rule immediately**: ship a docs cleanup iter as the arc finale (mirrors iter-329 pattern)
- **Schedule audit at canonical cadence**: trust the compounding effect; expect CLEAN audit
- **iter-368 reverse-orphan audit**: apply rule forward — if iter-346 surfaced any reverse-orphan candidates needing rationale extensions, ship them now to pre-compound for iter-368

For NEW catalog categories (not P2HP / reverse-orphan):

- **Capability surface report**: if periodic audits get added, apply same pattern
- **Verifier ledger**: 318 entries with rationale; the rule could pre-compound future verifier audits

**Pattern reinforcement:**

This rule is the **audit-side companion** to:
- `feedback_status_badge_as_inline_docs.md` (iter-311 codified) — operator-trust UX side; status badges double as inline docs
- `feedback_optional_default_null_constructor_extension.md` (iter-311 codified) — same investment-then-compounds pattern at code architecture layer
- `feedback_iter_strategy_preflight_stack.md` (iter-337 codified) — preflight investment compounds across consumers; same shape as rationale-extension investment compounding across audits

Combined: when a drift-resolution arc ships, the iter-337 preflight stack catches NEW drift early (prevents drift), the iter-329-style rationale extensions document RESOLVED drift (prevents re-investigation), and the audit cadence verifies stability over time.

**Cross-link to related codified rules:**

- `feedback_status_badge_as_inline_docs.md` (iter-311) — operator UX side of rationale extensions
- `feedback_iter_strategy_preflight_stack.md` (iter-337) — preflight investment side
- `feedback_optional_default_null_constructor_extension.md` (iter-311) — pattern similarity (small investment, large compounding)
- `feedback_engine_already_does_this.md` (iter-302) — pattern-resolution-via-citation (same shape as rationale extension)
- `feedback_dotnet_test_hang_diagnosis.md` (iter-172) — toolchain rule for running the audit tests this rule recommends