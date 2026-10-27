# RULERESEARCH — adversarial verification of round 4 (attacks BOTH the build and the audit)

Everything below was EXECUTED by this lane from `C:/Users/Prekzursil/source/ast-integrate`.
Exit codes are `subprocess.returncode`, captured unpiped — a pipeline returns the tail's rc, which
is how this whole defect class hides. Probes are re-runnable at
`C:/Users/Prekzursil/adv_r4/p1_core.py` … `p6_fix_neutrality.py`.

**VERDICT: build is SOUND. Audit HOLDS, with one label corrected. One NEW defect found that
neither lane reported — executably proven, verdict-neutral, therefore reported as a scoped
residual and NOT as a blocker.**

## 1. The one thing both lanes missed — tier-2 accepted-flag pollution (CONFIRMED)

`r4_receipt_argv_gate.py:36-40` claims of tier 2: *"it catches an unknown or misspelled flag and
CANNOT catch a missing value"*. The first half is **false**. `literal_flags()` harvests every
`--flag`-shaped string constant in the module AST, so a script that shells out donates its
**subprocess argv** to its own accepted set, and a script carrying self-test fixtures donates
**its fixture tokens**:

| script | accepted set as built | what is actually a real flag |
|---|---|---|
| `_r2_blobcheck.py` | `--cached`, `--check`, `--name-only`, `--rev` | `--rev` only (the rest are git/ruff argv) |
| `r4_receipt_argv_gate.py` | `--json`, `--md`, `--nope`, `--rev`, `--self-test`, `--self-tets` | `--self-test` only |

Both states, executed (`p5_tier2_defect.py`):

| documented invocation | gate verdict | what really happens |
|---|---|---|
| `_r2_blobcheck.py --cached` | **VALID** | rc=1 `FAILED:r2_blobcheck no .py files in staged index` |
| `_r2_blobcheck.py --check` | **VALID** | rc=1, same — the flag is not read at all |
| `r4_receipt_argv_gate.py --nope` | **VALID** | rc=0, flag ignored |
| `r4_receipt_argv_gate.py --self-tets` | **VALID** | rc=0 — the gate blesses the exact misspelling its own B3 control names |

The irony is load-bearing, not decorative: the gate would certify the round-3 defect string against
**itself**, because `--json` and `--md` live in its own fixtures.

DETECTOR CONTROL (so "VALID" is not just a broken matcher): a token in no string constant anywhere
is still caught — `_r2_blobcheck.py --totally-absent` <!--argv-invalid--> and
`r2_pathrefs.py --self-tets` <!--argv-invalid--> both return VIOLATION. The pollution is specific,
not a dead check.

**WHY THIS IS A RESIDUAL AND NOT A BLOCKER — measured, not asserted.** I re-ran all 12 committed
tier-2 invocations under a tightened `literal_flags()` (only flags the module actually
membership-tests): **0 verdict flips** (`p6_fix_neutrality.py`). Every committed receipt uses
`--self-test` or `--rev`, both genuinely accepted. Tier 1 — the real `argparse` parser, 33 of 45
invocations, including every instance of the defect the gate was built for — is untouched. So the
code's *verdict* is correct today and the *sentence* is wider than its evidence: the C2 shape.

CORRECTLY-SCOPED VERSION: *"tier 2 catches a flag that appears nowhere in the module's source. It
does NOT reliably catch an unknown or misspelled flag, because the accepted set is harvested from
all string constants and therefore includes subprocess argv and self-test fixtures. Measured: 0 of
12 committed tier-2 invocations are affected."* One-line fix if wanted: keep only constants that
appear in a membership test — verified verdict-neutral above.

## 2. Build claims — re-executed, not read

| claim | measured | verdict |
|---|---|---|
| `rule_audit.py --json --md` <!--argv-invalid--> is an argparse error | `EXACT_RC=2`, stdout 0 B, `error: argument --json: expected one argument` | CONFIRMED |
| correct form regenerates both artifacts identically | rc=0; JSON 123,434 B and TABLES 6,412 B, sha256 identical | CONFIRMED |
| gate FIRES before / SILENT after | my own git-only sandbox: BEFORE rc=1 / 2 violations, AFTER rc=0 | CONFIRMED |
| commits scope-clean | both 100% under `docs/rule-audit/`; filter controlled on 2 siblings | CONFIRMED |
| credential tracker: 6 controls, live arm RAN, 4 violations | reproduced exactly, rc=1 | CONFIRMED |
| mention composition 114 = 58 + 52 + 4 | reproduced, rc=0 | CONFIRMED |
| blobs LF-clean, mangle control fires | 7 and 3 blobs, 0 CRLF, control rc=1 both | CONFIRMED |
| 167 tests, pinned ruff clean | 167 passed 0.70s; ruff check + format clean | CONFIRMED |

A discriminating control on the headline: an unknown flag ALSO exits 2 but says
`unrecognized arguments`, so rc=2 alone would not have distinguished the two failure kinds.

