# RULERESEARCH — BUILD lane, round 1

STATUS: complete and measured. Every number below was produced by a command in this round;
where something was not executed it says so inline, next to the claim.

COVERAGE: grounding re-verification, what shipped, detector-control evidence, DoD status,
residual and commits are all measured. The one derived-not-executed claim is the tiktoken
repair, which names its settling experiment inline beside it.

That COVERAGE sentence originally numbered its sections, and the phrase "§3 detector
controls" <!--count-historical--> was parsed by this lane's own `r2_control_count_gate` as a
prose claim of three controls against the tool's emitted 19 — a real mismatch, and one the
working tree hid: the doc was rewritten *after* the last full gate run, so only the
fresh-clone run caught it. The gate was right and the sentence was wrong. Recorded rather
than quietly reworded, because it is the cleanest demonstration in this round that these
gates do what they claim — and the quoted phrase above needs the
`<!--count-historical-->` marker for exactly the use-vs-mention reason the gate documents.

## 0. What this round did NOT do

The DoD was already met by `23ee1622` and reproduced here, so **the audit was not rebuilt**.
The classification, the token totals and the contradiction census were re-run for
corroboration, not re-derived. What was missing was that **none of it could execute**, and that
is what this round shipped.

`rules/` was not edited. `AGENTS.md` was not edited. `agent-self/**` was not edited.

## 1. Grounding claims re-verified with independent instruments

| claim | verdict | independent probe |
|---|---|---|
| 0 of 8 rule-audit gates CI-wired | **CONFIRMED** | ripgrep over all `*.yml/yaml/toml/cfg/ini` + all of `ci/`; positive control (`test_rules_integrity` → `quality.yml:768`) fires, bogus-token negative control silent |
| repo 88 files / 8 always-on / 17,107 tok | **CONFIRMED** | `rule_audit.py` re-run: `repo files=88 always-on=8 lazy=80 always-on-tok=17,107 all-tok=63,294` |
| live 88 / 8 / 15,141; agent-self 78 / 4 / 1,201 | **CONFIRMED** | same run; always-on floor 23,050 tok |
| repo↔live drift 29 of 88 | **CONFIRMED** | `repo_vs_live: content_differs=29 only_first=0 only_second=0` |
| credential inversion live in the deploy source | **CONFIRMED** | `r4_credential_rule_gate.py` rc=1, 4 violations, its own 5 controls passing |
| the 8 always-on identities | **CONFIRMED** | now pinned in `ci_gate.ALWAYS_ON` and red-proofed |

**Corrected from the grounding:** it reported `r2_pathrefs` and `r3_corpus_parity` as
unmeasured/slow. They are neither hung nor broken — a 120 s cap sat almost exactly on
`r2_pathrefs`'s **110.5 s** runtime. Re-measured at 900 s: `r2_pathrefs` rc=**2** in 110.5 s
(a deliberate code meaning "known defect still tracked, no NEW finding"), `r3_corpus_parity`
rc=**0** in 89.0 s. All 8 gates run.

**New finding this round:** `rule_audit.py` run **bare** with no `~/.claude` prints
`SUCCESS:rule_audit` and exits **0** while the entire `live` tree scanned to zero files —
**fail-OPEN**. Its three siblings (`lazy_predict`, `r2_pathrefs`, `r3_corpus_parity`) all fail
*closed* on that same input. This is why the CI plan runs `--self-test` and not the bare form;
wiring the obvious argv would have shipped a permanently green gate.

## 2. What was built

**`docs/rule-audit/ci_gate.py`** — the lane's CI entry point. Asserts, in order:

1. **No silent shrink** — every `*.py` here is in `CI_PLAN` (with an expected exit code) or in
   `EXCLUDED` (with a written reason); a file in neither fails the run.
