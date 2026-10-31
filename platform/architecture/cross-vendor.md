---
title: cross-vendor
type: note
permalink: dqverify-repo-20261013/platform/architecture/cross-vendor
---

# Architecture Candidate: Cross-Vendor Adapter

Phase 3 tournament entry. Advocate: `tournament/cross-vendor`. Spec:
`_USER-PROMPTS.md:10775` ("cross-vendor adapter architecture").

**This architecture discards nothing from Wave 1.** Measured ledger: **418 files reused
unchanged** (9 schemas, 117 councilspecs, 233 substrate shims, 7 registry files, 51 lib
modules, the catalog), **2 files modified additively** (no field removed, no behaviour
narrowed), **10 new files**, **0 files deleted**. It is the only tournament entry whose
premise is that Wave 1 already *designed* this architecture and simply cannot execute it:
vendor identity is a first-class declared field in all three Wave 1 control planes and
**zero of it is executable**.

## Provenance and measurement scope

| item | value |
|---|---|
| HEAD measured | `833fb1ea0886a87a562be539a02839f8c6e6a6e4` |
| brief pinned | `dc90d64a` — is an **ancestor** of HEAD (verified `git merge-base --is-ancestor`), 2 commits behind |
| probes | `_probe_crossvendor_groundtruth.py`, `_probe_crossvendor_adapter_absence.py`, `_probe_crossvendor_alias_hole.py`, `_probe_crossvendor_demand_supply.py` (all in this directory) |

Two brief figures re-measured and **corrected**: the brief says *8 schemas* — disk has **9**
(`platform/schema/*.schema.json`; the substrate sibling added
`artifact-class-profiles.schema.json`). The brief says *"128 non-canonical
`assigned_model_vendor_role` shapes"* — CONFIRMED, and now characterised: the 128 are the
**legacy string form** `model/vendor/role`; the other 1,879 are the canonical **dict**
`{vendor, model, role}` (+ `basis` on 320, `rationale` on 128). My first canonicality
regex (`vendor/model:role`) matched 0/2007 — that was **my detector being wrong about the
canonical shape**, not a finding, and is recorded here so it is not cited as one.

Prior design consumed, not redesigned: doc 13 `A8` is titled "CROSS-VENDOR CAPABILITY-GRAPH"
but its body is a **build-time discovery index** carrying `OWNER-DECISION: no`
(`13-ARCHITECTURE-CANDIDATES.md:694-762`). A8 is **not** the spec's cross-vendor adapter, and
this entry does not propose it. The mechanisms that *are* this architecture are **MECH-16**
(vendor-neutral SSOT, `:1138`) and **MECH-30** (cross-vendor verification lane, `:1258`,
`route WRAP · size CONFIG · EV high · correctness high · effort S`). MECH-30's own risk note
is adopted verbatim as a design constraint: *"all 8 rules of `cross-vendor-dispatch.md`
apply"*.

---

## 1. Design

### 1.1 The measured gap this closes

Vendor identity is declared at **three** Wave 1 layers and executable at **none**.

**Declared (demand side), all measured on disk:**

| layer | vendor surface | count |
|---|---|---|
| `command-center/WORK-UNIT-CATALOG.json` | `assigned_model_vendor_role` present on **every** unit | 2,007 / 2,007 |
| — units assigned to `anthropic` | | 1,660 |
| — units assigned to `openai` | | 343 |
| — units assigned `mixed` | | 4 |
| `platform/council/**/*.councilspec.json` | files carrying a vendor-diversity floor | **101 / 117** |
| — `min_distinct_vendors: 2` | | 78 |
| — `min_distinct_vendors: 3` | | 23 |
| — `max_share_per_vendor` present | | 37 |
| — seats naming a **non-Anthropic** vendor | openai 174 · google 86 · human 16 · mistral 4 · xai 2 · local 2 | **284** |
| `platform/schema/receipt.schema.json` | `produced_by.vendor` (`:471`), `reviewer.vendor` (`:261`), `execution_substrate` (`:474`) | 3 fields |
| `platform/lib/completion_predicate.py` | condition 9 gate `require_cross_vendor_review` (`:174`, `:926-940`) | 1 enforced gate |

