# P2NEXT — BUILD round 3: the rail was never down, and the queue was priced as if it were

COVERAGE: every claim below names the probe that produced it. Three things stay unmeasured and say
so inline: whether the remaining units would PASS a Codex review, whether a full dispatch survives
the host sandbox policy, and full CI.

## 0. What I was sent back for, and what I read instead

My brief's `PRIOR ROUNDS` array carries only round 1 and asserts the rail is DOWN. The tree carries
a NEWER verifier verdict — `P2NEXT-VERIFY-R4.md`, `build_is_sound = false` — whose must-fix is that
**the rail premise itself is false**. I read the instrument on disk rather than the summary in my
prompt, then re-probed rather than trusting either. A verifier is one signal.

| id | defect | class | this round |
|---|---|---|---|
| MF-R4 | "the cross-vendor rail is DOWN" — the lane's central premise | FALSE, decision-relevant | re-probed, refuted, doc rewritten |
| MF-R4b | `codex login` priced as the unlock | FALSE pricing | corrected; no measured auth blocker exists |
| MF-R4c | 3 rail-blocked units already hold a cross-vendor PASS but are counted as unmet | CODE | producer + gate now split DEMAND from UNMET |

## 1. The rail answers. Two transports, control discriminates.

| transport | result |
|---|---|
| `codex exec --ignore-user-config --sandbox read-only -o <f> -` | **exit 0**, 7.9 s, out file 22 B, body is the demanded nonce `RAILPROBE-3DC854492AA8`, session `019ffe3a-2a43-7dd2-a36d-d836364b77dc`, 25,474 tokens |
| `mcp__codex__codex` (sandbox read-only, approval never) | **success**, `threadId 019ffe3a-0ba7-7812-a7e6-5e9bcba4c25a`, returned the exact nonce `RAILPROBE-MCP-7F3A21` |
| **CONTROL** — same CLI call, `CODEX_HOME` at an EMPTY dir | **exit 1**, `401 Unauthorized: Missing bearer or basic authentication` |

The CLI leg satisfies the `cross-vendor-dispatch.md` §2 AND-gate, not an exit code alone: exit 0
**AND** the `-o` file exists **AND** is non-empty **AND** validates — it carries a nonce generated
for that run, so a truncated or empty generation cannot pass. The nonce is what makes it a
validation rather than a length check.

**The control is what makes the green mean anything.** With no credential reachable the same call
fails 401, so the probe demonstrably CAN see an auth failure. No credential was written, rotated,
read for value, or printed; the control redirects one subprocess's home at an empty temp dir.
`codex login` was NOT attempted. Receipt: `J1-RAIL-PROBE.json`.

### My first probe run was a detector failure that would have CONFIRMED the stale doc

Run 1 passed the bare name `codex` to `subprocess` with `shell=False` and got
`[WinError 2] The system cannot find the file specified` for **both** legs. `codex` on PATH is
`codex.ps1`, a shim `CreateProcess` cannot launch; `codex.cmd` is the launchable one. A failing
live leg is exactly what the committed page asserts, and I was one step from reporting agreement
with it. The `control_discriminates` assertion refused — the control failed too, so the instrument
measured nothing. Same class as `which` in Git Bash missing a `.cmd` shim. This is the second time
in this lane's history a broken detector nearly certified the DOWN verdict.

### The refutation was already in the lane's own committed artifact

`_AUDIT-BLOCKED-POP.json`, written 08-11/12, read verbatim from the committed blob (not cited from
the verifier): *"the `mcp__codex__codex` rail failed …; **the codex CLI on the same credentials
succeeded, so the MCP failure was a transport fault and not an auth verdict**"*, and *"the model
AUTHENTICATED and ran (25,899 tokens), so the openai-auth-401 blocker ADV-0006 recorded is GONE …
REPLACED by … the host sandbox policy DECLINED every read-only filesystem probe"*. A correct
reading was on disk before the page was written. The dominant failure was recall, not detection.

## 2. Demand is not unmet demand — 3 of 42 are already served

`_j2_fulfilled_census.py`, my own reader over committed blobs, independent of the producer:

| population | n | has_any_reviewer | cross_vendor_pass | anthropic_pass |
|---|---|---|---|---|
| RAIL_BLOCKED | 42 | 38 | **3** (ADV-0023, ADV-0035, ADV-0042) | 0 |
| SATISFIABLE_NOW | 10 | 10 | **0** | 10 |

**Detector control, discriminating:** a counter that merely detected "has a reviewer" returns 38
and 10; the fulfilment counter returns 3 and 0. They separate on the SATISFIABLE population, so
what is measured is cross-vendor fulfilment and not reviewer presence. Had both counters agreed,
the reading would have been inert and unreportable.

**The use-vs-mention guard fires on a real row.** ADV-0006's `reviewer_id` reads
`codex-cli-0.145.0 (openai) -- DISPATCH BLOCKED` with verdict `NOT-REVIEWED`. A receipt that NAMES
a Codex reviewer did not GET one, and the predicate requires `verdict == PASS` AND
`independent is true` AND a reviewer vendor differing from the producer.

