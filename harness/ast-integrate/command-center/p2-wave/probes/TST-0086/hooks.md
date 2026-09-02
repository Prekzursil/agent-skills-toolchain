# Hook contract (TST-0086 live SUT)

AGENTS.md 6 and the Phase 4 hook contract, measured on this worktree:

- `hooks/_dispatch/dispatch.py` is inject-only: every in-process check is
  wrapped try/except and `main()` returns 0. A check that returns 2 is not
  propagated; a disarmed-block note is appended to additionalContext.
- Standalone settings.json PreToolUse gates (not folded into `_dispatch`)
  still honour exit 2. Live proof: `hooks/no-force-push/hook.py` on
  `git push --force`.
- Internal errors fail open (exit 0). Inject-at-entry on every registered
  Python hook under `hooks/` that `agent-self/config/settings.json` names
  continues the session.
- Advisory guidance (cmd-rewrite, dispatch rc=1) must not become a block.

This file is a probe-local reminder. The catalog inputs
`rules/common/hooks.md` and `hooks/_dispatch/dispatch.py` exist on this
tree and are the live SUT. This is not a claim that production
`~/.claude` host wrap or `~/.agents/harness/dispatcher.py` were executed.
