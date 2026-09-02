# test-tamper-guard — EvilGenie diff-guard

A **PreToolUse** hook that intercepts `git commit` Bash calls and scans staged
test-file diffs for weakening signals — the "EvilGenie" pattern where an agent
games the TDD / 100%-coverage gate by weakening tests instead of fixing code.

## What it detects

| Signal | Trigger |
|---|---|
| `file_deleted` | Staged deletion of a test file |
| `assertion_net_drop` | More assert-lines removed than added (net drop > 0) |
| `skip_added` | Added lines containing `@pytest.mark.skip`, `.skip(`, `.only(`, `xit(`, `xdescribe(`, `it.skip`, `test.skip`, `t.Skip(`, `@Disabled`, `@Ignore`, etc. |
| `trivial_assert_added` | Added lines containing no-op stubs: `assert True`, `assert 1`, `expect(true)`, `assertTrue(true)`, `ASSERT_TRUE(true)` |

Under `TEST_TAMPER_MODE=block`, the rows marked below block the commit (exit 2);
`trivial_assert_added` always stays a warn:

| Signal | block mode (exit 2)? |
|---|---|
| `file_deleted` | yes |
| `assertion_net_drop` | yes |
| `skip_added` | yes |
| `trivial_assert_added` | no — warn only |

The hook identifies "test files" by name patterns: `*test*`, `*spec*`,
`__tests__/`, `*.test.*`, `*.spec.*`, `test_*.py`, `*_test.go`,
`conftest.py`, and class-based test names (`TestXxx.java` etc.).

## Behavior

- **WARN by default** (exit 0 + `additionalContext` JSON). This is the original,
  unchanged behaviour — every signal warns, never blocks.
- **Opt-in BLOCK mode (G2)** — set `TEST_TAMPER_MODE=block`: the three
  HIGH-CONFIDENCE signals (`file_deleted`, `assertion_net_drop`, `skip_added`)
  exit **2** to block the commit (reason written to stderr); `trivial_assert_added`
  stays a warn even in block mode (higher false-positive risk). The default remains
  `warn`, so nothing changes unless you opt in.
- **Fail-open**: all logic wrapped in `try/except`; any exception → exit 0,
  no output.  A crashing hook is worse than a silent one.
- **Non-nagging**: emits output only when a concrete signal fires.  No staged
  test files, or no signal → completely silent.
- **External-anchored**: decisions come from `git diff --cached` (a real git
  artifact the model cannot retroactively alter from inside the hook).
- **Event-ledger logging**: each file+signal combo is logged as a `failure`
  entry via `note.py` with `--preconditions test-tamper:<file>:<signal>`.

## Registration (settings.json)

Add one entry to `hooks.PreToolUse` in `~/.claude/settings.json`:

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "python C:/Users/Prekzursil/.claude/hooks/test-tamper-guard/guard.py",
      "timeout": 20,
      "statusMessage": "EvilGenie TDD-guard scanning staged test diffs"
    }
  ]
}
```

Place it **after** the existing `Bash` entries so it runs after other guards
(e.g. the `--no-verify` blocker) but before the commit executes.

## Files

```
hooks/test-tamper-guard/
  guard.py   — the hook (this file)
  README.md  — this document
```

## Manual test

```powershell
# Tamper scenario (should WARN):
$repo = "$env:TEMP\tamper-test-repo"
git init $repo
"def test_add():`n    assert 1 + 1 == 2" | Set-Content "$repo\test_math.py"
git -C $repo add .
git -C $repo commit -m "initial"
"def test_add():`n    pass  # assert removed" | Set-Content "$repo\test_math.py"
git -C $repo add .
'{"tool_input":{"command":"git commit -m x"},"cwd":"' + $repo.Replace('\','\\') + '"}' |
    python C:\Users\Prekzursil\.claude\hooks\test-tamper-guard\guard.py
# Should print JSON with additionalContext warning.

# Benign scenario (should be SILENT):
$repo2 = "$env:TEMP\benign-test-repo"
git init $repo2
"hello" | Set-Content "$repo2\main.py"
git -C $repo2 add .
'{"tool_input":{"command":"git commit -m y"},"cwd":"' + $repo2.Replace('\','\\') + '"}' |
    python C:\Users\Prekzursil\.claude\hooks\test-tamper-guard\guard.py
# Should print nothing.
```