## 3. The code change — additive, so the two instruments still agree

`vendor_satisfiability.py:403` classified on the DEMANDED reviewer vendor and never read
`reviewer.verdict`. I did **not** redefine `rail_blocked`: it is what receipts ask for, and
`split_review_gate.py` independently reproduces it from different fields, so redefining it would
destroy the two-instrument agreement and read as weakening a gate to move a number. Instead the
distinction is added alongside.

- `vendor_satisfiability.py` — new `cross_vendor_fulfilled()` predicate; per-row
  `cross_vendor_fulfilled` / `still_needs_cross_vendor`; payload gains
  `rail_blocked_fulfilled` (3), `rail_blocked_unfulfilled` (39), `cross_vendor_fulfilled_ids`.
  Selftest gains **9 fulfilment cases exercised in both directions** — one accepting case first, so
  a wholesale `return False` cannot pass the block, then a case per rejecting branch
  (NOT-REVIEWED-but-named, FAIL verdict, non-independent, same-vendor both ways, ambiguous id,
  empty id, no reviewer block).
- `rail_count_gate.py` — both fields are REQUIRED in the RAIL-COUNT block and value-checked; C4
  gains three fail-closed invariants: unfulfilled within `0..rail_blocked`, fulfilled + unfulfilled
  **partition** rail_blocked, and a rail-blocked queue reporting **zero** owed fails closed rather
  than publishing "the queue is served" — the most flattering possible wrong answer and the one an
  owner would act on. The self-test case count is now **counted, not asserted** (the header said
  "30 cases" and was already stale), and a one-sided suite fails.

The producer's 39/3 and my independent census's 39/3 agree, from different code and different
readers.

## 4. Detector controls, per claim

| claim | control | result |
|---|---|---|
| rail is up | same call with an empty `CODEX_HOME` | fires — exit 1, 401 |
| 3 already fulfilled | "has any reviewer" counter on the same rows | separates: 38/10 vs 3/0 |
| the new gate field is enforced | `_j3_redproof.py`: A current doc / B pre-change doc @`0c64b983` / C field present but WRONG | **A exit 0, B exit 1 (field absent), C exit 1 (value wrong)** |
| the gate's own suite discriminates | 22 of 37 cases expect a FIRE; a one-sided suite now fails | PASS |

C is the case that matters in `_j3_redproof.py`: without it, a gate that demanded the field but
accepted any value would still pass A and B. B is pinned to a SHA, not `HEAD`, because a
before/after probe pointed at a moving ref went red the moment its own fix landed (round 1,
`48252d5e`), and it exits 2 if pointed at a state that already carries the field.

## 5. Evidence — commands and their real output

```
python command-center/p2-next/_j1_rail_probe.py
  -> VERDICT: RAIL-UP: codex exec authenticates and returns the demanded nonce
     control discriminates: True        SUCCESS:j1-rail-probe

python command-center/p2-next/_j2_fulfilled_census.py
  -> RAIL_BLOCKED 42: has_any 38, cross_vendor_pass 3 ['ADV-0023','ADV-0035','ADV-0042']
     SATISFIABLE_NOW 10: has_any 10, cross_vendor_pass 0
     control discriminates: True        SUCCESS:j2-census

python command-center/p2-next/_j3_redproof.py
  ok  A current doc: exit 0 (want 0)
  ok  B pre-change doc @0c64b983 (field ABSENT): exit 1 -- missing ['rail_blocked_unfulfilled', ...]
  ok  C field present but WRONG (control): exit 1 -- doc says 42, fresh derivation says 39
     SUCCESS:j3-redproof

python command-center/p2-next/rail_count_gate.py --self-test
  -> selftest: PASS (37 cases, 22 of them expecting a FIRE, every check in both states)

python command-center/p2-next/rail_count_gate.py --doc command-center/CROSS-VENDOR-RAIL-STATUS.md
  -> FRESH DERIVATION: 52 blocked units, 42 rail-blocked (39 still owed a cross-vendor review,
     3 already served), 10 satisfiable now, 10 of those reviewed; catalog 2007, 449 READY
     SUCCESS:rail-count-gate

python command-center/p2-next/vendor_satisfiability.py --basis committed
  -> selftest: PASS (8 ladder cases; 9 fulfilment cases, both states)
     STABILITY: 52 units at BOTH 899ff779^ and HEAD; 0 verdict(s) moved
     artifact drift: False              SUCCESS:vendor-satisfiability

python command-center/p2-next/split_review_gate.py --basis committed  -> SUCCESS
uvx ruff@0.15.17 check / format --check  (my 5 files)  -> All checks passed / 5 already formatted
```

**The gate caught a real violation in my own draft** before it shipped: the doc said "0 of the 10
receipts", and 0 is not a derivable figure, so C2 fired. Rewritten in words. That is the gate
working on its author.

## 6. What was NOT done, deliberately

