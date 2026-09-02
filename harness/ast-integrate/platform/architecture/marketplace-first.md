# Architecture Candidate: MARKETPLACE-FIRST

**Phase 3 — Architecture Tournament.** This is an *advocacy* artifact: I argue for this
architecture and I expose its real costs. Section 7 is the load-bearing one.

**Grounding commit:** `833fb1ea0886a87a562be539a02839f8c6e6a6e4` (branch `main`), **not** the
brief's `dc90d64a`. `dc90d64a..833fb1ea` is 2 commits, 159 files, +1,885/−52,666 — almost all of
which is `git rm --cached` of agent probe scripts, plus real edits to
`platform/lib/wfdsl/validate.py` (+188/−), `test_expr.py`, `test_schemas_and_examples.py`, and the
addition of `platform/schema/SUBSTRATE-RESOLUTION-STATUS.json`. Every number below was measured at
`833fb1ea`, not inherited from the brief.

**Evidence classes.** `[M]` measured by me in this unit with the command shown ·
`[S]` from repo source at `file:line` · `[SPEC]` from the owner spec
`C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:<line>` ·
`[L]` from `13-ARCHITECTURE-CANDIDATES.md:<line>` · `[B]` asserted by the orchestrator brief and
**not** independently re-derivable from disk. Bands are Sherman-Kent.

Every `[L]` line number in this document was verified by `sed -n "<n>p"` against
`13-ARCHITECTURE-CANDIDATES.md`; one citation (`[L:1002]`) was wrong on first write and was
corrected to `[L:998-999]`. Every `[S]` line number was verified against the file.

**Reproduce everything here:**

```
python platform/architecture/_mkt_measure.py    # substrate inventory
python platform/architecture/_mkt_measure2.py   # tracked-vs-untracked, ref normalization
python platform/architecture/_mkt_measure3.py   # plugin/marketplace planes the catalog names
python platform/architecture/_mkt_measure4.py   # normalization ladder + payload sizing
python platform/architecture/_mkt_measure5.py   # FAIRNESS CONTROL on the sibling's claim
python platform/architecture/_mkt_measure6.py   # profile= settling probe (with both-state controls)
python platform/architecture/_mkt_measure7.py   # license surface of the committed manifest
```

---

## 0. Does this architecture discard Wave 1? — No. Counted.

**It discards nothing. Zero deletions. It is additive, and it is the only candidate whose spine is
already half-built inside Wave 1.**

> **DRIFT DISCLOSURE — read before trusting any file count below.** Sibling architecture units
> are writing into `platform/lib/` and `platform/architecture/` **concurrently with this unit**.
> I watched `platform/lib` on-disk runtime `.py` go **20 → 27** and its probe scripts **23 → 34**
> inside one session. On-disk counts are therefore a moving target; **git-tracked counts are the
> stable ones** and are what this table uses. Where a number is disk-only I say so. This is the
> concurrent-work invariant trap from `rules/common/single-signal-verification.md` — an equality
> to a snapshot is self-falsifying while a peer is committing.

| verdict | what | count `[M]` |
|---|---|---|
| **REUSE unchanged** | `platform/schema/*.schema.json` | **8 git-tracked at HEAD + 1 untracked = 9 on disk** (352,723 B). The brief's "8 schemas" is the *tracked* count and is correct; the 9th, `artifact-class-profiles.schema.json`, is the substrate sibling's, still uncommitted |
| **REUSE unchanged** | `platform/lib` runtime modules (`.py`, excl. `_*`/`test_*`) | **19 git-tracked** (of 44 tracked `.py`: 19 runtime + 7 `test_*` + 18 `_probe`/`_gen`). 25 further `.py` are untracked on disk right now — sibling drift, not payload |
| **REUSE unchanged** | `platform/lib` test suite | **475 tests collected in 2.13 s** |
| **REUSE unchanged** | `platform/council/protocols/*.councilspec.json` | **48** (dir holds 52 files) |
| **REUSE unchanged** | `platform/council/presets/*.councilspec.json` | **69** (dir holds 94 files; 25 are lane build scripts + status, not payload) |
| **REUSE unchanged** | `platform/registry/workflow-candidates-*.json` | **7 files / 164 candidate rows** (863,779 B) |
| **REUSE unchanged** | `command-center/WORK-UNIT-CATALOG.json` | **2,007 `work_units` + 103 `items`** |
| **REUSE unchanged** | `command-center/schema/` generated `$ref` shims | **233** (262,248 B) |
| **REUSE, PROMOTED to load-bearing** | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | **2** (already git-tracked at HEAD) |
| **REWRITE (1 file)** | `.claude-plugin/marketplace.json` — flat `skills[]` array of **379** entries → typed multi-package index | **1** |
| **ADD** | the **40** schema files the catalog already declares and that do not exist | **40** |
| **ADD** | publisher CLI, linter, scaffolder, lockfile, fixture marketplace `[SPEC:10983]` | ~6 tools |
| **DELETE** | — | **0** |

Reused artifact files (git-tracked basis): **8 + 19 + 48 + 69 + 7 + 1 + 2 = 154 tracked**, plus
**234 on disk but uncommitted** (233 shims + `artifact-class-profiles.schema.json`) = **388**.
Rewritten: **1**. Deleted: **0**. The "234 uncommitted" figure is itself a migration finding, not
an accounting nicety — see FM-2.

