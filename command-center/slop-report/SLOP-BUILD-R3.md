# SLOP — BUILD lane, round 3

LANE: SLOP (build — implement and commit for real)
REPO: `C:/Users/Prekzursil/source/ast-integrate`, branch `main`
MEASURED AT: `ab3667d5` at lane start → `12f9e861` → `a144c27a` mid-run. **HEAD moved twice
under me inside ~40 minutes**, both times from a sibling lane committing to `main` in this same
worktree, so every number below carries its rev.

If this file still reads as a skeleton with `UNKNOWN - not yet measured`, the unit died before
measuring anything and no verdict here may be cited.

## COVERAGE

| section | state |
|---|---|
| B1 twin-parity guard extended from 7 declared pairs to full-surface discovery | **SHIPPED**, executed, both-states red-proof |
| B1 direction + sync-safety of every divergent pair | **MEASURED**, 3 instruments, one of them self-corrected |
| B2 `platform/` bucket-(b) commit decision | UNKNOWN - not yet measured (this milestone) |
| B3 `$null` deletion | UNKNOWN - not yet measured (this milestone) |
| B4 duplicate-directory proposals | NOT ATTEMPTED — grounding says propose-only, and it already did |
| B5 published-command gate corpus widening | UNKNOWN - not yet measured (this milestone) |
| B6 cache + empty-dir sweep | NOT ATTEMPTED this milestone |
| frozen evidence untouched | UNKNOWN - not yet measured (this milestone) |
| the ~84 non-ruff `quality.yml` steps | NOT-CHECKED — out of this lane's reach, unchanged from grounding |

---

## B1 — the deploy-twin guard now covers 195 pairs instead of 7. SHIPPED.

### What was wrong

`ci/tests/test_deployed_hook_twin_parity.py` guarded **7 hand-listed pairs** out of a surface of
**195**. It passed, and it was doing its job *within its declared set* — which is exactly why the
27 undeclared drifted pairs were invisible. A gate that only looks at what someone remembered to
list cannot report what nobody listed.

### What shipped

The gate now DISCOVERS the surface from `git ls-files` and requires **every** discovered pair to be
byte-identical or DECLARED. Concretely:

| | before | after |
|---|---|---|
| pairs the gate can fail on | 4 | **161** (every identical pair is now a ratchet) |
| declared divergences | 3 | **34** (30 `KNOWN_DIVERGENT` + 2 `TEMPLATED` + 2 `NOT_TWINS`) |
| undeclared divergence detectable | no | **yes** — `test_no_undeclared_divergence` |
| tests | 21 | **125** |

New checks, each one closing a way the old shape could lie:

* `test_no_undeclared_divergence` — the ratchet. Pure core (`undeclared_divergences`) takes an
  injected reader so it is exercised in both states as a unit test, not only against a tree that
  happens to satisfy it.
* `test_twin_surface_discovery_is_plausible` — fail closed below 150 pairs. A discovery that
  returns nothing must not read as a clean surface.
* `test_no_stale_declaration` — a declared row that no longer matches a real twin is flagged.
* `test_templated_pair_differs_only_by_the_token` — `{{USER_HOME}}` is an exemption that must be
  *earned*: same line count, token present on the mirror side, prefix and suffix match, and one
  single consistent expansion. Otherwise "it's just templating" is a free pass anyone could write
  next to a real behaviour change in the same file.
* `test_pinned_pairs_are_not_also_declared_divergent`, `test_declared_rows_are_unique`,
  `test_declared_mirror_path_matches_its_root` — tripwires against a future failure being "fixed"
  by demoting, duplicating, or mis-pathing a row.

**Adding a row to `KNOWN_DIVERGENT` records a divergence; it does not fix one.** Every round-3 row
is prefixed `DRIFT:` and states what was measured, so no reader can mistake the list for approval.
The three pre-existing rows are prefixed `REVIEWED:`.

### Both-states proof — the gate goes RED when it should

125 green tests on a tree that satisfies them is not evidence. `_r3_redproof.py` builds a throwaway
git repo, copies the **real** gate file into it byte-for-byte, and runs it against a known-broken
surface. Nothing touches the live tree.

```
python command-center/slop-report/_r3_redproof.py
```

| probe | expected rc | actual |
|---|---|---|
| fixture repo, twins IDENTICAL → ratchet | 0 | **0** |
| fixture repo, twins DIVERGENT → ratchet | 1 | **1** |
| fixture repo (1 pair) → plausibility floor | 1 | **1** |
| fixture repo (no declared paths) → staleness | 1 | **1** |
| live tree → ratchet / floor / staleness / all 125 | 0 | **0** |

10/10. The ratchet is the only check whose verdict differs between the two fixture states, which is
what makes it a control rather than a smoke test.

