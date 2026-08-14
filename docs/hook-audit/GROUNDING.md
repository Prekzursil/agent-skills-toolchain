# Hook fleet — GROUNDING lane (HOOKRESEARCH), round 5

STATUS: COMPLETE for a grounding pass. No production code written (grounding lane mandate).
All probes committed under `command-center/hook-audit/_g5_*.py` and re-runnable.

COVERAGE — MEASURED here: live-vs-repo wiring re-derived independently (25 vs 27 checks);
the `/rollback` producer's current state and its consumer-index freshness; the whole live
fleet against the VENDOR's documented timeout caps, `if`-field semantics and exit-code
contract; the 11 known blockers crossed against the event each is wired to; hook SCRIPT-BODY
drift repo vs live across 235 shared files.
NOT MEASURED, stated inline: whether the 12 drifted wired bodies are a repo upgrade or a
two-directional loss (needs a read of each diff — named as the settling experiment in P1);
per-hook wall time (rounds 1–4 own that axis and I did not re-run it).

If a section reads "UNKNOWN - not yet measured", the unit died before measuring anything and
no verdict here may be cited.

---

## 0. Headline for the BUILD lane: most of this lane's DoD is ALREADY DONE

Four rounds of HOOKRESEARCH already shipped, commits `de77c002` → `861fd533` (2026-08-12/13).
**Do not rebuild any of it.**

