# closed-batch — one reversible apply-when-closed batch for the config flips

`apply_closed_batch.py` applies several `~/.claude.json` changes in ONE guarded,
backed-up, revertible pass — because that file is rewritten by any live Claude session
every ~30s, so a hand edit made while Claude is open is clobbered within the minute.

Mirrors the shape of `tools/mcp/mcp-http-host/apply_registration.py` (dry-run by default,
timestamped backup, `--revert-from`), and adds a live-session guard, per-op selection,
and a scoped project matcher.

```bash
python apply_closed_batch.py --list            # live state, read-only, safe with Claude open
python apply_closed_batch.py                   # dry-run preflight (default; writes nothing)
python apply_closed_batch.py --apply           # the batch, with Claude CLOSED
python apply_closed_batch.py --revert-from ~/.claude.json.bak-20260724-012227
```

## Ops

Each is independently selectable: `--only serena-projects,grep`.

| op | change | notes |
|---|---|---|
| `serena-projects` | drop `"serena"` from `projects[<key>].disabledMcpServers` for the SCOPED repos only | default scope: `agent-skills-toolchain`, `Reframe`, `momentstudio`, `metaswarm` |
| `serena-root` | drop `"serena"` from the ROOT `disabledMcpServers` | see the precedence caveat below |
| `grep` | add `mcpServers["grep"] = {"type":"http","url":"https://mcp.grep.app"}` | remote HTTP ⇒ **zero** per-session stdio processes |
| `playwright` | append `--extension` to `mcpServers["playwright"].args` | has an unmet prerequisite today — see below |

Every op is additive/reversible in the narrow sense: they only delete the single string
`"serena"` from two list shapes, add one absent key, and append one argv flag. Nothing
else is normalised — the untouched value tree is carried through `copy.deepcopy` and
re-serialised verbatim.

## Measured live state (2026-07-24, this machine)

Read with `--list` against the real `~/.claude.json` (234,653 bytes):

```
root disabledMcpServers : 122 entries      root disables serena : True
mcpServers              : 66 registered    grep registered      : False
playwright args         : ["-y", "@playwright/mcp"]
project blocks          : 37   ...disabling serena : 37   (all of them)

scoped repo -> project keys:
  agent-skills-toolchain: 1     Reframe: 4     momentstudio: 1     metaswarm: 0
```

`Reframe` legitimately matches four keys — `Documents/GitHub/Reframe`, `/app`, `/sidecar`,
and the **case-variant** `Documents/github/Reframe`. Those last two differ only in case and
are DISTINCT keys in the live file; nothing here ever merges keys case-insensitively.

`metaswarm` matches **0** project blocks — no project key contains a `metaswarm` path
segment. It therefore gets serena only via the root removal (a cwd with no project block
inherits root). *UNVERIFIED which directory the owner considers "the metaswarm repo"; the
home dir `C:/Users/Prekzursil` is a project block and holds the metaswarm `CLAUDE.md`, so
that may be the intended target. Settling experiment: `--extra-project` it and re-run
`--list` to see the match.*

## The precedence caveat (read before running `serena-root`)

*UNVERIFIED: whether Claude Code resolves `disabledMcpServers` as a UNION of root +
project, or lets the project block override root.* It matters:

- **Union** ⇒ removing serena from a project block alone is a NO-OP; the root removal is
  required for the flip to work at all.
- **Project-overrides-root** ⇒ `serena-projects` alone is sufficient, and `serena-root` is
  unnecessary blast radius.

**Settling experiment (cheap, do this first):** run `--only serena-projects --apply`,
restart Claude, and check whether serena tools appear in `agent-skills-toolchain`. If they
do, precedence is project-overrides-root and you never need `serena-root`.

**Disclosed residual if you do run `serena-root`:** 31 of the 37 project blocks still list
serena and stay disabled, but any cwd WITHOUT a project block (every new/unlisted
directory) would then get serena enabled. That is the cost of the root removal, and it is
why the two halves are separate ops rather than one.

## The `--extension` prerequisite is NOT met today

`--extension` is a real flag — confirmed in the installed package's own docs,
`@playwright/mcp@0.0.78` `README.md:425`: *"Connect to a running browser instance
(Edge/Chrome only). Requires the 'Playwright Extension' to be installed."* (env equivalent
`PLAYWRIGHT_MCP_EXTENSION`).

**Measured 2026-07-24: that extension is NOT installed** — 21 extension `manifest.json`
files scanned across every Chrome profile (default + the `.chrome-automation` CDP profile),
**0** with a name matching `laywright`. Detector caveat, disclosed: it scans
`*/Extensions/**/manifest.json` to depth 3 and reads the `name` field; it is known to WORK
because it found 19 manifests in the CDP profile. So the absence is a real reading, not a
broken probe — but it cannot see an extension installed outside those profile dirs.

