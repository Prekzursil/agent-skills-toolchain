#!/usr/bin/env python3
"""IMP-0151 probe2: BOTH directions of divergence are detected. repo_only and
live_only are reported as their own classes; a shared artifact is not
misclassified as an orphan; the shared class is content-equal (CRLF-normalized
hash). One run, both states."""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixtures  # noqa: E402


def load_adapter():
    spec = importlib.util.spec_from_file_location("imp0151_adapter2", HERE / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    adapter = load_adapter()
    root, repo, live = fixtures.build_fixture()
    try:
        rep = adapter.discover(repo, live)
        repo_only_ok = rep["repo_only"] == ["repo-only-skill/SKILL.md"]
        live_only_ok = rep["live_only"] == ["live-only-skill/SKILL.md"]
        shared_ok = rep["shared"] == ["shared-skill/SKILL.md"]
        diverged_empty = rep["diverged"] == []

        # mutation control: drift the live twin of shared-skill -> diverged fires
        twin = live / "shared-skill" / "SKILL.md"
        twin.write_text(
            "---\nname: shared-skill\ndescription: drifted body\n---\nbody2\n",
            encoding="utf-8", newline="\n",
        )
        rep2 = adapter.discover(repo, live)
        drift_fires = rep2["diverged"] == ["shared-skill/SKILL.md"]
        shared_not_orphan = ("shared-skill/SKILL.md" in rep2["diverged"]
                             and "shared-skill/SKILL.md" not in rep2["repo_only"]
                             and "shared-skill/SKILL.md" not in rep2["live_only"])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    result = {
        "unit_id": "IMP-0151",
        "probe": "probe2-both-directions",
        "repo_only": repo_only_ok,
        "live_only": live_only_ok,
        "shared_classed": shared_ok,
        "no_false_divergence": diverged_empty,
        "drift_fires": drift_fires,
        "shared_not_orphan": shared_not_orphan,
        "pass": all([repo_only_ok, live_only_ok, shared_ok, diverged_empty,
                     drift_fires, shared_not_orphan]),
    }
    print("RESULT:" + json.dumps(result))
    tail = ("SUCCESS:IMP-0151-probe2 both divergence directions detected; drift control "
            "fires; shared never orphaned"
            if result["pass"] else
            "FAILED:IMP-0151-probe2 both-directions contract broken")
    print(tail)
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