The 40 additions are not my invention. They are named, today, inside
`command-center/WORK-UNIT-CATALOG.json` by 41 work units, and **none of them exists on disk** `[M]`:

```
$ python platform/architecture/_mkt_measure5.py
  composite units: 41
  composites whose SECOND schema survives parse_schema_ref(): 0 / 41
  distinct second-half schema paths: 40
  ... of which have NO artifact on disk: 40
      NO-ARTIFACT: .claude-plugin/marketplace.schema.json
      NO-ARTIFACT: .claude-plugin/plugin.schema.json
      NO-ARTIFACT: CycloneDX 1.5 JSON schema
      NO-ARTIFACT: in-toto attestation predicate schema
      NO-ARTIFACT: tools/marketplace/schema/advisory.schema.json
      ... (18 under tools/marketplace/schema/, 18 under tools/plugin/schema/)
```

**18 + 18 + 2 + 2 = 40.** `tools/plugin/` and `tools/marketplace/` do not exist as directories at
all (`exists=False files=0`) `[M: _mkt_measure3.py]`.

---

## 1. Design

### 1.1 The one-sentence thesis

**The package registry is the control plane.** Not a config file (A1), not a generator (A2): every
artifact class this platform produces — schema, council protocol, preset, workflow definition,
work-unit catalog, receipt — becomes a *versioned, hash-pinned, licensed, provenanced entry in one
registry index*, and **every consumer resolves through the index instead of through a filesystem
path**. Publishing is the gate; the gate is the 12-condition receipt predicate Wave 1 already built.

### 1.2 Why this is not a greenfield proposal: the resolver already exists

The strongest concrete fact in this architecture's favour is that the substrate sibling built the
first half of it without naming it. `platform/lib/schema_resolver.py` is already a
**registry-backed content resolver**, not a path opener:

- `load_registry(path=REGISTRY_PATH)` `[S:124]` — loads a registry document, not a directory scan
- `build_registry() -> Registry` `[S:156]` — constructs a `referencing.Registry`
- `_retrieve(uri) -> Resource` `[S:135]` — a URI retrieval hook with a **containment check** at
  `[S:147]`: `if not str(target).startswith(str(REPO_ROOT.resolve()) + os.sep)`
- `resolve(output_schema, ...) -> ResolvedSchema` with `shim_exists` / `physical_exists` /
  `resolves` properties `[S:88-104]` — i.e. a **logical→physical indirection with an existence
  predicate**, which is exactly a package resolver's core
- a `BASE_URI` and `validator_for(output_schema)` `[S:227]`

Marketplace-first is the *generalisation of that one file* from `artifact_class == schema` to all
artifact classes. Concretely: `ARTIFACT-CLASS-REGISTRY.json` becomes `REGISTRY-INDEX.json`; the 234
logical schema paths become N logical *package* paths; the 3-entry
`physical_control_plane` becomes a lockfile.

**Confidence that this reuse is real and not rhetorical: *almost certain* (90-99%)** — it is five
named functions in one 300-line file I read at `platform/lib/schema_resolver.py`.

### 1.3 The concrete file layout (real paths in this repo)

```
.claude-plugin/
  marketplace.json          REWRITTEN: registry index. Today = 1 plugin + a flat skills[379].
                            After  = N typed package entries, each {name, version, source,
                            sha256, license{spdx,notice_required}, provenance, permissions,
                            platform_compat, payload_allowlist_ref, conformance_score,
                            benchmark_evidence_ref, deprecation}
  plugin.json               UNCHANGED shape; version becomes the release coordinate
  marketplace.schema.json   NEW (declared by IMP-0006, missing)
  plugin.schema.json        NEW (declared by IMP-0006, missing)

tools/marketplace/schema/   NEW — 18 files, every one already named by a work unit:
  registry-api · registry-event · publisher · signature · trust-policy · permissions
  dependency · lockfile · advisory · disclosure-state · moderation · governance-policy
  quality-score · benchmark-evidence · collection · lint-report · offline-bundle
  install-handoff

tools/plugin/schema/        NEW — 18 files, likewise:
  payload-allowlist · payload-inventory · compatibility · conformance-report
  deploy-provenance · divergence-decision · drift-classification · error-taxonomy
  exec-policy · failure-policy · health-report · log-record · migration-ledger
  migration-step · probe-control · projection-map · secret-finding · txn-journal

tools/marketplace/          NEW tooling (spec 10983): linter, publisher CLI, scaffolder,
                            local validator, fixture marketplace
platform/lib/               UNCHANGED (19 tracked runtime modules); schema_resolver.py gains a
                            package-class branch, no signature change
command-center/schema/      UNCHANGED (233 shims) — becomes a *generated package* pinned by
                            sha256 in the lockfile
platform/council/           UNCHANGED (48 protocols + 69 presets) — become 2 packages
platform/registry/          UNCHANGED (164 rows) — becomes the *upstream* candidate index
```

### 1.4 The packages, sized from disk `[M: _mkt_measure4.py]`

