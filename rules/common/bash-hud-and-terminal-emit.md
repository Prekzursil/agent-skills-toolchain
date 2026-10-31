---
paths:
- '**/*.sh'
- '**/*.ps1'
- '**/statusline*'
permalink: dqverify-repo-20261013/rules/common/bash-hud-and-terminal-emit
---

# Bash HUD / terminal-emit gotchas

Hard-won building a Claude Code **statusline** (a bash script that runs on every render and emits
ANSI/OSC to the terminal from partly user-influenceable JSON). Every item below cost real debugging
or was caught only by an adversarial/perf lens. They generalise beyond the statusline — any bash that
parses a delimited record, colours output, reads file-mtimes, or emits terminal escapes.

## 1. A counter mutated inside `$( … )` is LOST (subshell), so caps silently fail

Command substitution runs in a **subshell**; assignments to a parent variable inside it are discarded.
A `≤2 coloured segments` cap implemented as `c=$(colorize …)` where `colorize` did `ncol=$((ncol+1))`
**never capped** — measured 3 coloured. The subshell's `ncol++` evaporated on return.

- **Fix:** mutate in the MAIN shell. Have the helper set a global (`REPLY`) and call it directly —
  `colorize "$lvl" "$txt"; seg=$REPLY` — never `seg=$(colorize …)`.