**Executable (supply side): zero.** `_probe_crossvendor_adapter_absence.py` walks all 51
`platform/lib/**/*.py` via the Python **AST** (so a vendor name in a string literal is
structurally distinguishable from an import or a call) and finds **61 vendor-name string
literals** and **0 files with real vendor dispatch** — no vendor SDK import, no `subprocess`
spawn of a vendor CLI, no HTTP POST to a vendor endpoint. Detector validated in both states:
it sees 33 ordinary `import json` and 7 `subprocess` call-sites (known-present control), and
it **fires** on a synthetic file containing `import anthropic` + `subprocess.run(["codex",…])`
+ `requests.post("https://api.openai.com/…")` (known-broken control). `SUCCESS:crossvendor-adapter-absence`.

Consequence, stated arithmetically rather than rhetorically: **347 of 2,007 units (17.3%)**
name a vendor nothing can invoke, and **101 of 117 councilspecs (86%)** declare a diversity
floor that is **unsatisfiable by construction** — 23 of them demand *three* distinct vendors.

### 1.2 The keystone defect: the existing cross-vendor gate is defeated by an alias

This is the load-bearing finding, and it is a live soundness hole rather than a missing
feature. `completion_predicate.py:935` enforces cross-vendor review by **string equality**:

```python
if rev_vendor == exec_vendor:
    return (Outcome.UNSATISFIED,
            f"unit requires a cross-vendor reviewer; reviewer vendor {rev_vendor!r} equals "
            "the executor's, and a same-vendor reviewer inherits the executor's blind spots", …)
```

and both operands are typed as free text with **no enum and no normalisation** —
`"vendor": { "type": "string", "maxLength": 64 }` at `receipt.schema.json:261` and `:471`. A
grep for any vendor-name enum in that schema returns **zero matches**.

`_probe_crossvendor_alias_hole.py` drives condition 9 directly. **10 of 10 same-vendor alias
pairs are accepted as cross-vendor**, including:

| executor vendor | reviewer vendor | accepted as cross-vendor? |
|---|---|---|
| `anthropic` | `Anthropic` | **yes** |
| `anthropic` | `claude` | **yes** |
| `anthropic` | `anthropic ` (trailing space) | **yes** |
| `openai` | `codex` | **yes** |
| `openai` | `OpenAI` | **yes** |
| `google` | `gemini` | **yes** |

Detector validated both states: identical spellings are correctly **rejected** (control
known-broken passes) and a genuinely distinct vendor is correctly **accepted** (control
known-good passes), so the probe is not simply always-accepting.
`SUCCESS:crossvendor-alias-hole`. Verdict **CONFIRMED**, confidence **almost-certain
(90-99%)** — it is a direct execution of the shipped gate, not an inference.

Why this matters more than the missing adapters: a receipt claiming independent cross-vendor
review can be produced **by one vendor reviewing itself**, and the strongest gate Wave 1
shipped will mark condition 9 `SATISFIED`. No number of adapters fixes that. Only a canonical
identity plane does. The identity plane is therefore justified **independently of whether any
adapter is ever built** — which is the severability that section 7 turns on.

### 1.3 Two control planes, both singular

The tournament rule is that a winner's control planes must remain *singular and
understandable*. This architecture adds exactly two, and each has exactly one authoritative
file.

**Plane A — vendor IDENTITY (answers "who is this vendor?").**

- `platform/registry/VENDOR-REGISTRY.json` — **the** single source of truth. One record per
  canonical vendor id: `{id, display_name, aliases[], models[], kind}` where `kind ∈
  {model-vendor, human, deterministic}`. Seeded from the 7 distinct seat vendors and 3
  distinct unit vendors already measured on disk (`anthropic`, `openai`, `google`, `mistral`,
  `xai`, plus `human` and `local`/`deterministic-*`) — the registry is *derived from* what
  Wave 1 already declares, and asserts authority over no other file.
- `platform/schema/vendor-identity.schema.json` — validates that registry and defines a
  reusable `$defs/canonical_vendor_id`.
- `platform/lib/vendor_identity.py` — one pure function, `canonicalize(s) -> str | None`,
  plus `same_vendor(a, b) -> bool`. Case-folds, strips, and resolves aliases
  (`claude → anthropic`, `codex → openai`, `gemini → google`). Deliberately **not** a
  network call, not a cache, not a class hierarchy.