| package | payload | files | bytes |
|---|---|---|---|
| `pkg/platform-schema` | `platform/schema/*.schema.json` | 9 on disk / 8 tracked | 352,723 |
| `pkg/platform-lib` | runtime `.py` only (excludes every `_probe`/`_gen` script) | 19 tracked | (44 tracked `.py` total) |
| `pkg/council-protocols` | 48 `.councilspec.json` | 48 | (dir 52 f / 758,076 B) |
| `pkg/council-presets` | 69 `.councilspec.json` | 69 | (dir 94 f / 1,236,275 B) |
| `pkg/schema-substrate` | generated shims | 233 | 262,248 |
| `pkg/workflow-registry` | candidate index | 7 | 863,779 |
| `pkg/skills` | enumerated skill dirs | 379 | (`skills` 1,721 f / 11,183,177 B) |

### 1.5 Control planes — singular, per the spec's own hybrid rule `[SPEC:10907]`

Exactly three, and each has one owner:

1. **Identity/version plane** — `.claude-plugin/marketplace.json`. Answers *what exists, at what
   version, under what license, from what provenance.*
2. **Integrity plane** — `tools/marketplace/schema/lockfile.schema.json` + a `sha256` per package.
   Answers *are the bytes the ones that were certified.*
3. **Acceptance plane** — `platform/schema/receipt.schema.json` + `completion_predicate.py`
   (12 conditions, 65 tests). Answers *may this version be published at all.*

