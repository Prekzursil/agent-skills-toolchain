# Hook dispatcher manifest: live vs repo, both directions

live `C:\Users\Prekzursil\.claude\hooks\_dispatch\manifest.json` = 11,219 B
repo `hooks\_dispatch\manifest.json` = 12,849 B

## Verdict: deploying repo->live is SAFE for the 2 missing hook(s) -- nothing live would be lost

2 hooks exist in git and are NOT deployed; 0 exist live and are
NOT in git; 0 exist on both sides with DIFFERENT behaviour.

With 0 behaviour differences and 0 live-only hooks, a repo->live deploy adds the missing hook(s) and overwrites nothing. The earlier union-merge warning applied to the three Stop timeouts that were live-ahead; those were reconciled in 1527449f.

## IN GIT, NOT DEPLOYED (the live harness is missing these)

* **`edit-checkpoints`** (PreToolUse) -- script `edit-checkpoints/checkpoint.py`, matcher `Edit|Write|MultiEdit`, timeout 15, emits False
* **`mcp-liveness/pretool`** (PreToolUse) -- script `mcp-liveness/liveness.py`, matcher `mcp__basic-memory__.*`, timeout 12, emits True

## DEPLOYED, NOT IN GIT (a redeploy would delete these)

* none

## SAME HOOK, DIFFERENT BEHAVIOUR (a deploy silently changes these)

| event | hook | field | live | repo |
|---|---|---|---|---|

Comment prose differs on 2 further entries with identical behaviour (claim-guard/ledger-write, edit-validate/record) -- not drift, reported so the byte-size difference is fully accounted for.

