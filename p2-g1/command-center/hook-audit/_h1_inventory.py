r"""H1 — hook fleet inventory: what is PRESENT, what is WIRED, on both sides.

Three independent surfaces, deliberately counted separately:
  A. repo hooks/*/            -- directories on disk that look like a hook
  B. hooks/_dispatch/manifest.json  events[<ev>]["checks"]  (repo + live)
  C. live settings.json ["hooks"]   -- the ONLY thing Claude Code actually reads

DETECTOR CONTROL (single-signal-verification 3c): events[<ev>] is a DICT
{settings_matcher, settings_timeout, checks}. len() of it returns 3 for every
event on both sides -> false parity. This script counts len(ev["checks"]) and
FAILS CLOSED at zero, so a shape change is loud instead of reporting parity.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIVE_HOOKS = Path("C:/Users/Prekzursil/.claude/hooks")
LIVE_SETTINGS = Path("C:/Users/Prekzursil/.claude/settings.json")
OUT = REPO / "command-center" / "hook-audit"


def load_manifest(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def checks_of(man: dict) -> dict[str, list[dict]]:
    ev = man.get("events") or {}
    out = {}
    for name, blob in ev.items():
        if not isinstance(blob, dict):
            out[name] = []
            continue
        out[name] = list(blob.get("checks") or [])
    return out


def summarize(man: dict, tag: str) -> dict:
    ck = checks_of(man)
    total = sum(len(v) for v in ck.values())
    if total == 0:
        raise SystemExit(f"FAILED:h1-inventory {tag} yielded 0 checks -- shape changed")
    return {
        "tag": tag,
        "events": {k: len(v) for k, v in ck.items()},
        "total_checks": total,
        "per_event": {
            k: [
                {
                    "name": c.get("name"),
                    "script": c.get("script"),
                    "matcher": c.get("matcher"),
                    "timeout": c.get("timeout"),
                    "args": c.get("args"),
                }
                for c in v
            ]
            for k, v in ck.items()
        },
        "settings_meta": {
            k: {
                "matcher": (man["events"][k] or {}).get("settings_matcher"),
                "timeout": (man["events"][k] or {}).get("settings_timeout"),
            }
            for k in ck
        },
    }


def hook_dirs(root: Path) -> dict[str, list[str]]:
    """Directories that contain at least one .py -- candidate hook modules."""
    out = {}
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name in ("__pycache__", "_fleet-backups"):
            continue
        pys = sorted(
            str(p.relative_to(root)).replace("\\", "/")
            for p in d.rglob("*.py")
            if "__pycache__" not in str(p) and not p.name.startswith("test_")
        )
        if pys:
            out[d.name] = pys
    return out


def live_settings_hooks() -> dict:
    """Read ONLY the 'hooks' key. settings.json holds live credentials elsewhere."""
    doc = json.loads(LIVE_SETTINGS.read_text(encoding="utf-8"))
    return doc.get("hooks") or {}


def flatten_settings(h: dict) -> list[dict]:
    rows = []
    for event, groups in h.items():
        if not isinstance(groups, list):
            continue
        for g in groups:
            matcher = (g or {}).get("matcher")
            for hk in (g or {}).get("hooks") or []:
                rows.append(
                    {
                        "event": event,
                        "matcher": matcher,
                        "type": hk.get("type"),
                        "command": hk.get("command"),
                        "timeout": hk.get("timeout"),
                    }
                )
    return rows


def script_from_command(cmd: str) -> str | None:
    """Pull the hook script path out of a settings.json command line."""
    if not cmd:
        return None
    m = re.findall(r"[A-Za-z]:[\\/][^\"'\s]+\.py|hooks[\\/][^\"'\s]+\.py", cmd)
    return m[0].replace("\\", "/") if m else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    repo_man = summarize(load_manifest(REPO / "hooks/_dispatch/manifest.json"), "repo")
    live_man = summarize(load_manifest(LIVE_HOOKS / "_dispatch/manifest.json"), "live")

    repo_dirs = hook_dirs(REPO / "hooks")
    live_dirs = hook_dirs(LIVE_HOOKS)

    sh = live_settings_hooks()
    srows = flatten_settings(sh)

    # names wired anywhere
    def names(man):
        return {
            (ev, c["name"])
            for ev, lst in man["per_event"].items()
            for c in lst
            if c.get("name")
        }

    rn, ln = names(repo_man), names(live_man)

    # settings.json direct (non-dispatch) hooks
    direct = []
    for r in srows:
        sc = script_from_command(r["command"] or "")
        if sc and "_dispatch/dispatch.py" not in sc:
            direct.append({**r, "script": sc})

    # which repo hook dirs are referenced by ANY wiring surface
    wired_scripts = set()
    for man in (repo_man, live_man):
        for lst in man["per_event"].values():
            for c in lst:
                if c.get("script"):
                    wired_scripts.add(c["script"].replace("\\", "/").split("/")[0])
    for d in direct:
        parts = d["script"].split("/")
        if "hooks" in parts:
            i = parts.index("hooks")
            if i + 1 < len(parts):
                wired_scripts.add(parts[i + 1])

    unwired = sorted(
        set(repo_dirs) - wired_scripts - {"_dispatch", "_shared", "_golden"}
    )

    report = {
        "repo_manifest": repo_man,
        "live_manifest": live_man,
        "repo_hook_dirs": {"count": len(repo_dirs), "names": sorted(repo_dirs)},
        "live_hook_dirs": {"count": len(live_dirs), "names": sorted(live_dirs)},
        "dirs_repo_only": sorted(set(repo_dirs) - set(live_dirs)),
        "dirs_live_only": sorted(set(live_dirs) - set(repo_dirs)),
        "manifest_repo_only": sorted(f"{e}:{n}" for e, n in rn - ln),
        "manifest_live_only": sorted(f"{e}:{n}" for e, n in ln - rn),
        "settings_hook_events": sorted(sh),
        "settings_entries": srows,
        "settings_direct_non_dispatch": direct,
        "unwired_hook_dirs": unwired,
    }
    (OUT / "H1-INVENTORY.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(
        f"repo manifest checks: {repo_man['events']} total={repo_man['total_checks']}"
    )
    print(
        f"live manifest checks: {live_man['events']} total={live_man['total_checks']}"
    )
    print(f"repo hook dirs={len(repo_dirs)} live hook dirs={len(live_dirs)}")
    print(f"dirs repo-only: {report['dirs_repo_only']}")
    print(f"dirs live-only: {report['dirs_live_only']}")
    print(f"manifest repo-only: {report['manifest_repo_only']}")
    print(f"manifest live-only: {report['manifest_live_only']}")
    print(f"settings.json hook events: {sorted(sh)}  entries={len(srows)}")
    print(f"settings direct (non-dispatch) hooks: {len(direct)}")
    for d in direct:
        print(f"   {d['event']:16s} matcher={str(d['matcher'])[:28]:28s} {d['script']}")
    print(f"UNWIRED repo hook dirs ({len(unwired)}): {unwired}")
    print("SUCCESS:h1-inventory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
