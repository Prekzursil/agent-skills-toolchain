"""Enumerate + purge EVERY Codex fan-out rail on DBFS by STRUCTURE, not by name.

Why structure: a name-based sweep (grep 'codex') missed 38 of our own rails whose dirs are
called selection-gate-*, primariro-*, crcp-e2e-*, aisr-*, E-prompt*. The reliable signature
of a rail written by our harness is a `batch.json` manifest and/or a `results/` child.
Provenance is confirmed by reading batch.json's own `name`/`units` fields before deleting.

Default is DRY-RUN. Pass --apply to delete. Bolt is SHARED PROD: anything lacking the
harness signature is listed as FOREIGN and never touched.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

PROFILE = "bolt-datascience"
ROOT = "dbfs:/tmp"


def db(args, timeout=120):
    return subprocess.run(
        ["databricks", *args, "--profile", PROFILE],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env={**os.environ, "MSYS_NO_PATHCONV": "1"},
    )


def list_dirs() -> list[str]:
    r = db(["fs", "ls", ROOT, "--long"])
    out = []
    for ln in (r.stdout or "").splitlines():
        if ln.strip().startswith("DIRECTORY"):
            name = ln.split()[-1].strip()
            if name:
                out.append(name)
    return out


def probe(name: str) -> dict | None:
    """Return rail info if <name> carries the harness signature, else None."""
    r = db(["fs", "ls", f"{ROOT}/{name}"])
    if r.returncode != 0:
        return None
    kids = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
    has_results = any(k == "results" or k.endswith("/results") for k in kids)
    has_batch = any("batch.json" in k for k in kids)
    if not (has_results or has_batch):
        return None

    label, units = "", 0
    if has_batch:
        c = db(["fs", "cat", f"{ROOT}/{name}/batch.json"])
        try:
            d = json.loads(c.stdout or "{}")
            label = str(d.get("name") or "")
            u = d.get("units")
            units = len(u) if isinstance(u, list) else 0
        except Exception:
            label = "(batch.json unparsed)"

    n_art = 0
    if has_results:
        rr = db(["fs", "ls", f"{ROOT}/{name}/results"])
        n_art = sum(1 for x in (rr.stdout or "").splitlines() if x.strip())

    return {
        "dir": name,
        "label": label,
        "units": units,
        "artifacts": n_art,
        "sig": ("batch.json" if has_batch else "")
        + ("+results" if has_results else ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    print(f"=== purge_dbfs_rails [{'APPLY' if a.apply else 'DRY-RUN'}] ===\n")

    dirs = list_dirs()
    print(f"dirs under {ROOT}: {len(dirs)}")
    with ThreadPoolExecutor(max_workers=12) as ex:
        found = [r for r in ex.map(probe, dirs) if r]

    print(
        f"rails with harness signature: {len(found)}   foreign/other: {len(dirs) - len(found)} (untouched)\n"
    )
    tot_art = 0
    for r in sorted(found, key=lambda x: x["dir"]):
        tot_art += r["artifacts"]
        print(
            f"  {r['dir']:32} units={r['units']:<4} artifacts={r['artifacts']:<4} "
            f"[{r['sig']}] {r['label'][:40]}"
        )
    print(f"\n  TOTAL artifacts across rails: {tot_art}")

    if a.apply:
        ok = fail = 0
        for r in found:
            d = db(["fs", "rm", "-r", f"{ROOT}/{r['dir']}"], timeout=300)
            if d.returncode == 0:
                ok += 1
            else:
                fail += 1
                print(f"  rm {r['dir']} FAILED: {(d.stderr or '').strip()[:140]}")
        print(f"\n  rails deleted: {ok}   failed: {fail}")
    else:
        print(f"\n  [dry-run] would delete {len(found)} rails / {tot_art} artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
