# SLOP lane — BUILD round 1

Round 1 of at most 4. Everything below was measured in this tree, not carried from the brief;
two of the brief's premises and **three of my own probes** were refuted in the process and are
recorded as such rather than deleted.

SHIPPED: commit `f5b596e6` — 47 files, +10,445/-0. Bucket (b) → bucket (a).
MEASURED AT: `f5b596e6a6e3729cf72812134a490a2b633ab064` (HEAD moved 4 times during this lane:
`ae8205a4 → 9353ed1f → 86dde6c1 → f5b596e6`; sibling lanes are committing right now).

COVERAGE: B0–B6 measured. Bucket (d) empty-dir removal NOT executed (blocked, reason inline).
The sibling-owned CI red is NOT fixed by me — deliberate, reason inline. External research:
NOT-CHECKED (every question here is answerable by an exact algorithm over this repo).

---

## Ranked findings

| # | severity | finding | evidence |
|---|---|---|---|
| **B-1** | **STOP-SHIP, not mine** | `main` is CI-RED on `gate-lint-format` at HEAD. 8 files, all `command-center/grounding/_s2_*.py`, added by sibling commit `1e9cfe81`. The gate is repo-wide, so this blocks **every** sibling PR. | `_c1_widen_probe.out.json` T2: `format_rc=1`, 8 files named. Fresh LF clone, 3 controls PASS. |
| **B0** | high, now reduced | `git clean -Xdf` was the single most destructive command available here. It still removes the **78** uncited root probe scripts — but no longer the 45 cited ones, because `f5b596e6` tracks them. | `_c2_final_census.out.json`: `root_probes_on_disk=123, now_tracked=45, still_ignored=78`. |
| **B1** | high, FIXED | 123 of 123 `command-center/_*.py` were ignored and 0 tracked; 1,269,072 B on one disk. 45 (403,870 B) are named inside committed artifacts, so those citations dangled on any clone. | `_b1_cited_probes.out.json`; detector controlled both ways (`_b1_control.out.json`: 248 citers on a known-referenced name incl. the expected `platform/lib/test_schema_resolver.py`, 0 on a nonexistent name). |
| **B2** | high, load-bearing | Committing those 45 **without** a ruff exclusion reds the gate: **29 files would reformat + 9 lint errors**. With it: 0 and 0. | `_b7_candidate_gate.out.json`, T1 vs T2, `controls_verdict: PASS`. |
| **B3** | medium | Three of my own detectors failed. Recorded below; two produced confidently wrong headlines before being caught. | §"My own detector failures". |
| **B4** | medium | Class defect, two instances 20 min apart: evidence probe scripts under `command-center/` get committed unformatted and red a repo-wide gate. Mine was caught pre-commit; the sibling's was not. | B1/B2 + B-1. |
| **B5** | low, PROVEN | Bucket (c) exists but is small. One instance executed and proven. | `_c3_bucket_c_exec.out.json`. |
| **B6** | — | Frozen evidence UNTOUCHED at lane start and lane end. | `_c2_final_census.out.json`. |

---

## The four buckets

### (a) EVIDENCE, kept, already committed
Tracked at HEAD: **10,307** files. Includes the **45** root probe scripts this lane moved out of
bucket (b) in `f5b596e6`.

### (b) EVIDENCE, kept, NOT committed — the dangerous bucket
This was the lane's whole point, because `git status` is silent about it and the routine cleanup
command destroys it.

- **45 cited root probe scripts — RESOLVED.** Committed byte-unchanged in `f5b596e6`, with
  per-path `!` negations in `.gitignore` and one `extend-exclude` entry in `ruff.toml`.
  Verified after the edit: 45/45 no longer ignored, 78/78 uncited ones still ignored — no
  collateral flip in either direction.
  Most-cited: `_sub1_normalize_probe.py` (6), `_catalog_integrity.py` (5), then
  `_b2_m09_probe{,2}.py`, `_p14_manifest_verify.py`, `_proto3_probe_sem001_vs_sem012.py`,
  `_wave1_mutation_control.py` (3 each).
