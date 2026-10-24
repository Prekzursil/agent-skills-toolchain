# durable-checkpoint

Keep a long job's state alive across interruption.

A job runs for longer than its container is guaranteed to live: a Modal function
caps at 24h, a connected FEP+ map is 12-27h, preemptible GPUs vanish with a
signal and a few seconds' notice, laptops lose power. The job's working
directory sits on fast local scratch, because a volume or network filesystem is
usually too slow and too loosely consistent for MD-style I/O — so when the
container dies, the scratch dies with it.

The pattern: **run in fast scratch, mirror to a durable path periodically, and
on re-invocation resume from the mirror instead of starting over.** This is that
mirror, hardened.

Stdlib only, no dependencies. Python 3.11+.

## What it fixes relative to the obvious version

A first cut of this pattern is `cp -a work/. durable/` on a timer. That has
three defects, each of which costs real GPU time:

| Defect | What goes wrong | What this does instead |
|---|---|---|
| **The copy isn't atomic** | Killed mid-copy, the durable path holds a torn mix of old and new files — and an earlier validity sentinel is still sitting there, so the next run loads the wreckage | Every file lands via write-temp-then-`os.replace`. The manifest that makes a checkpoint loadable is written **last** and removed **first**, so an interrupted mirror has no manifest and `verify()` refuses it |
| **No final checkpoint on the way out** | Preemption sends SIGINT (SIGTERM elsewhere) before the container goes; with only a timer, everything since the last tick is discarded for free | `start()` installs handlers that take one last incremental mirror first, then chain to whatever handler was already there |
| **Resume trusts what it finds** | `sorted(glob(...))[-1]` is lexicographic, not newest; globbing scratch after a copy that ignored its exit status raises `IndexError` instead of reporting a bad resume | `resume_into()` checks every manifest file by size and SHA-256 before a byte is hydrated, and fails closed |

The first of these is not hypothetical. The program this was ported from has it
on record: resumes died with *"Bad checkpoints, `ckpt_is_valid` missing after
mid-write kill"* — a sentinel lost after what was otherwise a complete write.
Sentinel-last plus verify-on-load is what turns that from a silent corruption
into a refusal you can act on.

## Use

```python
from durable_checkpoint import DurableCheckpoint, has_checkpoint, resume_into

work, durable = "/tmp/job-scratch", "/mnt/volume/jobs/my-job"

if has_checkpoint(durable):
    resume_into(durable, work)      # raises CheckpointError if the mirror is torn

with DurableCheckpoint(work, durable, interval_s=600, commit=vol.commit):
    run_the_job()                   # periodic mirrors + a final one on signal/exit
```

`commit` is any callable to run after each mirror — for a mounted volume that
needs an explicit commit, pass its commit function. It is called **after** the
manifest is written, so if it fails the local durable directory is already
self-consistent and the next pass simply retries.

`start()` installs signal handlers, so it must be called from the main thread
(a CPython restriction, not a choice here). From a worker thread, pass
`handle_signals=False` and call `mirror_now()` yourself on the way out.

### API

| Call | Does |
|---|---|
| `DurableCheckpoint(work, durable, interval_s=600, commit=None, exclude=(), logger=None, handle_signals=True)` | The mirror. Usable as a context manager |
| `.mirror_now()` | One pass now. Returns counts, bytes and duration |
| `.start()` / `.stop(final=True)` | Timer thread and signal handlers on/off |
| `has_checkpoint(durable)` | Cheap presence test. Says nothing about integrity |
| `verify(durable, quick=False)` | Is it loadable? Returns a truthy `VerifyResult` with a `reason` |
| `resume_into(durable, work, quick=False)` | Verify, then hydrate. Raises rather than half-hydrating |
| `clear_work_dir(work)` | Empty scratch without removing it |

`exclude` takes `fnmatch` patterns, matched against both the relative path and
the bare filename, so `("*.tmp", "logs")` drops scratch files and a log
directory.

## Before you automate restarts: the preemption trap

*Measured by this estate's fractal-compute steward, not by me.*

If a call's input status reads FAILURE while `FunctionCall.get(timeout=0)` still
raises `TimeoutError`, the platform is **mid-restart after preemption** — delays
of 13-20 minutes were observed. **Cancelling there kills a live restart** and
throws away the work it was about to resume. Only re-spawn once `get()` raises a
real error. Any supervisor built around this module should respect that, because
a naive "status says FAILURE, so respawn" loop destroys work in flight.

## Guarantees, and the one real tradeoff

**Guaranteed:** if `verify()` returns ok, every file in the manifest is present
with the recorded size and SHA-256. If a mirror is interrupted at any point,
`verify()` returns not-ok. A resume never hydrates a checkpoint that failed
verification.

**The tradeoff, stated plainly:** between the manifest being removed and the new
one being written, there is no loadable checkpoint. A container death inside
that window leaves nothing resumable — whereas the naive version would leave
*something*, albeit something corrupt that it would then load. This is a
deliberate trade of a small window of total loss against the much worse
open-ended cost of resuming onto corrupt state and finding out hours of GPU time
later.

Two things keep the window small: copies are **incremental** (only files whose
size or mtime changed are re-read, and unchanged files keep their previous hash),
and the final signal-driven mirror is incremental too. Mirror often enough that
a tick has little to do and the window is brief. If you need a previous-good
state preserved across the window, that wants generation directories and roughly
double the space — not implemented here, and a deliberate omission rather than
an oversight.

**Other limits:**

- **Symlinks are skipped, not followed.** Following them can copy a tree from
  outside the job directory, or loop.
- **Deleted files are pruned** from the mirror, so it stays a mirror. Without
  that, a resumed job sees a directory that never existed.
- **`quick=True` skips hashes** — size and mtime only. Fine for a cheap
  liveness poll on a huge tree; do not resume on a quick pass alone, since the
  corruption this guards against is exactly the kind that preserves size.
- **Hashing is close to free, but not free.** It happens in the same pass that
  reads a file to copy it. A full `verify()` does re-read everything, so run it
  at resume (where it matters and happens once), not on a timer.

## Scope

It mirrors one directory to one durable path. Moving state between accounts,
workspaces or providers is out of scope, and so is deciding *where* a job should
run — this module has no provider SDK, no network access and no notion of an
account. `test_durable_checkpoint.py::test_imports_match_the_allowlist` walks the
AST and fails on any import outside an explicit allowlist, so that stays true by
construction rather than by good intentions.

## Tests

```bash
python test_durable_checkpoint.py      # self-contained, or run under pytest
```

30 tests: mirror/verify/resume round trips; the torn-mirror refusal including a
simulated mid-copy container death; corrupted, truncated and missing files;
malformed and wrong-version manifests; incremental reuse; pruning; excludes;
symlink skipping; commit-hook ordering; construction guards; the periodic timer;
signal-driven final checkpoint with handler chaining; mirror failures isolated
from the job; and the import allowlist. All run in a temp directory on tiny
files with no network and no subprocess, so the suite is cheap on a
thermally-limited machine.
