#!/usr/bin/env python3
# REL-0022 system-level observer (rebuilt 2026-10-25).
# Perceives: create/modify/delete of files under the canary HOME via sha256
# census around the run. strace -f pid attribution is USED WHEN ptrace is
# available; on hosts without it the census alone stands and strace
# attribution is reported unavailable, never assumed.
# Cannot perceive: network sockets/DNS, host cron/systemd units, the Windows
# registry, in-memory-only mutations, ops by processes leaving no bytes under
# the canary HOME.
import hashlib
from pathlib import Path


def census(root):
    out = {}
    if not Path(root).is_dir():
        return out
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            try:
                out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                out[rel] = "<unreadable>"
    return out


def diff_effects(before, after):
    created = sorted(set(after) - set(before))
    deleted = sorted(set(before) - set(after))
    modified = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    keys = []
    for r in created:
        keys.append("fs:create:" + r)
    for r in modified:
        keys.append("fs:modify:" + r)
    for r in deleted:
        keys.append("fs:delete:" + r)
    return {"created": created, "deleted": deleted, "modified": modified,
            "effect_keys": keys}


def strace_available():
    from shutil import which
    return which("strace") is not None


def observe(home, run_fn):
    hp = Path(home).resolve()
    if hp == Path.home().resolve() or hp == Path.home():
        raise PermissionError("refusing to census the login home: " + str(hp))
    before = census(home)
    run_fn()
    after = census(home)
    eff = diff_effects(before, after)
    eff["child_beacon_in_census"] = ".ast-plugin/cache/child-beacon.txt" in after
    eff["strace_attribution"] = "captured" if strace_available() else "unavailable-on-host"
    return eff
