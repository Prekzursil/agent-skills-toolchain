"""Naive walkers used as both-states twins (TST-0335)."""
from __future__ import annotations

import os


def naive_walk_raise(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(str(root)):
        for name in filenames + dirnames:
            path = os.path.join(dirpath, name)
            stem = os.path.splitext(name)[0].upper()
            if stem == "NUL" or name.upper() == "NUL":
                raise ValueError(rf"reserved device name \\.\NUL at {path}")
            found.append(path)
    return found


def naive_walk_crash_as_zero(root):
    try:
        found = naive_walk_raise(root)
        return {"raised": False, "count": len(found), "paths": found}
    except Exception:
        return {"raised": True, "count": 0, "paths": []}


def naive_walk_silent_skip(root):
    """Known-broken twin: skips reserved entries silently and still claims complete."""
    files = []
    try:
        for dirpath, dirnames, filenames in os.walk(str(root)):
            for name in filenames:
                stem = os.path.splitext(name)[0].upper()
                if stem in {"NUL", "CON", "AUX", "PRN"}:
                    continue
                files.append(os.path.join(dirpath, name))
    except Exception:
        pass
    return {"complete": True, "unread_count": 0, "files": files}


def naive_walk_follow_unlimited(root, max_steps=10000):
    """Known-broken twin: follows every link with a step fuse."""
    steps = 0
    hit_cap = False
    for dirpath, dirnames, filenames in os.walk(str(root), followlinks=True):
        for name in filenames + dirnames:
            steps += 1
            if steps >= max_steps:
                hit_cap = True
                return {"steps": steps, "hit_cap": hit_cap}
    return {"steps": steps, "hit_cap": hit_cap}
