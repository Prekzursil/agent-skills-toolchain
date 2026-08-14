# P2NEXT — BUILD round 2 (artifact R4): the refuted sentence, and the anchor hole under it

COVERAGE: every claim below names the probe that produced it. Two things stay unmeasured and say
so inline: whether the rail-blocked units would PASS a Codex review, and whether `codex login`
clears agent-identity registration (owner-only credential write, not attempted).

## 0. What round 1 got wrong, and what it got right

A verifier CONFIRMED two must-fixes. One was a false sentence in the owner-facing pricing
paragraph; the other was a residual in the code this lane had just changed. Neither invalidates
the round's DoD — the auditor re-derived all four items independently and they pass — so this
round fixes the two defects and does not re-derive the split.

| id | defect | class | this round |
|---|---|---|---|
| MF1 | "all 449 READY units name a cross-vendor reviewer" | FALSE sentence | measured and rewritten |
| MF2 / D2 | `example.com:443` still passed as a file:line anchor | CODE | closed, both-states proof |
| O1 | "every one of the 52 rows carries verbatim `reviewer_requirement` + `blocked_on`" | overclaim | scoped |
| O2 | "no false positive — LIKELY 55-80%" | UNDER-claim | re-measured, raised |
| O3 | skill counts 347 / 339 / ~10 | ambiguous method | both methods stated |

## 1. MF1 — the sentence was false, the action it described was correct

Round 1 wrote, at `P2NEXT-BUILD-R3.md:186`:

> No READY units were built — all 449 name a cross-vendor reviewer

**REFUTED.** Recorded, not deleted: the same sentence is in the permanent commit message of
`1b1e1e4e`, which cannot be rewritten without a history rewrite this lane is forbidden to perform,
so the correction has to live here and in the artifact rather than in the commit.

Two prior probes disagreed about the true number (auditor 164/285, refuter 163/286), so this is a
third derivation from committed blobs at a pinned rev, with the predicate written out
(`_e1_ready_split.py`, `_e2_ready_vendor.py`). It reproduces the auditor's figures exactly and
explains the refuter's off-by-one.

### The measured split of the 449

`_e2_ready_vendor.py` classifies by the reviewer vendor each requirement DEMANDS, not by the words
it uses. All six detector controls pass before any count prints; a mismatch aborts the run.

| bucket | count | what it means for `codex login` |
|---|---|---|
| `NEEDS_CODEX` — names Codex/openai as a reviewer | **95** | the dead rail is required |
| `CROSS_ANTHROPIC` — cross-vendor clause naming only Anthropic | **49** | all 49 are assigned to openai; a fresh Claude reviewer qualifies **if** the unit is Codex-produced |
| `CROSS_UNDIRECTED` — cross-vendor clause naming no vendor | **20** | resolves to NOT(producer); assigned 10 anthropic / 10 openai |
| `SAME_OR_ANY` — no cross-vendor demand at all | **285** | any fresh independent reviewer qualifies |

`95 + 49 + 20 = 164` carry a cross-vendor clause of some kind, and `285` do not — the auditor's
figures, reproduced. The refuter's 163/286 is one short: two requirement texts occur exactly once
each and say "from the **OTHER vendor**" rather than "cross-vendor", and a predicate keyed on
`cross-vendor|different vendors` catches one of them and misses the other. [likely, 55-80%] on
that specific attribution — the refuter's probe is not on disk, so I am inferring its predicate
from its output; the settling experiment is to re-run their regex over the same 449, which needs
their source. **The count itself does not depend on this** and is [almost certain, 90-99%].

### The part that needs no predicate at all

**33 READY units carry a `reviewer_requirement` BYTE-IDENTICAL to text this lane itself classified
`SATISFIABLE_NOW`** (`_e1_ready_split.py` section D — set membership, no regex, no judgement).
Overlap control: 0 requirement texts appear under both verdicts, so the two classes are disjoint.
This reproduces the refuter's 33 exactly and is the floor that survives any argument about
predicates. The auditor's 28 is a smaller subset by a different rule and is not contradicted.

### The correction, and what it does NOT license

The ACTION was right and lane-mandated: the spec says *do not build more READY units into a dead
rail*. The REASON was false. Restated:

> 95 of 449 READY units name a Codex reviewer outright and 69 more carry a cross-vendor clause
> whose direction depends on who actually produces the unit; **285 carry no cross-vendor demand at
> all**, and 33 of those carry a requirement byte-identical to one this lane already satisfied
> with a fresh-context Claude review. None were built because the lane spec forbids it — not
> because none are satisfiable.

A caveat that cuts the other way and belongs next to the number: naming cross-vendor is not the
same as needing **the dead rail**. The 49 `CROSS_ANTHROPIC` units demand an *Anthropic* refuter,
which a fresh Claude agent supplies — but only while the unit itself is Codex-produced. With the
rail down they would be Claude-produced, at which point the requirement self-defeats and inverts
to openai (`vendor_satisfiability.py` rule 0). So the rail gates PRODUCTION for those, not just
review. [likely, 55-80%]: I measured what the requirements demand and what the catalog assigns,
not what a future execution would do.