- Generalises to any accumulator/counter/flag a helper is meant to advance (running totals, "have I
  seen X", width budgets). If the mutation must survive, the call cannot be in `$(…)`, `<(…)`, or a pipe.

## 2. Sanitize INSIDE the parse, BEFORE the delimiter split — not per-field after

Parsing a delimited record (`IFS="$US" read -r a b c …`) and *then* stripping bad bytes per-field is
too late: a delimiter byte **inside a field value** shifts every later column before your `tr` runs.
Measured (HIGH severity): a `U+001F` in `session_name` shifted its tail into the un-sanitized
`transcript_path` slot, which then built a spoofed OSC-8 link — the field defeated its own sanitizer.

- **Fix:** strip control bytes in the producer, before the join/split. With jq:
  `map(tostring | gsub("[[:cntrl:]]";"")) | join("\u001f")` — every field is clean *before* the
  delimiter is added, so no value can carry the delimiter OR an escape. (`jq [[:cntrl:]]` is verified
  to strip ESC/BEL/US/CR/LF.) This closes escape-injection AND column-shift in one place.
- Corollary — **treat every field that reaches the terminal as hostile**: `session_name`, a harness
  goal, a git branch, `pr.url`, `output_style.name` are all user/other-process-influenceable. A per-field
  `tr -d '\000-\037\177'` is the fallback for values that do NOT pass through that jq (cache/file reads).

## 3. Stall detection from file-mtimes alone is IMPOSSIBLE — don't ship it

A *stalled* process and a *long-completed* one are indistinguishable from mtimes: both simply stop
updating their file. A "subagent stall" segment that showed `⚠<oldest-file-age>` flagged an **11-hour-old
finished** agent as a live stall. mtimes give you exactly one honest signal: **N = files written in the
last ~T seconds = currently active**. Anything claiming "stuck/hung/frozen" needs orchestrator state
(which agents are *expected* to be running) that a file listing does not contain.

- **Fix:** ship only the defensible count (`ag:N`). If you need real stall detection, get it from the
  orchestrator, not the filesystem. Applies to any "is this job hung?" heuristic built on mtimes.

## 4. Don't hardcode "the default" from the session you're testing in

An expected-value comparison seeded from the current session mis-fires everywhere else. mode-drift used
`output_style != "Honest"` (this session's style) → every *normal* `default`-style session was flagged
as a drift. "Your normal" is not knowable from one sample.

- **Fix:** default expectations to the tool's **stock** defaults and make them env-tunable
  (`STATUSLINE_EXPECT_STYLE`, `…_EFFORT`). A deviation-detector must compare against a stable baseline, not a snapshot.

## 5. Emitting to the terminal: glyph width, colour, and the visible-width trap

- **Emoji-presentation glyphs are double-width and corrupt alignment.** `⚠` (U+26A0) renders width-2 on
  Windows Terminal and overlapped its neighbour. Use width-1-unambiguous marks (`!`, `✓`, `✗`) or ASCII;
  keep the line emoji-free. East-Asian *ambiguous* block chars (`▓ █` eighths) are width-2 under a CJK font.
- **Colour is a scarce channel — cap it.** Preattentive pop-out only fires when the coded feature is
  *unique*; colouring everything manufactures alarm-fatigue. Reserve colour for the ONE (≤2) segment
  crossing a threshold; carry a glyph too so mono / `NO_COLOR` / colour-blind readers still see it. Use
  16-colour SGR (maps to the user's theme) over hardcoded truecolor (can vanish on a dark theme).
- **`${#s}` counts escapes, not visible cells.** Any width-based truncation over a string containing ANSI
  or OSC-8 will slice mid-escape and corrupt it. Strip `ESC]8;;…BEL` and `ESC[…m` first. PERF: the raw
  `${#s}` (incl. escapes) is an *upper bound* on visible width, so only pay the strip when raw length already exceeds the budget.

## 6. Registry/URI handler: reject UNC and non-local paths after normalization

A custom URI scheme (e.g. `claude-session://`) is invocable by ANY app with an attacker-chosen target.
A crafted `claude-session:///evil.example/share` normalized to a UNC `\\evil.example\share`; `Test-Path`
/ `explorer` on a remote UNC coerce an outbound **SMB/NTLM** authentication = hash leak/relay.

- **Fix:** after path normalization, reject `^\\` (UNC) and anything that is not a drive-absolute local
  path (`^[A-Za-z]:\`). Never *synthesize* a UNC from `///server`. Validate the resolved path is under the expected root.

## 7. Statusline perf is per-render process spawns (a slow line is CANCELLED)

Claude Code debounces renders 300ms and **cancels** an in-flight one. On a memory-pressured Windows box a
`jq` spawn measured ~200ms, bare `bash` ~350ms — so spawn count, not code, is the budget.

- ONE `jq` to parse stdin (not one per field). Cache slow reads (`git`, `find`) with a short TTL keyed by
  session/cwd, and existence-gate them (`[ -d … ]`) so an idle session pays nothing. Prefer bash builtins
  over `cut`/`sha256sum` for cache-key derivation; cache a per-session hash so `sha256sum` runs once.
- Write caches atomically (`tmp.$$` + `mv -f`) so a render cancelled mid-write can't leave a half-file.
- Measure spawns by shimming `PATH` (a wrapper per tool logging its name), NOT by grepping the script text
  (a text grep counts comments and substrings). **Control the detector first** — confirm the shim catches a
  known spawn before trusting a zero.

## 8. Editing scripts that contain a `\u001f` (or any control byte) delimiter

The Edit tool may convert a `\u001f` in replacement text to a literal 0x1f byte, or drop it; and a literal
control byte in a **Bash-tool command** trips the control-char validator. jq `join("\u001f")` and
`join("<literal 0x1f>")` produce identical output, but the literal makes future Edits fragile.

- **Fix:** keep delimiters as the `\u001f` escape; normalize with a Write-tool python fixer using
  `chr(0x1f)`; verify counts with `grep -n` + a python `.count()` — a bare `grep -c 'join("\u001f")'` lies
  (`\u` is not portable grep regex; you'll see `grep -n` show 4 and `grep -c` show 0 = a broken detector, per single-signal-verification).

---
*Captured 2026-07-24 from the statusline-HUD rebuild. Related: [[single-signal-verification]] (detector
control), [[windows-shell]] (`\u001f`-in-command, CRLF), [[fan-out-contract]] (the parallel sec+perf review
that surfaced §2/§6/§7).*