- **78 uncited root probe scripts — LEFT IGNORED, not proposed for deletion.** Absence of a
  citation is not evidence of worthlessness. They remain destroyed by `git clean -Xdf`.
- **The grounding lane's R2 stands:** 31 of 32 apparent bucket-(c) outputs have a producer that
  is *not in git*, so they are bucket (b) wearing bucket (c)'s clothes. Untouched.

### (c) REPRODUCIBLE SCRATCH — one deletion executed, regeneration proven
`command-center/slop-report/__pycache__`.

Regenerating command, shown and then executed:

```
python command-center/slop-report/_b1_control.py
```

Deleted → verified absent (`n_files=0`) → re-ran the command → regenerated
**byte-identically** (`_b1_cited_probes.cpython-314.pyc`, sha256-16 `9ef271460a07b5f4` before
and after). All five checks PASS including the intermediate absence, which is what
distinguishes "regenerated" from "never deleted".

Scope was deliberately limited to a cache **this lane created**. The 48.9 MB cache sweep is
still available but was NOT run: sibling lanes are writing in this tree now (untracked count
moved 215 → 325 during this lane), and disk is not the constraint.

### (d) DEAD — nothing executed
The 13 empty directories including the `platform/~/` Windows path-bug tree remain. Still blocked
for the reason the grounding lane gave: `ADV-0041-path-and-identity-disclosure.json` documents
`platform/~` and is owned by another lane. Zero bytes at stake; not worth a collision.

---

## B-1: the CI red I did NOT fix, and why

Measured in a fresh LF clone of HEAD, both states, controls PASS:

- **as-is:** `ruff format --check .` → `format_rc=1`, 8 files:
  `_s2_appendonly_and_negcase.py`, `_s2_apply_negcase.py`, `_s2_budget_refit.py`,
  `_s2_bytestable.py`, `_s2_render_probe.py`, `_s2_restore_negcase.py`, `_s2_vault_gap.py`,
  `_s2_wa_union.py` — all under `command-center/grounding/`.
- **with the exclusion widened** to `command-center/**/_*.py` → green, 0 would reformat.

Two candidate fixes, with measured blast radius so the owner can choose:

| fix | blast radius | keeps gate strength |
|---|---|---|
| `ruff format` the 8 files | 8 files change bytes | yes — 144 files stay linted |
| widen exclude to `command-center/**/_*.py` | **144** tracked files leave the gate | no |

**I did neither, on purpose.** The owning lane is *live in that exact directory*:
`command-center/grounding/_audit_s2_negcase.py` and `_AUDIT-S2-NEGCASE.json` are untracked and
being written now, and `_s2_render_probe.py:9` reasons explicitly about its result being
"STABLE while the bytes are stable". Reformatting those 8 files mid-audit could invalidate a
sibling's in-flight measurement, and unilaterally dropping 144 files out of the lint gate to fix
8 is disproportionate. Handing it back with the measurement is the correct move.

*UNVERIFIED:* whether the 8 carry a declared digest. My digest detector cannot answer it — see
below. Settling experiment: ask the grounding lane, or locate the casualty sha256 manifest and
re-run the matcher against it.

---

## My own detector failures (3), recorded because deleting them would hide the correction

1. **False CI-red, and it was the trap I already had written down.**
   `_b3_head_blob_gate.py` materialised HEAD blobs into a temp tree and reported *"HEAD is
   CI-RED, 4 files under `tools/mcp/patent-search-mcp`"*. **REFUTED.** It materialised only
   `*.py`, so `tools/mcp/patent-search-mcp/pyproject.toml` — which carries
   `[tool.ruff] line-length = 100` — was absent and root defaults (88) applied. 16 tracked
   ruff/pyproject configs exist; a partial materialisation cannot reproduce ruff's per-file
   config discovery. Fixed by replacing the simulation with a real
   `git clone -c core.autocrlf=false -c core.eol=lf` (`_b4_clone_gate.py`), which reports
   **HEAD CI-GREEN at `86dde6c1`** with controls: 0 CRLF in the clone, nested config present,
   mangled control fires.