## 2. MF2 — a host:port was still a valid file:line evidence anchor

Round 1 closed "anything with a colon and a digit" by requiring the head to name a path, where a
path meant *an extension carrying at least one letter*. The auditor measured the residual: `.com`
and `.io` carry letters, so `example.com:443` and `site.io:8080` still satisfied the evidence
requirement of a CONFIRMED verdict. Same class as the defect just fixed.

*(My brief truncated MF2 mid-sentence at "`.agents/sk`". The only `.agents/skills/**` files this
lane has ever touched are the three claim-verify-gate scripts, and the only CONFIRMED code defect
in them is this one, so I read MF2 as this. [likely, 55-80%] — settled by the refuter's full text,
which is not on disk.)*

### Direction chosen on evidence, not taste

A **TLD blocklist** fails OPEN: the corpus contains `db.internal:5432` and
`postgres.render-internal.com:5432`, which no list of TLDs catches. An **allowlist of file
extensions** fails CLOSED and loudly — an unrecognised extension is rejected and the author adds
the directory. The gate exists to stop non-evidence passing silently, so it takes the allowlist.

### Measured with MECHANICAL ground truth, before shipping

`_e3_anchor_corpus.py` extracts every anchor-shaped head from all 4,972 committed markdown blobs
and calls a head REAL when it resolves to a path `git ls-files` tracks. Byte equality, no
judgement, and conservative in the right direction: every resolving head is certainly a real
anchor. BEFORE is pinned to `5423de0f` and the probe exits 2 if pointed at a state that already
carries the fix.

```
   distinct anchor-shaped heads : 4187
   heads that RESOLVE (ground truth REAL)   : 2568
   REAL accepted BEFORE : 2567/2568        REAL accepted AFTER  : 2568/2568
   REGRESSIONS (real anchors lost): 0 []
   pre-existing false positives FIXED: 1 ['.gitattributes']
   NON-RESOLVING accepted BEFORE : 1204/1619   AFTER : 1193/1619
   newly REJECTED: 11   (turn.cloudflare.com x42, stun.cloudflare.com x18, db.internal,
                         postgres.render-internal.com, edge/region.argotunnel.com, api.com, …)
```

Every one of the 11 newly-rejected heads is a hostname. `.gitattributes` is the reverse direction:
it was a **pre-existing false positive** — 13 characters of extension overflowed the old length
window while the shorter `.gitignore` passed by accident of length. A dotfile is now recognised
structurally instead, because a hostname never begins with a dot.

### Both-states proof through the real CLI (`_e4_hostport_anchor.py`)

```
  ok    A real file:line anchor              old exit 0 (want 0), new exit 0 (want 0)
  ok    B obvious non-evidence (CONTROL)     old exit 1 (want 1), new exit 1 (want 1)
  ok    C host.tld:port (the defect)         old exit 0 (want 0), new exit 1 (want 1)
  ok    D .gitattributes:2 (false positive)  old exit 1 (want 1), new exit 0 (want 0)
```

**B is the control**: it fires in BOTH states, so the anchor rule was demonstrably live while it
was silent on C. Without B, C flipping would be indistinguishable from "the old gate did nothing".
D proves the change is not purely restrictive.

### A mutation SURVIVED, and chasing it correctly meant deleting code

Adding the allowlist made `extension need not contain a letter` survive: the allowlist already
rejects `2` from `v1.2` for the same reason it rejects `com`, so the letter rule had become a
second decision guarding nothing. It was not an *equivalent* mutant either — the two forms differ
on exactly one shape, `x.entitlements:5`, which the old length window rejected **wrongly**.
Writing a test to pin that would have pinned a false negative as desired behaviour.

So the redundant decision was removed from `claim_gate` (the extension regex now just captures the
extension and the allowlist decides), the mutation is RETIRED in place with that reasoning
recorded, and its replacement — mutating the allowlist membership test to `True`, which is exactly
the `host.tld:port` state — is KILLED. Tests 39 → 42, mutations 8 → 9, **9/9 killed**. Measured:
the windowed and unwindowed forms agree on all 4,187 corpus heads, so this is a simplification,
not a behaviour change.

## 3. O1, O2, O3 — the sentences, scoped

**O1.** Round 1: *"every row carries verbatim `reviewer_requirement` + `blocked_on`"*. **REFUTED as
written.** Measured myself, not cited: 9 of 52 rows carry an EMPTY `blocked_on` (ADV-0001, -0006,
-0007, -0014, -0015, -0020, -0021, -0022, -0036), and reading all 9 receipts shows every one has
`failure.blocked_on` = null. The extraction is faithful with 0 data loss; the sentence was wider
than its evidence. Scoped: *all 52 rows carry a verbatim `reviewer_requirement` (52/52 exact
against the catalog); 43 of 52 also carry a verbatim `blocked_on`, and the 9 empty ones are
faithful because their receipts have `failure.blocked_on` = null.*

