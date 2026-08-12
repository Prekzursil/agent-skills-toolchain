# Cross-vendor review rail is DOWN — and it gates 43 blocked units

**Measured 2026-08-12 ~10:45.** This matters because `blocker_census.py` (3adf4ceb) established that
43 of 47 BLOCKED Prompt Two receipts name an **independent cross-vendor review** gate —
`blocked-on-independent-cross-vendor-review`, `reviewer-absent`, `self-review-is-not-review`. Those
units are measurement-complete. The single mechanism that would unblock them is Codex review, and
that mechanism does not currently work.

## "Connected" is not "works"

| probe | result |
|---|---|
| `codex --version` | `codex-cli 0.145.0` |
| `Get-Command codex` | `…\npm\codex.ps1` — on PATH in both shell views |
| `claude mcp list` | `codex: codex mcp-server - ✔ Connected` (line 37 of 67; 55 servers connected) |
| **an actual `mcp__codex__codex` call** | **FAILS**: `agent identity registration failed for https://auth.openai.com/api/accounts/v1/agent/register` |

Three green signals and the rail is still unusable. The health check proves the server *starts*; it
does not exercise OpenAI auth. This is the single-signal trap in its most expensive form — **had I
dispatched all 43 units instead of probing one first, all 43 would have failed**, likely after
burning wall-clock on each.

That is the reusable lesson: before a cross-vendor fan-out, spend one unit proving the rail
end-to-end. `claude mcp list` is not that proof.

## Read-only diagnosis (no credential action taken)

`~/.codex/auth.json` — 215 bytes, modified **2026-08-11 22:15**:

```
top-level keys: ['auth_mode', 'OPENAI_API_KEY']
```

Key *names* only; no value was read, printed, or logged. What this shows:

- There is **no OAuth token object** — no `tokens`, no `id_token`/`access_token`/`refresh_token`, so
  there is no JWT whose `exp` could be checked. The file is API-key mode only.
- The failing endpoint is `accounts/v1/agent/register` — *agent identity* registration, which is a
  ChatGPT-account-session operation, not an API-key operation.

So the most likely cause (**likely, 55-80%**) is that `codex mcp-server` requires the ChatGPT login
session for agent registration and only the API key is configured. The competing explanation
(**uncertain, 20-55%**) is that the key exists but lacks the agent-registration entitlement. Both
are settled by the same one command, which is why I did not spend more probes separating them.

UNVERIFIED, inline: I did not establish *what* modified `auth.json` at 22:15 on 2026-08-11, roughly
when this session began. It was not this session — no credential file has been written here.
Settling experiment: check the file's prior version if any backup exists, or correlate against the
other session's activity.

## What unblocks it — OWNER ACTION, not mine

```
codex login
```

AGENTS.md §9 reserves credential lifecycle to the owner: never remove, rotate, revoke, regenerate,
unset or otherwise modify any API key or token. `codex login` writes credentials, so it is yours.
Read-only diagnosis — presence, size, key names, whether it authenticates — is expected and is what
was done here.

Note also, observed while probing and unrelated to the fix: `claude mcp list` prints
*"claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth source is set and takes
precedence over your claude.ai login"*. Same shape — an env-set API key shadowing a login session.
Reported, not touched.

## Consequence for the program

Until the rail is restored, the 43 review-gated units **cannot** be moved to DELIVERED by any amount
of further building, because their own receipts withhold SUCCESS pending an independent reviewer and
`self-review-is-not-review` is one of the recorded classifications. Building more units adds more
artifacts to the same queue.

Two paths, and the choice is the owner's:

1. **Restore the rail** (`codex login`) and run one review agent per gated unit. Highest value; also
   spends the ChatGPT subscription rather than competing for Claude tokens.
2. **Accept a same-vendor independent reviewer** — a fresh-context Claude agent that did not build
   the unit. Weaker than cross-vendor (it shares the builder's blind spots, which is precisely what
   `blocked-on-independent-cross-vendor-review` is guarding against), but it is available now and
   several receipts name only `blocked-on-independent-review` without the cross-vendor qualifier.

Option 2 would move some units but must not be silently substituted for option 1 on the receipts
that explicitly demand cross-vendor — doing so would satisfy the gate's letter while defeating its
purpose.
