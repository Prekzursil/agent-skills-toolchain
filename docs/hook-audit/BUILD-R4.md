---
title: BUILD-R4
type: note
permalink: dqverify-repo-20261013/docs/hook-audit/build-r4
---

# HOOKRESEARCH — BUILD round 4

Round 3 fixed one CONFIRMED defect and four overclaims and closed the verifier's residual. This
round's first duty was to EXECUTE those fixes rather than read them — this lane has twice recorded
"two independent readings agreed because neither executed it" — and only then to build.

What that produced: all six prior items verified by execution, one flagged UNVERIFIED settled
against the lane's own prediction, one round-4 finding REFUTED as a detector artifact, and one
CONFIRMED defect that four rounds had described as cosmetic shown to be output-destroying and then
fixed.

## 1. Re-entry verification — the prior round's fixes, executed

| item | how it was checked | result |
|---|---|---|
| D1 exit-0 claim in `hook-audit.yml` | ran the subject AND a control in one shell | subject **exit 5**, control **exit 0** |
| O1–O4 corrections | `check_citations.py` resolves every marker | 211 checked, 0 unbacked |
| R1 early-return sweep | `_b11_earlyreturn_sweep.py` re-run | reproduces, controls pass |
| `_b10_ci_proof.py` C2 fix | re-run | exit 0 |
| `_b9_format_tracked.py` | re-run | exit 0 |

<!-- uncited-table: reason=re-entry receipts; each is an exit code from a live shell reproduced in this round's evidence section, and the artifact is the command itself, not a JSON blob -->

The D1 reproduction is the one that matters, because it is the claim that was false. I re-ran it
independently rather than trusting the corrected header: `python -m pytest … test_citation_gate.py`
exits **5**, while `test_hook_predeploy_gate.py` exits **0** in the same shell. The control is what
makes exit 5 a property of the subject and not of my environment. Round 3's correction stands.

## 2. Round 2's flagged UNVERIFIED, settled — and its prediction refuted

Round 2 shipped `.github/workflows/hook-audit.yml` and rated it **LIKELY (55-80%)** that it "will
be green on its first real GitHub run", flagging that the only evidence was a local fresh-clone +
redirected-HOME proxy. That is now answerable.

It **has** run on real runners
<!-- cite: id=R4-ci-ran file=B12-CIRUNS.json path=has_ever_run_on_a_real_runner value=True -->,
and it was **not** green on its first runs
<!-- cite: id=R4-ci-first file=B12-CIRUNS.json path=was_green_on_its_first_runs value=False -->.
It went red and needed two further fixes — `fetch-depth: 0` for a pinned historical blob, and a
control that pinned a Windows path frozen inside a blob — before reaching its current green streak.

**The prediction was wrong, and the reason generalises:** a Windows fresh-clone proxy cannot model
a shallow checkout or a case-sensitive Linux path, so it was never evidence about a runner. It
remains a useful pre-push filter and must not be quoted as a CI verdict.

Counts are deliberately **not** pinned here — `runs_seen`, `n_success` and `current_green_streak`
move on every push by any lane, which is the maintenance trap round 3 named in O2. The citable
claims are the two booleans above. Detector control: the history contains both successes and
failures <!-- cite: id=R4-ci-both file=B12-CIRUNS.json path=controls.C2_both_states_present value=True -->,
so a green is distinguishable from a probe that cannot see red; and an unreachable `gh` returns
`FAILED:` rather than "no runs", because an auth failure is a detector failure, never a verdict.

## 3. The CONFIRMED budget-ceiling defect is not cosmetic — measured

Round 4 found `Stop/git-hygiene` declaring a 90 s budget inside a 35 s event budget and called the
surplus "unreachable"; `hook_predeploy_gate.lint_budget_ceiling` encoded that verbatim. Both stop
at "55 s cannot be spent", which reads as untidy bookkeeping. Neither asked what the DISPATCHER
does with an over-ceiling number.

`dispatch.py:360-372` collects checks **sequentially, in manifest order**, each with an **absolute**
deadline of `start + its own declared timeout`:

```
start = time.monotonic()                                    # :360, once, after all threads start
for (chk, _mod, buf, rc_sink), t in zip(loaded, threads):   # :362, MANIFEST ORDER
    budget = float(chk.get("timeout") or 8)                 # :364
    remaining = max(0.0, budget - (time.monotonic() - start))  # :367 absolute deadline
    t.join(timeout=remaining)                               # :368
```

So the declared timeout is not decoration: it is how long `run()` will sit at that index. Per the
vendor contract `timeout` is per-hook-**command**, and our dispatcher is ONE command holding N
checks, so a cancellation lands on the whole dispatcher and every check on that event loses its
output together.

`_b12_joinorder.py` executes the **real** dispatcher (not a re-implementation of the loop) with two
arms that share an identical worker, so the only moving part is the declared budget:

- over-ceiling (6 s declared inside a 2 s ceiling): `run()` **overruns the ceiling**
  <!-- cite: id=R4-jo-bad file=B12-JOINORDER.json path=arms.A_over_ceiling.overran_ceiling value=True -->
