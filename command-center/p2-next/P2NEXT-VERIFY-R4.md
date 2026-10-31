---
title: P2NEXT-VERIFY-R4
type: note
permalink: dqverify-repo-20261013/command-center/p2-next/p2-next-verify-r4
---

# P2NEXT — ADVERSARIAL VERIFIER, round 4

STATUS: COMPLETE. Verdict **build_is_sound = false**, one must-fix, decision-relevant.

COVERAGE: V1–V11 all MEASURED by my own instruments over committed blobs and live probes.
V12 (full CI) NOT-CHECKED — ~10 of ~25 steps run locally; a Windows-local green is not CI green.

---

## MUST-FIX — the lane's central premise is false, and nobody probed it

The brief, the build (`P2NEXT-BUILD-R4.md:195`) and the owner-facing deliverable
(`command-center/CROSS-VENDOR-RAIL-STATUS.md:1`) all rest on:

> "Cross-vendor review rail is **DOWN** — and it gates 42 blocked units" …
> "`codex login` buys review capacity for the rail-blocked queue"

**Measured live, 2026-08-14T02:49–02:52Z, two mechanically independent transports. Both answer.**
No credential was written, read for value, or printed — this is the read-only "does it still
authenticate" diagnosis AGENTS.md §9 explicitly permits, and `codex login` was NOT attempted.

| transport | result |
|---|---|
| `codex exec --ignore-user-config --sandbox read-only -o <f> -` | **exit 0**, session `019ffe2c-d568-7021-914f-0c71efa6e4f6`, model `gpt-5.6-sol`, provider `openai`, 25,453 tokens |
| `mcp__codex__codex` (read-only, approval never) | **success**, `threadId 019ffe2d-312c-7951-9c0f-6f71e42f51eb` |

Full cross-vendor-dispatch AND-gate satisfied on the CLI leg — exit 0 **AND** the `-o` file exists
**AND** is non-empty (8 B) **AND** parses (`PROBE_OK`). Not an exit-code-alone claim.

### The refutation was already inside the lane's own committed artifact, unread

`command-center/p2-next/_AUDIT-BLOCKED-POP.json:1439`, verbatim:

> "the `mcp__codex__codex` rail failed with 'agent identity registration failed'; **the codex CLI on
> the same credentials succeeded, so the MCP failure was a transport fault and not an auth verdict**."

`:694`, verbatim:

> "STRIKE 2 — `codex exec --ignore-user-config --sandbox read-only` … **the model AUTHENTICATED and
> ran (25,899 tokens), so the openai-auth-401 blocker ADV-0006 recorded is GONE**"

### The doc's own rail evidence is one transport, and two days stale

`CROSS-VENDOR-RAIL-STATUS.md` states "Rail probed 2026-08-12 ~10:45"; its "Connected is not works"
table probes `codex --version`, `Get-Command codex`, `claude mcp list`, and **one
`mcp__codex__codex` call**. `codex exec` — the transport `rules/common/cross-vendor-dispatch.md` §3
actually PRESCRIBES — never appears in it. The build round committed at 02:13–02:18Z on 08-14 and
re-probed nothing.

The doc teaches the exact lesson it violates: *"before a cross-vendor fan-out, spend one unit
proving the rail end-to-end. `claude mcp list` is not that proof."* One failing `mcp__codex__codex`
call is not that proof either — it is one transport onto the rail, not the rail.

### Three of the 42 already hold an executed cross-vendor Codex PASS

Mechanical: `reviewer.verdict == PASS` **AND** `reviewer.independent is true` **AND** `reviewer_id`
names openai/codex. Read off committed receipt blobs at `a71a7c0a`.

| unit | reviewer_id (verbatim head) |
|---|---|
| ADV-0023 | `openai/codex-cli-0.145.0 (gpt-5.x), fresh context, cross-vendor` |
| ADV-0035 | `codex-cli GPT-5 Codex (OpenAI), session 019ff3f2, dispatched via 'codex exec --ignore-user-config -s read-only'` |
| ADV-0042 | `codex-exec-cli refuter (ADV-0042)`, `vendor: openai` |

**DETECTOR CONTROL, discriminating:** the same reader returns **3 openai-reviewed of 42**
RAIL_BLOCKED and **0 openai-reviewed of 10** SATISFIABLE_NOW (all 10 are anthropic PASSes). A
counter that merely detected "has a reviewer" would have returned 3/42 and 10/10. It does not, so
it is measuring cross-vendor fulfilment and not reviewer presence.

### Why no gate could catch this — the green is structurally vacuous

- `rail_count_gate.py` contains **zero** network or subprocess calls to codex (grep for
  `codex|subprocess|requests|urllib|http` returns one hit: an unrelated regex at `:133`). It checks
  that the published number equals a fresh derivation from the receipts. **It returns the identical
  SUCCESS whether the rail is up or down.** So DoD-4's "gate-enforced" evidence proves arithmetic,
  not the rail verdict — a control that looks the same under both hypotheses.
