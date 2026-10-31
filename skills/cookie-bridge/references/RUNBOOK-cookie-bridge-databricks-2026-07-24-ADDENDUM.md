---
title: RUNBOOK-cookie-bridge-databricks-2026-07-24-ADDENDUM
type: note
permalink: dqverify-repo-20261013/skills/cookie-bridge/references/runbook-cookie-bridge-databricks-2026-07-24-addendum
---

# ADDENDUM — cookie-bridge handoff, verification pass 2026-07-24

**Additive to** `handoff-cookie-bridge-databricks-2026-07-24.md`. Does not replace it.
**Nature:** read-only verification of the handoff's claims. No browser profile was mutated.
**Why it exists:** three of the handoff's statements need correcting, and one Definition-of-Done
item is a FAIL that the handoff records as OK.

---

## 1. REGRESSION the handoff does not cover — Chrome `account_info` is now 0

**Trajectory: 6 → 2 → 0.** The handoff and the 2026-07-23 23:32 receipt both record **2**.
On-disk it is now **0**.

Confirmed by **three mechanically independent detectors**, all agreeing:

| Detector | LIVE | BAK (21-Jul) |
|---|---:|---:|
| JSON parse of `Default\Preferences` | 0 | 6 |
| raw-byte regex `"account_id"\s*:` (different parser entirely) | 0 | 6 |
| `safe_restore_prefs_accounts.py --dry-run` (the bridge's own tooling) | `[]` | 6 |

LIVE `Preferences`: 319,502 B, mtime **2026-07-24 01:02** — i.e. *after* the inject.

**Most likely cause, from the handoff's own record:** step D.5 —
*"patched Preferences (`exit_type=Crashed`, `restore_on_startup=1`)"* — a Preferences rewrite
performed **as part of the cookie operation**, which the handoff's own **hard rule #3** forbids
(*"Never rewrite Preferences as part of cookie inject"*). The rule was written and violated in the
same session. Confidence: **likely (55-80%)** — the mtime ordering and the rule violation line up,
but Chrome rewrites Preferences on its own schedule too, so this is not proven causation.
[UNVERIFIED] Settling experiment: diff the D.5 patch code path against a Preferences snapshot taken
immediately before and after that step.

**Recovery source is INTACT and not at risk:** `Preferences.bak-before-session-restore`
(334,656 B, 2026-07-21 00:36) holds all **6** accounts. Nothing in this flow overwrites it.

**Recovery is BLOCKED on an owner action:**
`safe_restore_prefs_accounts.py --apply --browsers chrome` requires Chrome fully quit.
Chrome was at 51-65 processes across both verification passes. **Not attempted** — force-killing
live browsers is the exact vector that caused the original 2026-07-20 corruption.

**Caveat that cannot be closed read-only:** this is an **on-disk** finding. Whether Chrome's UI
currently shows signed-out requires driving the browser. It may look fine now and only surface on
next launch.

---

## 2. CORRECTION — `--dry-run` is not "Status only"

The handoff's §6 labels the dry-run under **"Status only"**. Measured: it **writes**.

`safe_main_cookie_inject.py --dry-run` created:
- `pre-main-inject-20260723T223726Z\chrome\` and `...\edge\` snapshot directories
- `safe_main_inject_report_20260723T223726Z.json`

**Additive only — no profile mutation** — but it is not read-only, and an operator trusting the
"Status only" label could be surprised. Re-label as *"non-mutating, but writes snapshots + a report."*

---

## 3. CORRECTION — the ChatGPT DoD item was never probed

Handoff §7 lists *"ChatGPT still works without re-inject"* as a Definition-of-Done item.

- `probe_chatgpt_ok` is **empty in both** 2026-07-23 receipts — it was never run.
- The claim rests on *"owner said it's already there"*, which is an assertion, not a probe.

**Mechanically confirmed as skipped (this is good news):** the payload reports
`has_dbauth: True`, `has_okta_idx: True`, **`has_nextauth: False`** — no ChatGPT session cookie was
ever in the Databricks payload. So *"ChatGPT skipped"* holds **mechanically**, not just by
assertion. But *"ChatGPT still works"* remains **UNPROBED** and its DoD box must not be ticked.

---

## 4. What the receipts DO corroborate (handoff is accurate here)

Read with their real schema (`at / payload / cookie_summary / dry_run / snap_root / results` —
an earlier summary used guessed field names and showed blanks):

| Claim | Chrome | Edge |
|---|---|---|
| 30/30 cookies set | `set_ok:30 set_fail:0` ✓ | ✓ |
| probe | `looksLogin:False looksApp:True` ✓ | ✓ |
| integrity | `integrity_ok:True`, 0 issues ✓ | ✓ |
| logins not decreased | 354 → 354 ✓ | 272 → 272 ✓ |
| browsers properly quit | `process_count_start: 0` ✓ | ✓ |

Profile health: Chrome logins 354 / history 7,091 · Edge logins 272 / history 13,978.
**Edge confirmed never multi-account** — single MSA `a_visalon@yahoo.com` before and after,
exactly as the handoff states.
**The guard works:** with both browsers live, the tool correctly declared *"dry-run only; apply will
refuse"*.

**The safety design held. What failed is the Preferences patch bolted onto the end of it.**

---

## 5. Session runway

Cookie store: 30 cookies, extracted 2026-07-23T20:05:38Z.
`DBAUTH` ×3 (one per workspace) expire **2026-07-28 22:51** → **~4.9 days** of runway.
Also present: `bolt.okta.com:idx` (session cookie, no expiry — depends on Chrome restore-on-startup
persistence), `bolt.okta.com:JSESSIONID`, `databricks.com:rl_session`.
Hosts: databricks.com 18 · bolt.okta.com 8 · one per workspace host.

---

## 6. Corrected Definition-of-Done scorecard

| Item | State |
|---|---|
| Main Chrome+Edge reach bolt-datascience without Okta wall | **Not verifiable read-only** — needs the browser driven |
| ChatGPT still works without re-inject | **UNPROBED** — see §3 |
| `account_info` unchanged by cookie ops | **FAILED for Chrome** (2 → 0) · Edge PASS |
| Login Data counts not decreased | **PASS** both |
| Owner-confirmed window restore | Owner judgement |

---

## 7. Next action (owner decision)

The only blocked item is the Chrome account merge. Safe sequence when you are ready to close Chrome:

1. Snapshot Sessions first (handoff hard rule #4) — windows must be preserved.
2. Graceful quit of Chrome (never force-kill — that is the original corruption vector).
3. `safe_restore_prefs_accounts.py --dry-run` → inspect.
4. `safe_restore_prefs_accounts.py --apply --browsers chrome`.
5. Restore Sessions, relaunch with `--restore-last-session`.
6. Re-verify `account_info` = 6 by two independent detectors.

**Do not** bundle any cookie inject into this. The account merge is a **separate step** —
that conflation is what produced §1.

*No cookie values, PATs, or secret-vault contents were read or printed in producing this addendum.*