- within-ceiling (1 s declared inside the same 2 s ceiling): `run()` **returns inside it**
  <!-- cite: id=R4-jo-good file=B12-JOINORDER.json path=arms.B_under_ceiling.overran_ceiling value=False -->
  and the trailing check is still collected
  <!-- cite: id=R4-jo-fast file=B12-JOINORDER.json path=arms.B_under_ceiling.fast_output_collected value=True -->

Observed wall times were ~5.0 s and ~1.0 s against the 2 s ceiling. Those are **not** pinned as
citations: they move a few milliseconds per run, and pinning a number that legitimately moves is
the defect round 3 recorded in O2 and in `_b10_ci_proof.py`'s C2 anchor. The booleans are the
stable claim.

**Correctly scoped:** an over-ceiling declared budget lets `run()` return after the vendor has
already cancelled the command, so the cost is not 55 unusable seconds — it is every check on that
event losing its output together. `git-hygiene` is one of nine Stop checks.

## 4. A round-4 violation REFUTED — the ceiling was read from a stale mirror

Round 4 also reported `PreToolUse/edit-checkpoints` as an `EQUALS` violation (15 s declared inside
a 15 s event budget). **REFUTED.** It read `settings_timeout` from `manifest.json`, which is a
MIRROR of the value the vendor enforces, and the mirror is stale on half the fleet:

| event | manifest mirror | settings.json enforced | agree? |
|---|---|---|---|
| SessionStart | 20 <!-- cite: id=R4-c-ss-m file=B12-CEILING.json path=rows.0.manifest_mirror_s value=20 --> | 20 <!-- cite: id=R4-c-ss-e file=B12-CEILING.json path=rows.0.settings_enforced_s value=20 --> | yes |
| Stop | 35 <!-- cite: id=R4-c-st-m file=B12-CEILING.json path=rows.1.manifest_mirror_s value=35 --> | 35 <!-- cite: id=R4-c-st-e file=B12-CEILING.json path=rows.1.settings_enforced_s value=35 --> | yes |
| PostToolUse | 15 <!-- cite: id=R4-c-po-m file=B12-CEILING.json path=rows.2.manifest_mirror_s value=15 --> | 25 <!-- cite: id=R4-c-po-e file=B12-CEILING.json path=rows.2.settings_enforced_s value=25 --> | **no** |
| PreToolUse | 15 <!-- cite: id=R4-c-pr-m file=B12-CEILING.json path=rows.3.manifest_mirror_s value=15 --> | 20 <!-- cite: id=R4-c-pr-e file=B12-CEILING.json path=rows.3.settings_enforced_s value=20 --> | **no** |

`edit-checkpoints` declares 15 s. Against the stale mirror that is `EQUALS`; against the **enforced
20 s** it fits with room to spare. It was never a defect. `Stop` is unaffected — mirror and
enforced both read 35 — so the `git-hygiene` finding survives the same correction that kills this
one, and that asymmetry is the point: the mirror was right twice and wrong twice.

**I was one step from "fixing" this non-defect.** My plan for this round included lowering
`edit-checkpoints` to 10 s and widening the gate's comparison from `>` to `>=`. Both would have
been wrong, and the `>=` change would have *introduced* a false positive into a gate. Measuring the
enforced value first is the only reason it did not ship.

## 5. What shipped

**5.1 `hooks/_dispatch/manifest.json` — `Stop/git-hygiene` 90 s → 30 s.** The enforced Stop ceiling
is 35 s, so 30 leaves collection headroom for the five checks that follow it in manifest order. The
repo manifest now has no check above its enforced ceiling
<!-- cite: id=R4-fix-fits file=B12-CEILING.json path=rows.1.worst_check_fits_enforced value=True -->,
with the worst Stop declaration now 30 s
<!-- cite: id=R4-fix-max file=B12-CEILING.json path=rows.1.max_declared_check_timeout_s value=30 -->.

**The cost is real and is recorded in the manifest itself, not hidden.** `git-hygiene`'s measured
range is 11.8 s <!-- cite: id=R4-gh-lo file=R4-GITHYGIENE-RANGE.json path=range_ms.0 value=11800.0 -->
to 32.7 s <!-- cite: id=R4-gh-hi file=R4-GITHYGIENE-RANGE.json path=range_ms.1 value=32700.0 -->,
reaching 93.4% of the enforced budget
<!-- cite: id=R4-gh-pct file=R4-GITHYGIENE-RANGE.json path=range_pct_of_enforced_35s_event_budget.1 value=93.4 -->,
so runs above 30 s now lose **this check's** output. That is an acceptable trade only because
git-hygiene is advisory and inject-only, while an overrun lost **every** check on the event. The
90 s came from a round-2 remediation for it being disarmed at 28.3 s against a 30 s budget — a
remediation that was inert, because it raised a number above the ceiling that caps it.