2. **Real exit codes**, captured per child, never through a pipe (a pipeline reports the last
   command's status, which turns a red gate green). 6 planned invocations over 6 gates,
   31 excluded with reasons.
3. **DoD-1 always-on set** must be exactly the measured 8 — catching both a promotion and a
   demotion, the latter being the charter's inverse-intuition trap (`paths: ["**/*"]` *demotes*).
4. **Deploy-source load-semantics parity** between `rules/` and `agent-self/config/rules/`,
   allowlisted at exactly the 3 measured divergences.

Invariants 3 and 4 read only the two **in-repo** trees, so they need no `~/.claude` and no
tokenizer — they mean the same thing on a runner as on this box.

**`.github/workflows/rule-audit.yml`** — a separate workflow, not a job in `quality.yml`
(which is a charter-policed closed gate set; a separate file carries no charter obligation and
touches no sibling's file). Installs `tiktoken==0.13.0`, runs the self-test, then the gate.

**`docs/rule-audit/RULE-AUDIT-INTEGRATE.md`** — was a skeleton reading `UNKNOWN` in every
section, i.e. by its own sentinel uncitable. Now filled with the measured integration.

### The measured gate table that chose the plan

| gate | rc | wall | in CI? |
|---|---|---|---|
| `rule_audit.py --self-test` | 0 | 1.2 s | wired |
| `r2_pathrefs.py --self-test` | 0 | 2.8 s | wired |
| `r2_control_count_gate.py` | 0 | 1.6 s | wired |
| `r2_failclosed_mutation.py` | 0 | 3.1 s | wired |
| `r4_receipt_argv_gate.py` | 0 | 0.5 s | wired |
| `r4_credential_rule_gate.py` | 1 | 0.2 s | wired at **expected rc=1** (owner action) |
| `rule_audit.py` bare | 0 | 1.3 s | **excluded — fail-OPEN without `~/.claude`** |
| `r2_pathrefs.py` bare | 2 | 110.5 s | excluded — needs live tree (fails closed) |
| `lazy_predict.py` | 0 → **1** no-HOME | 0.7 s | excluded — needs live tree |
| `r3_corpus_parity_gate.py` | 0 → **1** no-HOME | 89.0 s | excluded — needs live tree |

## 3. Detector controls — every check seen in BOTH states

| control | broken state | good state |
|---|---|---|
| `ci_gate --self-test`, 12 pure predicates | each FIRES | each SILENT — rc=0 |
| shrink-guards (CI_PLAN, allowlists, last expected-FAIL) | fail closed | pass |
| `_b8_redproof.py` on **real file bytes**, 6 states | 5 mutations FIRE | untouched copy SILENT — rc=0 |
| inventory invariant, end-to-end | transient unclassified `.py` → **rc=1** | removed → **rc=0** |
| the "0 gates wired" search itself | bogus token → silent | `test_rules_integrity` → fires |
| `_b9_preflight` post-commit inventory | would report ghosts | none, 39 files |

The red-proof matters separately from the self-test: the self-test proves the *comparison
logic* with hand-made sets and says nothing about whether the classifier, reading real files,
notices changed frontmatter. `_b8` copies both trees to a temp dir, mutates the copies
(demote / promote / new divergence / repaired divergence / empty tree) and requires
`measure_trees()` to fire on each. The repo is never modified — `TREES` is restored in a
`finally`.

**A detector artifact I caused and corrected:** an early probe captured gate stdout with
`text=True`, which decodes as cp1252 on Windows and rendered `§` as `Â§`. That was my probe,
not the gates. Fixed with `encoding="utf-8"`; the gate now prints `§9` correctly.

### Clone and CI-simulation results

Working-tree green is not clone green, so both were run — and the clone run **caught a real
red** the working tree hid (see the COVERAGE note at the top: a prose claim in this very
document). After the fix:

| environment | result |
|---|---|
| working tree | `SUCCESS:rule-audit-ci-gate 6/6 gates behaved, always-on=8, divergence=3` |
| fresh `git clone` at HEAD | self-test 12/12; gate **rc=0**, 6/6, 39 tracked `.py`, no ghosts |
| fresh clone **+ no `~/.claude`** (closest local approximation of a runner) | gate **rc=0**, 6/6 |

In the no-home simulation `r4_credential_rule_gate` reports **2** violations instead of 4 —
its live-tree arm cannot run there — and still exits 1, which is exactly what the plan pins
it at. That is the designed degradation, verified rather than assumed.

**Still unmeasured in that simulation:** POSIX, and tiktoken absence. Those are the two
remaining differences between this box and `ubuntu-latest`, and they are the residual in §5.

## 4. DoD status, item by item

- **DoD-1 — every rule classified always-on vs lazy by measured frontmatter: PASS.**
  88 repo / 78 agent-self / 88 live, three-bucket classification (no-frontmatter,
  frontmatter-without-paths, paths-scoped). Reproduced this round and now *enforced* by
  `ci_gate` invariant 3 — previously measured but unprotected.
- **DoD-2 — always-on token cost totalled: PASS.** 17,107 tok repo / 15,141 live over 8 rules;
  63,294 all-repo; always-on floor 23,050 tok including the three memory files. Counts are
  cl100k_base (OpenAI's tokenizer, not Anthropic's) — estimates ±10-20%, stated as such.
- **DoD-3 — every contradiction measured and listed with the correction: PASS (inherited,
  spot-corroborated).** The nine corrections landed in `23ee1622`; ADV-R4 called the build
  sound. This round re-measured the credential inversion (4 violations) and the deploy-source
  divergence (3 files, identified) rather than re-running the whole census. **Not
  individually re-measured this round: the other contradictions.**
- **DoD-4 — no rule rewritten without evidence: PASS, trivially.** No rule was rewritten at
  all; `rules/`, `AGENTS.md` and `agent-self/**` are untouched. `git status` on those paths is
  clean.

## 5. Residual, and what is NOT claimed

- **UNVERIFIED — "installing tiktoken makes Linux go 19/19."** Measured that *without* tiktoken,
  Linux fails exactly 2/19 (`encoder is tiktoken/cl100k_base`, `known string -> known count`)
  because `Counter` degrades to `ESTIMATE chars/4` and `round(11/4)==3!=2`, and that two more
  gates cascade red off it. Could not install tiktoken to confirm the repair: this box's WSL has
  **no DNS**. Derived from the mechanism (only the 3-control `encoder` group touches tiktoken;
  its third control passes either way) plus Windows-with-tiktoken at 19/19.
  **Settling experiment: the first runner execution of the new workflow.**
- **The workflow has never run on a runner.** Everything here is local execution, a fresh
  clone, and a fresh clone with no `~/.claude`. The last of those is green, which removes the
  live-tree unknown; what remains is POSIX and tiktoken. Confidence that the workflow goes
  green on its first runner execution is *likely* (55-80%), not certain.
- **Network at gate time** (`tiktoken.get_encoding` fetches the BPE file). Accepted: the failure
  mode is loud — a failed fetch makes the encoder control fire and the job go red, never a quiet
  pass.
- **Repo↔live drift (29/88 files, 7/8 always-on) is neither gated nor fixed.** No runner has
  `~/.claude`, so no CI job can see it. The corrected `harness-vcs-hygiene` (the `-Report json`
  data-loss form) and `cross-vendor-dispatch` rules are still wrong in the live tree. Not
  deployed this round — deploying changes what every other running session reads, which is an
  owner-visible action, not a silent build-lane side effect.
- **The credential inversion is pinned, not fixed** — owner action under AGENTS.md §9. CI now
  tracks it at expected rc=1 instead of merely documenting it.
- **NOT-CHECKED:** the full ~25-step `quality.yml` was not run (out of lane; shared-file
  hazard). No claim is made that CI overall is green — only that the 195 tests named here pass.
- **Out-of-charter file touched, declared:** `.github/workflows/rule-audit.yml` is outside the
  lane's literal file scope (`docs/rule-audit/**`, `rules/**`, `AGENTS.md`). It is a **new**
  file, so it collides with no sibling — deliberately *not* an edit to `quality.yml`, which the
  ground floor names as the highest-hazard shared surface. Wiring was the orchestrator's plan
  step 1 and is the whole point of a build round; flagged here rather than done silently.

Confidence: **almost certain (90-99%)** on everything executed — the gate table, the fail-open
finding, the 3 divergence identities, the 12+6 both-states controls, the clone verification.
**Likely (55-80%)** that the workflow goes green on its first runner execution, the tiktoken
step being the named risk.

## 6. Commits

`ci(rule-audit): wire the lane's 8 gates into CI and gate the two facts nothing protected`

Files: `.github/workflows/rule-audit.yml`, `docs/rule-audit/ci_gate.py`,
`docs/rule-audit/RULE-AUDIT-INTEGRATE.md`, `docs/rule-audit/RULE-AUDIT-BUILD-R1.md`,
the `_b1`–`_b9` build probes and their JSON receipts, plus two prior-round instruments that
were sitting **untracked and at risk** and that `ci_gate.EXCLUDED` names — `_i1_ci_portability.py`
(+ its JSON) and `_r5_grounding_probe.py` — which had to be committed or CI would have failed
on them as ghosts. Also rescued from untracked: `RULE-AUDIT-ADV-R4.md` and
`RULERESEARCH-GROUNDING-R2.md`.
