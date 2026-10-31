---
title: grill-restore
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/followup/grill-restore
---

# Lane report: grill-restore (2026-09-30)

Three closures from the completed fleet run. All commands below were executed in this
session unless tagged *(recorded)*, which means output quoted from the run's own
artifacts (dossier §4) and not re-executed here.

## Closure 1 — consolidated grill.yaml recovered and restored

**Incident (as disclosed):** the audit-fixes lane, while unifying the grill skill trio,
overwrote `~/.agents/workflows/grill.yaml` with the repo's pre-consolidation version and
then restored only the one field it had verified before overwrite (`skills: [grill]`).
That partial-restore state is preserved as `out/followup/grill.yaml.partial-restore.txt`
(834 bytes, sha256 `7c03676c…`).

**Where the consolidated version actually lives in git.** The ask's premise that the
consolidated file is recoverable from `D:\opt\vault\agent-skills-toolchain` history does
not hold — verified, not assumed:

- `git log --all --oneline -- '**/grill.yaml'` in the **vault** repo
  (`D:\opt\vault\agent-skills-toolchain`, branch `vm/offload-w2025-2026-09-29-offensive-stack`)
  returns exactly one commit: `ecf600ce` (2026-09-28, PR #360 merge) — the
  **pre**-consolidation 849-byte version (`skills: [grill-me, grill-me-extensive,
  grill-with-docs]`).
- Vault reflog has 3 entries (fresh clone 2026-09-29 18:57 → checkout vm branch → one
  commit `058bb9de`); `git fsck --lost-found` dangling blobs contain no grill.yaml
  (the only blob matching "grill" is a GitHub API search JSON); `git stash list` empty.
  The vault remote has no `vm/offload…` branch to fetch (origin refs: `main` only).

The consolidated version **is** in git in the **source** repo
(`C:\Users\prekzursil\source\agent-skills-toolchain` — the repo the ask described as
"HEAD 6793d8e2 = remote main", which matches the source repo, not the vault, whose HEAD
is `058bb9de` on the vm branch). Its `reattach_git.sh` fetch was
`+refs/heads/*:refs/remotes/origin/*`, so remote-tracking branches beyond main exist
there:

- `git log --all --oneline -- '**/grill.yaml'` (source repo) →
  `81d7e0ea0` **"grill: merge three skills into one; add the no-gaps enforcement layer"**
  (2026-09-24 19:53:38 +0000), reachable from `origin/live-capture/2026-09-02`.
- File path in that commit: `workflows/grill.yaml` (live-capture layout; not
  `.agents/workflows/grill.yaml`, which is why the exact-path log shows only
  `15905d35c`/`ecf600ce`).
- `git log --oneline origin/live-capture/2026-09-02 -- workflows/grill.yaml` → only
  `81d7e0ea0` and `c3cde97bd` (its pre-consolidation ancestor), and the branch tip
  `9909c43af` (2026-09-29 16:12) did not touch the file — so `81d7e0ea0` holds the
  **newest** consolidated version in git. No extra fetch was required (already fetched
  by the reattach); the ask's fetch-and-use fallback therefore applied in spirit via the
  already-fetched remote-tracking branch.

**Recovery commit: `81d7e0ea0d2502e2ad3c30671aed4e2d06109bda`**
(`origin/live-capture/2026-09-02`, author Prekzursil). The same commit also carries the
skill-side consolidation (R100 renames `skills/grill-me*` → `skills/grill/…`,
`commands/grill*.md`, `hooks/gap-check/*`), and the live skill tree matches it
(`~/.agents/skills/grill/` exists with SKILL.md, references/, both LICENSEs).

**Restore performed and verified:**

```
git -C /c/Users/prekzursil/source/agent-skills-toolchain show 81d7e0ea0:workflows/grill.yaml \
  > ~/.agents/workflows/grill.yaml
sha256sum → 3a2a1bcc4943991eed29b8194be2cde40525c5c39b9be0772f173fb3363be39d  (1834 bytes)
C:/Python314/python.exe -c "import yaml …"  → YAML-OK id=grill skills=['grill']
  superseded=['grill-me','grill-me-extensive','grill-with-docs']
  seq=7-steps invariants=10
```

The consolidated content confirms the merge semantics: provider aliases keep the three
legacy invocations working, `depth:` tiers, tiered-question sequence, 10 invariants
including the owner-reversed "ask one question at a time" → tier batching, explicit
`superseded:` trio, and the 2026-09-24 merge note.

**Deliberately left alone:** the *tracked* copies at
`source/.agents/workflows/grill.yaml` and repo `main:.agents/workflows/grill.yaml`
remain the pre-consolidation version — that is what origin/main holds; rewriting tracked
repo content was not in this ask's scope.

## Closure 2 — Honesty ledger appended to the dossier

Appended `## 8. Honesty ledger update (2026-09-30)` to `out/SOTA-STACK-DOSSIER.md`
(diff vs the vault copy: single hunk `183a184,220`, nothing else touched). Two tables:

- **8a fixed-by-the-run** — env restore, repo git reattach, loopback enforcement, SSOT
  totals, canonical ghosts, skills index, golden pointer, plus the grill.yaml incident
  now closed by this follow-up. Each row carries command evidence tagged **(R)**
  (recorded by the round, quoted from dossier §4) or **(V)** (re-verified live in this
  pass).
- **8b still-open** — the §7b owner decisions, each marked `— (owner decision)`, plus a
  count note: §7b as written has 11 bullets; the ask's "ten" maps to §7b minus the
  bench-re-run bullet (that one duplicates §7a residual risk #1). All nine §7a residual
  risks also remain open.

**Live re-checks run in this pass (all passed):**

1. Loopback — `netstat -ano`: 127.0.0.1 LISTENING on 3001/3002/3003/8501/18888/31100;
   zero 0.0.0.0 matches on those ports.
2. Skills index — `find ~/.agents/skills -maxdepth 2 -name SKILL.md | wc -l` → **416**
   (matches the recorded `gen_skills_index.ps1` → 416).
3. Golden pointer — `C:\Users\prekzursil\AGENTS.md:22-27` carries the pointer;
   `source\agent-skills-toolchain\golden\AGENTS.md` and `golden\SHA256.txt` present.
4. Repo reattach — source repo HEAD `6793d8e2` == `origin/main` (git log/status);
   consolidation history reachable via `origin/live-capture/2026-09-02`.

**Not re-run in this pass** (cited from §4 as recorded): `restore_env.ps1` (314 vars),
`verify_stack.py` (29 available), the canonical post-fix ghost script (`[]`),
`cc-validate`, the `.agents` test suite. They belong to other lanes' fixes; re-running
the full battery was not this lane's ask.

## Closure 3 — vault commit and push

Mirrored into the vault repo
(`D:\opt\vault\agent-skills-toolchain`, branch `vm/offload-w2025-2026-09-29-offensive-stack`):

- `estates/offload-w2025/2026-09-29-offensive-stack/SOTA-STACK-DOSSIER.md` — updated
  with §8.
- `estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/followup/` — this
  report, `grill.yaml.partial-restore.txt` (834 B), and
  `grill.yaml.consolidated-81d7e0ea0` (1834 B, the recovered file preserved as evidence).

Constraints honored: only the dossier + `out/followup/` were staged (the repo's
pre-existing dirty submodule state `research/mythic_ornn_src` and untracked `_bhmcp`
were left alone); every staged file is < 5 MB (largest is the dossier at ~38 KB); no
bench raw responses staged; no secrets added (hashes appear as full file sha256 or sha8
— file digests, not credentials) — nothing pushed beyond what the private vault remote
already holds. The new commit hash is reported in the lane's submit_result (a file cannot
contain the hash of the commit that includes it).