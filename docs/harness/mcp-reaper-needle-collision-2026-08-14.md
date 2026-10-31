---
title: mcp-reaper-needle-collision-2026-08-14
type: note
permalink: dqverify-repo-20261013/docs/harness/mcp-reaper-needle-collision-2026-08-14
---

# The MCP reaper would have killed a live `git status` — needle collision, found and fixed

**Severity: HIGH.** `mcp_doctor.py reap --apply` selected an unrelated live process as a kill
target. The background resource-guard digest actively recommends running that command
(`PROPOSE: ... then reap --apply if real`), so this was one step from executing.

Found 2026-08-14 while investigating genuine memory pressure (C: 97%, RAM 1.8 GB free, 153
node processes holding 3.9 GB). The pressure is real; the tool that was supposed to relieve
it was not safe to run.

## What happened

`cloud-hub`, `social-hub` and `search-hub` all launch the same script basename:

```
C:\Python314\python.exe  ...\tools\mcp\cloud-hub\hub.py
C:\Python314\python.exe  ...\tools\mcp\social-hub\hub.py
C:\Python314\python.exe  ...\tools\mcp\search-hub\hub.py
```

`mcp_inventory.derive_needle()` returns a path **stem** unless that stem is listed in
`_GENERIC_SCRIPT_STEMS`. `hub` was not in the set, so all three servers derived the identical
needle `'hub'`. `mcp_procscan.match()` is an unanchored substring test:

```python
hits = [p for p in procs if needle and needle in p.cmdline.lower()]
```

`'hub'` is a substring of **`GitHub`**. Every process whose command line mentioned a
`Documents\GitHub\...` path was therefore classified as an MCP hub server — three times over.

## Measured, before the fix

| signal | reading |
|---|---|
| processes matching needle `'hub'` | **43** |
| of those, actually MCP hub servers | 18 |
| **unrelated bystanders** | **25** — `git.exe`, `node.exe`, the unrelated `biomni-hub` |
| `audit` pile-up report | cloud-hub 39, social-hub 39, search-hub 39 (the *same* 39, counted 3×) |
| `reap` plan | `keep=6068` and `would_kill=64236` — **identical for all three servers** |
| what pid 64236 actually was | `git.exe -C ...\Documents\GitHub\PrimariRo-atlas-build status --porcelain` |

## The tell that exposed it

The audit claimed **39 live instances** while the reap plan could find **one** killable
process. Those cannot both be true. A self-contradicting report is a detector failure, not a
finding — and the second tell was `keep=6068` appearing under three different server names.
One PID cannot be three servers.

Chasing the pile-up number instead of the contradiction would have led straight to
`reap --apply`.

## Why the existing test did not catch it

`test_reap_orphan_only.py` passes, and cannot fail for this defect class, because it **stubs
out the function that is broken**:

```python
core.mcp_inventory.derive_needle = lambda e, m: "foo-mcp"
```

It proves the orphan-selection logic is correct *given a correct needle*. It says nothing
about whether the needle is correct. That is a control that cannot distinguish the two
hypotheses: it passes identically whether `derive_needle` is right or catastrophically wrong.

## The fix

One line, using the mechanism the author had already built for `server.py` — declare the stem
non-distinctive so lookup climbs to a distinctive ancestor directory:

```python
_GENERIC_SCRIPT_STEMS = {
    "server", "index", "run_server", "main", "__main__", "app", "start", "cli", "hub",
}
```

Needles become `cloud-hub` / `social-hub` / `search-hub`.

## Verification (both states, end to end)

`test_needle_collision.py` was written **first** and proven RED before the fix — 5 failing
checks — with its own controls passing so a broken test could not masquerade as a red one.

| | before | after |
|---|---|---|
| `test_needle_collision.py` | FAILED, 5 checks | **SUCCESS**, 8/8 |
| `test_reap_orphan_only.py` | 2 passed | 2 passed (no regression) |
| reap kill candidates | 4, incl. a live `git status` | **1**, a genuine duplicate hexstrike server |
| audit pile-up | cloud/social/search = 39 each | cloud-hub 11, search-hub 4, social-hub below ceiling |

The test asserts the property that actually matters — a real `Documents\GitHub\` git command
line must NOT match — and keeps a control that each needle still matches its own process, so
the fix cannot pass by making the matcher blind.

## Residual, disclosed rather than fixed

* **The unanchored substring match is still there.** This fix removes the collision that made
  it dangerous; it does not add word-boundary matching. Any future server whose needle is a
  substring of an unrelated path will reproduce the class. **UNVERIFIED** whether other
  needles currently collide — only the three hub servers were checked.
* **The pile-up counts that remain are real and unaddressed**: playwright 24,
  playwright-extension 20, playwright-cdp 20, frida-mcp 12, cloud-hub 11 against a ceiling of
  3. That is the per-session stdio duplication already recorded as the box's
  commit-exhaustion freeze driver. Reaping is now *safe*, but whether to reap is the owner's
  call — it kills servers other live sessions may hold.
* **The tool is live-only and in no git repository.** `~/.local/opt/re-harness/` is not a
  checkout, and the toolchain repo carries only an unrelated `tools/re-harness/mcp_doc_drift.py`.
  So this fix, and the tool it fixes, are outside version control — exactly the architecturally
  orphaned state `rules/common/harness-vcs-hygiene.md` exists to prevent. **Reconciling
  `re-harness/` into the repo is an owner decision and was not done unilaterally.**