**5.2 `lint_budget_ceiling` — `WARN` → `HAZARD`.** `Report.hazards()` filters on
`severity == "HAZARD"` and the exit code counts only hazards, so as a WARN this invariant was
**detected but unenforced**: every other hazard could be fixed and the gate would exit 0 with an
over-ceiling budget still in place. Same class as the `/rollback` gap this audit opened with.

**5.3 `lint_budget_ceiling` — ceiling now read from `settings.json`, not the mirror.** Via the new
`enforced_ceilings()`, which reuses the existing security-scoped `settings_hooks()` reader (the
`hooks` subtree only — no other key of the credential-bearing file is read). Falls back to the
mirror when settings cannot be read, so a fresh clone still gets an answer rather than silence.

**5.4 Five red-first regression tests.** All four new assertions failed against the pre-fix gate
and pass after; the fifth (mirror fallback) passed both ways by design and is the control arm
proving the set is not trivially red.

After the fix the gate reports **only** `live:Stop/git-hygiene` — correctly, because live still
runs the unfixed 90 s until someone deploys. The repo finding is gone; the deploy obligation is
not, and the gate keeps saying so.

## 6. Detector controls

| probe | control that had to hold | why it exists |
|---|---|---|
| `_b12_joinorder.py` | C1 arms discriminate | else the probe measures the sleep, not the declared budget |
| | C2 trailing output visible in the good arm | **fired on me** — see §7.1 |
| | C3 module under test is the real `dispatch.py` | else it proves a re-implementation, not the harness |
| | C4 slow check dropped in the good arm | the cost of the fix, reported not hidden |
| `_b12_ceiling.py` | C1/C2/C3 fail closed on unreadable settings, moved manifest shape, or zero dispatcher commands | refuses to report a ceiling it cannot read |
| `_b12_ciruns.py` | C2 both success and failure present in history | else green is indistinguishable from a blind probe |

<!-- uncited-table: reason=index of which control guards which probe; every control value is asserted and cited at its point of use above, not re-cited here -->

## 7. Self-corrections made before publishing (recorded, not deleted)

1. **My probe reported "output lost" in both arms, and the control caught it.** `dispatch.main()`
   installs `_ThreadStdout`/`_ThreadStdin` at `:407-408` before calling `run()`; calling `run()`
   directly bypasses that, so every check's `print()` escaped to the real stdout and the buffers
   read empty. Without control C2 I would have published "the dispatcher loses all output" as a
   catastrophic finding. The bug was in my probe.
2. **I shadowed an existing helper and broke two unrelated tests.** My fixture was named
   `_manifest`, which already exists in that file returning a doc *dict*; mine returned a *Path*
   and two manifest-reader tests died with a `TypeError`. Renamed to `_ceiling_manifest`, with the
   collision recorded in a comment rather than silently cleaned up.
3. **I nearly "fixed" a non-defect** — see §4. Lowering `edit-checkpoints` and widening `>` to `>=`
   were both in my plan and both refuted by measuring the enforced ceiling first.
4. **I did not pin the wall times.** My first draft cited `run_wall_s = 5.024`; the next run
   produced 5.005. Cited the booleans instead.

## 8. What this round did NOT do

- **Did not touch `dispatch.py`.** The sequential-join-with-absolute-deadline is arguably the root
  cause rather than the manifest number, but that file is one of the 12 DIVERGED wired bodies (live
  and repo differ), and changing dispatcher semantics deserves its own gated round. Fixing the
  declared budget removes the live hazard without altering harness behaviour.
- **Did not deploy.** The repo is fixed; live still runs 90 s. That is why the gate still reports
  one hazard, and it should keep reporting it until a deploy happens.
- **Did not re-time the fleet.** Rounds 1-4 own that axis; round 3 re-scoped what the artifact means.
- **Did not touch `commands/rollback.md`** (outside this lane's file scope) or
  `agent-self/config/settings.json` (the SessionEnd deploy hazard remains contained by a failing
  gate axis, which is containment, not a fix).
- **UNVERIFIED, inline:** I have not observed a real Stop turn being cancelled mid-dispatch. The
  mechanism is proven on the real dispatcher with a synthetic manifest, and the vendor contract
  supplies the cancellation half. **Settling experiment:** set `GIT_HYGIENE_THROTTLE_SEC=0` on a
  live turn with the 90 s budget restored and confirm the Stop event delivers no additional
  context at all, rather than delivering eight checks minus git-hygiene.

## 9. Noise observed while working (DoD-4 corpus)

The `SENSITIVE ARTIFACT REPORT` hook fired **three times** on my edits to
`test_hook_predeploy_gate.py` with an identical artifact id (`sha256:ee4704cabe65`) — a file whose
only "credential" is a synthetic `settings.json` fixture built at runtime. This is the third
independent corpus for the repeat-fire false positive already named in DoD-4, and it strengthens
the proposed fix: dedupe by artifact id per session. `per-edit-check` also fired usefully in the
same window (F401, F821 on files I had just written), so the fleet is not uniformly noisy — the
defect is specific and worth fixing rather than silencing.