2. **A worktree reading that contradicted itself.**
   `ruff format --check .` listed 3 casualty files as "would reformat" while
   `ruff format --diff <same 3>` said "3 files already formatted", and my
   `_b2_blob_check.py` recorded `worktree_bytes == blob_bytes` for files that differ by 14
   bytes. Root cause: the tree is a moving target (repo-wide fmt-fail count moved 61 → 66
   between two runs minutes apart). *UNVERIFIED:* I could not reconcile the 63-minute-old
   mtime with the observed mid-measurement transition. Consequence: **no worktree ruff reading
   in this lane is load-bearing**; every gate verdict here comes from a fresh clone instead.

3. **The digest-lock detector failed its positive control — and that changed the fix.**
   `_b6_digest_match.py` asked "does a committed artifact declare a digest *of* one of these 45
   files". It answered "no locks, formatting is safe" — but its positive control, the
   known provenance-locked `casualty/probes/adv0022_probe2.py`, **also** came back unlocked. The
   5 digests published near its name are digests of probe *output*
   (`_build_adv0022.py:57-58`), not of the file. A matcher that cannot find a lock it is
   pointed straight at cannot certify the absence of one, so "no receipt depends on these
   bytes" is UNVERIFIED. **This is why the 45 were committed byte-unchanged with a ruff
   exclusion instead of being reformatted** — the byte-preserving route is the one that cannot
   destroy evidence.

---

## Brief premises corrected

- *"16 untracked files fail ruff format and 9 fail lint"* — the real, stable number is not a
  worktree count at all. At `86dde6c1` the **tracked** tree was ruff-**green**; of the 45 files
  I committed, 29 would reformat and 9 lint errors exist, which is where those figures land.
- *"`_advver_M14` orphans, 77 files / 735 KB"* — confirmed still out of scope: no such path in
  this repo; already measured and committed at `18798852`. Not re-measured.
- *`skills/` vs `.agents/skills/`* — sanctioned dual-write under a green guard. NOT slop. Not
  touched.

---

## Frozen evidence — untouched, two independent signals

| path | `git status --porcelain` | files hashed |
|---|---|---|
| `command-center/casualty/probes` | 0 lines | 7 |
| `command-center/p2-wave/probes` | 0 lines | 25 |

Hasher control PASS (stable re-hash equal, mutated copy differs, file count > 0) — so "all
digests match" is not a constant function returning success. Nothing in either directory was
opened for write at any point.

Census disjointness control PASS: `untracked ∩ ignored = 0`, `tracked ∩ untracked = 0`.

---

## Confidence

- **almost certain (95–99%)** — B-1 (fresh clone, both states, 3 controls PASS); B1's 123/0/45/78
  split (two mechanically different signals: `git check-ignore -v` naming `.gitignore:76`, and
  `git ls-files` showing zero); B2's 29+9-vs-0+0 (both states); bucket (c) byte-identical
  regeneration (executed, with the intermediate absence checked); frozen dirs untouched.
- **likely (55–80%)** — that `ruff format` on the sibling's 8 files is safe. Nothing suggests a
  lock, but my lock detector is broken (failure 3), so this is not established.
- **uncertain (20–55%)** — the mechanism behind detector failure 2.
- **not asserted** — whether the 78 uncited probe scripts have value; whether the 144-file
  exclusion widening is the right long-term call (that is an owner decision, not a measurement).

If this file still reads as a skeleton with `UNKNOWN - not yet measured`, the unit died before
measuring anything and no verdict here may be cited.