- `vendor_satisfiability.py:403` — `"verdict": BLOCKED_RAIL if rv == "openai" else SAT` — classifies
  purely on the **demanded** reviewer vendor and never consults `reviewer.verdict`. A unit that
  already consumed cross-vendor review capacity is still counted as needing it.

### Confidence and residual

- Both transports authenticate as of 2026-08-14T02:52Z — **almost certain (90–99%)**: two
  mechanically independent instruments, one with the full AND-gate receipt.
- The premise was never re-probed this round — **almost certain (90–99%)**: the doc's own timestamp
  is 08-12, the commits are 08-14, and the audit records the rail probe as NOT-CHECKED.
- *UNVERIFIED, inline:* whether the MCP transport was genuinely failing at 02:15Z on 08-14 and came
  up in the ~35 min before my probe. Settling experiment: correlate `~/.codex` session logs against
  the build round's timestamps. **This does not rescue the verdict either way** — the CLI leg was
  already recorded as working in the lane's own committed artifact on 08-11, so a correct reading
  was available at build time regardless of the live MCP state.

---

## What the fix is (scoped, so the round is not wasted)

1. Re-probe **both** transports and record both in `CROSS-VENDOR-RAIL-STATUS.md`, replacing the
   single-transport table. Keep the old verdict visible under a REFUTED/superseded marker — the
   headline is in permanent commit messages (`fd615ce7`) and cannot be corrected there.
2. Correct the headline and the `codex login` pricing line. `codex login` is not established as the
   lever for anything; the measured blocker on the CLI leg in the committed corpus was the **host
   sandbox policy** (`_AUDIT-BLOCKED-POP.json:694`), not auth.
3. Subtract already-fulfilled reviews from the queue: teach `vendor_satisfiability.py` to
   distinguish *demands cross-vendor* from *still needs cross-vendor*, so ADV-0023/0035/0042 stop
   being priced as unmet capacity. This changes an owner-facing number, so it needs its own
   both-states control.
4. Do **not** treat this as licence to build READY units — that call is the orchestrator's.

---

## Verified and standing — no defect found

- **DoD 1** — 52 rows, `{RAIL_BLOCKED: 42, SATISFIABLE_NOW: 10}`. My reader, committed blob.
- **DoD 2** — `reviewer_requirement` non-empty 52/52; `blocked_on` non-empty 43/52; all 52
  `output_path`s resolve to committed blobs (0 missing, 0 unparseable).
- **DoD 3** — 10/10 `verdict=PASS`, `independent=true`, notes 1027–2092 chars. **No same-vendor
  substitution**: I read all 10 requirement texts verbatim; none demands cross-vendor. Overlap
  control between the SATISFIABLE and RAIL_BLOCKED requirement-text sets = **0**.
- **`produced_by_vendor` is faithful, not defaulted** — the field rules 0/D/D2 pivot on. 50/52
  receipts carry a `produced_by`; all 50 agree with the derived value; the 2 silent ones are
  labelled `ASSUMED` with `produced_by_known: False`. Zero contradictions.
- **MF2 code fix** — real. `example.com:443`, `site.io:8080`, `db.internal:5432` now rejected;
  a genuine full-path anchor accepted and an obvious non-anchor rejected by the same function
  (control discriminates in both directions).
- **Commits clean** — 8096dff3 / b09136ae / a71a7c0a exist with the claimed file lists; no sibling
  path swept.
- **Dual-write blocker** — CONFIRMED pre-existing: `VIOLATIONS: 1` on 8096dff3 (builder's) *and* on
  1b1e1e4e (already in origin/main); `OK` on 7618a6fa. The control returns green, so the instrument
  discriminates. Escalation over remediation was correct.

## Auditor's own claims, re-measured (auditors are not exempt)

| claim | my measurement | verdict |
|---|---|---|
| O-B: `.sh/.so/.md/.zip` still accepted | `deploy.sh:8080`, `host.so:443`, `docs.md:443`, `files.zip:8080` all `accepted=True`; `api.dev:443`, `svc.ai:443` correctly rejected | **CONFIRMED** |
| O-C: 152 bare-filename regressions | **163**, not 152 — the auditor's per-extension breakdown sums to 152 and omits the 10 extensionless basenames. Full-path anchors rejected: **0 of 11,075** | **direction right, count low by 11** |
| O-D: key ABSENT, not null | 9 empty rows: key ABSENT 9, present-with-null **0** | **CONFIRMED** (builder's "= null" refuted) |
| "42 rail-blocked carry NOT-REVIEWED — honest, not backfilled" | 35 NOT-REVIEWED, **3 PASS**, 4 no reviewer block. The auditor's 38 is 35+3 collapsed into one label | **REFUTED as written** — and this is the thread that leads to the must-fix |

The auditor's 38/42 partial census is the miss that mattered: it counted the rows but flattened
their values, so the three cross-vendor PASSes inside the rail-blocked population were reported as
absent. Four rows were left unaccounted for and not chased.