**O2.** Round 1 rated "no false positive introduced by the anchor rule" at [likely, 55-80%] on a
10-string hand-built corpus. That was an UNDER-claim, and this round's corpus settles it in the
direction of the code: **0 regressions across 2,568 mechanically-verified real anchors**, plus
15/15 on the hand-built set. Raised to [almost certain, 90-99%] **for a separator-less head whose
extension is in the allowlist, or any head containing a path separator**. The residual moved
rather than vanished — see §5.

**O3.** Round 1: *".agents/skills/ holds 347 skills, skills/ projects 339 … about ten canonical-only"*.
The auditor measured 352 / 338 / 12. **Both counts are right; they count different things**, and
the sentence failed to say which:

| method | `.agents/skills` | `skills` | canonical-only |
|---|---|---|---|
| distinct top-level directories | **347** | **339** | **11** |
| `SKILL.md` files | **352** | **338** | — |

The 5-file gap is nested `SKILL.md` under `microsoft-foundry/**` and one template. That is also
why an SKILL.md-path-based diff files `microsoft-foundry` as canonical-only when it is published
(42 tracked files under `skills/microsoft-foundry/`) — the auditor's 12 minus that one is my 11.
The canonical-only set is `claim-verify-gate`, the nine `codex-*` skills, and `qdx-rush`. None of
this changes the load-bearing conclusion, which rests on the per-commit gate runs, not the counts.

## 4. What was NOT done, deliberately

- **No same-vendor review substituted where cross-vendor is demanded.** The 42/10 blocked-set
  split is untouched.
- **No READY units built.** The lane spec forbids it; §1 corrects the reason, not the action.
- **No `codex login`.** Credential write, owner-only (AGENTS.md §9). `auth.json` never read.
- **Condition 11 untouched.** Unchanged and still decisive: all 10 reviewed units remain blocked on
  `manifest_registration.registered`, which `receipt_schema_gate.py:515-527` hard-rejects while
  nothing in production sets it. `codex login` buys review capacity for 42 units and delivers
  zero. The two owner decisions must be priced together.
- **The dual-write blocker not papered over.** `ci/check_skill_dual_write.py --strict-parity` is
  still RED on any commit touching a canonical-only skill, including this one. Pre-existing and
  systemic (green at `5d573583` and `7618a6fa`, red at `d34b74a7`, `00d0a311`, `1b1e1e4e`).
  Escalated in round 1, unchanged here.

## 5. Residuals — disclosed inline, not blocking

1. **The allowlist is a maintenance surface.** A bare-filename anchor whose extension is outside
   the list is now rejected. Measured cost on the corpus: 0. Failure mode is LOUD (the gate reds
   and the author adds the directory or the extension), which is why this direction was chosen.
   Settling experiment: re-run `_e3_anchor_corpus.py` after the next 500 markdown commits and
   check `real_regressions` is still empty.
2. **The corpus is markdown-only.** JSON ledgers were not scanned; their `evidence` fields are the
   population the gate actually runs over. [likely, 55-80%] the result holds there — the previous
   round measured only 3 anchored strings across 2 committed ledgers, so there is little to
   contradict it and little to confirm it.
3. **`CLAIM-REGISTRY.json` uses `verifier_probe`; claim_gate reads `verify_probe`.** Unchanged from
   round 1. UNVERIFIED whether this is drift or two deliberate schemas; not this lane's call.
4. **C5's resolvable-anchor half stays ADVISORY.** 0 of 10 receipts carry a resolving anchor;
   enforcing it would red CI on every existing receipt.
5. **Windows-local green is not CI green.** See §6 for exactly which steps ran.
6. **MF2's identity is inferred**, not read — my brief truncated it. See §2.

## 6. Evidence — commands and their real output

```
python .agents/.../test_claim_gate.py            -> All 42 test functions passed.   (was 39)
python .agents/.../test_claim_gate_mutations.py  -> 9/9 mutations killed             (was 8/8)
python .agents/.../claim_gate.py --self-test     -> OK: all 11 rules fire in the known-broken state.
python command-center/p2-next/_e4_hostport_anchor.py -> 4/4 cases matched, control fires in BOTH states
python command-center/p2-next/_e3_anchor_corpus.py   -> 0 regressions / 2568, 11 newly rejected
python command-center/p2-next/_e1_ready_split.py     -> 449 pop, 33 byte-identical floor, overlap 0
python command-center/p2-next/_e2_ready_vendor.py    -> 95 / 49 / 20 / 285, 6/6 controls ok
```

Gate results, ruff, and the blob check are recorded in §7 once run.

## 7. Gates run this round

Populated at the end of the round; if this section still reads UNKNOWN, no gate verdict here may
be cited.

UNKNOWN - not yet measured.
