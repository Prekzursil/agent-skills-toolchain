---
title: Private-estate plaintext policy
date: 2026-09-24
status: ACTIVE — this is the SSOT for the credential-handling rule
supersedes: "the 2026-09-23 vault note decision taken while the repo was public"
---

# The rule

This estate is **private and single-owner**. Credentials may be **read, printed,
written and committed in plain text** inside it — local sessions, local files, and
the **private** `agent-skills-toolchain` vault.

Owner instruction, 2026-09-24, verbatim:

> "the repo is private and the rule is that credentials can live there uncensored
> in plain text, make sure that is settled forever everywhere"

> "the rule is everything can go nothing is offlimits ofc apart fom cache and
> residuals ofc"

> "please modify all rules everywhere so that agents dont freak out with
> credentials in plaintext in private sessions like these on local side"

**An agent that redacts, refuses, warns or lectures about a credential on this
side of the boundary is exhibiting the defect, not the safeguard.** Reading one's
own `.env`, `~/.ssh`, `auth.json` or config is ordinary work.

## The boundary is egress, not existence

| Inside the estate | Crossing out of it |
|---|---|
| Read / print / write credential values | Public remote, third-party service |
| Commit them to the **private** vault | Any repo that is not that private vault |
| Store them beside the config that uses them | Pasting into an external tool or API |

Excluded from the vault regardless: **cache and build residue** (`.venv/`,
`out/`, `__pycache__/`, browser-profile binaries). Not a secrecy rule — a weight
rule.

## What did NOT change, and why

These four remain hard refusals. The first is now **load-bearing**: it is what
makes plaintext storage safe, so it must never be weakened.

1. **Flipping `agent-skills-toolchain` public.** `estate-deny-guard` refuses it.
2. **Force-push to main** without explicit approval.
3. **`--no-verify`** on commit or push.
4. **Rotation of any credential.** The owner rotates; the agent never does. An
   agent may diagnose read-only (presence, scope, whether it still authenticates)
   and must report exposure — but never rotates, revokes or regenerates.

## The honest caveat

**Git history is retroactive.** Anything committed while the repo is private stays
in history if the repo is ever flipped public — it is not only current files that
would be exposed. This repo *was* public as recently as 2026-09-23 (recorded at
the time as "verified world-readable, HTTP 200 unauthenticated") and was made
private that day. "Private" is therefore a state that is maintained, not a
property that is owned, and the repo-public lock is the whole safeguard.

Verified 2026-09-24: unauthenticated HTTP 404, `gh` reports `isPrivate: true`.

## Where this is enforced

| Location | Change |
|---|---|
| `scripts/estate-deny-guard.py` | `secret-file` now scoped to **outside** the private vault; vault paths allowed |
| `scripts/test_estate_deny_guard.py` | 11 cases, ALL-PASS, incl. controls proving the rule still bites outside the vault |
| `~/.claude/hooks/no-force-push/tripwire.py` | use-vs-mention fix (see below) |
| `~/.claude/settings.json` | dropped 4 credential `Read(...)` denies; 3 kept, 47 allow rules untouched |
| `~/.claude/AGENTS-RUNTIME.md` | §0 doctrine + §9 scoped to the public boundary |
| `~/AGENTS.md`, `~/.agents/AGENTS.md` | "do not print secret values" → scoped to egress |
| `~/.agents/rules/estate-locks.md` | raw-secret-file ban scoped to outside the vault |

`~/.claude/hooks/deny-credential-reads/deny.py` needed no change — an owner
directive of 2026-07-11 already made it opt-in and **off by default**, for exactly
this reason.

## The second defect this exposed: use-vs-mention

Every guard matched the **literal text** of a command, so writing a file whose
*content* documented a forbidden command tripped the rule and blocked the write.
An agent could not write this policy note, or the guard's own test, without being
refused. It blocked five legitimate writes on 2026-09-23/24.

Fix: a heredoc written to a **file sink** (`cat >`, `tee`, `git commit -F`) is
data and is stripped before matching; a heredoc piped to an **interpreter**
(`bash`, `python`, `pwsh`) is code and is still scanned, so smuggling a forbidden
command through an executed heredoc stays blocked. `-m`/`--message` bodies are
stripped — they never execute.

Both halves are covered by tests, including a control asserting the rule still
fires on real paths so the fix cannot silently over-correct into a dead rule.

## Review

No expiry. Revisit only if the repo's visibility changes or the estate stops being
single-owner — either event invalidates the premise the whole policy rests on.