Plane 3 already exists and passes. That is the reuse: **a package version is publishable iff every
unit that produced its payload emitted a receipt that clears the 12-condition gate.** The spec's
completion predicate `[SPEC:10743-10756]` becomes the publish gate verbatim — condition 11
("output was registered in the artifact manifest") and condition 12 ("downstream consumers can read
it") are *already* registry conditions that today have no registry to check against.

### 1.6 Why the spec demands this lane regardless of who wins

Phase 4 `[SPEC:10909-10932]` mandates schema-checking a **plugin manifest, marketplace manifest,
package metadata, permission model, versioning rules, migration rules, rollback contract,
compatibility matrix, and release policy**. Phase 5 `[SPEC:10936-10954]` mandates building the real
plugin. Phase 6 `[SPEC:10956-10983]` mandates *canonical registry, publisher identity, channels,
dependency metadata, permissions, provenance, signatures, SBOM, license metadata, vulnerability
status, quality score, benchmark evidence, lockfile, deprecation/revocation, federated mirrors,
offline export/import, moderation, advisory flow, governance model* — plus a linter, publisher CLI,
scaffolder, validator, and fixture marketplace.

Measured against the catalog: **Phase 5 = 79 units, Phase 6 = 64 units, total 143 of 2,007
(7.1%)**, and **47 units** name a plugin/marketplace artifact in `output_schema` or `output_path`
`[M: _mkt_measure3.py]`. An architecture that treats packaging as an afterthought is declining
7.1% of the owner's own program.

---

## 2. Cost and complexity analysis

### 2.1 The honest headline cost: ~5× the schema surface Wave 1 built

Wave 1: 8 schemas (9 today) + 5 lib packages → **444 tests** (475 at HEAD). That is **≈55 tests per
schema**. This architecture adds **40 schemas**. At Wave-1 density that is **≈2,200 new tests**.

I do not believe all 40 need equal test mass — a `log-record.schema.json` is not a
`receipt.schema.json`. But the order of magnitude is right and I will not hide it: **the contract
surface this architecture requires is roughly five times the one Wave 1 spent 444 tests on.**
Confidence in the ≈2,200 figure as an *upper bound*: *likely* (55-80%). UNVERIFIED whether a
thinner per-schema test budget still kills the mutations in §6.3 — the settling experiment is to
build `lockfile.schema.json` + `payload-allowlist.schema.json` first with a minimal battery and
measure whether the four §6.3 mutations die.

### 2.2 Where the complexity actually lands

| axis | cost | evidence |
|---|---|---|
| Contract authoring | 40 schemas + 40 conformance batteries | `[M]` 40 declared-missing |
| Payload boundary | **excluding** `_probe`/`_gen` scripts is now load-bearing: HEAD `833fb1ea` is literally *"stop tracking agent probe scripts — they are scratch, not deliverables"* and added `command-center/_*.py` to `.gitignore`. `platform/lib` still tracks 18 such scripts | `[M]` |
| Tooling | linter + publisher CLI + scaffolder + validator + fixture marketplace | `[SPEC:10983]` |
| Payload curation | `tools/` is **6,443 files, of which 3,733 are `node_modules` and 474 are caches → only 2,236 (34.7%) shippable** | `[M: _mkt_measure5.py]` |
| Licensing remediation | root `LICENSE`/`COPYING`/`NOTICE` = **NONE** | `[M: _mkt_measure7.py]` |
| Registry maintenance | 379 hand-listed skill paths in one JSON file | `[M]` |
| Resolver change | one branch in `schema_resolver.py`; **no signature change** | `[S:161]` |

The payload number is the one people underestimate. `[SPEC:10954]` says *"Never ship the
repository's `.git`, unrelated caches, logs, transcripts, credentials, or gigabytes of unrelated
content as the plugin artifact."* Today there is nothing that enforces it — `payload-allowlist`
and `payload-inventory` are declared by `IMP-0001`/`IMP-0005` and **do not exist**. A naive package
of `tools/` ships **65,788,500 bytes** including 3,733 `node_modules` files.

### 2.3 What it costs *nothing*

- No new runtime. Rides the existing `.claude-plugin` loader and the existing resolver. Anchor-compliant
  `[L:127]`: *"A3 marketplace-first · rides existing bus: yes (plugin loader is native) · reintroduces
  a rejected component: no · **PASS**"*.
- No change to `platform/lib`'s 19 tracked runtime modules or its 475 collected tests.
- No change to the 117 councilspecs, the 2,007 catalog units, or the 233 shims.

---

## 3. Failure-mode analysis

### FM-1 — Registry index is a single point of total failure (severity P1)

One malformed `.claude-plugin/marketplace.json` unresolves every package. Today that file is
**379 hand-maintained path strings**; one wrong path and the payload is silently short.

Partial mitigation already on disk: `schema_resolver.py:147` refuses any retrieval outside
`REPO_ROOT`. Required addition: `registry-api.schema.json` + a linter that asserts *every* enumerated
path exists. **Measured proof this fires today:** my own first-pass scanner reported
"346 paths missing on disk" — a real self-contradiction against an independent tree-walk that found
49 `LICENSE` files under `.agents/skills`. Root cause was my bug (`lstrip("./")` also eats the dot of
`.agents`), fixed and documented in `_mkt_measure7.py`. The lesson stands for the *linter*: a
path-existence check over 379 entries is exactly where an off-by-one-character normalisation bug
becomes a silent short-ship.

### FM-2 — Generated-artifact drift on the 233 shims (severity P1)

`command-center/schema/` holds **233 files on disk and 0 git-tracked** `[M: _mkt_measure2.py]`.
It is **not** gitignored (`git check-ignore -v command-center/schema/receipt.schema.json` → exit 1,
no match), so these are simply uncommitted new files. Nothing on disk detects divergence between
`_gen_schema_substrate.py` and the 233 shims it produced.

Marketplace-first's answer is a lockfile `sha256` per generated package, so drift becomes a hard
install failure. Without it, the P1 the substrate sibling closed can silently re-open. **Settling
probe:** re-run `_gen_schema_substrate.py` into a temp dir and diff against
`command-center/schema/`.

### FM-3 — Blanket-license misstatement (severity P0 for publish, P3 for local use) — CONFIRMED

See §4.2. This is not hypothetical; it is committed at HEAD.

### FM-4 — Payload bloat / secret leakage through the registry (severity P1)

Beyond the `node_modules` count in §2.2: the registry rows themselves embed local filesystem
topology. Measured, a `license` value in `platform/registry/workflow-candidates-*.json` contains
`git --git-dir C:/Users/Prekzursil/.claude/harness-restore-20260806/main-mirror.git ls-tree ...`
`[M]`. Publishing the registry publishes the owner's absolute paths. `secret-finding.schema.json`
is declared by `IMP-0004` and does not exist.

### FM-5 — `profile=` silent widening: untyped silence at the package boundary (severity P1) — CONFIRMED

This is the most important failure mode in the document because it is **live, measured, and
undetected by the existing gate**.

**118 work units** declare `output_schema` of the form
`command-center/schema/receipt.schema.json profile=council-runtime-module (required: unit_id,
artifact_paths[], ...)`. There are **30 distinct profile names**. `artifact-class-profiles.schema.json`
has **295 `$defs`**. Overlap: **0 of 30** `[M: _mkt_measure6.py]`.

All 118 resolve to the *generic* core:

```
profile=council-runtime-module      -> physical=platform/schema/receipt.schema.json  frag=#/$defs/receipt_core
profile=council-participants-module -> physical=platform/schema/receipt.schema.json  frag=#/$defs/receipt_core
... (8 sampled, all identical)
```

**Detector controls, both directions, run in the same script:** Control A — a known-present
`$defs` key (`AdapterConformanceReport`) reports `True`. Control B — `zzz-not-a-real-profile`
reports `False`. `detector usable: True`. So the `0 of 30` is not a broken matcher.

Consequence: for **118 of 2,007 units (5.9%)** the declared per-profile required-field contract is
accepted-by-widening. A publish gate that trusts "schema-valid" green-lights receipts that omit
every field their own unit declared mandatory. This is hazard **H-h "untyped silence"** `[L:111]`
reappearing at the package boundary — *"an architecture that does not make silence typed is an
architecture that cannot tell you it is broken"* `[L:73]`.

### FM-6 — Loader coupling for hooks is unproven (severity: blocking probe, not a step)

`[L:377-378]`: *"Prove the loader can register the `_dispatch` battery — **this is a blocking probe,
not a step**."* I did **NOT** run it. **NOT-CHECKED.** Confidence the loader can host a PreToolUse
battery with per-check budgets: *roughly even* (40-60%), inherited from `[L:322]` and not
independently raised. Settling experiment: install a scratch plugin carrying a `hooks/hooks.json`
into a throwaway `CLAUDE_CONFIG_DIR` and check whether the handler fires.

### FM-7 — 1,021 units target a directory that does not exist (severity P3, informational)

`command-center/receipts/` is the `output_path` prefix for **1,021 of 2,007 units** and has
**0 files / does not exist** `[M: _mkt_measure3.py]`. This is write-on-first-use and is *not* a
defect — but it means condition 11 of the completion predicate ("registered in the artifact
manifest") has never been exercised at scale. Flagging it so nobody reads the empty directory as
evidence of anything.

---

## 4. Security review

### 4.1 The threat model shifts from "drift" to "supply chain"

A marketplace is a *code-execution distribution channel*. `AGENTS.md §9` already names the class:
*"A `.codex/`, `.claude/`, `.mcp.json`, hooks, or an `AGENTS.md`/`CLAUDE.md` in a freshly cloned or
untrusted repo may auto-load config **and hooks** the moment an agent runs inside it."* The
committed `.claude-plugin/marketplace.json` enumerates **379 skill directories** — 379 auto-loaded
prompt surfaces per install. `[L:371]` puts it correctly: A3 *"makes that class of surface
load-bearing."*

### 4.2 CONFIRMED license defect in a committed manifest

Two mechanically independent signals, plus a classifier with both-state controls.

```
$ python platform/architecture/_mkt_measure7.py
  root LICENSE/COPYING/NOTICE: NONE            (control: README.md present -> True)
  plugin name : agent-skills-toolchain version 0.3.0
  declared license : MIT
  skills enumerated: 379    by source root: {'.agents': 346, 'skills': 3, 'skills-claude-only': 30}
  skill dirs WITH a LICENSE file : 49
  skill dirs WITHOUT one         : 330
     permissive:Apache-2.0    31
     permissive:MIT           18
  COPYLEFT / SHARE-ALIKE payload entries: 0
  DETECTOR CONTROLS
    A KNOWN-PRESENT CC BY-SA -> [('COPYLEFT/SHARE-ALIKE', 'CC-BY-SA')]
    B KNOWN-PRESENT MIT      -> [('permissive', 'MIT')]
    C KNOWN-ABSENT  noise    -> []
```

The `49` is corroborated by an independent tree-walk that counted `49` `LICENSE` files under
`.agents/skills` without reading the manifest at all.

**Findings:**

1. **The repo root has no LICENSE.** `[SPEC:10969]` requires license metadata; the registry's own
   rows say `redistributable: False` and *"no-declared-license (all-rights-reserved by default)"*
   `[M]`. Publishing is therefore not merely un-governed, it is not lawful. **CONFIRMED.**
2. **31 payload entries are Apache-2.0** and the aggregate declares `"license": "MIT"`. Apache-2.0
   requires NOTICE preservation and carries patent terms MIT does not. The declared license
   misstates the aggregate. **CONFIRMED.**
3. **My own "0 copyleft" is a detector artifact, not a clean bill of health.** The classifier only
   reads `LICENSE`/`COPYING`/`NOTICE` *files*. `.agents/skills/trail-of-bits-re/` contains **only
   `SKILL.md`** — no LICENSE file — and that body says, at `SKILL.md:15-16`: *"Licensed **CC BY-SA
   4.0** (attribution + share-alike; keep the attribution if you fork a rule/skill)"*, repeated at
   `:108-109`. So a **share-alike copyleft** entry sits inside a package declaring MIT, and a
   file-presence scanner reports it clean. Real copyleft exposure is **≥ 1 and otherwise UNKNOWN**
   across the 330 undeclared dirs. The settling experiment is a body-scan of all 379 `SKILL.md`
   frontmatter+prose for license strings — **NOT-CHECKED** in this unit.

This is simultaneously the strongest *pro*-marketplace-first argument (only this lane's contracts —
`publisher`, `signature`, `trust-policy`, `advisory`, SBOM, license metadata — detect it) and a
real cost this architecture must pay before its primary verb is legal.

### 4.3 Integrity controls: all four are declared and all four are missing

`signature.schema.json`, `publisher.schema.json`, `trust-policy.schema.json`,
`advisory.schema.json` — declared by work units, **0 exist** `[M]`. Today's publish path has zero
integrity control: no signing, no publisher identity, no revocation, no advisory flow.

### 4.4 What is already secure and should be preserved

- **Path containment** at `schema_resolver.py:147` — a retrieval hook that refuses to leave
  `REPO_ROOT`. Reuse verbatim for package retrieval; do not re-derive it.
- **Reversibility.** `claude plugin disable --scope user` `[L:322]`, plus version-pin rollback,
  which `[L:361]` calls *"the cleanest rollback story of any candidate and the only one that
  survives a corrupted live tree."* Under the binding PR-ONLY release mode this reduces to
  "revert the lockfile entry", which is still the cheapest rollback in the tournament.
- **Secrets.** No credential was read, printed, or modified by this unit. The registry's absolute-path
  leak (§FM-4) is topology, not credentials.

---

## 5. Migration design from today's state

Five stages. Stage 0 and Stage 1 are gates, not steps — if either fails, this architecture loses the
deployment axis and should be reduced to its contract half (see §7).

### Stage 0 — GATE: legal precondition (blocks all publishing)

Root `LICENSE` decision + per-entry SPDX + NOTICE for the 31 Apache-2.0 entries + resolution of the
share-alike entry. **This is an owner decision, not an engineering task**, and no amount of tooling
substitutes for it. Until it clears, the architecture runs in *local-registry* mode: index +
lockfile + resolver, no publish. Everything in stages 2-4 still delivers value in that mode.

### Stage 1 — GATE: the loader probe (FM-6)

Install a scratch package carrying `hooks/hooks.json` into a throwaway `CLAUDE_CONFIG_DIR`; assert a
handler fires with a per-check budget. **NOT-CHECKED.** If it fails, the deployment axis goes to
A11-style content-addressed deploy and this lane keeps only the contract plane.

### Stage 2 — Land the 40 contracts, ordered by what they unblock

1. `payload-allowlist` + `payload-inventory` — closes the 65.8 MB / 3,733-`node_modules`
   bloat and satisfies `[SPEC:10954]`. Cheapest, highest immediate value.
2. `lockfile` — turns the 233 untracked shims from drift (FM-2) into a hash-pinned generated
   package.
3. `registry-api` + `.claude-plugin/{plugin,marketplace}.schema.json` — makes the 379-entry index
   validatable (FM-1).
4. `permissions` + `exec-policy` + `trust-policy` + `signature` + `publisher` — the security plane
   (§4.3).
5. The remaining 27.

### Stage 3 — Fix FM-5 *before* extending the index

Give the 30 declared profile names real `$defs` in `artifact-class-profiles.schema.json`, and make
`parse_schema_ref` **fail** rather than widen on an unknown profile. `receipt_schema_gate.py:216`
is the exact line:

```python
head = text.split(" profile=")[0].split(" + ")[0].split(" (")[0].strip()
```

and its docstring at `:213` is honest about the scope: *"Only the receipt-schema part is
returned."* The fix is not to blame that function — it does what it says — but to add the
strict-mode caller that refuses an unmapped profile.

### Stage 4 — Rewrite the index and generate packages

`marketplace.json`: flat `skills[379]` → typed package entries with sha256 + SPDX + provenance.
Generated by a builder from the trees already on disk, so the 379 hand-maintained strings stop
being hand-maintained.

### What migration does NOT touch

`platform/schema` (9 on disk / 8 tracked), `platform/lib` (19 tracked runtime modules / 475
collected tests), `platform/council` (117
councilspecs), `platform/registry` (164 rows), `command-center/WORK-UNIT-CATALOG.json` (2,007 +
103), `command-center/schema` (233 shims). **Zero edits, zero deletions.**

Note for the migration record: `platform/schema/receipt.schema.json` on disk is **not** raw-byte
identical to `HEAD` (37,715 vs 36,940 bytes) but **is** identical after LF normalisation — 775 CRLF
on disk, 0 in the blob `[M]`. The sibling's "byte-identical to HEAD" is correct in substance; the
775-byte delta is line endings, per `rules/common/windows-shell.md §8b`. Any lockfile `sha256` must
therefore hash the **normalised** bytes or it will report false drift on every Windows checkout.
That is a concrete design constraint this architecture must honour and a real trap it introduces.

---

## 6. Test design

### 6.1 Reuse Wave 1's harness shape verbatim

Wave 1's probes already emit terminal states (`SUCCESS:substrate-bothstates`,
`SUCCESS:substrate-receipts`, `SUCCESS:substrate-selfaudit`, `SUCCESS:schema-resolver-audit`). New
gates follow the same contract: `SUCCESS:<id>` / `FAILED:<id> <reason>`.

### 6.2 Conformance layer (deterministic, no LLM judgement)

Per `fan-out-contract §C4` — if an exact algorithm answers it, write the algorithm:

| gate | assertion | id |
|---|---|---|
| index-validity | every entry validates against `registry-api.schema.json` | `mkt-index` |
| path-existence | every enumerated payload path exists (see FM-1) | `mkt-paths` |
| lockfile-integrity | recomputed sha256 (LF-normalised) == pinned | `mkt-lock` |
| payload-allowlist | 0 `node_modules`, 0 cache, 0 `.git`, 0 transcript paths | `mkt-payload` |
| license-completeness | every entry has an SPDX id; NOTICE present for every Apache-2.0 | `mkt-license` |
| profile-completeness | every `profile=<n>` maps to a real `$defs` | `mkt-profile` |

### 6.3 Mutation battery — four mutations, each must go red

Wave 1 killed 12/12 predicate mutations with an independent control. The publish-gate equivalents:

| # | mutation | required outcome | status today |
|---|---|---|---|
| M1 | flip one byte of a pinned `sha256` | install FAILS | **would survive — no lockfile exists** |
| M2 | delete NOTICE from an Apache-2.0 entry | license gate FAILS | **would survive — no gate exists** |
| M3 | add a `node_modules/` path to a payload | allowlist gate FAILS | **would survive — no allowlist exists** |
| M4 | declare `profile=zzz-nonexistent` | resolver FAILS, not widens | **SURVIVES — measured 118/118 widen** |

M4 is not a hypothetical: it is the current behaviour for 118 real units. **This is the single
test I would write first**, because it is the one mutation I can already prove survives.

### 6.4 Both-states discipline on every new gate

Per `rules/common/single-signal-verification.md §3b`, no gate ships until it has been run against a
**known-broken** fixture and observed to FIRE. Wave 1's `platform/schema/examples/substrate/`
already holds 4 valid + 4 malformed receipts — the pattern is on disk; extend it with a fixture
marketplace (`[SPEC:10983]` requires one anyway).

My own license classifier is the worked example of why this matters: Controls A/B/C pass, and it
*still* reports 0 copyleft for a tree containing a CC BY-SA entry, because the *input surface*
(LICENSE files only) is wrong. A gate whose controls pass can still measure the wrong thing.
`mkt-license` must therefore scan `SKILL.md` bodies, and its known-broken fixture must be
`trail-of-bits-re`.

### 6.5 Reproducible-build test

Install from clean into a scratch `CLAUDE_CONFIG_DIR`, then run
`python platform/lib/schema_resolver.py --audit` and require the same
`references_resolving: 2007 / references_unresolved: 0`. `[L:373-374]` is right that this would be
*"the first time the estate would have a reproducible harness build."*

---

## 7. STRONGEST ADVERSARIAL REFUTATION OF THIS ARCHITECTURE

I will state the argument that kills it as strongly as I can, and then say plainly whether it does.

### 7.1 The refutation

**Marketplace-first is a distribution answer to a contract problem, its own primary verb is
currently illegal, and the release channel it needs has been closed by owner decision.** Two of
those three are measured on disk by me; the third (the closed channel) is `[B]` brief-asserted and
I flag it as such rather than borrowing its authority — saying "all three are measured" would be
exactly the overclaim §7.3 warns about.

**(a) Nothing that actually hurt in this program is a packaging defect.** The measured defect
inventory is: 0 of 234 declared schema paths resolving (the P1 — fixed by a `$ref` shim tree, not by
a registry); 96 completion sentinels not naming their own unit; 41 unresolvable dependency refs;
128 non-canonical `assigned_model_vendor_role` shapes; strict-profile conformance 1,679/2,007. Not
one of those is fixed by a lockfile, a publisher identity, a moderation flow, or a federated mirror.
The estate is **one user, one machine, one clone**. Nobody installs this. `[L:385-390]` says it
better than I can: *"It is a product answer to an estate problem. There is one user, one machine,
and the measured pain is drift and silence — neither of which the plugin loader addresses."*

**(b) The architecture cannot perform its own primary verb.** Publishing requires a license basis
and there is none: root `LICENSE`/`COPYING`/`NOTICE` = **NONE**; the registry's own rows read
`redistributable: False`; 31 Apache-2.0 payload entries are aggregated under a declared `MIT`; and at
least one entry (`trail-of-bits-re`) is **CC BY-SA 4.0 share-alike**. An architecture whose central
act is blocked by a precondition it cannot fix by engineering is not an architecture, it is a
backlog item.

**(c) The release channel is closed by binding owner decision** `[B — orchestrator brief, not
independently re-derivable from disk in this repo]`. Release mode is **PR-ONLY**.
Program stopping condition 13 ("release/canary succeeds") is already declared UNSATISFIABLE as
literally written and reinterpreted as "a merged PR plus a local rollback rehearsal". A marketplace
with no publish channel is a directory with extra JSON.

**(d) The cost is the worst in the tournament for the value delivered.** ~2,200 tests and 143 work
units (7.1% of the program) to build publisher CLIs, moderation and dispute processes, advisory
flows, and federated mirrors **for an audience of one** — while `M4`, a *contract* defect affecting
118 units that I can prove survives today, costs perhaps 30 lines to close. `[L:998-999]` ranks it
**A3 ninth of eleven** on leverage: *"A10 > A9 > A2 > A7 > A6 > A4 > A11 > A8 > A3 > A5 > A1."*

**(e) It imports the loader's failure modes wholesale.** `[L:387-389]`: `installed_plugins.json`
already has 5 sibling copies including a `.corrupt-NUL-20260720` and two live `.tmp.<hex>` orphans;
230,181 files of plugin cache; an unregistered marketplace clone shipping its own `hooks/`. Betting
harness availability on that machinery to gain multi-machine distribution nobody asked for is a poor
trade.

**(f) And the loader probe that would even permit it has not been run.** FM-6 is NOT-CHECKED at
*roughly even* odds. Advocating an architecture whose enabling precondition is unmeasured is
advocating a coin flip.

### 7.2 Does it kill the design? — Yes, half of it. I concede that half.

**REFUTED, and I am not defending it: the deployment/distribution half.** Multi-machine
distribution, moderation, dispute process, federated mirrors, publisher reputation, a public
channel — for this estate these are **dead weight**. Arguments (a), (c), (d) and (e) are each
independently sufficient, they are measured rather than asserted, and (f) means I cannot even claim
the mechanism works. Marketplace-first must **lose the deployment axis** — to A11-style immutable
content-addressed deploy, or to plain A1 config-first. I am not going to argue that a one-user
estate needs a moderation flow.

**NOT REFUTED: the contract/provenance/integrity half.** Three falsifiable reasons the refutation
does not reach it:

1. **The owner's own spec mandates it, in detail, twice.** `[SPEC:10909-10932]` (Phase 4) and
   `[SPEC:10956-10983]` (Phase 6) enumerate manifest schemas, permission model, provenance,
   signatures, SBOM, license metadata, lockfile, versioning, migration, rollback, compatibility
   matrix, release policy — and the catalog already encodes **40 schema files** and **143 units** to
   build them. Refutation (a) says "no measured pain"; the answer is that 7.1% of the declared
   program *is* the pain, and declining it is declining the spec. This is the argument I would put
   in front of the judge panel.
2. **The license defect is live at HEAD and only this lane's contracts see it.** A committed
   manifest declares MIT over 31 Apache-2.0 entries and ≥1 share-alike entry, with no root license.
   Refutation (b) says the architecture cannot publish — correct — but it *inverts* into the
   strongest argument for the contract plane: **the reason it cannot publish was invisible until
   this lane's schemas were specified.** A defect you cannot see is worse than a verb you cannot
   perform.
3. **M4 proves the integrity plane has teeth where the current gate does not.** 118 units
   (5.9%) declare per-profile required fields; 0 of 30 profiles exist; all 118 widen to
   `receipt_core`; detector controls pass both directions. That is hazard H-h *inside Wave 1's own
   acceptance gate*. The `mkt-profile` gate closes it. This one is cheap, and it is the reason a
   contract plane earns its place independently of any marketplace.

### 7.3 The verdict I would defend in front of the judge panel

**Marketplace-first should WIN the contract/provenance/integrity axis and LOSE the deployment axis.
It is a component of the hybrid, not the spine.** Concretely: adopt `.claude-plugin/*.schema.json`,
`registry-api`, `lockfile`, `payload-allowlist`, `payload-inventory`, `permissions`, `exec-policy`,
`signature`, `publisher`, `trust-policy`, `license-*`, `provenance`, SBOM — and **drop** moderation,
dispute process, federated mirrors, publisher reputation, collections, and the public channel until
someone other than the owner installs this.

Under `[SPEC:10907]` — *"The winner may be a hybrid only when its control planes remain singular
and understandable"* — that reduction keeps exactly the three planes of §1.5 and discards the
fourth (distribution). Three planes, three owners, no ambiguity.

I would rather commit that than defend a strawman, and per `fan-out-contract §C2` an advocate whose
sentence is wider than their evidence has shipped a defect even when the code is fine. The wide
sentence here would have been *"marketplace-first should win"*. It should not. **Half of it
should.**

---

## 8. Coverage and residuals

**MEASURED (CONFIRMED):** reuse/replace counts · 40 declared-missing schemas with a fairness
control on the sibling's resolver · 41 composites, 0/41 second halves retained · 118 `profile=`
units, 0/30 profiles defined, with both-state detector controls · 379-entry manifest with 49
licensed / 31 Apache-2.0 / 18 MIT / 330 undeclared · no root LICENSE · `trail-of-bits-re` CC BY-SA
at `SKILL.md:15-16` · 233 shims untracked and not gitignored · 3,733 `node_modules` of 6,443 in
`tools/` · 475 tests **collected** · Phase 5/6 = 143 units · 47 plugin/marketplace-naming units ·
receipt LF-identity (775 CRLF on disk, 0 in the HEAD blob, identical after normalisation).

**PARTIAL / scope corrections (not refutations):**
- The brief's *"0 → 234 of 234 declared output_schema paths now resolve"* is correct **for the
  receipt half of every reference**, which is what `receipt_schema_gate.py:213` says it returns. On
  a normalisation that keeps both halves of a composite there are **274 filesystem-shaped logical
  paths, 234 resolving, 40 with no artifact at all**. The normalisation ladder is
  `2,007 refs → 367 raw strings → 305 after '#'-strip → 275 after full normalisation → 234 existing`.
  Not a defect in the sibling's work; a scope boundary the brief's sentence did not carry.
- The brief's *"269 distinct / 1,896 refs"* is also normalisation-dependent; I measure 2,007 refs on
  every ladder rung, so the 1,896 is REFUTED on the reference count.
- Registry candidates: I count **164 rows, 162 with `counts_toward_range != False`**; the brief says
  161. 1-row variance, **UNVERIFIED** which convention is canonical. Settling probe: read each
  slice's own declared total (slice 1's `count_read_back_off_disk = 32`).