**Plane B — vendor ADAPTER (answers "how do I invoke vendor X?").**

- `platform/lib/vendor_adapter/base.py` — one `Adapter` protocol with one method:
  `marshal(unit, prompt_path, out_path) -> Invocation`, where `Invocation` is a frozen
  dataclass `{argv: tuple[str,…], cwd: Path, env_keys: tuple[str,…], timeout_s: int}`.
  **The adapter constructs an invocation; it does not run it, own it, retry it, queue it, or
  persist anything about it.** That boundary is the whole anchor-compliance argument and
  section 7 attacks it.
- `platform/lib/vendor_adapter/openai_codex.py` — thin marshaller over the **already-mounted
  `codex mcp-server` rail**, per MECH-30's `route WRAP`. It does not build an HTTP client and
  does not re-implement the working Codex path; it emits the argv/prompt-file shape that
  `cross-vendor-dispatch.md` §3 (prompt by file, never inline — Windows `CreateProcess` caps
  the command line at 32,767 chars) and §4 (`--ignore-user-config` on every non-interactive
  invocation) already mandate.
- `platform/lib/vendor_adapter/anthropic_task.py` — marshals to the in-session Task rail.
- `platform/lib/vendor_adapter/human_gate.py` — marshals to a written question. `kind: human`
  is a real vendor in the registry because 16 councilspec seats name it; modelling the owner
  as a vendor is what lets `min_distinct_vendors: 2` be satisfied honestly on a call where a
  second model adds nothing.
- `platform/lib/vendor_adapter/registry.py` — maps canonical id → adapter. One dict.

**Where the planes attach to Wave 1 (the two additive modifications):**

1. `platform/schema/receipt.schema.json` — `produced_by.vendor` and `reviewer.vendor` gain a
   `$ref` to `canonical_vendor_id`. Additive: the field keeps its name, type and position;
   only the accepted value set narrows. `execution_substrate` (`:474`) **already exists** and
   becomes the adapter's declared output — no new field needed.
2. `platform/lib/completion_predicate.py:935` — `rev_vendor == exec_vendor` becomes
   `vendor_identity.same_vendor(rev_vendor, exec_vendor)`. One expression. Condition 9's
   contract, message, and spec anchor (`:78` → spec line 10641) are unchanged; it simply
   stops being fooled.

Nothing else in Wave 1 is touched. The DSL validator, councilspec layer, council protocols,
receipt schema gate, schema resolver, 233 substrate shims and 2,007-unit catalog are all
consumed as-is.

---

## 2. Cost and complexity analysis

| tranche | new files | modified | LOC estimate | test LOC | verdict |
|---|---|---|---|---|---|
| **T1 identity plane** | 4 (`VENDOR-REGISTRY.json`, `vendor-identity.schema.json`, `vendor_identity.py`, `test_vendor_identity.py`) | 2 (additive) | ~180 | ~260 | **cheap, high-value** |
| **T2 adapter plane** | 6 (`base`, 3 adapters, `registry`, `test_vendor_adapter.py`) | 0 | ~420 | ~380 | **anchor-borderline** (§7) |

Total: 10 new files against **418 reused unchanged**, ratio 1:42. Zero deletions.

**Complexity honestly accounted.** T1 adds one concept ("vendors have canonical ids") and one
lookup table. That is genuinely small, and the schema/predicate edits are two lines of real
change. T2 adds a plugin surface, and plugin surfaces are where complexity hides: every new
vendor is a new file, a new set of contract tests, a new credential path, and a new failure
mode nobody exercises until it fires in production. **I will not claim T2 is cheap.** Its
`effort S` label in MECH-30 is credible *only* because it wraps the mounted MCP rail rather
than building transports; if a future adapter needs a real HTTP client, that adapter is not
`S` and should be costed separately.

**The cost that is easy to miss:** the registry is a **derived** artifact (seeded from
councilspec seats and catalog assignments) that then becomes **authoritative** for schema
validation. Doc 13's A8 argues exactly this hazard — *"derived indexes go stale silently, and
this estate has measured exactly that failure with `recall-index.json` (103.8 h stale and
being served)"* (`:750`). A stale vendor registry is worse than none because a validator will
trust it: a vendor added to a councilspec but not to the registry makes a legitimate receipt
**schema-invalid**. Mitigation is a mechanical consistency test (§6, T1-4), not a promise.

