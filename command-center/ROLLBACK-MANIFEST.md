# ROLLBACK-MANIFEST

Every change this command center makes, and the exact one-line undo. A control you cannot
revert cheaply is a control nobody will dare enable.

## 1. The register gate

| what | undo | effect |
|---|---|---|
| Gate is too noisy after promotion | delete the `"register_gate"` key from `~/.agents/state/harness/module-modes.json` | returns to its tier default, `shadow` — observes, injects nothing |
| Gate must stop entirely, this session | `HARNESS_GATE_MODE__register_gate=off` | no verdict, no sink write |
| Gate must stop entirely, always | `HARNESS_REGISTER=off` | short-circuits before any file read |
| Gate must be removed from the code | drop `"register_gate"` from `MODULE_ORDER` and the entry from `build_default_modules()` in `agent-self/harness/modules.py` | the module is never constructed; nothing else references it |

The gate **cannot** fail closed by design: its verdict is always `action="inject"`, and
`stage()` passes an inject through unchanged in every mode. Even a hand-forced `enforce`
cannot make it block. There is therefore no rollback needed for "it blocked my work" — that
state is unreachable.

**Blast radius if the gate misbehaves:** one extra `additional_context` string on
`UserPromptSubmit` / `SessionStart`, and one sampled line in the shadow sink. It writes no
file, mutates no catalog, and spawns no process — it rides the dispatcher wire
`settings.json` already runs, so it adds zero process spawns.

## 2. The catalog and its derived files

| what | undo |
|---|---|
| A wrong close / defer / drop | `git checkout -- command-center/WORK-UNIT-CATALOG.json command-center/DEPENDENCY-GRAPH.json` then re-render. The `events/EVENTS.jsonl` line stays: the log is append-only, so a reverted action remains visible as history rather than being erased. |
| A wrong bulk edit | `python tools/command-center/seed.py --force` re-derives the whole catalog from `sources/REGISTER.md` + `sources/overlay.json`. **Destructive**: it discards every close, defer and note. |
| Derived files disagree with the catalog | `python tools/command-center/render.py` |
| The graph disagrees with the catalog | any `close.py` verb regenerates it; or `python tools/command-center/seed.py --force` |

## 3. What has no rollback, stated plainly

- **A close's evidence string is written into the catalog and the event log.** If it contained
  something sensitive, `git checkout` restores the catalog but the event log line and the git
  history do not un-happen. Do not paste secrets into `--evidence`; cite a `file:line`.
- **`seed.py --force` cannot be undone from within the tool.** Its only recovery is git.

## 4. Rollback of this PR as a whole

Revert the merge commit. Nothing in this PR writes outside the repository: no live tree is
touched, `scripts/sync-from-live.ps1` is not run, `install.py` is used only with `--check`, and
the gate ships in shadow. The complete footprint is `command-center/`, `tools/command-center/`,
the `register_gate` module plus its test in `agent-self/harness/`, and one CI step.
