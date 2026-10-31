---
title: config-first
type: note
permalink: dqverify-repo-20261013/platform/architecture/config-first
---

# Architecture Candidate — CONFIG-FIRST MINIMAL

**Phase 3 architecture tournament entry.** Spec anchor: `_USER-PROMPTS.md:10769-10796` ("config-first
minimal architecture", first of the nine required committed architectures). Lineage:
`13-ARCHITECTURE-CANDIDATES.md:145-212` candidate **A1** ("the two files are the architecture"),
which passed the anti-overfit anchor gate at `:125`.

**Measured against:** working tree at `HEAD = 833fb1ea` (three commits past the `dc90d64a` named in
my brief: `dc90d64a` → `36070a6f` → `833fb1ea`). Every number below carries the command that
produced it; the raw outputs are in the appendix files listed in §8.

**Evidence tags.** `[M]` measured by me in this pass · `[L]` cited from a repo/corpus artifact at
`file:line` · `[B]` asserted by my spawn brief and *not* independently re-derived · `UNVERIFIED`
inline where a premise is unproven, naming the settling experiment.

---

## §0 — Does this architecture discard Wave 1? No. It is the only candidate that adds nothing to it.

**It reuses 349 of 349 committed files and replaces 0 of them** `[M]`. Config-first's entire claim is
that Wave 1 *already is* the architecture — **8 committed schemas** (9 on disk; the 9th,
`artifact-class-profiles.schema.json`, is a concurrent sibling's untracked addition, which
config-first keeps `[M]`), **6 code units** (`wfdsl` 12 modules/3,094 LOC · `councilspec` 10/2,529 ·
`council_protocols` 7/5,174 · `completion_predicate.py` 1,301 · `receipt_schema_gate.py` 732 ·
`corpus/corpusnorm` 7 modules `[M]`), 117 council specs, 163 classified candidates and a 2,007-unit
catalog are already a complete declarative control plane, and the correct next move is to stop adding
planes.

| area | tracked files at `833fb1ea` | config-first disposition |
|---|---|---|
| `platform/schema/` | 32 `[M]` | **REUSE** unchanged (8 committed schemas + examples) |
| `platform/lib/` | 50 `[M]` | **REUSE** unchanged (wfdsl, councilspec, council_protocols, completion_predicate, receipt_schema_gate) |
| `platform/council/` | 164 `[M]` | **REUSE** unchanged (48 protocols + 69 presets = 117 `.councilspec.json`) |
| `platform/registry/` | 7 `[M]` | **REUSE** unchanged (163 classified candidates) |
| `platform/corpus/` | 19 `[M]` | **REUSE** unchanged (`corpusnorm`, 7 modules) |
| `command-center/` | 75 `[M]` | **REUSE**; one field of one file is rewritten (§5) |
| `.claude-plugin/` | 2 `[M]` | **REUSE** as the entire plugin + marketplace surface |
| **total** | **349** | **349 reused · 0 replaced · 4 added** |

Command: `git ls-files <prefix> | wc -l` per row; totals cross-checked with
`git ls-files | wc -l` → `8244` repo-wide `[M]`.

**What it declines** — and this is the honest headline, because it is a live disagreement with a
sibling unit running right now, not with Wave 1. The concurrent substrate unit closed the
`command-center/schema/` P1 by generating **231 `$ref` shim files** (233 files including the two
meta aliases, **259,158 bytes**) that carry no constraints of their own and delegate to one physical
plane. Those 233 files are **UNTRACKED at `833fb1ea`** `[M]` (`git status --porcelain -uall
command-center/schema | wc -l` → `233`; `git ls-files --error-unmatch
command-center/schema/abstraction-leak.schema.json` → not tracked). Config-first proposes a
different close for the same defect (§5.2) and therefore declines those 233 files, while **keeping**
the sibling's one genuinely new physical plane, `platform/schema/artifact-class-profiles.schema.json`
(295 `$defs`, 189,910 B, also untracked `[M]`). Declining them is not a revert of committed work —
but it *is* a rejection of a sibling's shipped answer, and §7 argues the sibling's side of it as
strongly as I can.

**Adds 4 files.** `platform/architecture/CONTROL-SURFACE.md` (the prohibition list),
`platform/lib/catalog_normalize.py`, `platform/lib/test_catalog_normalize.py`,
`command-center/CONTROL-SURFACE-CONFORMANCE.json` (the gate's output).

---

## §1 — DESIGN

### §1.1 The thesis, stated so it can be falsified

> Every capability this program needs is expressible as **a field in an existing declarative file,
> validated by an existing schema, and executed by a host that is already installed**. Therefore the
> program should add zero runtimes, zero generators, zero services and zero registries — and should
> instead make the fields it already has *typed, singular and enforced*.

Falsifier: name one Phase-0-through-4 requirement in `_USER-PROMPTS.md:10473-11437` that cannot be
encoded as a field over the nine schemas in `platform/schema/`. §7 finds one for Phase 6 and concedes
it.

### §1.2 The five authored control planes, by real path

Config-first's whole discipline is that this list is **closed**. Anything not on it is derived,
and anything derived must be reproducible from something on it.

| # | authored plane | bytes `[M]` | what it decides |
|---|---|---|---|
| **CP-1** | `command-center/WORK-UNIT-CATALOG.json` | 5,343,710 | *what work exists* — `work_units[]` = 2,007 units × 20 mandatory fields, plus a separate `items[]` = 103 register entries |
| **CP-2** | `platform/schema/receipt.schema.json` | 37,715 (39 `$defs`) | *what a finished unit looks like* — the receipt envelope |
| **CP-3** | `platform/schema/artifact-class-profiles.schema.json` | 189,910 (295 `$defs`) | *what each artifact class looks like* inside a receipt |
| **CP-4** | `command-center/COMPLETION-GATES.json` | 16,770 | *what "done" means* — Gate A (12-condition unit predicate) + Gate B (program stopping rule) |
| **CP-5** | `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` | 535 + 18,905 | *how it ships* — the native loader's own two files |

Measured with `os.path.getsize` per path and `len(d["$defs"])` per schema `[M]`.

**Derived, therefore not authored** (must be regenerable, never hand-edited):
`command-center/PHASE-GRAPH.json` (51,401 B, and the sole declaration of buckets `B01`–`B13`
at `allocation_buckets.buckets[].id` `[M]`), `DEPENDENCY-GRAPH.json` (26,642 B, 103 nodes),
`ARTIFACT-MANIFEST.json`, `TEST-REGISTRY.json`, `CLAIM-REGISTRY.json`,
`CATALOG-INTEGRITY.json`, and every `*-STATUS*.json`.

### §1.3 Control and data flow — no indirection is added

```
                 AUTHORED (5 planes, hand-reviewed, schema-checked)
                 ┌──────────────────────────────────────────────┐
                 │ CP-1 catalog   CP-2/3 schemas   CP-4 gates   │
                 │                CP-5 plugin+marketplace       │
                 └───────┬──────────────────┬───────────────────┘
                         │                  │
        dispatch         │                  │  validate
                         v                  v
   Claude Code host ─> subagent ─> writes command-center/<area>/<unit>.json
   (hooks + skills +      │                  │
    mcp__codex__codex)    │                  v
                          │      platform/lib/receipt_schema_gate.py
                          │        layer 1: JSON-Schema over CP-2/CP-3
                          │        layer 2: evaluate_gate_a() = 12 conditions
                          v                  │
                    SUCCESS:<id> / FAILED:<id> <reason>   (AGENTS.md §4)
                                             │
                         DERIVED  <───────────┘  regenerated, never authored
                    PHASE-GRAPH · DEPENDENCY-GRAPH · *-INTEGRITY · *-STATUS
```

The execution substrate is the one already declared per unit: `local-parallel` 784 ·
`local-serialized` 565 · `worktree-isolated` 456 · `cloud-batch` 202 `[M]`. Config-first adds no
scheduler; `local-*` is the Claude Code session, `worktree-isolated` is `git worktree`, and
`cloud-batch` is the existing `codex-databricks-fanout` skill. Four substrates, zero new runtimes.

### §1.4 The three prohibitions (this is the whole architecture)

**P-1 — One physical schema plane per constraint.** A schema file either *carries constraints* or
*does not exist*. A file whose entire body is `{"$ref": ...}` is an alias, and aliases go in the
field that names them, not on disk. Enforced by a conformance test (§6, **T-1**).

**P-2 — Every authored field is typed; free text is a defect, not a style.** Measured today, four
fields in CP-1 are free text and that is the program's dominant defect surface (§3.1). P-2 makes each
one an `enum` or a `pattern` in `work-unit.strict.schema.json` and moves the catalog from
1,679/2,007 strict-passing `[B]` toward 2,007.

**P-3 — Derived files are regenerated, never edited.** Every derived file carries `generated_by` +
`source_sha256`; the gate re-derives and byte-compares. This is the *only* mechanism config-first
adds, and it is 40 lines.

### §1.5 What config-first says about each spec phase

| spec phase | config-first answer | new files |
|---|---|---|
| 2B — 96 workflow blueprints | a blueprint is a `.json` document validated by the existing `platform/lib/wfdsl` validator (12 modules, 3,094 LOC `[M]`); the runner is the existing `~/.claude/workflows/*.js` Workflow API | 96 data files, 0 code |
| 2C — council foundry | **already done**: 117 `.councilspec.json` validate on both the JSON-Schema and semantic layers `[B]`; median spec 12,046 B `[M]` | 0 |
| 3 — architecture tournament | this document + its 8 siblings under `platform/architecture/` | 0 code |
| 4 — formal contracts | the 9 schemas in `platform/schema/`, extended by field, not by file | 0 |
| 5 — plugin | `.claude-plugin/plugin.json` **is** the package; "install" is `claude plugin install`, "rollback" is `git checkout <tag>` + re-install | 0 |
| 6 — marketplace | `.claude-plugin/marketplace.json` + a git remote. **Config-first cannot satisfy signatures / SBOM / vulnerability status / quality score (`:10846-10859`)** — see §7.3 | — |

---

## §2 — COST AND COMPLEXITY ANALYSIS

### §2.1 Build cost, in files and lines

| item | config-first | measured comparator |
|---|---|---|
| new production code | **~340 LOC** (`catalog_normalize.py` ≈ 220 + gate ≈ 120) | the shim route shipped `_gen_schema_substrate.py` 373 LOC + `schema_resolver.py` 322 LOC = **695 LOC** `[M]` |
| new files on disk | **4** | **236** (233 shims/meta + resolver + test + generator) `[M]` |
| new bytes on disk | ~30 KB | **259,158 B** of shims alone `[M]` |
| files mutated | **1** (CP-1, one field) | 0 — byte-identity with HEAD preserved `[B]` |
| new dependencies | 0 (stdlib + already-vendored `jsonschema`) | 0 |
| new runtimes / services / daemons | **0** | 0 |

### §2.2 Ongoing complexity: the honest ledger

**Cheaper, measurably:**
- *Comprehension surface.* 5 authored planes vs 5 + 231 aliases. A reviewer asking "what constrains
  an `audit-drift` receipt?" opens one file under config-first; under the shim route they open
  `command-center/schema/audit-drift.schema.json`, read `x-physical-definition`, then open
  `artifact-class-profiles.schema.json#/$defs/audit-drift`. Two hops, one of which is a file that
  exists only to be a hop.
- *Regeneration risk.* No generator on the read path means no "the generator was stale" failure mode.
- *Review cost per change.* Adding an artifact class = 1 `$defs` entry. Under the shim route it is
  1 `$defs` entry + 1 generated file + a re-run + a diff review.

**More expensive, and I am not hiding it:**
- **CP-1 is 5.34 MB and 99,535 pretty-printed lines** `[M]` (`json.dumps(cat, indent=1)` newline
  count). Any config-first change that touches a field touches this file. Diffs are large, merge
  conflicts across ~20 concurrent agents are likely, and no human reviews the whole thing. This is
  the single largest cost and §7.1 argues it is fatal to the *slogan*.
- **P-2 is 328 units of work.** Strict conformance is 1,679/2,007 `[B]`; closing it means fixing
  every free-text field, and the four I measured (§3.1) touch 159 + 40 + 1,686 + 576 unit-fields.
- **No second machine.** Config-first is Windows-only by construction (`13-ARCHITECTURE-CANDIDATES.md:187-188`)
  and has no answer for a second host beyond `git clone`.

### §2.3 Complexity that config-first *reveals* rather than adds

Dependency resolution today is a **three-file join**: a token resolves if it is a `work_units[].id`,
or a `PHASE-GRAPH.json:allocation_buckets.buckets[].id`, or a `DEPENDENCY-GRAPH.json:nodes[].id`.
Measured: **1,007 distinct dependency tokens**. Join against the catalog's ids alone and 736 units look
broken; join against ids + a one-level-deep read of `allocation_buckets` + `DEPENDENCY-GRAPH` nodes and
794 look broken; join against all three planes *correctly* and exactly **4 tokens / 41 references / 40
units** remain unresolved `[M]`. Both larger numbers were **detector failures on my side, corrected
before they reached a conclusion** (see §8, note D2).
Config-first's cost here is not new complexity; it is being forced to *name* the resolver that today
exists only in each reader's head.

---

## §3 — FAILURE-MODE ANALYSIS

### §3.1 The failure class config-first is built for, measured on today's catalog

`13-ARCHITECTURE-CANDIDATES.md:69-73` names the estate's dominant failure class: **untyped silence**
— "an architecture that does not make silence typed is an architecture that cannot tell you it is
broken." Four independent instances, each re-derived by an exact algorithm with a known-broken
control (§8):

| # | measured defect | scale `[M]` | why it is silence |
|---|---|---|---|
| **F-1** | `completion_sentinel` with **no `FAILED` branch at all** | **1,686 / 2,007 = 84.0%**; 1,687 lack the strict `SUCCESS:<id>` + `FAILED:<id>` pair; e.g. `ARC-0001`'s entire sentinel is the string `SUCCESS:ARC-0001` | a unit that cannot express failure reports success or nothing — exactly the AGENTS.md §4 hole |
| **F-2** | `output_schema` decoration silently discarded by the splitter | **159 units** (40 × ` + <2nd schema>`, 1 × parenthetical, 118 × ` profile=`); **38 co-declared schema paths, 0 of 38 exist on disk, 39 units affected** | `receipt_schema_gate.py:216` keeps only the text before the first `" + "` / `" ("` / `" profile="`; the second declared schema is never checked and never reported unchecked |
| **F-3** | dependency tokens resolving to nothing | **4 tokens / 41 refs / 40 units** (`ARC` 19, `WFA` 17, `CC` 4, `IMP` 1) | a bare family prefix is not a node; the edge silently does not exist |
| **F-4** | `assigned_model_vendor_role` shape drift | **128 bare strings** + **448 dicts with extra keys** = 576 non-canonical of 2,007 | a consumer that expects `{model,vendor,role}` gets `"opus/anthropic/implementer"` and either crashes or, worse, `.get("model")` → `None` |

F-3's count **independently CONFIRMS** my brief's "41 unresolvable dependency refs" `[B]` by a
mechanically different route (set-difference over a three-file join, vs the catalog's own
`work_units_meta.known_defects_at_merge.unknown_form_dependency_refs: 41`). Note the catalog's
metadata names *different* token spellings (`BKT-ARC`, `BKT-CMD`, `BKT-IMP`, `WFA-1of2`) than the
four live tokens I found — same count, stale spellings. F-4's 128 likewise CONFIRMS the brief's "128
non-canonical … shapes" under the definition *not-a-dict*; my stricter key-set definition gives 576.

F-1 **REFUTES** my brief's "96 completion sentinels that do not name their own unit": under that
literal rule the measured count is **0 / 2,007**, with a passing known-broken control `[M]`. The real
defect is an order of magnitude larger and differently shaped.

### §3.2 Failure modes config-first introduces or leaves open

| id | failure mode | likelihood | blast radius | config-first's mitigation | residual |
|---|---|---|---|---|---|
| **FM-1** | **A prohibition is not an enforcement.** P-1/P-2/P-3 are prose; the estate has already measured that "the ban is enforced by nothing but this document" (`13-ARCH:206-208` quoting `16-GRILL-QUEUE.md:80-81`) | **high** | whole architecture | ship P-1/P-2/P-3 as three *tests* (§6 T-1..T-3) in the suite that already runs 475 tests | a test can be skipped; only CI enforces. **This is the strongest failure mode and §7.2 concedes it** |
| **FM-2** | **Concurrent edits to a 5.34 MB plane.** ~20 agents share one git index; two units editing CP-1 conflict | **high** | the plan of record | all CP-1 writes go through `catalog_normalize.py`, which is idempotent and sorts keys, so conflicts are line-local | large diffs remain unreviewable by eye |
| **FM-3** | **Free-text field re-enters.** P-2 types four fields; a fifth is added untyped next week | medium | one field | `work-unit.strict.schema.json` uses `additionalProperties: false` on the unit object | a new field must be added to the schema first — friction, by design |
| **FM-4** | **Derived file hand-edited.** Someone edits `PHASE-GRAPH.json` directly | medium | phase math | T-3 re-derives and byte-compares | detects, does not prevent |
| **FM-5** | **Silent narrowing.** P-1 deletes the 231 shims; a consumer that resolved `command-center/schema/x.schema.json` by *path* now 404s | **certain if unsequenced** | 2,007 refs | migration is field-first, delete-last (§5.2 step order is load-bearing) | if the order is inverted, every unit breaks at once |
| **FM-6** | **Windows-only.** No POSIX path story | certain | portability | none — accepted | `13-ARCH:187` accepts it explicitly; a second machine forces A3/A11 |

---

## §4 — SECURITY REVIEW

### §4.1 Where config-first is genuinely stronger

**No generator on the read path = no generator to poison.** This is A1's real security argument
(`13-ARCH:190-192`) and it is not rhetorical: the shim route's read path resolves 2,007 references
through a generated tree, so a single write to `_gen_schema_substrate.py` rewrites the effective
constraints of 231 logical classes. Config-first's read path touches 3 authored files.

**Bounded write blast radius, measured.** All **2,007 of 2,007** units write under
`command-center/`, and there are **0 output_path collisions** `[M]`. So the program's entire
filesystem effect is one directory, and no two units can race the same file. Config-first preserves
this as an invariant (T-4) rather than assuming it.

**The one control I would keep verbatim from the sibling.** `platform/lib/schema_resolver.py:135-155`
implements a disk-only retriever: it refuses any `$ref` URI outside `BASE_URI`, then re-resolves and
requires `str(target).startswith(str(REPO_ROOT.resolve()) + os.sep)` — a network-fetch ban *and* a
path-traversal guard, with `$id`s under the deliberately non-resolvable
`https://ast-integrate.invalid/`. Config-first adopts this file unchanged even while declining the
231 shims it was written to serve.

### §4.2 Findings against config-first (measured, not hypothetical)

**S-1 — `tool_permissions` is a security field written in three syntaxes, one of which is English.**
Least-privilege in this architecture is expressed per unit in `tool_permissions`. Measured over
2,007 units, 85 distinct tokens `[M]`:

- **13 tokens in a `Bash:<subcommand>` colon form, 162 references, 113 units** — `Bash:python` (96),
  `Bash:pytest` (17), `Bash:pwsh-readonly` (10), `Bash:git-readonly` (8), `Bash:codex` (2),
  `Bash:gitleaks` (2), `Bash:uv` (1), `Bash:semgrep` (1), … The Claude Code permission system
  matches `Tool(scope)`, not `Tool:scope`. **UNVERIFIED** whether `Bash:python` is rejected outright
  or silently treated as an unknown literal; settling experiment: place `Bash:python` in a scratch
  `permissions.allow` and attempt a `python -c` Bash call, then compare against `Bash(python:*)`.
- **10 values whose scope body is prose, 128 references, 126 units** —
  `Bash(python, pytest; git read-only; NO add/commit/push)` (60 refs),
  `Bash(python analysis only; no network, no git write)` (37),
  `Bash(git read-only: ls-tree/cat-file/show/log/diff/worktree list; NO add/commit/push/reset)` (8),
  `mcp__search-hub__* (read-only retrieval)` (8), `Bash(torsocks curl, sandboxed + egress-logged)` (1).
  These parse as `Tool(scope)` and can never match.

So **222 units carry at least one permission token no enforcement layer can evaluate** (113 ∪ 126,
intersection 17, measured directly rather than inferred `[M]`), and the failure is fail-*open* in the
dangerous direction: an unmatched allow-rule does
not deny, it just does not allow, and the unit then runs under whatever the session already permits.
Note also that 1,613 units grant `Bash` and 1,549 grant `Write` unscoped `[M]` — the field's
*intent* is least-privilege and its *content* is mostly unrestricted. Config-first's answer is P-2
(make `tool_permissions` a typed enum of real matcher forms); until P-2 lands, this is config-first's
worst security position, because config-first is precisely the architecture that trusts fields.

*Detector caveat, disclosed:* my first pass classified `mcp__codex__codex-reply` and two
`mcp__context7__*` names as non-canonical because my regex disallowed a hyphen in the tool segment.
Those are valid names; the 162/128 figures above exclude them.

**S-2 — a checked-in `.claude/settings.json` is an auto-loading control plane in an untrusted
clone.** The repo tracks `.claude/settings.json` (280 B) containing `extraKnownMarketplaces`
(pointing at `github:Prekzursil/agent-skills-toolchain`) and `enabledPlugins`
(`agent-skills-toolchain@agent-skills-toolchain: true`) `[M]`. Per AGENTS.md §9, a cloned repo's
`.claude/` may auto-load config *and hooks* the moment an agent runs inside it (CVE-2026-47751 class).
Config-first makes this **worse than the alternatives** because it elevates checked-in config to
*authority*: "the files are the architecture" means a hostile fork's files are a hostile
architecture. Mitigation config-first must carry: CP-5 is the *only* checked-in host-config plane,
`.claude/settings.json` is demoted to an explicitly non-authoritative example, and T-5 asserts the
repo tracks no `hooks` key in any `.claude/settings*.json`.

**S-3 — no signature, no SBOM, no provenance chain.** `.claude-plugin/marketplace.json` (18,905 B)
has `name`/`owner`/`description`/`plugins` `[M]` and no signing or attestation surface. Spec
`:10853-10858` requires provenance, signatures, SBOM and vulnerability status. Config-first's honest
answer is "git tag + `git verify-commit`", which is a real provenance chain for *authorship* and no
chain at all for *artifact integrity at install time*. See §7.3 — I treat this as a refutation, not a
gap.

**S-4 — 144 of 2,007 units set `owner_approval_required: true`** `[M]`. Config-first expresses the
human gate as a field, which means an agent that ignores the field is unstopped. There is no code
today that reads it. **UNVERIFIED** that any consumer honours it; settling probe:
`grep -rn "owner_approval_required" platform/ ci/ hooks/` and check for a *read*, not a *write*.

### §4.3 What config-first does not change

`permissions.deny`, the credential-read guard, and the no-force-push rule are host- and hook-level
and are untouched. No secret is introduced; no credential is read, printed, or rotated by anything
in this design.

---

## §5 — MIGRATION DESIGN FROM TODAY'S STATE

Six steps (0-5). Steps 1-4 are reversible with one `git checkout` / one file deletion; **step 5 is the
only destructive one and it comes last on purpose** (FM-5 — inverting the order breaks all 2,007
references at once). Even step 5 has a re-derivation path (§5.6).

### §5.1 Step 0 — freeze the baseline (both-states control)

```
git rev-parse HEAD                                     # 833fb1ea, recorded in CONTROL-SURFACE.md
python platform/lib/schema_resolver.py --audit         # today: 2007/2007 resolving  [B, re-run by me: SUCCESS]
cd platform/lib && python -m pytest -q --no-header     # today: 475 collected, rc=0  [M]
```
Record all three in `command-center/CONTROL-SURFACE-CONFORMANCE.json`. Any later step that changes a
number must change it *on purpose and say so*.

### §5.2 Step 1 — normalize `output_schema` (this is config-first's answer to the P1)

Rewrite CP-1's `output_schema` for every unit to exactly one bare pointer:

```
platform/schema/artifact-class-profiles.schema.json#/$defs/<class>     (295 $defs available [M])
platform/schema/receipt.schema.json#/$defs/receipt_core                (bare canonical receipts)
command-center/schema/_meta/json-schema-2020-12.json                   (the 21 meta-schema units [M])
```

Scale of the edit, measured: 305 naive distinct file-paths collapse to 234 logical files `[B]`;
**180 values are not a bare `path[#frag]`** and **159 of those carry text the splitter discards**
`[M]`. The 21-value gap between 180 and 159 is exactly the meta-schema URL
`https://json-schema.org/draft/2020-12/schema` on `ARC-0078`…`ARC-0085`+ `[M]` — the substrate unit
already aliased it to a real file, and config-first keeps that alias.

Co-declared second schemas (F-2) are **not** dropped: each becomes an explicit
`additional_output_schemas: []` array, so a unit that must satisfy two contracts says so in a field a
validator can read. Today 38 such paths exist and **0 of 38 are on disk** `[M]` — so this step
converts a silent miss into 38 typed, visible `NOT-CHECKED`s. That is the whole point.

Guard: `catalog_normalize.py --check` must be idempotent (run twice → identical bytes) and must not
change any field other than `output_schema` / `additional_output_schemas`; the test asserts a
field-level diff, not a byte diff.

### §5.3 Step 2 — type the other three free-text fields (P-2)

- `completion_sentinel` → `pattern` requiring both `SUCCESS:<own-id>` and `FAILED:<own-id>`. This
  moves 1,686 units `[M]`. Do it mechanically: the sentinel body is derivable from
  `evidence_requirement` + `output_path`, and where it is not, the unit gets the canonical
  two-branch form.
- `assigned_model_vendor_role` → object with exactly `{model, vendor, role}`; `basis`/`rationale`
  move to a sibling `assignment_basis` string. Moves 576 units `[M]`.
- `tool_permissions` → `enum` of real matcher forms; the 13 colon-form tokens and 10 prose values
  (S-1) are rewritten to `Tool(scope)` or split into a `tool_permissions_rationale` string.
- `dependencies` → each token must resolve; the 4 bare family prefixes (`ARC`/`WFA`/`CC`/`IMP`, 41
  refs, 40 units `[M]`) are either expanded to the real ids or declared as a new bucket in the
  *derived* PHASE-GRAPH, which then must be regenerated.

### §5.4 Step 3 — write `CONTROL-SURFACE.md` and wire the four gates

Names the five authored planes, the derived list, and P-1/P-2/P-3. This is the doctrine, and §7.2
concedes it is worth nothing without step 4.

### §5.5 Step 4 — enforce, don't document

Add T-1…T-5 (§6) to `platform/lib`'s suite, which already runs 475 tests `[M]`. A prohibition that
is not a test does not exist. `13-ARCH:206-208` is explicit that this estate has already measured
that failure once.

### §5.6 Step 5 — delete the 231 shims (last, and only after T-1..T-5 are green)

`command-center/schema/*.schema.json` (231 files) is removed; `command-center/schema/_meta/` and
`command-center/schema/meta/` **stay** (they are real aliases with a real body, and 21 units point at
one of them `[M]`). Order matters absolutely: delete-before-normalize breaks 2,007 references at once
(FM-5). Because all 233 files are untracked at `833fb1ea` `[M]`, if config-first *wins the tournament
before those files are committed* this step is a no-op — the shim tree simply never lands.

**Rollback.** Steps 1-3 are one `git checkout -- command-center/WORK-UNIT-CATALOG.json`. Step 5 is
`python platform/lib/_gen_schema_substrate.py`, which regenerates all 231 files deterministically
`[B]` — so even the irreversible step has a re-derivation path, which is exactly the property
`13-ARCH:263` credits to generated architectures. Config-first borrows it for its own rollback and
should say so plainly.

---

## §6 — TEST DESIGN

Every test below is stated with the **known-broken state that must make it fail**. A test that is
green in both states measures nothing (`rules/common/single-signal-verification.md` §3b), and this
program has already shipped that mistake.

| id | asserts | known-broken control (must go RED) |
|---|---|---|
| **T-1** (P-1) | no `*.schema.json` under `command-center/schema/` has a body whose only semantic key is `$ref` | restore one generated shim → RED. Control that it is not vacuous: `_meta/json-schema-2020-12.json` has a real body and must stay GREEN |
| **T-2** (P-2 · shape) | every `work_units[]` entry validates against `work-unit.strict.schema.json` with `additionalProperties: false` | inject `assigned_model_vendor_role: "opus/anthropic/implementer"` (a real current value, 128 units) → RED |
| **T-3** (P-3) | for each derived file, re-derive and byte-compare | hand-edit one integer in `PHASE-GRAPH.json` → RED |
| **T-4** (blast radius) | 2,007/2,007 `output_path` start with `command-center/` **and** are pairwise distinct | point one unit at `platform/` → RED; duplicate one path → RED |
| **T-5** (S-2) | no tracked `.claude/settings*.json` contains a `hooks` key | add `"hooks": {}` → RED |
| **T-6** (F-1) | every sentinel contains `SUCCESS:<own-id>` **and** `FAILED:<own-id>` | today's `ARC-0001` (`"SUCCESS:ARC-0001"`) → RED **before** migration §5.3. This is the fail-first proof that step 3 did something |
| **T-7** (F-2) | for every unit, `output_schema` + every `additional_output_schemas[]` entry resolves to a file **and** compiles | today's 38 co-declared paths → RED (0 of 38 on disk) |
| **T-8** (idempotence) | `catalog_normalize.py` twice → identical bytes | seed a dict-ordering bug → RED |
| **T-9** (regression floor) | the existing suite still passes at ≥ 444 (Wave 1 floor) and the resolver audit still reports 0 unresolved | any of the above breaking a Wave 1 test → RED |

**Mutation discipline.** T-1..T-8 are each paired with the mutation that kills them, mirroring the
12/12 predicate-mutation battery Wave 1 already ran `[B]`. **T-9's floor of 444 is the committed
baseline; the 475 measured today includes 31 tests from the untracked substrate unit** `[M]` — so if
config-first declines those files, the honest floor is 444, not 475, and T-9 must say which.

**What I did not test and will not claim.** I have not executed T-1..T-9; they are a design. The only
executable claims in this document are the measurements in §8. `NOT-CHECKED`: whether normalizing
5.34 MB of CP-1 in one pass survives a 20-agent shared index without conflict — settling experiment
is a two-agent race on a scratch clone.

---

## §7 — THE STRONGEST ADVERSARIAL REFUTATION OF THIS ARCHITECTURE

Three arguments. I believe the first two are **true and partially fatal**, and the third is **true and
fully fatal to the scope the spec asks for**. An advocate who cannot say that has not understood the
design.

### §7.1 The refutation that kills the *justification*: "readable in one sitting" is measurably false

Config-first's entire claim to be *better* rather than merely *smaller* rests on one property, stated
verbatim at `13-ARCHITECTURE-CANDIDATES.md:155-156`: **user-control "highest" — "the owner can read
the whole control plane in one sitting."** That is A1's differentiator; strip it and A1 is just A2
without the generator.

I measured it. The authored control plane (CP-1…CP-5) is **5,607,545 bytes across 6 files**, of which
CP-1 alone is **5,343,710 bytes = 99,535 pretty-printed lines** `[M]`. (Adding the five *derived*
JSON planes brings the named-plane total to 5,683,579 B across 9 files `[M]` — but config-first only
claims humans read the authored six, so the six-file figure is the one that must be defended.) At a
generous 500 lines/hour of careful review that is ~200 hours for one file alone. The 2,007 units carry
20 mandatory fields each ≈ 40,000
field-values. **No one has read this control plane and no one will.** The property that justifies
config-first is false by roughly three orders of magnitude, today, at `833fb1ea`.

**Does it kill the design? It kills the justification, not the mechanism — and that is a real
demotion, not a rescue.** The mechanism (declarative planes, existing host, zero new runtimes) still
passes the anti-overfit anchor at `13-ARCH:125` and still costs 4 files against 236. But once I
concede that the plane is only *machine*-auditable, config-first's advantage over **generated-SSOT**
collapses on the exact axis it was supposed to own: if a tool must read the plane for you, the
argument against a tool *writing* it is much weaker. Generated-SSOT then wins on
`13-ARCH:263`'s byte-exact rollback and on `:265-266`'s path-templated cross-platform emitter, both
of which config-first lacks.

**My honest revision:** config-first should be re-pitched as **"one physical definition per
constraint, and every field typed"** — a *singularity* claim, not a *readability* claim. That version
survives §7.1 intact and is what §1.4's P-1/P-2 actually encode. I am revising the pitch because the
measurement refutes the original wording, not because of any argument's tone.

### §7.2 The refutation that kills enforcement: a doctrine is not a mechanism, and this estate has already measured that

`13-ARCH:202-208` makes this argument against A1 and it transfers exactly: *"A1 is a doctrine with no
enforcement, and this estate has already measured that a documented ban is not an enforcement."* My
own §3.2 FM-1 says the same thing, and the corpus supplies the receipt: `16-GRILL-QUEUE.md:80-81` —
*"the ban is enforced by nothing but this document."*

The concrete form here is worse than in A1's original framing, because config-first's central
promise is that **fields are trustworthy**, and I measured four fields and all four are untrustworthy:
84.0% of sentinels cannot express failure; 159 `output_schema` values carry text the checker
discards; 41 dependency references resolve to nothing; 576 role fields are off-shape. A field-trusting
architecture whose own corpus fails on every field it trusts is refuted **by its own data**, not by
an opinion.

**Does it kill the design? No — but only because the enforcement already exists and is not new.**
`platform/lib/completion_predicate.py` (1,301 LOC) and `receipt_schema_gate.py` (732 LOC) are
committed, tested, and are exactly the code that turns a field into a gate `[M]`. So config-first can
adopt code-enforcement **without violating "add no new machinery"** — the machinery is already in
`platform/lib`. That is a legitimate rescue, and I mark it as a rescue: config-first-as-doctrine is
dead, and config-first-as-*five-planes-plus-nine-tests* is what survives. If the tournament judge
reads P-1/P-2/P-3 as prose commitments rather than as T-1..T-9, they should score this candidate as
refuted.

### §7.3 The refutation I cannot answer: config-first is non-compliant at Phase 6

Spec `:10846-10859` enumerates the marketplace's required support: canonical registry, publisher
identity, versions and channels, dependency metadata, platform/client compatibility, permissions,
**provenance, signatures, SBOM, license metadata, vulnerability status, quality/conformance score**.

Config-first's answer is `.claude-plugin/marketplace.json` (18,905 B; keys
`name`/`owner`/`description`/`plugins` `[M]`) plus a git remote. That delivers publisher identity and
versions. It delivers **no signature, no SBOM, and no vulnerability status** — those are not fields
you can add to a static JSON file and have mean anything; they require a build step that produces an
attestation and a verifier that checks it at install time. A build step is a generator, and a
verifier at install time is a service. **Both are exactly what config-first forbids.**

**Does it kill the design? For the scope the spec asks for, yes.** Config-first cannot be the
whole-program architecture. Its honest scope is **Phases 0-4 plus 2C** — the schema/catalog/council
core, where it is the strongest candidate on the board because that core is *already built* as
declarative data and needs typing rather than tooling. For Phases 5-6 it must yield to
marketplace-first (A3) or immutable-deploy (A11). And per the spec's own hybrid rule at `:10795` —
*"the winner may be a hybrid only when its control planes remain singular and understandable"* —
config-first's real contribution to the tournament may be the **singularity constraint itself** (P-1),
applied to whichever candidate wins the release layer.

### §7.4 Three lesser objections, answered rather than conceded

- *"Declining the 231 shims discards a sibling's shipped, proven work."* It declines 233 **untracked**
  files `[M]` and keeps the sibling's 189,910-byte physical plane, its 322-LOC resolver with the
  path-traversal guard, and its 31 tests. The disagreement is one design choice — alias-on-disk vs
  normalize-the-field — not a rejection of the unit.
- *"Editing a 5.34 MB plan of record is riskier than adding files."* True, and it is why the sibling
  chose byte-identity. But 41 dependency refs, 576 role shapes and 1,686 sentinels **cannot be fixed
  anywhere except inside CP-1**. The catalog must be edited regardless; config-first argues for
  editing it once under a schema rather than growing an alias layer that defers the edit.
- *"Windows-only is disqualifying."* It is a real loss (`13-ARCH:187-188`) and it is bounded: 2,007/2,007
  units write under one directory `[M]`, so a POSIX port is a path-prefix change, not a rewrite.

---

## §8 — MEASUREMENT LOG AND HONEST SCOPE

### Probes (all read-only; each carries its detector controls)

| probe | what it settles | terminal state |
|---|---|---|
| `platform/architecture/_measure_cf.py` → `_measure_cf.out.json` | inventory: schemas, lib LOC, council, registry, catalog, tracked counts | ran, exit 0 |
| `platform/architecture/_measure_cf2.py` → `_measure_cf2.out.json` | control-plane bytes, candidate recount, ref shapes, 475-test collect | ran, exit 0 |
| `platform/architecture/_probe_cf_compound.py` → `.out.json` | F-2: splitter drops (2 controls: known-present compound fires, known-absent plain silent) | `SUCCESS:cf-compound-ref-probe detector_valid=True` |
| `platform/architecture/_probe_cf_catalog_defects.py` → `.out.json` | F-1/F-3/F-4 + collisions (6 controls) | `SUCCESS:cf-catalog-defects controls=True` |
| `platform/architecture/_probe_cf_reconcile.py` → `.out.json` | reconciles my numbers against the brief's; finds the bucket declaration | `SUCCESS:cf-reconcile` |

Corroborating runs of **existing** tooling (not mine): `python platform/lib/schema_resolver.py
--audit` → `references_resolving: 2007, references_unresolved: 0, distinct_logical_files: 234`,
`SUCCESS:schema-resolver-audit`; `cd platform/lib && python -m pytest --collect-only -q` → `475 tests
collected`, rc 0.

### Verdict table

| claim | verdict | band |
|---|---|---|
| 349 tracked files reused, 0 replaced, 4 added | CONFIRMED `[M]` | almost certain |
| 233 files under `command-center/schema/` are untracked at `833fb1ea` | CONFIRMED `[M]` | almost certain |
| CP-1 = 5,343,710 B / 99,535 pretty lines; authored plane (CP-1…CP-5) = 5,607,545 B / 6 files; all named planes incl. derived = 5,683,579 B / 9 files | CONFIRMED `[M]` | almost certain |
| 222 units carry an unenforceable `tool_permissions` token (113 colon-form ∪ 126 prose, ∩ 17) | CONFIRMED `[M]` | almost certain |
| 1,686/2,007 sentinels have no `FAILED` branch | CONFIRMED `[M]` | almost certain |
| brief's "96 sentinels not naming their own unit" | **REFUTED** — measured 0/2,007, control passes `[M]` | almost certain |
| brief's "41 unresolvable dependency refs" | **CONFIRMED** independently (4 tokens / 41 refs / 40 units) `[M]` | almost certain |
| brief's "128 non-canonical role shapes" | **CONFIRMED** under *not-a-dict*; 576 under strict key-set `[M]` | almost certain |
| brief's "159 unloadable `output_schema` refs" | **PARTIAL** — 159 carry dropped text, 180 are not bare paths; both true under stated definitions `[M]` | almost certain |
| brief's "269 distinct / 1,896 refs" | already refuted by the substrate unit; my naive count is 305 file-paths / 2,007 refs, resolver says 234 logical `[M]` | almost certain |
| 163 candidates (my exact recount) vs 161/160 MET in the floor state | **PARTIAL / definitional** — 163 elements carry both `id` and `classification`; not re-litigating the floor | likely |
| config-first is non-compliant at spec Phase 6 | CONFIRMED by reading `:10846-10859` against `marketplace.json`'s 4 keys | almost certain |
| T-1..T-9 pass | **NOT-CHECKED** — designed, not executed | — |
| CP-1 normalization survives ~20 concurrent agents | **NOT-CHECKED** — settling experiment in §6 | — |
| whether any consumer reads `owner_approval_required` | **NOT-CHECKED** `UNVERIFIED`; probe in §4.2 S-4 | — |
| whether `Bash:python` is rejected or silently ignored by the matcher | **NOT-CHECKED** `UNVERIFIED`; probe in §4.2 S-1 | — |

### Detector failures I made and corrected (disclosed, per §3b)

- **D1.** My first compound-ref probe counted `#/$defs/...` fragments as "dropped text" and reported
  **446 units**. `parse_schema_ref` *returns* the fragment; it is not dropped. Corrected to **159**
  by subtracting `head + fragment`. The corrected taxonomy sums exactly (`plus` 40 + `paren` 1 +
  `profile` 118 + `other` **0**), and `other == 0` is the check that the correction is complete.
- **D2.** My dependency probes read `PHASE-GRAPH.json:allocation_buckets` only one level deep and
  missed `.buckets[].id`, reporting **736** units (catalog-ids-only join) and then **794** units
  (shallow three-file join) as having unresolvable dependencies. Buckets `B01`–`B13` *are* declared at
  `allocation_buckets.buckets[].id`; corrected to **41 refs / 40 units**, which then matched the
  brief's independently-stated 41.
- **D3.** My permission-token regex disallowed hyphens in an MCP tool segment and mis-flagged
  `mcp__codex__codex-reply` and two `mcp__context7__*` names. Excluded from the S-1 figures.

Each of these was a self-contradicting reading caught before it reached a conclusion, which is the
only reason the numbers in §3 and §4 are worth reading.

### Honest scope of this document

This is an **advocacy artifact**, and my brief's instruction was to argue this architecture honestly
rather than to hold a tournament. **I did not read any sibling candidate's document.** Timestamps
matter here, so: when I began drafting §7, `platform/architecture/` held one complete sibling
(`cross-vendor.md`, 30,759 B) and four skeletons of 760-1,006 B `[M]`; by the time I finished, six
siblings were complete (`cross-vendor` 30,759 · `distributed-runtime` 40,255 · `gateway-lazy` 45,427 ·
`generated-ssot` 40,068 · `marketplace-first` 39,094 B, plus `security-first` still a 802 B skeleton)
`[M]`. I did not go back and read them. Therefore §7's comparisons to generated-SSOT,
marketplace-first and immutable-deploy are drawn from `13-ARCHITECTURE-CANDIDATES.md` §A2/§A3/§A11
only, and are my characterisation of those *cards*, not of the siblings' committed arguments. **A
judge panel must weight the siblings' own documents over my summary of them** — in particular, my §7.1
concession that generated-SSOT beats config-first on the readability axis was reasoned from
`13-ARCH:263-266`, and `generated-ssot.md` may make a stronger or weaker case than that card does.

I have **not** implemented any part of this architecture. Nothing in `command-center/` or
`platform/schema/` was modified by this unit; the only files it wrote are this document and the five
probes named above.