---
title: CONVENTIONS
type: note
permalink: dqverify-repo-20261013/hooks/tms/conventions
---

# TMS auto-retraction — record convention + helper

A Truth-Maintenance justification graph for **derived reverse-engineering facts**.
It exists to kill the costliest recurring RE failure: the **wrong-but-consistent
anchor** — a bad base/offset/pid that silently poisons every downstream finding and
is only discovered hours later. Here it is *structural*: retract one premise and
every dependent flips `OUT` automatically; a PreToolUse hook then refuses to write
to a stale anchor.

- Engine + CLI: `~/.claude/hooks/tms/` (`tms_core.py`, `tms.py`, `stale_anchor.py`)
- Belief DB: `~/.claude/tms/beliefs.db` (override with `TMS_DB`)
- Stdlib + sqlite3 only. Deterministic and fast.

## The one rule

**When you *confirm* a derived RE fact, record it — with its premises and (if it came
from a file) its source — by calling the CLI.** Building the chain as you go is what
makes the cascade possible later. Asserting only the final finding gives you nothing
to retract.

```
python ~/.claude/hooks/tms/tms.py assert <id> --statement "<what + value>" --kind <kind> \
       [--premises <id,id,...>] [--source <path-to-artifact>]
```

- Assert **premises before dependents** (a premise must already exist).
- Re-asserting the same `<id>` *refreshes* it: clears any retraction/drift and
  re-hashes `--source`. Dependents that rested on it come back `IN` automatically.
- `<id>` is your stable handle (e.g. `base_libnative`, `off_getglobal`, `pid_bc`).

### `--kind`
| kind | use for | hook matching |
|------|---------|---------------|
| `address` | an absolute VA / runtime address | numeric (hex + dec) |
| `offset`  | a module-relative offset / field offset | numeric (hex + dec) |
| `pid`     | a target process id | numeric (dec) |
| `version` | a build/app version the offsets are valid for | version token `15.4.1` |
| `fact`    | any other derived conclusion | symbol-name substring |

## Typical lifecycle (copy-paste helper)

```bash
# 1. anchor (a premise with a source artifact — its bytes get sha-pinned)
python ~/.claude/hooks/tms/tms.py assert base_lib \
   --statement "image base of libnative.so = 0x7fcd000000" --kind address \
   --source /data/app/.../libnative.so

# 2. a derived offset that RESTS ON the base
python ~/.claude/hooks/tms/tms.py assert off_getglobal \
   --statement "getGlobal render fn at base+0x4F1E20" --kind offset --premises base_lib

# 3. the finding that RESTS ON the offset
python ~/.claude/hooks/tms/tms.py assert find_noenergy \
   --statement "no-energy patch target 0x4F1E20" --kind fact --premises off_getglobal

# ...later you discover the base was wrong:
python ~/.claude/hooks/tms/tms.py retract base_lib       # off_getglobal + find_noenergy -> OUT
python ~/.claude/hooks/tms/tms.py explain find_noenergy  # why it is OUT + the root cause
python ~/.claude/hooks/tms/tms.py recheck                # re-hash sources; OUT anything that drifted

# re-derive, then re-assert base_lib -> the whole chain returns to IN.
```

Inspect anytime:
```
python ~/.claude/hooks/tms/tms.py status [--out-only] [--json]
python ~/.claude/hooks/tms/tms.py trace <id>        # full closure: premises up, blast-radius down
```

## What the hook does (`stale_anchor.py`, PreToolUse)

Before an RE tool call it reads the materialized `OUT` set and:

- **SOFT (exit 0 + injected note):** the call's input mentions any `OUT` node's
  value/version/symbol token → injects `STALE ANCHOR: … re-derive before using`.
- **HARD (exit 2, blocks):** a recognized **write/patch to a live target**
  (cheatengine `write_*`/`auto_assemble`, binja/ida `patch_bytes`, frida script
  with a write primitive) whose **target address/offset equals an `OUT`
  `address`/`offset` node**. This is the *only* case that blocks. Re-derive +
  re-assert to clear it.
- **SILENT otherwise.** Fail-open is absolute: missing/corrupt DB or any error →
  exit 0 (allow). Soft injects are deduped for 300 s; hard blocks are not.

Opt-out: `TMS_STALE_ANCHOR=off`, or `touch ~/.claude/hooks/tms/.disabled`.

## Honest limits

- **Source drift is surfaced after `tms.py recheck`** — the hook stays read-only and
  never re-hashes large binaries inline. Run `recheck` (or wire it) after rebuilds.
- **Value-token matching is literal**, not semantic: it matches the same number in
  the tool input. It will *not* see `base + 0xOFFSET` arithmetic resolved at runtime
  unless the literal `OUT` value appears in the call. Hex vs decimal is compared
  per-base (a `0x4536` node won't match a bare `4536`). `fact`/symbol matches are
  best-effort and can collide on common identifiers — hence they only ever *warn*.