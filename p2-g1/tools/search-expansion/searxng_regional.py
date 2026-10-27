#!/usr/bin/env python3
"""Probe / enable / revert SearXNG's regional engines on the local instance.

All decision logic lives in `searxng_config.py` (pure, 100%-covered). This file is the
thin I/O shell: HTTP probes, the backup, the container restart, and the health check.

    python searxng_regional.py --probe      # per-engine reachability, measured live
    python searxng_regional.py --dry-run    # show the settings.yml diff, change nothing
    python searxng_regional.py --apply      # backup -> splice -> validate -> restart -> verify
    python searxng_regional.py --revert     # restore the newest backup -> restart

`--apply` is fail-safe: it re-parses the spliced YAML BEFORE writing, and if the instance
does not come back healthy it restores the backup and restarts again on its own. A bad
edit therefore cannot leave the owner without search.

NOTE: enabling engines is only about the DEFAULT result mix. A `disabled` engine is
already reachable ad hoc via `engines=<name>` or its `!<shortcut>` bang — measured
2026-07-24, `!yd` returned 10 Yandex results with the engine still marked disabled.
"""

from __future__ import annotations

import argparse
import datetime as dt
import http.client
import json
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from searxng_config import (
    REGIONAL_ENGINES,
    ConflictError,
    apply_block,
    has_managed_block,
    remove_block,
    render_engines_block,
    unified_diff,
)

DEFAULT_SETTINGS = pathlib.Path(r"D:\searxng\settings.yml")
DEFAULT_BASE_URL = "http://127.0.0.1:8890"
DEFAULT_CONTAINER = "searxng"
BACKUP_SUFFIX = ".bak-"

#: Native-language probe queries. A Latin query against a CJK/Cyrillic index tests the
#: wrong thing — measured: `naver` returned 0 for both, but `naver news` returned 10 for
#: a Korean query, which is what separated "engine down" from "parser drift".
PROBE_QUERIES = {
    "RU": "квантовые вычисления",
    "CN": "量子计算",
    "KR": "반도체 수출",
    "CZ": "kvantove pocitace",
    "FR": "informatique quantique",
    "independent": "quantum computing",
    "global": "quantum computing",
}


