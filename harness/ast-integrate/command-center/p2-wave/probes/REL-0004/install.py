#!/usr/bin/env python3
"""Install the packaged artifact from a local file-backed mirror into a throwaway HOME."""
from __future__ import annotations

import argparse
import json
import shlex
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fence import IsolationError, OwnerFence  # noqa: E402
from package_spec import (  # noqa: E402
    FIXTURE_PACKAGE,
    INSTALL_SUBDIR,
    MISREGISTER_EVENT,
    PLUGIN_ID,
    PLUGIN_VERSION,
)


def materialize_mirror(dest: Path, source: Path | None = None) -> Path:
    source = source or FIXTURE_PACKAGE
    if dest.exists():
        shutil.rmtree(dest)
    pkg = dest / "packages" / f"{PLUGIN_ID}-{PLUGIN_VERSION}"
    pkg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, pkg)
    index = {
        "backend": "file",
        "packages": [
            {
                "id": PLUGIN_ID,
                "path": f"packages/{PLUGIN_ID}-{PLUGIN_VERSION}",
                "version": PLUGIN_VERSION,
            }
        ],
    }
    (dest / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return dest


def _rewrite_python(plugin_dir: Path) -> None:
    hooks = plugin_dir / "hooks.json"
    text = hooks.read_text(encoding="utf-8")
    text = text.replace("__PYTHON__", shlex.quote(sys.executable))
    hooks.write_text(text, encoding="utf-8")


def misregister_hook(plugin_dir: Path, event: str = MISREGISTER_EVENT) -> dict:
    """Deliberately break one contracted hook in the installed manifest."""
    path = plugin_dir / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    matchers = (data.get("hooks") or {}).get(event)
    if not matchers:
        raise RuntimeError(f"event {event} missing from hooks.json")
    hook = matchers[0]["hooks"][0]
    before = dict(hook)
    hook["type"] = "misregistered"
    hook["command"] = ""
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"event": event, "before": before, "after": dict(hook), "path": str(path)}


def add_schema_key_unloads_all(plugin_dir: Path) -> None:
    """Reproduce spec 11303 / Codex: a $schema key loads ZERO hooks."""
    path = plugin_dir / "hooks.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["$schema"] = "https://example.invalid/hooks.schema.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def plugin_dir_for(profile: Path) -> Path:
    return profile / INSTALL_SUBDIR


def install_from_mirror(
    mirror: Path,
    profile: Path,
    *,
    fence: OwnerFence | None = None,
    package_id: str = PLUGIN_ID,
) -> dict:
    fence = fence or OwnerFence.capture()
    profile = fence.assert_throwaway(profile)
    index_path = mirror / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = None
    for item in index.get("packages") or []:
        if item.get("id") == package_id:
            entry = item
            break
    if entry is None:
        raise FileNotFoundError(f"package {package_id} not in {index_path}")
    src = mirror / str(entry["path"])
    dest = plugin_dir_for(profile)
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if fence.is_forbidden(dest):
        raise IsolationError(f"ISOLATION-VIOLATION: install dest {dest} is under owner home")
    shutil.copytree(src, dest)
    _rewrite_python(dest)
    command = (
        f"PYTHONDONTWRITEBYTECODE=1 python3 -B "
        f"command-center/p2-wave/probes/REL-0004/install.py "
        f"--mirror {mirror} --profile {profile} --package {package_id}"
    )
    return {
        "command": command,
        "mirror": str(mirror),
        "package_id": package_id,
        "package_version": entry.get("version"),
        "plugin_dir": str(dest),
        "profile": str(profile),
        "source": str(src),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REL-0004 file-backed mirror install")
    parser.add_argument("--make-mirror", action="store_true")
    parser.add_argument("--mirror", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=None)
    parser.add_argument("--package", default=PLUGIN_ID)
    parser.add_argument("--misregister", default="", help="event name to mis-register after install")
    args = parser.parse_args(argv)
    fence = OwnerFence.capture()
    if args.make_mirror:
        if args.mirror is None:
            print("FAILED:REL-0004-install --make-mirror requires --mirror")
            return 2
        materialize_mirror(args.mirror)
        print(json.dumps({"mirror": str(args.mirror), "ok": True}, sort_keys=True))
        return 0
    if args.mirror is None or args.profile is None:
        print("FAILED:REL-0004-install --mirror and --profile required")
        return 2
    try:
        rec = install_from_mirror(args.mirror, args.profile, fence=fence, package_id=args.package)
    except IsolationError as exc:
        print(str(exc))
        return 3
    if args.misregister:
        rec["misregister"] = misregister_hook(Path(rec["plugin_dir"]), args.misregister)
    print(json.dumps(rec, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