---

## 3. Failure-mode analysis

| # | failure | mechanism | detection | severity |
|---|---|---|---|---|
| F1 | **Alias hole persists** — an alias not in the registry (`claude-opus`, `oai`, a new product name) still defeats condition 9 | `canonicalize` returns `None` for unknown input; if `same_vendor` treats `None != None` as "different", the hole reopens under a new spelling | `same_vendor` must return **False-with-error** (not "different") when either side fails to canonicalize; test T1-2 asserts unknown input raises rather than silently passing | **high** — this is the defect the plane exists to close, reintroduced |
| F2 | **Registry drift** → legitimate receipt rejected | a councilspec names a vendor absent from the registry; schema `$ref` rejects the receipt | consistency test (T1-4) enumerates all 628 `vendor` values across 117 councilspecs + 2,007 catalog assignments and asserts every one canonicalizes | **high**, and it is the A8 staleness failure applied to this design |
| F3 | **Adapter returns a receipt-shaped pass without running** — the `cross-vendor-dispatch.md` §2 failure: exit 0 with a progress-stream tail mistaken for a result | adapter is stateless and returns an `Invocation`, so the *caller* must AND-gate ≥2 signals (exit 0 **and** non-empty output file **and** schema-valid) before writing a receipt | T2-3 asserts a severed stream (exit 0, empty output file) yields `SEVERED`, never `SUCCESS` | **critical** — a fake cross-vendor pass is worse than no cross-vendor lane |
| F4 | **Windows arg-limit kill** — inline prompt → `os error 206` | prompt-by-file is mandatory in `Invocation`; `marshal` takes a `prompt_path`, and there is no parameter that accepts prompt text | T2-1 asserts no adapter's argv contains a payload over 8 KB | medium, **already measured** in this estate |
| F5 | **Fire-and-forget** — a backgrounded dispatch whose result is unreachable (`sessionId: null` filtering) | `Invocation` has no background flag; `timeout_s` is required | T2-2 asserts no adapter emits `--background`/`&`/`nohup`; regex-reject any result containing `started in the background` | medium |
| F6 | **Human adapter as a diversity launder** — `human` counted as a distinct vendor for a review the owner never performed | registry `kind: human` requires the receipt to carry an owner-attributable anchor | T2-5 asserts a `human`-vendor reviewer record without an owner anchor fails condition 9 | **high**, and it is *created by this design* — `human` was not previously executable |
| F7 | **Credential absence read as vendor failure** | an adapter with no key returns a transport error indistinguishable from a bad response | `Invocation.env_keys` names required keys; a presence check runs before marshalling and reports `MISSING-CREDENTIAL`, distinct from `vendor-error` | T2-4 | medium |
| F8 | **Vendor-identity monoculture through the back door** — all three adapters route to the same underlying provider (e.g. a gateway) so `min_distinct_vendors` is nominally met and actually not | `execution_substrate` (`:474`) records the real substrate; diversity is computed over (vendor, substrate) pairs | T2-6 asserts two seats sharing a substrate do not satisfy a 2-vendor floor | **high** — this is the subtlest one and I rate it the most likely to ship undetected, confidence **likely (55-80%)** |

---

## 4. Security review

**Credential handling — the hard constraint.** No adapter reads, prints, logs, or stores a
credential **value**. `Invocation.env_keys` carries key *names* only; the process environment
supplies values, and the adapter never touches them. This follows the discipline doc 13
records for A8's MCP indexing — *"must not read credential values; entries are indexed by
name and state only"* (`:735`). Per AGENTS.md §9 nothing in this design rotates, revokes, or
modifies any credential; a missing or 401-ing key is **reported by name and scope and handed
back to the owner**. F7 exists specifically so a credential problem is legible as a
credential problem rather than misattributed to the vendor.

**New attack surface, stated plainly.** T2 creates the estate's first in-repo code path that
constructs a command line for an external agent runtime. Three concrete risks:

1. **Prompt-file path injection.** `marshal` takes a `prompt_path`; a caller-controlled path
   could point outside the repo. Mitigation: resolve and assert containment under the repo
   root before emitting the argv — and note the estate has a **measured** sibling-bug in
   exactly this pattern (a `StartsWith` containment guard with an `ensure_within` sibling
   defect). So the containment check must be a real path-resolution comparison, not a string
   prefix test. Test T2-7.