**DoD-1 re-derived by a mechanism no prior lane used.** The 8 always-on repo rules are exactly the
8 the harness injected into MY turn-0 context. Better: `lazy_predict.py`'s 16 `OBSERVED_INJECTED`
files are exactly the 16 lazy rules the harness injected into my turn-1 context after I touched
`.py` files, and its negative control `common/hooks.md` did **not** arrive for me either. That is a
third-session live replication of both halves of the always-on/lazy model — real harness behaviour,
not a frontmatter parse.

## 3. Attacks on the AUDIT

**Reproduced and upheld.** Overclaim 1 is real: I rebuilt the pre-fix corpus from git alone —
7 corpus files tracked at `c847b6b1`, 8 more added as status `A` by `aa50e309` = the builder's 15,
so "ON REAL COMMITTED BYTES" is wrong for 8 of 15. The both-states property survives anyway
(git-only BEFORE still fires, with exactly the 2 genuinely-committed false receipts). Overclaim 2
is real but is disclosed drift: the count is now **18** at my read, because I added this file to the
corpus it measures — 16 → 17 → 18 across three readers is the volatility the builder pre-declared.
All 5 marker arms reproduce, including M4 silent at rc=0.

**One audit label is wrong — the auditor reproduced the class it was cataloguing.** The audit calls
M4 *"undisclosed"* and *"ONE UNDISCLOSED GAP"*. Executed: the gate's own module docstring says
*"It does NOT check the claimed rc, and that distinction is load-bearing"* — a blanket disclosure
that covers M4 exactly. The auditor argued from the build report's residual #5 and split a hair
about which case it framed, without reading the primary disclosure site in the code. The
*mechanism* stands; the *label* does not. Scoped version: "a disclosed limitation with no live
instance, whose cheapest closure is to parse an rc token on marked lines." This is a sentence
defect, not a finding defect, and it does not move the audit's verdict.

The audit also missed §1 above, which is the stronger disclosure error of the two: M4 is disclosed,
tier-2 is affirmatively mis-claimed.

## 4. Checks that came back clean (stated so silence is not mistaken for absence)

- **No PASS rests on a missing input.** Every gate ran; `lazy_predict` and `r4_credential_rule_gate`
  fail closed on an absent live tree, and the live arm reports `RAN`, never `SKIPPED`.
- **No vacuous control found.** `r2_control_count_gate` fails closed on zero extracted claims
  (`zero live claims -- extractor found nothing, fail closed`); the credential gate's "repaired copy
  scores clean" arm fails closed if its `replace` no-ops; `lazy_predict` carries a real negative
  control. None is identical under both hypotheses.
- **Credential inversion — a fourth independent read.** `agent-self/config/AGENTS.md` §9 opens with
  "Never hardcode secrets" and has no rotate-prohibition bullet; its §9b ends "rotate, don't just
  delete". My own turn-0 context carries the LIVE §9 with "NEVER remove, rotate, revoke,
  regenerate, unset or otherwise MODIFY any API key or token" and a §9b saying to leave rotation to
  the owner. `bootstrap.ps1:45` is `Copy-Item (Join-Path $Self 'config\*') $ClaudeHome -Recurse
  -Force`. CONFIRMED, owner action, correctly left unfixed and correctly out of lane write scope.
- **Neither nonzero script is CI-wired** — grep over `ci/` and `.github/` finds nothing, and the
  same grep fires on a known-wired `test_rules_*` file, so the absence is measured.
- **Latent, no instance:** `parser_of()` decides tier by the substring `def build_parser(`, which its
  own source contains inside a string literal — use-vs-mention inside the gate. Harmless (the
  `getattr` fallback returns None) but it means the gate imports modules it need not.
  `load_module()` catches `Exception`, not `BaseException`, so a module-level `sys.exit()` would
  escape; no tier-1 candidate has a module-level call expression, so there is no live instance.
- **Working-tree only:** `_rule-inventory.err` is a stray 0-byte file, untracked, never reaches CI.

## 5. Confidence

ALMOST CERTAIN (90-99%) on everything executed above: the tier-2 pollution and its 0 verdict flips,
the core defect both directions with a discriminating control, the git-only both-states
reconstruction, the 11 gate exit codes, 167 tests, both blob checks with firing mangle controls, the
credential inversion, and the turn-0/turn-1 injection replication.

LIKELY (55-80%) that the tier-2 pollution stays harmless. It is latent, not live: the next receipt
that names a shelling script with a plausible-looking flag would be blessed falsely. Settling
experiment is in §1 and takes one line.

UNCERTAIN (20-55%) that no OTHER documented command in this corpus is false in a way argv validity
cannot see — unchanged from the builder's own statement of the boundary, and correctly stated there.

NOT-CHECKED, declared rather than folded into a pass: I did not run the full ~25-step CI (out of
lane, shared-file hazard), so "CI is green" is not a claim I make. I did not verify the builder's
marker content-neutrality shas — both reviewer artifacts were first tracked by `aa50e309`, so no
prior blob exists to diff; the auditor reached the same wall and substituted the same structural
check.
