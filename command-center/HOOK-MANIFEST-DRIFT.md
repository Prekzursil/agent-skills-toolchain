# Hook dispatcher manifest: live vs repo, both directions

live `C:\Users\Prekzursil\.claude\hooks\_dispatch\manifest.json` = 11,219 B
repo `hooks\_dispatch\manifest.json` = 12,848 B

## Verdict: do NOT deploy repo over live, and do NOT sync live over repo

2 hooks exist in git and are NOT deployed; 0 exist live and are
NOT in git; 3 exist on both sides with DIFFERENT behaviour. A one-directional
copy in either direction destroys one of those sets. Union-merge per entry.

## IN GIT, NOT DEPLOYED (the live harness is missing these)

* **`edit-checkpoints`** (PreToolUse) -- script `edit-checkpoints/checkpoint.py`, matcher `Edit|Write|MultiEdit`, timeout 15, emits False
* **`mcp-liveness/pretool`** (PreToolUse) -- script `mcp-liveness/liveness.py`, matcher `mcp__basic-memory__.*`, timeout 12, emits True

## DEPLOYED, NOT IN GIT (a redeploy would delete these)

* none

## SAME HOOK, DIFFERENT BEHAVIOUR (a deploy silently changes these)

| event | hook | field | live | repo |
|---|---|---|---|---|
| Stop | `forge/todo-surfacer` | timeout | `18` | `8` |
| Stop | `git-hygiene` | timeout | `30` | `12` |
| Stop | `stub-ledger/report` | timeout | `25` | `10` |

Comment prose differs on 2 further entries with identical behaviour (claim-guard/ledger-write, edit-validate/record) -- not drift, reported so the byte-size difference is fully accounted for.

