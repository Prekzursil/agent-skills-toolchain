# durable-checkpoint

Keep a long job's state alive across interruption.

A job runs for longer than its container is guaranteed to live: a Modal function
caps at 24h, a connected FEP+ map is 12-27h, preemptible GPUs vanish with a
signal and a few seconds' notice, laptops lose power. The job's working
directory sits on fast local scratch, because a volume or network filesystem is
usually too slow and too loosely consistent for MD-style I/O — so when the
container dies, the scratch dies with it.

The pattern: **run in fast scratch, write successive checkpoint generations to a
durable path, and on re-invocation resume from the newest one that verifies.**

Stdlib only, no dependencies. Python 3.11+.

## Why generations, and not an in-place mirror

The obvious implementation of this pattern is `cp -a work/. durable/` on a timer,
writing into the live durable path. That has a fatal window, and it is not an
exotic edge case — **it is exactly where a preemption lands.** Writing in place
means invalidating the existing checkpoint before the replacement is complete, so
a kill in between leaves nothing loadable.

This was measured on an earlier build of this module, not theorised. Four
complete checkpoint files sat physically intact on disk and every one was
unusable, because the manifest vouching for them had been removed to begin a
final checkpoint that never finished. **Total loss, not last-interval loss** —
and on the ordinary preemption path, since SIGINT is precisely when the final
checkpoint runs. That is the one failure a durability tool must never have.

So each checkpoint goes into its own **new, monotonically numbered generation
directory** — files first, the manifest with hashes last — and only then is the
volume committed. Nothing existing is touched. The loader takes the
highest-numbered generation whose manifest verifies and walks down on failure,
so **at least one complete checkpoint exists at every instant**, mid-write
included. An interrupted generation has no manifest and is simply skipped.

```
durable/
  gen-00000003/   MANIFEST.durable-checkpoint.json + files   <- verifies, used
  gen-00000004/   files only, no manifest                    <- interrupted, skipped
```

There is **no pointer file and nothing is renamed**, which matters because a
Modal Volume promises neither. Its docs make no atomicity claim for rename,
writes become durable only on `commit()`, background commits happen "every few
seconds", and v2 is beta and "may lose data". A design resting on an atomic
rename would be resting on an unsupported assumption. "Highest generation that
verifies" stays correct even if a rename or a background commit tears.

An older generation is deleted only once a newer one has been **committed and
re-verified by reading it back**, and never below `keep_generations` (minimum
two, enforced in the constructor). Pruning is therefore always a no-op on the
only good copy.

## The other two fixes

| Defect in the naive version | What this does |
|---|---|
| **No final checkpoint on the way out.** Preemption signals before the container goes; with only a timer, everything since the last tick is discarded for free | `start()` installs SIGINT/SIGTERM handlers that write one last generation, then chain to whatever handler was already installed |
| **Resume trusts what it finds.** `sorted(glob(...))[-1]` is lexicographic, not newest; globbing scratch after a copy that ignored its exit status raises `IndexError` instead of reporting a bad resume | `resume_into()` checks every manifest file by size and SHA-256 before a byte is hydrated, and fails closed |

## Use

```python
from durable_checkpoint import DurableCheckpoint, has_checkpoint, resume_into

work, durable = "/tmp/job-scratch", "/mnt/volume/jobs/my-job"

if has_checkpoint(durable):
    resume_into(durable, work)      # newest generation that verifies; raises if none

with DurableCheckpoint(work, durable, interval_s=600, commit=vol.commit):
    run_the_job()                   # periodic generations + a final one on signal/exit
```

`commit` is any callable to run once a generation is complete — for a mounted
volume, pass its commit function. It is called **after** the manifest and
**before** the read-back verification, because on a volume nothing written is
durable until it returns.

`start()` installs signal handlers, so it must be called from the main thread
(a CPython restriction, not a choice here). From a worker thread, pass
`handle_signals=False` and call `mirror_now()` yourself on the way out.

### API