2. **Fetched content is untrusted data.** A vendor's response is a *result*, never an
   instruction. It is written to a file and schema-validated; it is never eval'd, never
   shell-interpolated, and a response containing `curl … | sh` or "ignore previous
   instructions" is inert because nothing executes it. The receipt schema gate is the
   quarantine boundary.
3. **`--ignore-user-config` is a security control, not just an arg-limit fix.** It prevents
   the dispatched vendor from inheriting this estate's MCP inventory and hooks. A cloned or
   untrusted repo can carry auto-loaded agent config (CVE-2026-47751-class); an adapter that
   forwarded the ambient config would widen that blast radius.

**What this design *improves* security-wise:** F1/the alias hole is a security-relevant
soundness defect today — an integrity gate that can be satisfied by self-review. Closing it
strengthens the one mechanism this program's own evidence says catches real defects.

**Residual, disclosed inline:** the human adapter (F6) is a *new* laundering path for review
attestation, created by this architecture, and its mitigation (owner-attributable anchor) is
enforceable only as strongly as the anchor-validation logic already in the predicate.
**UNVERIFIED** — I did not measure whether the existing evidence-anchor validation is strong
enough to make an owner attribution unforgeable; the experiment that settles it is to attempt
a `human`-vendor receipt with a fabricated anchor against the current
`receipt_schema_gate.py` + condition-9 pipeline and see whether it is rejected.

---

## 5. Migration design from today's state

Ordered, each step independently revertible, no step leaves the tree red.

**M0 — baseline.** `cd platform/lib && python -m pytest -q` → 475 collected (measured).
Record it. Every later step must not reduce this number.

**M1 — seed the registry (read-only, zero risk).** Generate `VENDOR-REGISTRY.json` from disk:
the 7 distinct councilspec seat vendors and 3 distinct catalog vendors already measured.
Nothing consumes it yet. Revert = delete one file.

**M2 — land `vendor_identity.py` + its schema + tests. Still nothing consumes it.** This is
where the alias table is reviewed by a human, because it encodes judgements
(`claude → anthropic` is obvious; whether `local` and `deterministic-differ` are one vendor
or two is a real decision and belongs to the owner, not to me).

**M3 — the consistency gate (T1-4) goes green *before* anything depends on the registry.**
This is deliberately ordered ahead of M4: it proves all 628 councilspec vendor values and all
2,007 catalog assignments canonicalize. If it is red, M4 would start rejecting valid receipts
(F2). Gate, not a promise.

**M4 — flip condition 9 to `same_vendor`.** One expression at `completion_predicate.py:935`.
The alias probe in this directory becomes a **regression test**: it currently reports 10/10
leaks and must report 0/10, with its two controls still passing. This is a genuine both-states
test — the probe already demonstrably fires in the broken state, which is the property that
makes its later silence meaningful.

**M5 — narrow the receipt schema.** Add the `$ref` at `:261` and `:471`. Re-run the substrate
sibling's audit (`python platform/lib/schema_resolver.py --audit`) and require
`references_unresolved: 0` and 234/234 logical files still resolving — i.e. prove this change
did not disturb the P1 closure that just landed. **This is the step most likely to break
something outside my unit**, because 4 valid + 4 malformed example receipts exist under
`platform/schema/examples/substrate/` and their `vendor` values must canonicalize or the
sibling's proof goes red.

**M6 — T2 adapters, one at a time, Codex first** (it is the only vendor with a proven working
rail in this estate, so it is the only one whose contract tests can be validated against
reality). `human_gate` second. `anthropic_task` third. **Each behind the anti-drift gate of
§7.** If the owner declines T2 after reading §7, M0-M5 still deliver the whole keystone fix
and the migration simply stops here — that is the severability, and it is designed in, not
retrofitted.

**Rollback rehearsal** (required, since release mode is PR-ONLY and stopping condition 13 is
treated as "a merged PR plus a local rollback rehearsal"): `git revert` the M4+M5 commits on a
scratch branch and re-run `pytest` + `schema_resolver.py --audit`; both must return to the M0
baseline. Rehearse before the PR, report the result.

---