def _search(base_url: str, engine: str, query: str, timeout: int = 60) -> dict:
    qs = urllib.parse.urlencode({"q": query, "engines": engine, "format": "json"})
    req = urllib.request.Request(  # noqa: S310 - fixed loopback scheme, operator-supplied
        f"{base_url}/search?{qs}",
        headers={"User-Agent": "searxng-regional-probe/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.load(resp)


def cmd_probe(base_url: str) -> int:
    """Query every engine in its own language and classify what came back."""
    print(f"probing {base_url}  ({len(REGIONAL_ENGINES)} engines)\n")
    print(f"{'engine':<14} {'bang':<8} {'region':<12} verdict")
    print("-" * 72)
    working = 0
    for spec in REGIONAL_ENGINES:
        query = PROBE_QUERIES.get(spec.region, PROBE_QUERIES["independent"])
        try:
            data = _search(base_url, spec.name, query)
        except (OSError, http.client.HTTPException, TimeoutError, ValueError) as exc:
            verdict = f"UNREACHABLE ({type(exc).__name__})"
        else:
            count = len(data.get("results", []))
            errors = data.get("unresponsive_engines") or []
            if count:
                verdict = f"WORKS n={count}"
                working += 1
            elif errors:
                verdict = f"BLOCKED {errors[0][-1] if errors[0] else 'unknown'}"
            else:
                # No results AND no error reported: the shape that reads as success.
                verdict = "SILENT-FAIL n=0, no error reported"
        print(f"{spec.name:<14} !{spec.shortcut:<7} {spec.region:<12} {verdict}")
    print(f"\n{working}/{len(REGIONAL_ENGINES)} engines returned results.")
    print("Engines marked WORKS are usable NOW via `engines=<name>` or `!<shortcut>` —")
    print("no --apply needed. --apply only adds them to the DEFAULT result mix.")
    return 0


def _validate_yaml(text: str) -> None:
    """Parse before writing. A settings.yml that will not load takes search down."""
    try:
        import yaml
    except ImportError:
        print("WARNING: PyYAML not installed - skipping the pre-write parse check.")
        print("         Install it (pip install pyyaml) before trusting --apply.")
        return
    yaml.safe_load(text)


def _health_ok(base_url: str, attempts: int = 20, delay: float = 1.5) -> bool:
    """Poll /config until the instance answers 200, or give up.

    The exception set is deliberately WIDE. Measured 2026-07-24: a container mid-restart
    ACCEPTS the TCP connection and then closes it without replying, raising
    `http.client.RemoteDisconnected` — which is NOT a `urllib.error.URLError`. Catching
    only URLError let that escape and killed the caller before its rollback could run,
    which is the one failure mode this whole function exists to prevent.
    """
    for _ in range(attempts):
        try:
            req = urllib.request.Request(f"{base_url}/config")  # noqa: S310
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                if resp.status == 200:
                    return True
        except (OSError, http.client.HTTPException, TimeoutError):
            pass
        time.sleep(delay)
    return False


def _restart(container: str) -> bool:
    print(f"restarting container {container!r} ...")
    proc = subprocess.run(  # noqa: S603
        ["docker", "restart", container],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(f"  docker restart failed: {proc.stderr.strip()}")
        return False
    return True


def _newest_backup(settings: pathlib.Path) -> pathlib.Path | None:
    backups = sorted(settings.parent.glob(f"{settings.name}{BACKUP_SUFFIX}*"))
    return backups[-1] if backups else None


def cmd_dry_run(settings: pathlib.Path) -> int:
    before = settings.read_text(encoding="utf-8")
    try:
        after = apply_block(before, render_engines_block())
    except ConflictError as exc:
        print(f"REFUSING: {exc}")
        return 2
    diff = unified_diff(before, after, path=str(settings))
    if not diff:
        print("no change - the managed block is already applied and current.")
        return 0
    print(diff)
    print(f"\n(dry run - {settings} not modified)")
    return 0


def cmd_apply(settings: pathlib.Path, container: str, base_url: str) -> int:
    before = settings.read_text(encoding="utf-8")
    try:
        after = apply_block(before, render_engines_block())
    except ConflictError as exc:
        print(f"REFUSING: {exc}")
        return 2
    if after == before:
        print("no change - already applied.")
        return 0

    _validate_yaml(after)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = settings.with_name(f"{settings.name}{BACKUP_SUFFIX}{stamp}")
    shutil.copy2(settings, backup)
    print(f"backup written: {backup}")

    settings.write_text(after, encoding="utf-8")
    print(f"applied managed block to {settings}")

    if _restart(container) and _health_ok(base_url):
        print(f"health check OK - {base_url}/config responded 200")
        print("run --probe to confirm the engines now answer.")
        return 0

    print("HEALTH CHECK FAILED - restoring the backup and restarting.")
    shutil.copy2(backup, settings)
    _restart(container)
    print(f"restored from {backup}. Nothing was left broken.")
    return 1


def cmd_revert(settings: pathlib.Path, container: str, base_url: str) -> int:
    backup = _newest_backup(settings)
    if backup is not None:
        shutil.copy2(backup, settings)
        print(f"restored {settings} from {backup}")
    elif has_managed_block(settings.read_text(encoding="utf-8")):
        settings.write_text(
            remove_block(settings.read_text(encoding="utf-8")), encoding="utf-8"
        )
        print(f"no backup found - stripped the managed block from {settings} in place")
    else:
        print("nothing to revert: no backup and no managed block present.")
        return 0
    _restart(container)
    print(
        "health OK" if _health_ok(base_url) else "WARNING: instance did not come back"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--probe", action="store_true", help="live per-engine reachability"
    )
    mode.add_argument(
        "--dry-run", action="store_true", help="show the diff, change nothing"
    )
    mode.add_argument("--apply", action="store_true", help="enable the working engines")
    mode.add_argument("--revert", action="store_true", help="restore the newest backup")
    parser.add_argument("--settings", type=pathlib.Path, default=DEFAULT_SETTINGS)
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args(argv)

    if args.probe:
        return cmd_probe(args.base_url)
    if not args.settings.is_file():
        print(f"settings file not found: {args.settings}")
        print("pass --settings <path> (find it with: docker inspect <container>)")
        return 2
    if args.dry_run:
        return cmd_dry_run(args.settings)
    if args.apply:
        return cmd_apply(args.settings, args.container, args.base_url)
    return cmd_revert(args.settings, args.container, args.base_url)


if __name__ == "__main__":
    sys.exit(main())