- **No `codex login`.** Credential write, owner-only (AGENTS.md §9). `auth.json` never read.
- **No READY units built.** The lane spec forbids it. Round 2 already corrected the false REASON
  ("all 449 name a cross-vendor reviewer" — refuted; 163-164 do, 285-286 do not); that correction
  stands and is not re-litigated here.
- **No same-vendor review substituted where cross-vendor is demanded.** The 42/10 demand split is
  untouched; only the already-SERVED subset is now reported separately.
- **`rail_blocked` not redefined.** Moving it would have broken the agreement between two
  independent instruments to make a number smaller.
- **Condition 11 untouched.** Still the decisive ceiling — and now the *whole* owner decision,
  since no auth blocker is measured. ADV-0023/0035/0042 prove it: they cleared cross-vendor review
  and still cannot reach DELIVERED.
- **`_v4_rail_premise.py` left alone** — it carries a ruff F541, but it is the verifier's untracked
  scratch, not mine and not tracked, so it cannot red CI.
- **`.github/workflows/**` untouched**, including the shared `quality.yml`.

## 7. Residual — inline, not blocking

1. **No gate could have caught the false rail verdict, and probably none should.**
   `rail_count_gate.py` makes no call to codex; it returns the identical SUCCESS whether the rail
   is up or down. That is a control that looks the same under both hypotheses, so "gate-enforced"
   must never be read as evidence for the rail claim. **UNVERIFIED** whether a liveness probe
   belongs in CI: it would make a hermetic gate depend on a live third-party endpoint, which
   `ci-hygiene.md` §2 forbids in the fast suite. Settling experiment: a separate scheduled job with
   a hard timeout, never the per-PR gate.
2. **UNVERIFIED [uncertain, 20-55%]:** whether the MCP transport genuinely failed on 08-12 and
   recovered, or was intermittent throughout. Settling experiment: correlate `~/.codex` session
   logs against the earlier probe timestamps. It does not change the verdict — the CLI leg was
   recorded working in the committed corpus on 08-11.
3. **The host sandbox policy blocked a real review dispatch once, after auth succeeded.** Not
   re-measured this round. That is the concrete next blocker to price, not the credential.
   Settling experiment: dispatch one real review unit and require the §2 AND-gate plus a
   non-trivial verdict.
4. **UNVERIFIED [uncertain, 20-55%]:** whether the 39 would PASS a Codex review. Measured what
   receipts DEMAND and which are already SERVED, never what a review would conclude.
5. **The fulfilment predicate is strict by choice.** It requires a vendor-naming `reviewer_id`; a
   genuine cross-vendor review whose `reviewer_id` names no vendor would be counted as still owed.
   That errs toward *overstating* the queue, which is the safe direction. Measured cost today: 0 —
   all 38 reviewed rail-blocked rows carry a vendor-naming id or an explicit NOT-REVIEWED.
6. **The dual-write blocker is unchanged and untouched** — `ci/check_skill_dual_write.py
   --strict-parity` reds on any commit touching a canonical-only skill. This round touches no
   `.agents/skills/**` file, so it is not implicated here.
7. **NOT-CHECKED: full CI.** 11 gates ran locally out of a suite of roughly 25 steps. A
   Windows-local green is not CI green.

## 8. Gate sweep — measured after the commit, on the COMMITTED state

`.github/workflows/p2next-rail-count.yml` runs exactly four commands. All four are green on the
committed tree:

| gate | result |
|---|---|
| `rail_count_gate.py --self-test` | PASS — 37 cases, 22 expecting a FIRE, every check in both states |
| `rail_count_gate.py` (committed basis) | SUCCESS — 52 / 42 (39 owed, 3 served) / 10 / 10, catalog 2007, READY 449 |
| `vendor_satisfiability.py --basis committed` | SUCCESS — selftest PASS, stability 0 moved, artifact drift False |
| `split_review_gate.py --basis committed` | SUCCESS |
| `_c4_blobcheck_mine.py 23ed5b1c` | 5 python blobs derived from the commit, **0 CRLF**, blob-form ruff check + format rc=0, **CONTROL mangled blob fires rc=1** |
| `ci/check_skill_dual_write.py --strict-parity` on `23ed5b1c` and `245a24ec` | **OK** both — this round touches no `.agents/skills/**` file. **Control:** the same command on `1b1e1e4e` still reports `VIOLATIONS: 1`, so the gate discriminates rather than having been quietly satisfied |
| `ci/gen_skill_index.py --check --fail-on-drift` | INDEX DRIFT: no; canonical NOT declared: 0 |
| `ci/gen_skills_manifest.py --check` | skills_tracked=337 manifest_rows=337 malformed_lines=0 |
| `ci/check_skill_description_ratchet.py` | SUCCESS, no violations (advisory) |
| `uvx ruff@0.15.17 check` / `format --check` (my 5 files) | All checks passed / 5 already formatted |

The dual-write row is the one worth reading twice. Round 1 escalated it as a blocker and it stayed
open; it is **not** implicated here, and that is established by a control that still reds on a
commit which does touch a canonical-only skill — not by my commits merely coming back green.

Not run: the node/npm steps, CodeQL, gitleaks, and the hook/workflow gates owned by sibling lanes.