## 6. Test design

Every test below is a **mechanical** check — none asks a model to judge. Where a check is
about absence, it carries a known-broken control, because a probe silent in both states
measures nothing.

**T1 — identity plane**

| id | assertion | control (known-broken) |
|---|---|---|
| T1-1 | `canonicalize` maps every alias in the registry to its canonical id | an alias deliberately absent must return `None`, proving the map is consulted |
| T1-2 | `same_vendor(x, y)` **raises** (not "returns different") when either side fails to canonicalize | pass a garbage vendor; assert raise, so F1 cannot reopen the hole silently |
| T1-3 | the 10 measured alias pairs all report **same vendor** | the same test asserts `anthropic`/`openai` reports **different** — the pair is what makes it a detector rather than a constant |
| T1-4 | **consistency**: all 628 councilspec `vendor` values + all 2,007 catalog assignments canonicalize | temporarily inject an unknown vendor into a copy and assert the gate fails — proves it is not vacuous |
| T1-5 | mutation: revert `same_vendor` to `==` and require T1-3 to go **red** | this is the C1-style mutation the estate's own measurement says catches a suite that only appears to protect a behaviour |

**T2 — adapter plane** (T2-1..T2-7 map 1:1 to F3-F8 and the path-containment risk; each is
listed in §3/§4 with its failure mode, so it is not repeated here).

**What these tests cannot do, stated inline.** A contract test against a recorded transcript
**cannot** catch a vendor changing its API or CLI surface. That is a real residual and no
amount of in-repo testing closes it; the only honest detector is a periodically-run live smoke
test behind an explicit env var, and its absence must be reported as `NOT-CHECKED` rather than
folded into a pass. I am not claiming adapter correctness against live vendors — I am claiming
adapter *marshalling* correctness (argv shape, prompt-by-file, no background flag, credential
presence, containment), which is exactly what the measured failure history in
`cross-vendor-dispatch.md` says actually breaks.

---

## 7. The strongest adversarial refutation of my own architecture

I owe the tournament the argument that would kill this, not the one I can answer easily.

### 7.1 The strongest attack: **Plane B is a second orchestration runtime, and is therefore anchor-REJECTED**

Doc 13 §1 is a hard gate: an option counts only if it *"reintroduces none of: a 2nd
orchestration runtime · a vector-DB/KG memory · a durable-execution engine · a trained critic
· observability SaaS · a guardrail framework"* (`:119-121`). A5-naive was **anchor-REJECTED**
under exactly this clause (`:130`).

The attack: a component that decides *which vendor runs a work unit*, constructs its
invocation, sets its timeout, defines its terminal states, distinguishes `SEVERED` from
`SUCCESS`, gates on credentials, and enforces diversity floors across seats **is an
orchestration runtime**, whatever the file is called. Calling `Invocation` "stateless" is a
naming choice, not an architectural property: the moment a caller needs retries, ordering,
or partial-failure recovery across 284 non-Anthropic seats, that logic must live somewhere,
and the adapter package is where it will accrete. My own §3 table already assigns the adapter
plane eight failure modes with terminal-state semantics — that is the shape of a runtime, not
of a marshaller. And this estate has **measured** that a written boundary without a mechanical
gate drifts: doc 13's own A8 concedes the analogous staleness failure, and the session record
includes cases where a rule was written down and did not prevent the failure it described.

**Does it kill the design? Partly — and I will say which part.**

It **does** kill the maximal form. An adapter plane that owns the work-unit lifecycle is the
banned component, and I concede it without hedging. It would be dishonest to relabel a
dispatcher as a shim and claim anchor compliance on the strength of the label.

It does **not** kill Plane A. The identity plane is 4 files and ~180 LOC, contains no
dispatch, no transport, no state, and no scheduling — it is a lookup table and a pure
function. It is justified entirely by a **confirmed, executed, both-states-validated defect**
(10/10 alias pairs defeating condition 9), and closing that defect requires *no adapter at
all*. Under this attack the correct verdict is therefore: **commit T1, and make T2
conditional on a mechanical anti-drift gate** — a test asserting the `vendor_adapter` package
imports no queue/scheduler/persistence module, holds no module-level mutable state, and that
`Invocation` is frozen with no background flag. If that gate cannot be written, T2 should not
ship. That is a falsifiable boundary rather than a promise, and it is the honest resolution.