| DoD item | status | artifact |
|---|---|---|
| every wired hook timed against its budget | DONE (round 4 corrected round 1's table) | `docs/hook-audit/HOOK-AUDIT.md` DoD-1; `command-center/hook-audit/H4-TIMING-live.json` |
| inert hooks proven inert BY FIRING | DONE — 6 INERT-CONFIRMED <!-- cite: id=I1-g-inert file=B6-FLEET.json path=inertness.verdicts.INERT-CONFIRMED value=6 --> + 1 non-terminating (this row said 5 until 2026-08-14; see the HOOK-AUDIT.md DoD-2 correction) | `HOOK-AUDIT.md` DoD-2; `B6-FLEET.json` → `inertness`; `probe_hook_fleet.py --inertness` |
| /rollback producer gap resolved or deploy plan | DEPLOY PLAN WRITTEN | `docs/hook-audit/ROLLBACK-DEPLOY-PLAN.md` |
| false-positive sources named with a fix | DONE — F1/F2/F3 fixed + red-first tests | `HOOK-AUDIT.md` DoD-4; `hooks/wire-check/test_wire_check_{decode,noise}.py` |

Tools that already exist and must be **reused, not reimplemented**:
`command-center/probe_hook_manifest_drift.py` (both-direction manifest differ),
`command-center/fix_hook_timeouts.py` (surgical textual timeout edits — the first version
reformatted 296 lines, hence "textual"), `command-center/hook-audit/probe_hook_fleet.py`
(fleet timing + fire-to-prove-inertness), `command-center/hook-audit/check_citations.py`
(evidence-drift gate), `hooks/checkpoint/wire.py --check` (purpose-built wiring detector,
fails closed, `rc 1` on FINDING).

---

## 1. /rollback gap — STILL OPEN, re-confirmed independently today

`_g5_livestate.py`, reading `events[ev]["checks"]` (the dict-vs-list trap that produced a
false parity four times in this program):

| | live | repo |
|---|---|---|
| dispatcher checks | **25** | **27** |
| PreToolUse checks | 5 | 7 |
| repo-only checks | — | `edit-checkpoints`, `mcp-liveness/pretool` |
| live-only checks | **none** | — |

`settings.json` (42 entries / 20 events) mentions `checkpoint` **nowhere**, so the producer is
unwired on both surfaces. Consumer freshness, `_g5_ckptroot.py` — and note the index lives at
`~/.claude/checkpoints/<session-id>/index.ndjson`, a per-session subdir; my first pass looked
at the root and reported "no index", repeating round 1's exact detector error:

* 12 session dirs carry an index, **944 records total**
* newest write **2026-07-17T21:24Z** = **26.7 days stale**

So `/rollback` has silently returned nothing for ~27 days. Verdict `PRODUCER-DARK`.

Controls: C1 live count ≥20 (fail-closed); C2 a known-present check (`wire-check`) must be
found by the same matcher, else silence about `edit-checkpoints` means nothing — passed;
C3 the repo must actually contain it, else the premise moved — passed.

---

## 2. NEW AXIS nobody has checked: the fleet against the VENDOR's contract

Source: `https://code.claude.com/docs/en/hooks`, **fetched 2026-08-13** (not recalled).
`_g5_vendorcaps.py` encodes each vendor fact so a doc change invalidates loudly.

### 2.1 The round-4 event-ceiling finding is CONFIRMED by the vendor spec, and now has a mechanism

The vendor says `timeout` is **per-hook-command**, and a timed-out hook "is canceled
individually … other hooks continue running". That does **not** soften round 4 — it explains
it. Our dispatcher is registered as **one** command holding N checks, so the vendor's
per-command cancellation lands on the whole dispatcher and **all 9 Stop checks lose their
output together**. Round 4's `55 s of git-hygiene's 90 s is unreachable` stands, and the
architectural reason is now citable rather than inferred.

### 2.2 `if` is usable for the /rollback deploy — and is a landmine everywhere else

`if` is evaluated **only** on `PreToolUse`, `PostToolUse`, `PostToolUseFailure`,
`PermissionRequest`, `PermissionDenied`. **On any other event a hook carrying `if` never
runs at all.**

* Deploy-plan option (b) "narrow with an `if`" targets `PreToolUse` → **valid**. Confirmed.
* `V4_if_used_total = 0` of 42 — third independent confirmation of the rounds-1–4 count.
* Nobody has been bitten yet *because* nobody uses it; the first author who adds `if` to a
  `Stop` or `SessionStart` hook silently disables it. Worth a one-line lint.

### 2.3 Vendor timeout caps — one flag, and I am calling it a NON-issue

`SessionEnd/end.py` declares 10 s against a documented **1.5 s shared** SessionEnd budget.
The same doc sentence grants an automatic raise to 60 s max when individual timeouts require
it, so 10 s is accommodated. **My probe flagged it; the flag is wrong and I am withdrawing
it rather than shipping it.** `UserPromptSubmit` (cap 30 s) and `MessageDisplay` (cap 10 s):
no entry exceeds its cap. **Real cap violations: 0.**

### 2.4 Unused event surface

11 of the vendor's events are unused: `Setup`, `PostToolBatch`, `FileChanged`, `CwdChanged`,
`DirectoryAdded`, `InstructionsLoaded`, `Notification`, `MessageDisplay`,
`UserPromptExpansion`, `Elicitation`, `ElicitationResult`. Capability map, not a defect.

---

## 3. NEW FINDING: a blocking gate wired where blocking is ignored

`H9-BLOCK-CENSUS.json` lists 11 blockers **as file paths with no event attached**, so the
question "is this blocker wired somewhere blocking is honoured?" was never asked.
`_g5_blockevent.py` asks it (K1 positive control `deny-credential-reads`→PreToolUse resolved;
K2 synthetic name→0; K3 arms discriminate — all passed).

**10 of 11 are fine.** One is not:

> **`per-edit-check/check.py` is wired ONLY at `PostToolUse`, and `PostToolUse` ignores exit 2.**

Two independent signals place it: live `settings.json` → `PostToolUse`, matcher
`Edit|Write|MultiEdit`, timeout 12; and it fired at me during this very session as
`PostToolUse:Write hook additional context: [per-edit-check] …`. It is in no manifest event.

It genuinely attempts to block — `return 2` at two sites in **both** trees (repo 658 / 694,
live 326 / 362) — and its own comment asserts the mechanism:

```
# Hard block: Claude Code reads STDERR on exit 2; any JSON on
# stdout is silently ignored at that exit code.
```

Per the vendor spec `PostToolUse` is non-blocking: the tool **already ran**, and exit 2 only
routes stderr to Claude as feedback. So:

* the **syntax-error** "hard block" cannot prevent the write — the file is already on disk;
* the **hardcoded-credential** `return 2` (AGENTS.md §9 text in the message) likewise cannot
  prevent the secret being written. It is a strong *nudge*, not a guard.

**Correctly scoped:** this is not "the hook is broken" — as an injector it works and I watched
it work. The defect is that a security-relevant path is *documented and coded as prevention*
while being *positioned as after-the-fact feedback*. Fix is a positioning decision (move the
secret check to `PreToolUse`, where `deny-credential-reads` already blocks successfully), not
a code fix. **UNVERIFIED inline:** I did not execute a write containing a synthetic fake
secret to observe that the file survives. Settling experiment: write a file with a
placeholder-shaped fake credential to a scratch path and check whether it exists afterwards.

---

## 4. NEW FINDING: the drift surface is the script BODIES, not just the manifest

Every prior round measured `_dispatch/manifest.json` (which hooks are *wired*).
`_g5_bodydrift.py` measures the layer underneath — for files present in **both** trees, do the
bytes agree? sha256 over **LF-normalised** bytes, so a pure CRLF difference is not counted
(counting it would manufacture a flood, and "hooks that fire so noisily they are ignored" is
one of this audit's own axes). Controls D1 positive (192 files compare EQUAL), D2 negative
(synthetic mutation detected), D3 discriminate — all passed.

* 235 files shared · **43 differ (18.3%)** · 29 repo-only · 1 live-only
  (`semantic-router/success.json`)
* **12 of the 43 are WIRED live checks** — the live harness is running a different program
  from the one in git:

<!-- cite: id=G5-pec-r file=G5-BODY-DRIFT.json path=differs_and_wired.7.repo value=29703 -->
<!-- cite: id=G5-pec-l file=G5-BODY-DRIFT.json path=differs_and_wired.7.live value=15378 -->
<!-- cite: id=G5-wc-r file=G5-BODY-DRIFT.json path=differs_and_wired.10.repo value=24936 -->
<!-- cite: id=G5-wc-l file=G5-BODY-DRIFT.json path=differs_and_wired.10.live value=13862 -->
<!-- cite: id=G5-disp-r file=G5-BODY-DRIFT.json path=differs_and_wired.0.repo value=16138 -->
<!-- cite: id=G5-disp-l file=G5-BODY-DRIFT.json path=differs_and_wired.0.live value=20378 -->
<!-- cite: id=G5-gh-r file=G5-BODY-DRIFT.json path=differs_and_wired.3.repo value=53882 -->
<!-- cite: id=G5-ttg-r file=G5-BODY-DRIFT.json path=differs_and_wired.9.repo value=14626 -->
<!-- cite: id=G5-nfp-r file=G5-BODY-DRIFT.json path=differs_and_wired.6.repo value=3856 -->

| wired check | repo B | live B | delta |
|---|---|---|---|
| `per-edit-check/check.py` | 29,703 | 15,378 | −14,325 |
| `wire-check/check.py` | 24,936 | 13,862 | −11,074 |
| `codex-monitor-autolaunch/check.py` | 10,829 | 5,359 | −5,470 |
| `_dispatch/dispatch.py` | 16,138 | 20,378 | **+4,240** |
| `git-hygiene/check.py` | 53,882 | 50,504 | −3,378 |
| `background-digest/reader.py` | 12,055 | 9,081 | −2,974 |
| `test-tamper-guard/guard.py` | 14,626 | 12,742 | −1,884 |
| `no-force-push/hook.py` | 3,856 | 2,200 | −1,656 |
| `memory-spool/flush_check.py` | 6,124 | 4,773 | −1,351 |
| `workflow-monitor-autolaunch/check.py` | 4,628 | 3,449 | −1,179 |
| `honest-signal/check.py` | 14,699 | 15,482 | +783 |
| `semantic-router/route.py` | 15,725 | 15,524 | −201 |

`wire-check` and `git-hygiene` are the two already-known undeployed fixes. The other ten are
new. **Two are blocking security hooks** — `test-tamper-guard` and `no-force-push` — running
bodies that are not the audited ones.

### 4.1 The deploy plan's safety claim is scoped to the manifest and must not be generalised

`HOOK-MANIFEST-DRIFT.md` concludes "deploying repo→live is SAFE … nothing live would be
lost". That is **true of manifest entries** and is not refuted. It is **not** true of the
trees, and it is one careless copy away from being read that way — the deploy plan's Step 1
says "copy … the two hook trees if absent".

**I nearly shipped this as "live-ahead" off the byte count. It is DIVERGED, both directions:**

| file | defs LIVE-only | defs REPO-only | repo mtime | live mtime |
|---|---|---|---|---|
| `_dispatch/dispatch.py` | `_budget`, `_collect`, `_label`, `_wall_cap` | `_blocking_status`, `_check_label`, `_disarmed_note`, `_receipt`, `_resolve_script` | 2026-08-09 | 2026-08-07 |
| `honest-signal/check.py` | `_analyze_forward`, `_analyze_tail`, `_readable`, `_tail_lines`, `_tool_names` | `_anchors`, `_blocks`, `_stringify` | 2026-08-09 | 2026-08-08 |

The name sets *look* like a refactor (`_label`→`_check_label`), which would make repo→live a
clean upgrade. **Byte counts, def names and mtimes cannot settle that** — mtime distinguishes
"written recently" and nothing else. This is exactly the DIVERGED case that a one-directional
read misclassifies as deploy-safe (measured elsewhere on this estate: 31 of 47 such errors all
pointed at data loss). **Settling experiment: read the 12 diffs before any tree copy.**

---

## 5. Ranked plan

**P0 — read the 12 drifted wired diffs before ANY deploy.** Cheap, blocks the one action that
can destroy live behaviour, and converts §4 from a warning into a decision. Start with
`_dispatch/dispatch.py` (the dispatcher itself) and the two security blockers.

**P1 — decide `/rollback`, do not leave it as-is.** The plan's three options are costed
(369 ms first edit per turn, 195 ms after, quiet box; up to ~7.4 s under a full wave; worst
sample ever = 49.5% of the 15 s check budget). Option (c) — amend `commands/rollback.md` — is
the zero-latency honest default and needs no owner latency call. A command that has promised
a capability it has not had for 27 days is the worst of the three states.

**P2 — wire `check_citations.py` into CI.** Round 4 named this "the single highest-value
follow-up"; I re-measured and it is still true: `grep -rn check_citations .github/workflows/`
returns **0 hits**. A gate that runs only when an agent remembers is a producer with no
consumer — the same class as the `/rollback` gap. One line in the existing docs job.
**Hazard: `.github/workflows/quality.yml` is shared with every sibling lane and is the file
that red-blocked main.** Coordinate before editing.

**P3 — reposition `per-edit-check`'s secret check to `PreToolUse`** (§3), or downgrade its
"Hard block" comment and `return 2` to an honest inject. Prevention and feedback are different
products; today it is coded as the first and wired as the second.

**P4 — extend the drift differ to the body axis and gate the deploy.** `probe_hook_manifest_drift.py`
already covers manifest entries both directions; `_g5_bodydrift.py` covers bodies. Merging them
into one local pre-deploy gate closes "the repo→live deploy step has no gate at all", which
every round has named as the largest hole. It cannot run on a GitHub runner (no `~/.claude`).

**P5 — one-line lint for `if` on a non-tool event** (§2.2). Nothing is broken today because
`if` is unused; this is a tripwire for the first person to use it.

**Explicitly NOT recommended:** re-timing the fleet (rounds 1–4 own it), rebuilding any differ
in §0, or "consolidating" `command-center/hook-audit/` — it holds the frozen evidence blobs the
citation gate resolves against.

---

## 6. Detector failures of mine, recorded not deleted

1. Looked for the checkpoint index at the CKPT root; it is per-session. Reported "no index",
   which is round 1's identical error. Fixed in `_g5_ckptroot.py`, which now reports
   SEARCH-FAILED rather than "absent" when no root exists at all.
2. Flagged `SessionEnd` 10 s as a vendor-cap violation, then read the rest of the sentence
   (auto-raise to 60 s) and withdrew it. Shipped as a non-issue in §2.3.
3. Called `_dispatch/dispatch.py` "live-ahead" from a byte count. It is DIVERGED. Corrected
   in §4.1 before it reached a recommendation.
4. Feared I had clobbered a pre-existing untracked `docs/hook-audit/GROUNDING.md`. Two signals
   say no: `git log` shows no commit ever touched the path, and the slop-report census records
   it at **999 bytes** — exactly my skeleton's size, i.e. it censused my own file.