| Call | Does |
|---|---|
| `DurableCheckpoint(work, durable, interval_s=600, commit=None, exclude=(), logger=None, handle_signals=True, keep_generations=2, link_unchanged=True)` | The mirror. Usable as a context manager |
| `.mirror_now()` | Write one new generation now. Returns generation number, counts, bytes, duration, what was pruned, and whether read-back verified |
| `.start()` / `.stop(final=True)` | Timer thread and signal handlers on/off |
| `has_checkpoint(durable)` | Is any generation present? Cheap; presence, not integrity |
| `generations(durable)` | Generation numbers present, ascending |
| `verify_generation(durable, n, quick=False)` | Is generation `n` loadable? |
| `latest_verified(durable, quick=False)` | `(n, VerifyResult)` for the newest that verifies — this *is* the pointer, derived on read |
| `verify(durable, quick=False)` | Is anything loadable? Delegates to `latest_verified` |
| `resume_into(durable, work, quick=False)` | Verify, then hydrate. Raises rather than half-hydrating |
| `clear_work_dir(work)` | Empty scratch without removing it |

`exclude` takes `fnmatch` patterns matched against both the relative path and the
bare filename, so `("*.tmp", "logs")` drops scratch files and a log directory.

## Before you automate restarts: the preemption trap

*Measured by this estate's fractal-compute steward, not by me.*

If a call's input status reads FAILURE while `FunctionCall.get(timeout=0)` still
raises `TimeoutError`, the platform is **mid-restart after preemption** — delays
of 13-20 minutes were observed. **Cancelling there kills a live restart** and
throws away the work it was about to resume. Only re-spawn once `get()` raises a
real error. A naive "status says FAILURE, so respawn" loop destroys work in
flight.

## Cost

A new generation does **not** mean re-writing unchanged bytes. Unchanged files are
**hardlinked** from the previous generation where the filesystem allows it — no
space, no I/O — and their hashes are carried over rather than recomputed. Where
linking is unsupported, which is a plausible outcome on a FUSE volume mount, it
falls back to copying, and then each retained generation costs a full copy of the
job directory. Size that against `keep_generations` before pointing this at a
15 GB tree; `link_unchanged=False` forces the copy path if you want to measure it.

Hashing happens in the same pass that reads a file to copy it, so it is close to
free. A full `verify()` does re-read everything, so run it at resume — where it
matters and happens once — not on a timer; `quick=True` checks size only for a
cheap poll.

## Limits

- **Single writer.** One process mirrors one durable path. Concurrent mirrors
  would race on generation numbering, and Modal's own guidance is that a given
  file should be written by one container at a time anyway.
- **Symlinks are skipped, not followed.** Following them can copy a tree from
  outside the job directory, or loop.
- **Deleted files are implicitly pruned.** Each generation is built from current
  scratch, so a file deleted in scratch is absent from the next generation —
  while remaining in older ones, which are immutable.
- **`quick=True` is not enough to resume on.** The corruption this guards
  against is exactly the kind that preserves size.
- **An empty scratch directory is refused** rather than written as a generation
  that could never verify.

## Scope

It writes generations of one directory to one durable path. Moving state between
accounts, workspaces or providers is out of scope, as is deciding *where* a job
should run — this module has no provider SDK, no network access and no notion of
an account. `test_durable_checkpoint.py::test_imports_match_the_allowlist` walks
the AST and fails on any import outside an explicit allowlist, so that stays true
by construction rather than by good intentions.

## Tests

```bash
python test_durable_checkpoint.py      # self-contained, or run under pytest
```

38 tests. The centrepiece is
`test_preemption_during_final_checkpoint_keeps_the_previous_generation`, which
reproduces the original data-loss scenario and asserts the previous generation
still verifies *and* still resumes. Also covered: fallback past a torn newest
generation; manifest-less generations skipped; retention keeping the configured
count; pruning refused when read-back fails; `keep_generations < 2` rejected;
hardlink reuse and the copy fallback; corrupted, truncated and missing files;
malformed and wrong-version manifests; excludes; symlink skipping; commit
ordering; the periodic timer; signal handler chaining; mirror failures isolated
from the job; and the import allowlist. All run in a temp directory on tiny files
with no network and no subprocess, so the suite is cheap on a thermally-limited
machine.