- Tree-wide LICENSE count of 113 includes **3 false positives** — `command-center/schema/license-*.schema.json`
  match a `LICENSE*` glob. True count 110.
- The brief's *"8 schemas"* vs my *"9"* is **not a disagreement**: 8 git-tracked at HEAD, 9 on
  disk, the 9th uncommitted. Both statements are true at different scopes; stating either without
  the scope is the overclaim.
- **Every on-disk file count in this document is a moving target.** `platform/lib` runtime `.py`
  went 20 → 27 on disk *during this unit* because sibling architecture units are writing there.
  Load-bearing counts were therefore re-taken on a git-tracked basis (19 runtime, 44 `.py`, 8
  schemas, 272 files under `platform/`). Any reader re-running the probes should expect different
  disk numbers and identical tracked numbers until someone commits.

**NOT-CHECKED (named, with settling experiments):**
- FM-6 loader-hosts-hooks probe. Experiment: scratch `CLAUDE_CONFIG_DIR` install + handler fire.
- Body-scan of all 379 `SKILL.md` for prose license declarations. Experiment: grep each for SPDX /
  share-alike strings; expected to raise the copyleft count above 1.
- Whether a thinner-than-Wave-1 per-schema test budget still kills M1-M4. Experiment: build
  `lockfile` + `payload-allowlist` with a minimal battery and run the four mutations.
- I did **not** run the 475-test suite in this unit; the 475 figure is `pytest --collect-only -q`
  (`475 tests collected in 2.13s`), i.e. a collection count, not a pass count. The pass count is the
  sibling's claim, not mine.

**Files this unit wrote:** `platform/architecture/marketplace-first.md` (this file) and the seven
`platform/architecture/_mkt_measure*.py` probes. **No repo artifact was modified. Nothing was
committed.**