### Direction of every divergence — and an instrument I had to correct mid-round

The decision that matters is not "do they differ" but **"can they be reconciled without losing
content"**. Three instruments, run in order:

1. `_r3_twinsurface.py` — enumerate + compare. **195 pairs / 161 identical / 34 differing**,
   independently reproducing the grounding round's counts from a different code path (`git ls-files -z`
   + difflib rather than that lane's probe). 5 controls pass.
2. `_r3_direction.py` — line-multiset set-difference. Reported **30 "two-way"**.
3. `_r3_direction2.py` — difflib opcodes. Reported only **3 two-way**, because a `replace` opcode
   is one edited slot, not two independent additions.

Instruments 2 and 3 looked like a refutation. **They were not, and saying so would have been the
overclaim.** `_r3_synctable.py` names the actual decision variable and resolves it: a `replace` run
means *both sides hold bytes in the same slot*, so it is exactly as content-destroying to sync as an
`insert` is. Under that definition instrument 2's **partition** was right all along and only its
LABEL was wrong; instrument 3 answered a narrower question ("independent additions") and its
`in-place-edit-only` label understated the hazard — `hooks/README.md` carries that label while
holding a 171-line block replaced by a 100-line one.

Final, decision-grade table (4 controls pass, including one proving `replace` is never scored safe):

| sync safety | pairs | meaning |
|---|---|---|
| **needs-human-read** | **30** | each side holds bytes the other lacks; a mechanical sync deletes content |
| safe mirror ← root | 3 | `rules/common/security.md`, `rules/golang/coding-style.md`, `rules/rust/coding-style.md` — mirror is a strict subset |
| safe root ← mirror | 1 | `hooks/memory-guard/test_scan.py` — root is a strict subset |

**This is why the fix is a guard and not a sync.** 30 of 34 cannot be reconciled by a script, and
the fan-out contract's C4 result is that 100% of the errors in exactly this shape of task pointed at
data loss.

### The three divergences worth a human's attention first

| pair | what was measured |
|---|---|
| `hooks/precompact-basicmemory/capture.ps1` | the repo-root copy is a **compatibility shim** whose own docstring says it exists so "an older sync or cached hook definition cannot revive the previous raw conversation capture behavior" — and the agent-self mirror **is** that previous behaviour, ~78 lines of it, still deployed by `agent-self/bootstrap.ps1:38-45`. The shim cannot suppress a copy that a different bootstrap installs over it. |
| `hooks/event-ledger/test_prune_oats.py` | the mirror keeps a 51-line `Section 5b / D-wu-25` outcome-vs-attempt-frequency test the root does not have; the root replaced the ranking assertions with the `D-n01` OBSERVED-ONLY set the mirror does not have. **Reconciling in either direction deletes real test coverage.** |
| `hooks/edit-validate/validate-stop.py` | root `hashlib.sha1(..., usedforsecurity=False)` vs mirror `hashlib.sha256(...)`, at both call sites. |

Scope on the sha1/sha256 item, stated because the grounding round rated it *likely* a
security-relevant defect: both call sites are a wrapper filename and a dedupe signature, i.e.
**non-security uses**, and the root side carries the explicit `usedforsecurity=False` annotation a
linter asks for. On that evidence it reads as a lint-driven edit applied to one tree only, not a
weakening. **UNVERIFIED**: which side changed and whether a review is recorded — settling
experiment unchanged and still unrun, `git log -S "hashlib.sha256" -- <both paths>`.

The `capture.ps1` finding is the one I would rank highest, and it is new this round.

### Evidence

```
python -m pytest ci/tests/test_deployed_hook_twin_parity.py -q     # 125 passed
python command-center/slop-report/_r3_twinsurface.py               # 195/161/34, 5 controls
python command-center/slop-report/_r3_direction2.py                # opcode profile, 4 controls
python command-center/slop-report/_r3_synctable.py                 # sync safety, 4 controls
python command-center/slop-report/_r3_redproof.py                  # both-states, 10/10
```

`python -m pytest ci/tests -q` at `a144c27a` with these changes: **781 passed, 1 skipped, 1 failed**.
The one failure is `test_check_skill_dual_write.py::test_strict_parity_keeps_distinct_invalid_utf8_path_bytes_distinct`,
a Windows-only `UnicodeDecodeError` on a filename byte `0xff`. **Proven pre-existing rather than
argued**: it fails identically in a detached worktree at `HEAD` that contains none of my changes,
and `git status` shows I never touched that file, its fixture module, or `conftest.py`.

---

## B2 · B3 · B5 · frozen evidence

UNKNOWN - not yet measured. This milestone committed B1 only.

## Commits

Milestone 1: the guard extension + its probes. Explicit-path commit, listed in the final section
once landed.
