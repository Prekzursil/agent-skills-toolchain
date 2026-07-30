---
paths:
  - "**/hooks/**"
  - "**/settings*.json"
  - "**/.claude/**"
---
# Hooks System

## Hook Types

The provider emits far more than three events. Registering only the three below is how a
working hook silently never runs — always check the event you need against the generator
before assuming it is wired.

- **SessionStart** / **UserPromptSubmit**: session bootstrap, prompt-time context injection
- **PreToolUse**: before tool execution (validation, parameter modification) — the only
  place an `exit 2` block is honoured
- **PermissionRequest** / **PermissionDenied**: permission-flow observation
- **PostToolUse** / **PostToolUseFailure**: after tool execution (auto-format, checks)
- **PreCompact** / **PostCompact**: context-compaction checkpoints
- **ConfigChange**: settings/config mutation
- **SubagentStart** / **SubagentStop**: subagent lifecycle
- **TaskCreated** / **TaskCompleted** / **TeammateIdle**: task + teammate lifecycle
- **Stop**: when the turn ends (final verification)
- **Notification**: attention alerts (`idle_prompt|permission_prompt`)

**Registration is generated, so an event missing from the generator cannot be reached.**
`agent-self/harness/registration.py:17-34` defines the `EVENTS` tuple and `build_hooks()`
(`:151-183`) emits registrations by iterating **only** that tuple. `Notification` is not in
it, so `hooks/notify-idle/notify.py` — whose module docstring at `:24` explicitly requires
registration under `Notification` with matcher `idle_prompt|permission_prompt`, and whose
desktop/BEL handler at `:118-129` is fully implemented — is never invoked. An unattended
session waiting on a permission prompt therefore alerts nobody. Adding an event to the
generator, not to a hook, is what wires it.

**A conformance check is not an event-name check.** `ci/emit_hook_manifest.py:55-77`
validates top-level keys, that `hooks` is a mapping, an optional string `description`, and
strict JSON round-tripping. It does **not** validate event names, matcher-group nesting, or
typed handler fields — so a malformed registration (a matcher group with no nested `hooks`
array, or a command handler missing `type`/`command`) passes CI unchanged. Verify a new
registration by observing the hook actually fire, not by a green manifest gate.

## Auto-Accept Permissions

Use with caution:
- Enable for trusted, well-defined plans
- Disable for exploratory work
- Never use dangerously-skip-permissions flag
- Configure `permissions.allow` in `settings.json` instead

## Task-tracking Best Practices (Task tools; `TodoWrite` is legacy)

Interactive/default sessions track progress with **`TaskCreate`, `TaskUpdate`, `TaskList`,
`TaskGet`**. `TodoWrite`/`TodoRead` are the superseded names — still accepted, but any hook
or monitor that matches only on them measures nothing in a current session.

Use the Task tools to:
- Track progress on multi-step tasks
- Verify understanding of instructions
- Enable real-time steering
- Show granular implementation steps

The task list reveals:
- Out of order steps
- Missing items
- Extra unnecessary items
- Wrong granularity
- Misinterpreted requirements

**Progress bookkeeping is NOT verification — a hook must classify it as neither.** A
`TaskCreate`/`TaskUpdate`/`TaskList`/`TaskGet` call says where the work stands; it supplies
zero evidence for a claim like *"the payload schema is guaranteed to be valid JSON"*. Any
gate that counts "the agent used a tool" as corroboration must exclude the whole Task family
alongside the legacy Todo names, or an unsupported certainty claim slips through unflagged
the moment the only tool call in the turn is progress bookkeeping. Measured on the current
`hooks/honest-signal/check.py` (`_NON_VERIFYING = {"TodoWrite", "TodoRead"}` at `:54-55`):
the `TodoWrite` control emits the warning, while `TaskCreate`, `TaskUpdate`, `TaskList` and
`TaskGet` each suppress it against the identical offending transcript. When a tool family is
renamed, the exclusion sets that reference it are part of the rename.