**Therefore: leave `playwright` out of the first apply** (`--only serena-projects,serena-root,grep`)
until the extension is installed, or the MCP server will fail to connect. The preflight
prints this prerequisite every time.

## grep endpoint

CONFIRMED live (2026-07-24): a stdlib `POST` of an MCP `initialize` to
`https://mcp.grep.app` returned `200 text/event-stream` with
`{"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":true}},"serverInfo":{"name":"mcp-typescript server on vercel"}}`,
no auth required. *UNVERIFIED: quota, rate limits, and pricing — single-source, not
measured. Settling experiment: register it, run a few searches, and watch for 429s.*

## Safety

- **Refuses to write while Claude runs.** Matches the process IMAGE NAME (`claude.exe` /
  `claude`), never the command line — a command-line match would self-fire on this script's
  own argv when it runs from under a `.claude` directory.
- **Fails CLOSED.** If the process table cannot be read at all, it refuses rather than
  assuming the coast is clear. `--ignore-claude-check` overrides with a loud warning.
- **Read-only modes are always allowed** (`--list`, dry-run) — deliberately, since that is
  how you inspect before deciding. Only `--apply` / `--revert-from` are gated.
- **Backup first**, timestamped `<target>.bak-YYYYmmdd-HHMMSS`, then write.
- **Never touches `accounts.json`** or any credential store — asserted by a test that spies
  on every `open`/`copy2` and requires each path to be the target or its own backup.
- **Never clobbers.** A pre-existing `grep` entry with a different value is reported as
  CONFLICT and skipped, not overwritten.

## Test evidence

Two evidence tiers, kept distinct so nothing below reads wider than it was measured.
**Only the 35-test pytest suite is CI-enforced, and every one of those tests runs against
the committed 8-block `tests/fixture_claude.json` — not the live 37-block file.** The
mutation harness and the real-`~/.claude.json` runs further down were **one-off manual
measurements**: real when taken, but their harness/driver is not committed, so CI does not
re-run them — treat them as evidence-once, not standing guarantees.

`python -m pytest tools/mcp/closed-batch/tests -q` → **35 passed**. Wired into CI as
`gate-tests-coverage closed-batch config editor` (reuses the existing charter slug, so
`.quality/charter.yml` needs no edit).

**Mutation harness (one-off; the harness itself is not committed, so CI does not re-run it):
12 mutations, 12 killed, 0 survivors.** Green tests are not evidence
until each safety behaviour, when reverted, turns the suite red. Killed: guard disabled ·
scope widened to every project block · grep clobbers · backup skipped · `apply_plan`
mutates its input · dedup loses case-normalisation · detector matches command lines
(self-match) · guard fails OPEN · writer emits CRLF · serena removal drops the other
disabled servers · dry-run writes anyway · playwright flag replaces instead of appends.

**Both-states probe on the guard** (a probe silent in both states measures nothing):
- known-RUNNING (live, `claude.exe` up): `--apply` against a copy of the real file →
  exit 3, `REFUSING: Claude is RUNNING (claude.exe)`, file hash unchanged, 0 backups.
- known-CLOSED (stubbed lister): applies normally.

**End-to-end, a one-off manual run on a COPY of the real 234,653-byte `~/.claude.json`**
(live file never touched, verified by hash afterwards; the committed, CI-enforced proxy for
this is `test_apply_touches_only_the_intended_sites` on the 8-block fixture):

```
project blocks changed : 6 of 37     (the 4 scoped repos -> 6 keys)
project blocks identical: 31         ...of which still disable serena: 31
root list  : 122 -> 121   (only "serena" removed, order preserved)
mcpServers : 66  -> 67    (grep added; all 65 other entries byte-identical)
playwright : ["-y","@playwright/mcp"] -> ["-y","@playwright/mcp","--extension"]
backup sha == pre-apply sha : True
REVERT byte-identical       : True
```

**Serialiser fidelity.** `dumps_config(load_config(x)) == x` byte-for-byte — Claude Code
writes `indent=2`, no trailing newline, and this writer reproduces it exactly. CI enforces
this round-trip on the committed 8-block fixture (`test_writer_round_trips_the_fixture_exactly`);
it was ALSO measured once, by hand, against the real 234,595-character `~/.claude.json`.
So "every untouched region is preserved" is CI-proven on the fixture and measured once on
the real file — not a standing guarantee continuously enforced over the live file's full
37-block shape.
