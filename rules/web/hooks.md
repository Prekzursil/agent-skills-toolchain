---
paths:
  - "**/*.tsx"
  - "**/*.jsx"
  - "**/*.ts"
  - "**/*.js"
  - "**/*.css"
  - "**/*.scss"
  - "**/*.html"
  - "**/*.vue"
  - "**/*.svelte"
---
> This file extends [common/hooks.md](../common/hooks.md) with web-specific hook recommendations.

# Web Hooks

## The shape every example below uses (get this wrong and NOTHING runs)

A hook entry has **three** nesting levels, not two:

```text
<Event>  ->  [ matcher group ]  ->  "hooks": [ { "type": "command", "command": … } ]
```

A `"command"` placed directly on the matcher group is **not a handler**: the group carries no
recognized handler list, so the entry is structurally invalid and the command never spawns. It
fails SILENTLY — no error, just a hook that never fires. Two in-repo confirmations, read from
the source rather than inherited: the builder that writes the live config emits exactly the
nested form (`agent-self/harness/registration.py:82-102` `_command_group`, `:151-169`
`build_hooks`), and the hooks this repo actually ships use it too (`hooks/hooks.json`).

`Stop` and the other no-matcher events take **no** `matcher` key — omit it entirely rather than
passing an empty string (`registration.py:99-101` omits the key when `matcher is None`).

**Hooks read their input as JSON on stdin — there is no `$FILE_PATH`.** The edited path arrives
as `tool_input.file_path`; nothing exports it as a shell variable, so a command interpolating it
runs against an empty path. Extract it in the command (the examples below use `python -c`, which
is available wherever the harness runs).

## Recommended PostToolUse Hooks

Prefer project-local tooling. Do not wire hooks to remote one-off package execution.

### Format on Save

Use the project's existing formatter entrypoint after edits:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import json,subprocess,sys; p=json.load(sys.stdin).get('tool_input',{}).get('file_path'); p and subprocess.run(['pnpm','prettier','--write',p])\"",
            "timeout": 30,
            "statusMessage": "Format edited frontend files"
          }
        ]
      }
    ]
  }
}
```

Equivalent local commands via `yarn prettier` or `npm exec prettier --` are fine when they use repo-owned dependencies.

### Lint Check

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import json,subprocess,sys; p=json.load(sys.stdin).get('tool_input',{}).get('file_path'); p and subprocess.run(['pnpm','eslint','--fix',p])\"",
            "timeout": 60,
            "statusMessage": "Run ESLint on edited frontend files"
          }
        ]
      }
    ]
  }
}
```

### Type Check

`tsc` is whole-project, so it needs no path from the payload:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "pnpm tsc --noEmit --pretty false",
            "timeout": 120,
            "statusMessage": "Type-check after frontend edits"
          }
        ]
      }
    ]
  }
}
```

### CSS Lint

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python -c \"import json,subprocess,sys; p=json.load(sys.stdin).get('tool_input',{}).get('file_path'); p and subprocess.run(['pnpm','stylelint','--fix',p])\"",
            "timeout": 60,
            "statusMessage": "Lint edited stylesheets"
          }
        ]
      }
    ]
  }
}
```

## PreToolUse Hooks

### Guard File Size

Flag oversized writes from tool input content, not from a file that may not exist yet.

**Do NOT `process.exit(2)` here.** File length is neither irreversible nor dangerous, and
`AGENTS.md` §6 reserves exit 2 for that class alone (destructive git ops, secrets in code,
force-push to main) — everything else is exit 0 plus `additionalContext`. A length blocker
deterministically denies legitimate work: a generated parser emitted at 801 lines is
refused purely for being long. Inject the nudge instead and let the agent decide:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const i=JSON.parse(d);const c=i.tool_input?.content||'';const lines=c.split('\\n').length;if(lines>800){console.log(JSON.stringify({hookSpecificOutput:{hookEventName:'PreToolUse',additionalContext:'[Hook] This Write is '+lines+' lines (>800). Prefer splitting into smaller modules unless it is generated output.'}}))}})\"",
            "timeout": 10,
            "statusMessage": "Warn (exit 0 + additionalContext) on writes over 800 lines — never blocks"
          }
        ]
      }
    ]
  }
}
```

## Stop Hooks

### Final Build Verification

`Stop` takes no matcher — omit the key entirely rather than passing an empty string:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "pnpm build",
            "timeout": 300,
            "statusMessage": "Verify the production build at session end"
          }
        ]
      }
    ]
  }
}
```

## Ordering

Recommended order:
1. format
2. lint
3. type check
4. build verification
