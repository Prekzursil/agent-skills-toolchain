# UNKNOWNS-REGISTER

Things this command center does **not** know, each with the experiment that would settle it.
An unknown recorded here is a measurement that was not taken; it is never folded into a pass.

The distinction this file enforces: `NOT-CHECKED` is a typed status, not a soft `CLEAN`.

## 1. Unknowns about the tracked work

| # | unknown | why it is not knowable today | settling experiment |
|---|---|---|---|
| U-1 | **Whether the 38-item harness tranche was an approved substitute for Prompt Two.** | No approving owner turn was found in the corpus, `17-DECISION-LOG.md`, or `32-OWNER-DECISIONS.md`. Absence of an approval record is weaker than a recorded refusal, so this is UNKNOWN and not DROPPED. | Ask `OQ-4`; or find the turn and record it in `17-DECISION-LOG.md`. Tracked as `R-A04`. |
| U-2 | **Current exposure state of the `Diag 1.txt` credentials.** | Confirmed by a controlled scanner on 2026-07-23 with reproduced counts. Not re-scanned since; the file was deliberately not opened. | A read-only, count-only re-scan plus an inventory of what indexes that directory. Tracked as `R-B08`. |
| U-3 | **Direction of the repo↔live drift for each of the 18 differing rule files.** | Direction is inferred from file size plus one corroborating source (a Q19 measurement of `owner-ops-authorization.md` as live-ahead). Size is not direction. | Search each live variant's hash against every blob of that path in git history — the algorithm already run for monitorcore. Tracked as `R-H10`. |
| U-4 | **Whether all 46 named failure classes are actually seeded as regressions.** | Seven are demonstrably seeded; no registry enumerates the set, so the other 39 are unmeasured. | Populate `TEST-REGISTRY.json` per class and run each. Tracked as `R-A19`. |
| U-5 | **Whether `13-ARCHITECTURE-CANDIDATES.md` really contains 9 committed architectures with independent teams.** | The file exists (98,891 B); the count was never verified. | Parse it and count. Recorded in the register as NOT-CHECKED on the count. |
| U-6 | **Whether `skills/gem-hunt` and the game-domain skill families have any runtime behind their prose.** | DONE-CLAIMED with no `scripts/` and no validation run; `validate-all-skills.ps1` is itself unrunnable. | Re-probe for executable surface; restore the validator (`Q22`). Tracked as `R-A14`, `R-B04`. |
| U-7 | **The two "already answered" owner questions the brief refers to (agentify, dependency).** | Neither appears in `32-OWNER-DECISIONS.md` Q1-Q25 and neither was located elsewhere, so they can be neither listed as open nor confirmed as answered. | Grep the corpus for the answering turn and record it. Carried forward from the register verbatim. |
| U-8 | **Everything marked `[inherited]` in the register snapshot.** | Those rows were not re-probed by the register's own author; by that lane's vocabulary they are NOT-CHECKED-by-them, and they are NOT-CHECKED-by-this-lane too. The largest blocks are the Program-B wiring probes, the monitor package greps (U7/U10/U14/U18/U20/E5/E7), and the Prompt-Two mission grades other than M-1/M-3. | Re-probe per row with a controlled detector before citing any of them as fact. |

## 2. Unknowns about this command center

| # | unknown | settling experiment |
|---|---|---|
| U-9 | **Whether the register gate's advice is any good.** The shadow sink records `{ts, gate, tier, event, reason_code, session_hash}` and **no payload**, so it can settle frequency, timing and selectivity — never whether the item surfaced was the right item. | Add truncated+redacted injected text to `shadow_log()` (already filed as `module-modes.json:41 _next_experiment`), then score fires against subsequent `close.py --evidence` calls via the `register_item_closed_after_fire` metric. Until then the gate may not be promoted past `advise`. |
| U-10 | **Real-session firing rate.** The measured 375-prompt corpus replay is an offline upper bound: it applies no per-item session cooldown and no calibrated-silence gating, both of which only subtract. | Collect ≥20 distinct `session_hash` values in the shadow sink and recompute `fires / distinct sessions`. That is the stage-2 gate in the ladder. |
| U-11 | **Whether the 21 encoded dependency edges are the right ones.** Each quotes the register text that asserts it, and three plausible edges were deliberately NOT encoded with the reason recorded — but "the register says so" is not the same as "it is true of the code". | Attempt the blocked item and see whether the blocker actually bites. A false edge shows up as an item that was ready all along. |
| U-12 | **Whether `close.py`'s refusal policy is the right strictness.** It refuses only violations the change introduces. A close that breaks something two hops away is caught; a close that is merely premature is not. | Observe: count refusals and overrides over the first 20 real closes. |
| U-13 | **Whether the live `~/.agents/harness/modules.py` matches this repo's copy.** The gate is authored against the REPO file, which is the source of truth; the L17 spec's line numbers refer to the LIVE file and do not match the repo's. Deploy state was not measured by this lane. | `install.py --check`, or a sha256 compare of the two trees. Do not assume the live tree has this module until that runs. |
