#!/usr/bin/env python3
"""ARC-0015 probe1 (mutation-control): determinism goes red on injected non-determinism.

Both-states discipline (TEST-PLAN T-MUT-DATETIME-NOW + T-MUT-DICT-ORDER):
  * CLEAN state   : two generate() calls over the live ARC-0010 registry are
                    byte-identical and cover every registry entry.
  * DATETIME-NOW  : a module clone whose provenance() stamps
                    datetime.now().isoformat() must make the two runs differ.
  * DICT-ORDER    : a module clone whose second generate() drops sort_keys and
                    reverses top-level key order must make the two runs differ.

Fail-closed: any control not both fired-on-bad and silent-on-clean exits 1.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GEN_PATH = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010" / "generator.py"
REG_PATH = REPO / "command-center" / "p2-wave" / "probes" / "ARC-0010" / "registry.json"

_line = ""


def _say(msg: str) -> None:
    global _line
    _line = msg
    print(msg)


def load_generator(name: str):
    spec = importlib.util.spec_from_file_location(name, GEN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load generator at {GEN_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def tree_digest(files: dict[str, bytes]) -> dict[str, str]:
    return {rel: sha(data) for rel, data in sorted(files.items())}


def main() -> int:
    registry = json.loads(REG_PATH.read_text(encoding="utf-8"))
    n_entries = len(registry.get("entries") or [])

    # --- control 1: CLEAN state stays byte-identical across two runs ------ #
    clean = load_generator("a2gen_clean")
    fa = clean.generate(registry)
    fb = clean.generate(registry)
    da, db = tree_digest(fa), tree_digest(fb)
    clean_identical = da == db
    clean_full = len(fa) == n_entries and n_entries > 0
    print(f"clean two_run_identical={clean_identical} files={len(fa)} entries={n_entries}")
    if not clean_identical:
        _say("FAILED:ARC-0015-probe1 clean generator is non-deterministic (control fired on GOOD state)")
        return 1
    if not clean_full:
        _say(f"FAILED:ARC-0015-probe1 generate() covered {len(fa)} of {n_entries} entries")
        return 1

    # --- control 2: DATETIME-NOW injection goes red ------------------------ #
    dtmod = load_generator("a2gen_dt")
    orig_prov = dtmod.provenance

    def stamped(entry):
        prov = orig_prov(entry)
        prov["generated_at"] = _dt.datetime.now().isoformat()
        return prov

    dtmod.provenance = stamped
    g1 = dtmod.generate(registry)
    g2 = dtmod.generate(registry)
    dt_fired = tree_digest(g1) != tree_digest(g2)
    print(f"mutation_datetime_now fired_on_bad_state={dt_fired}")
    if not dt_fired:
        _say("FAILED:ARC-0015-probe1 datetime.now() injection did NOT turn determinism red")
        return 1

    # --- control 3: DICT-ORDER leak on the second generate() goes red ----- #
    domod = load_generator("a2gen_dictorder")
    orig_gen = domod.generate
    orig_canon = domod.canonical_json_bytes
    calls = {"n": 0}

    def keyed_gen(registry_arg):
        calls["n"] += 1
        if calls["n"] == 2:
            def leaky(obj):
                rev = dict(reversed(list(obj.items())))
                return (
                    json.dumps(rev, sort_keys=False, indent=2, ensure_ascii=True) + "\n"
                ).encode("utf-8")
            domod.canonical_json_bytes = leaky
            try:
                return orig_gen(registry_arg)
            finally:
                domod.canonical_json_bytes = orig_canon
        return orig_gen(registry_arg)

    domod.generate = keyed_gen
    h1 = domod.generate(registry)
    h2 = domod.generate(registry)
    dict_fired = tree_digest(h1) != tree_digest(h2)
    print(f"mutation_dict_order fired_on_bad_state={dict_fired}")
    if not dict_fired:
        _say("FAILED:ARC-0015-probe1 dict-order leak did NOT turn determinism red")
        return 1

    # --- negative-control summary ------------------------------------------ #
    print(
        "negative_controls silent_on_clean: "
        f"clean_identical={clean_identical} clean_full={clean_full}"
    )
    print(
        f"arc0015_probe1 clean_identical={clean_identical} "
        f"datetime_fired={dt_fired} dictorder_fired={dict_fired}"
    )
    _say("SUCCESS:ARC-0015-probe1 mutation controls both-states verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
