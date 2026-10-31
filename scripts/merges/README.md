---
title: README
type: note
permalink: dqverify-repo-20261013/scripts/merges/readme
---

# `scripts/merges/` — hand-reconciled copies of held files

`sync-from-live.ps1` keeps a **repo-owned hold list**: paths that exist in both the live
harness and this repo but whose repo copy must never be overwritten from live. A held file is
divergent by definition — that is *why* it is held — so each one needs a deliberate human
decision, not an automatic overwrite in either direction.

This directory holds the reconciled result for the files that need one, laid out under their
repo-relative path so the tree can be copied straight across.

Nothing here is deployed automatically. Deploy is a human step (see the bottom of this file).

---

## 1. `hooks/README.md` — **stays repo-owned permanently. No merge exists or should exist.**

Re-read side by side 2026-07-18. These are not two versions of one document; they are two
unrelated documents that collide on a filename:

| | repo `hooks/README.md` | live `~/.claude/hooks/README.md` |
|---|---|---|
| Title | `# hooks/ — agentic-perfection hook set (canonical copy)` | `# Hooks` |
| Subject | *this repo tree* — what it is, how to deploy it back with `sync-hooks.ps1`, its design law, its hook catalog | a general tutorial — how hooks work, the hooks *in a plugin*, how to disable one, how to write your own |
| Headings | Design law · Dispatcher architecture · Hook catalog · Durability spine · Wildcard gems | How Hooks Work · Hooks in This Plugin · Customizing Hooks · Writing Your Own Hook |
| Overlap | **none** | **none** |

There is no content to preserve from live and no coherent document that could contain both.
Merging them would produce a file that documents neither thing well. The repo copy is the only
one that describes this tree, and it is the file that tells a future reader how to restore the
hook set — losing it is the expensive outcome.

**Decision: permanent hold. Do not remove this entry from `$RepoOwnedFiles`.** The right
long-term fix is to rename one of them (e.g. the repo copy to `hooks/CANONICAL.md`) so the
collision disappears; that is a rename in two trees and is out of scope for this unit.

---

## 2. `.agents/skills/multi-agent-quickstart/SKILL.md` — **not actually bidirectional**

The hold-list comment described this as "true bidirectional divergence ... each side holds
content the other lacks". Re-measured 2026-07-18:

```
$ diff -u repo/SKILL.md live/SKILL.md
lines only in live (+): 0
lines only in repo (-): 1 hunk, 5 lines
```

The entire difference is one repo-only section:

```markdown
## Execution Choice
- After planning, prefer subagent-driven execution for complex work.
- Use inline execution when the task is small or subagents would be overhead.
- Do not silently force one path after the plan is written.
```

**Live holds nothing the repo lacks.** This is staleness in live, not divergence, so the merged
content is the repo copy byte-for-byte (checked into `merges/` unmodified, and asserted
byte-identical by the generator rather than re-typed).

That section is a governance rule mirroring the metaswarm `CLAUDE.md` execution-method gate
("ALWAYS ask the user which approach — never auto-pick"). Dropping it would let the skill
quietly recommend one execution path as a default, which is exactly what the governance rule
forbids. It must survive.

**Decision: repo wins entirely. The reconcile is a repo → live deploy, not a merge.** The hold
stays until that deploy happens — remove it before, and the very next sync copies live over
repo and deletes the section.

---

## 3. `audit_quality_zero_platform.py` — **genuinely bidirectional; both sides kept**

This one is real. Each side carries a *different* fallback for "PyYAML is not importable in
this interpreter", and neither side has the other's:

| | strategy | present in |
|---|---|---|
| repo | `find_python_with_yaml()` — probe `$CODEX_PYTHON_WITH_YAML`, then `sys.executable`, `python`, `py -3`, `python3`, then every `%LOCALAPPDATA%` Python install, returning the first with PyYAML | repo only |
| live | shell out to `pwsh -Command "$input \| ConvertFrom-Yaml \| ConvertTo-Json -Depth 100"` | live only |

Live had also deleted `import os` and `import sys` (dead once `find_python_with_yaml` went) and
replaced the actionable `RuntimeError` with a bare `subprocess` call. An overwrite in either
direction silently destroys a working escape hatch.

### Ordering, and why

Measured on this box 2026-07-18:

* `python -c "import yaml"` → **PyYAML 6.0.3 present**. The in-process path works today.
* `Get-Command ConvertFrom-Yaml` → **not found**. `Get-Module -ListAvailable powershell-yaml`
  → **not installed**. `ConvertFrom-Yaml` is *not* a built-in cmdlet; it ships with the
  `powershell-yaml` module. On this machine the live fallback would always raise.

So the merged order is: in-process `yaml` → `find_python_with_yaml()` → `pwsh ConvertFrom-Yaml`
→ actionable `RuntimeError` naming all three remedies. The live strategy is kept last rather
than dropped because it is the only path that works on a box with `powershell-yaml` installed
and exactly one Python that lacks PyYAML — a real configuration, just not this one.

The live copy called the pwsh path with `check=True` and no guard, so a missing module
surfaced as a bare `CalledProcessError`. The merged version catches `OSError`,
`CalledProcessError` and `JSONDecodeError` and falls through to the `RuntimeError`, so the
operator gets the remedy instead of a stack trace.

### Verification

* `python -m py_compile` → OK
* `ruff check` → All checks passed
* Functional, both reachable paths, same input `a: 1\nb: [x, y]`:
  * path 1 (`import yaml`) → `{"a": 1, "b": ["x", "y"]}`
  * path 2 (`find_python_with_yaml`, with `yaml` hidden from `__import__`) → `{"a": 1, "b": ["x", "y"]}`
* Path 3 (`pwsh ConvertFrom-Yaml`) is **UNVERIFIED** — it cannot be exercised here because
  `powershell-yaml` is not installed; the experiment that would settle it is
  `Install-Module powershell-yaml -Scope CurrentUser` followed by re-running the functional
  check with both `yaml` and `find_python_with_yaml` forced to fail.
* The generator asserts both sides' unique markers survive (`find_python_with_yaml`,
  `CODEX_PYTHON_WITH_YAML`, `ConvertFrom-Yaml`, `import os`, `import sys`) and refuses to
  write if the source block is not found verbatim, so it can never silently half-apply.

**Decision: merged. After deploying to BOTH trees, remove this entry from `$RepoOwnedFiles`.**

---

## Deploying these (human step — deliberately not automated)

```powershell
# 1. review
git -C <repo> diff --no-index `
    .agents/skills/quality-zero-platform-control-plane/scripts/audit_quality_zero_platform.py `
    scripts/merges/.agents/skills/quality-zero-platform-control-plane/scripts/audit_quality_zero_platform.py

# 2. land the merge in the repo tree
Copy-Item -LiteralPath scripts/merges/.agents/skills/... -Destination .agents/skills/... -Force

# 3. push repo -> live for both files
pwsh -File scripts/sync-skills.ps1            # -WhatIf first

# 4. confirm the divergence is gone, then drop the two entries from $RepoOwnedFiles
pwsh -File scripts/sync-from-live.ps1 -Drift
```

Keep `hooks/README.md` on the hold list.