I hold the position that T1 survives this attack, and I am **not** claiming T2 does on its own
merits — it survives only behind the gate, and the owner should treat it as a separate
decision.

### 7.2 Second attack: delete the demand instead of building the supply

101 councilspecs declare an unsatisfiable floor. The cheapest possible fix is to **lower the
floors** — cost ≈ 0 files, 0 LOC. Against building three adapters, that is overwhelmingly the
better trade on cost alone, and a disciplined reviewer should press it.

My answer, and I concede its shape: this is a *real* alternative and it is *cheaper*, and it
is worse on the axis the owner's own measured evidence cares most about. Cross-vendor
adversarial review is the mechanism this program has repeatedly measured as the thing that
catches real defects — the 42%-REFUTED rate on a large audit, and the C2 finding that 5 of 8
refutations were **overclaims** caught by fresh-context reviewers. Lowering the floors deletes
the mechanism that works in order to make an unimplemented feature stop looking unimplemented.
But note what this attack *does* legitimately win: it wins on the **347 units**. Assigning a
vendor to a unit nobody can dispatch is a declaration, not a capability, and if T2 is declined
then those 347 assignments should be honestly re-marked rather than left as latent claims.

### 7.3 Third attack: the only validatable adapter already exists outside the repo

Codex is reachable today via the mounted `codex mcp-server` and `cross-vendor-dispatch.md`
already documents the correct invocation discipline. So T2's Codex adapter partly
re-implements a **working** rail, and the other two adapters cannot be validated against
reality at all.

Conceded, and it changes the design rather than defending it: the Codex adapter must **WRAP,
not rebuild** (MECH-30's stated route is `WRAP · CONFIG` precisely because of this), and any
adapter that would need a new transport is out of scope for `effort S` and must be costed
separately. This attack correctly shrinks T2; it does not touch T1.

### 7.4 What would make a different candidate win

If a judge finds that (a) the alias hole is better closed inside the predicate alone — a
`.casefold().strip()` plus a small inline alias set, no registry, no schema, ~15 LOC — **and**
(b) T2 is declined, then this architecture reduces to a two-line bugfix and should **not** win
a tournament slot; the config-first candidate (A1) absorbs it. I think that is a genuinely
strong line, and the only thing that resists it is F2/F8: an inline alias set has no
consistency gate against the 628 declared seat vendors and cannot express the
(vendor, substrate) pair that F8 needs. That is a narrow margin, and I would rather state it
than hide it.

---

## 8. Verdict ledger

| claim | verdict | confidence | anchor |
|---|---|---|---|
| Vendor identity is declared in 3 Wave 1 planes, executable in 0 | **CONFIRMED** | almost-certain | `_probe_crossvendor_adapter_absence.py` — 0 dispatch files / 61 literals, both controls pass |
| The shipped cross-vendor gate is defeated by 10/10 vendor aliases | **CONFIRMED** | almost-certain | `_probe_crossvendor_alias_hole.py`; `completion_predicate.py:935`; `receipt.schema.json:261,471` |
| 101/117 councilspecs declare an unsatisfiable diversity floor | **CONFIRMED** | almost-certain | `_probe_crossvendor_demand_supply.py` (78×2, 23×3) |
| 347/2,007 units name a non-dispatchable vendor | **CONFIRMED** | almost-certain | same probe (1,660 anthropic / 343 openai / 4 mixed) |
| Reuses 418 files, modifies 2 additively, deletes 0 | **CONFIRMED** | almost-certain | same probe, REUSE_REPLACE_LEDGER |
| Brief's "8 schemas" | **REFUTED** — disk has 9 | almost-certain | `platform/schema/*.schema.json` |
| Brief's "128 non-canonical amvr shapes" | **CONFIRMED** + characterised as the legacy string form | almost-certain | 1,879 dict / 128 str |
| Plane B is anchor-compliant on its own merits | **NOT-CHECKED / conceded as unproven** | — | §7.1; needs the anti-drift gate to be written before any claim is made |
| Adapter correctness against live vendors | **NOT-CHECKED** | — | no live smoke test run; §6 residual |
| A `human`-vendor attestation cannot be forged | **UNVERIFIED** | — | experiment named in §4 |