---
name: "playwright-interactive"
description: Use when iteratively debugging a local web or Electron app in a persistent Playwright js_repl session without restarting between steps ; do NOT use for one-shot navigation or data extraction (use playwright) ; returns live browser state, screenshots, and console output across iterations.
---

# Playwright Interactive Skill

Use a persistent `js_repl` Playwright session to debug local web or Electron apps, keep the same handles alive across iterations, and run functional plus visual QA without restarting the whole toolchain unless the process ownership changed.

## Preconditions

- `js_repl` must be enabled for this skill.
- If `js_repl` is missing, enable it in `~/.codex/config.toml`:

```toml
[features]
js_repl = true
```

- You can also start a new session with `--enable js_repl` (equivalent to `-c features.js_repl=true`).
- After enabling `js_repl`, start a new Codex session so the tool list refreshes.
- For now, run this workflow with sandboxing disabled: start Codex with `--sandbox danger-full-access` (or the equivalent config for `sandbox_mode=danger-full-access`). This is a temporary requirement while `js_repl` + Playwright support inside the sandbox is still being completed.
- Run setup from the same project directory you need to debug.
- Treat `js_repl_reset` as a recovery tool, not routine cleanup. Resetting the kernel destroys your Playwright handles.

## One-time setup

```bash
test -f package.json || npm init -y
npm install playwright
# Web-only, for headed Chromium or mobile emulation:
# npx playwright install chromium
# Electron-only, and only if the target workspace is the app itself:
# npm install --save-dev electron
node -e "import('playwright').then(() => console.log('playwright import ok')).catch((error) => { console.error(error); process.exit(1); })"

### Core Workflow
### Bootstrap (Run Once)
### Choose Session Mode
### Start or Reuse Web Session
### Desktop Web Context
### Mobile Web Context
### Native-Window Web Pass
