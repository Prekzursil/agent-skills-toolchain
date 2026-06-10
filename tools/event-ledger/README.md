# event-ledger — the N2 keystone (anti-echo-chamber memory)

**Deployed at:** `~/.claude/hooks/event-ledger/` (this is the versioned copy — keep in sync).

The root fix for the post-compaction **echo-chamber** + repetitive actions: an append-only,
failure-aware, per-project **typed event ledger** that hooks write continuously, and that
**recovery replays as ground truth** instead of trusting a lossy self-summary.

Compaction keeps *what happened* and destroys *why* (decisions/failures/rationale). The
ledger stores exactly that. Because it's written every turn (Stop hook), it's always
current *before* compaction — unlike a PreCompact snapshot authored from an already-degraded
context (and PreCompact doesn't even fire on `/clear`, CC #13572 — the replay covers it).

## Files
- `ledger.py` — stdlib core: `append(project, kind, **fields)`, `replay(project, n)`, `state(project)`. Storage `~/.claude/event-ledger/<project-slug>/events.jsonl` + `state.json`. Monotonic `seq`. Kinds: turn / decision / failure / goal / milestone / note.
- `stop-hook.py` — **Stop hook**: per-turn objective harvest (git HEAD/branch/dirty). Record-only, exit 0, honors `stop_hook_active` (never loops).
- `sessionstart-replay.py` — **SessionStart hook**: on `resume`/`compact`/`clear` injects the ground-truth tail (goal + open **failures** + decisions + turn timeline) and flags **HEAD drift**. No-op on fresh `startup` (keeps tokens off the normal path).
- `note.py` — agent-facing CLI to annotate the *why*: `python note.py --kind failure "X" --preconditions "Y"` ; `--kind milestone "Z" --supersedes 3,5` auto-tombstones retired failures.
- `test_ledger.py` — `python test_ledger.py` (13 checks, temp root, stdlib only).

## Wiring (settings.json, additive)
```
"Stop":        [{ "hooks": [{ "type":"command", "command":"python …/event-ledger/stop-hook.py", "timeout":10 }] }]
"SessionStart":[ …existing…, { "matcher":"*", "hooks":[{ "type":"command", "command":"python …/event-ledger/sessionstart-replay.py", "timeout":10 }] } ]
```

## Design provenance
N2 in `docs/plans/2026-06-11-workspace-design-v1.md` / knowledge base. Failure-aware + TTL +
auto-tombstone fixes the rotting-notes problem (the vault's own scholarly-access "don't trust
it" amendment). Future: feed `(query, chosen_tool, success)` triples to the **OATS** loop (N3)
so discovery self-improves from usage.
