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

A `"command"` placed directly on the matcher group is **not a handler** — the group has no
recognized handler list, so the config is structurally invalid and the command never spawns.
It fails SILENTLY: no error, just a hook that never fires. The in-repo builder emits exactly the
nested form (`agent-self/harness/registration.py:82-102`, `:151-169`), and the live config uses
it too (`agent-self/config/settings.json`).

**Hooks read their input as JSON on stdin — there is no `$FILE_PATH`.** The edited path arrives
as `tool_input.file_path`; nothing exports it as a shell variable. Extract it in the command
(the examples use `python -c`, which is available wherever the harness runs).

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

Block oversized writes from tool input content, not from a file that may not exist yet.
This is a BLOCKING gate (`exit 2`), so it must stay a standalone `settings.json` entry — folding
an `exit 2` check into a shared inject-only dispatcher silently disarms it:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "node -e \"let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const i=JSON.parse(d);const c=i.tool_input?.content||'';const lines=c.split('\\n').length;if(lines>800){console.error('[Hook] BLOCKED: File exceeds 800 lines ('+lines+' lines)');console.error('[Hook] Split into smaller modules');process.exit(2)}console.log(d)})\"",
            "timeout": 10,
            "statusMessage": "Block writes that exceed 800 lines"
          }
        ]
      }
    ]
  }
}
```

## Stop Hooks

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
