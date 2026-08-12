r"""The dangerous dark state: resolver FILE absent, so `_load_resolver()` returns None.

Probe 1 measured the jsonschema-missing state and found it fails closed -- but for a reason that
has nothing to do with the predicate: `platform/lib/schema_resolver.py` raises `SystemExit` at
import time, and `_load_resolver`'s `except Exception` does not catch `SystemExit` (it derives from
BaseException), so the process dies with exit 1 and a clear message. Accidental, but effective.

That leaves the OTHER dark state untested, and it is the one `_load_resolver` is actually written
for: the resolver file is missing or unimportable, the function returns None by design, and the
caller is documented to "DEGRADE LOUDLY". Loudly is not the same as non-zero. This measures whether
`self_test()` and `main()` RETURN non-zero with resolver=None, because a CI gate is only as good as
its exit code.

Method: import the module and monkeypatch `_load_resolver` to return None. Mechanically independent
of probe 1 (no subprocess, no PYTHONPATH shadow, a different failure injection point), so the two
readings corroborate rather than repeat each other.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "command-center" / "ready_units.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ready_units_probe", TOOL)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ready_units_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def call(mod, name: str) -> tuple[int, str]:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = getattr(mod, name)()
    except SystemExit as exc:  # main() may raise rather than return
        code = int(exc.code or 0)
    except Exception as exc:  # a crash is also a fail-closed, but a different one
        return -1, f"{type(exc).__name__}: {exc}\n{buf.getvalue()}"
    return int(code), buf.getvalue()


def main() -> int:
    out = {}

    # --- LIT state: the control. If this is not 0 the probe is measuring something else. ---
    mod = load_module()
    for fn in ("self_test", "main"):
        code, text = call(mod, fn)
        out[f"{fn}/LIT"] = {"exit": code, "terminal": _terminal(text)}

    # --- DARK state: resolver absent by design. ---
    mod2 = load_module()
    mod2._DISCRIMINATES.clear()
    mod2._REGISTRY_CACHE.clear()
    mod2._load_resolver = lambda: None
    for fn in ("self_test", "main"):
        code, text = call(mod2, fn)
        out[f"{fn}/DARK"] = {
            "exit": code,
            "terminal": _terminal(text),
            "resolver_line": next(
                (ln.strip() for ln in text.splitlines() if "resolver:" in ln), ""
            ),
            "vacuity_line": next(
                (ln.strip() for ln in text.splitlines() if "contract-vacuity" in ln), ""
            ),
        }

    for key, val in out.items():
        print(f"  {key:<18} exit={val['exit']:<3} {val['terminal']}")
        if val.get("resolver_line"):
            print(f"  {'':<18} {val['resolver_line']}")
        if val.get("vacuity_line"):
            print(f"  {'':<18} {val['vacuity_line']}")

    lit_ok = out["self_test/LIT"]["exit"] == 0 and out["main/LIT"]["exit"] == 0
    verdict = {
        "control_lit_is_green": lit_ok,
        "self_test_fails_closed_when_dark": out["self_test/DARK"]["exit"] != 0,
        "partition_fails_closed_when_dark": out["main/DARK"]["exit"] != 0,
        "detail": out,
    }
    Path(__file__).with_suffix(".out.json").write_text(
        json.dumps(verdict, indent=2), encoding="utf-8"
    )

    if not lit_ok:
        print(
            "FAILED:i1-dark2 the LIT control is not green; the DARK reading means nothing"
        )
        return 1
    print(
        "SUCCESS:i1-dark2 "
        f"self_test dark-exit={out['self_test/DARK']['exit']}, "
        f"partition dark-exit={out['main/DARK']['exit']}"
    )
    return 0


def _terminal(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.startswith(("SUCCESS:", "FAILED:")):
            return line.strip()[:110]
    return "<no terminal marker>"


if __name__ == "__main__":
    raise SystemExit(main())
