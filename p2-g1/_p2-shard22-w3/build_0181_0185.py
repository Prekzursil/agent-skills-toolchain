#!/usr/bin/env python3
"""Write TST-0181 + TST-0185 probe files."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "command-center" / "p2-wave" / "probes"

M181 = r'''#!/usr/bin/env python3
"""TST-0181 measured layer: hooks-config loader (with a $schema-crash mutant).

Loaded-set semantics: every hook entry whose command target exists is LOADED;
a hook whose file is missing is a LOUD per-hook error (never a silent zero).
The $schema key is metadata: it must be ignored entirely.
"""
from __future__ import annotations

import json
from pathlib import Path


class HookLoadError(Exception):
    def __init__(self, message: str, missing: list[str] | None = None):
        super().__init__(message)
        self.missing = missing or []


def load_hooks(config_path: Path, base_dir: Path, *, crash_on_schema: bool = False) -> dict:
    """Returns {loaded: {name: command}, errors: [missing files]}.

    The mutant (crash_on_schema=True) reproduces the regression seed: any
    $schema key in the config makes the client load ZERO hooks.
    """
    doc = json.loads(config_path.read_text(encoding="utf-8"))
    if crash_on_schema and "$schema" in doc:
        return {"loaded": {}, "errors": [], "crashed_on_schema": True}
    loaded: dict[str, str] = {}
    errors: list[str] = []
    for name, spec in (doc.get("hooks") or {}).items():
        cmd = spec.get("command") if isinstance(spec, dict) else None
        target = base_dir / (spec.get("file") if isinstance(spec, dict) else None)
        if cmd is None:
            errors.append(name + ": missing command")
            continue
        if not target.is_file():
            errors.append(name + ": hook file missing: " + str(spec.get("file")))
            continue
        loaded[name] = cmd
    return {"loaded": loaded, "errors": errors, "crashed_on_schema": False}
'''

P181_1 = r'''#!/usr/bin/env python3
"""TST-0181 probe1 -- a $schema key must not change which hooks load.

Both-states: identical loaded set and count with and without the $schema key.
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hooks_loader as HL  # noqa: E402

UNIT = "TST-0181"
RUN = HERE / ".run-p1"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    (RUN / "hooks").mkdir(parents=True)
    for i in range(3):
        (RUN / "hooks" / ("h%d.py" % i)).write_text("# hook %d\n" % i)
    with_schema = {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "hooks": {
            "alpha": {"command": "run-alpha", "file": "h0.py"},
            "beta": {"command": "run-beta", "file": "h1.py"},
            "gamma": {"command": "run-gamma", "file": "h2.py"},
        },
    }
    without_schema = {k: v for k, v in with_schema.items() if k != "$schema"}
    (RUN / "with.json").write_text(json.dumps(with_schema), encoding="utf-8")
    (RUN / "without.json").write_text(json.dumps(without_schema), encoding="utf-8")

    a = HL.load_hooks(RUN / "with.json", RUN / "hooks")
    b = HL.load_hooks(RUN / "without.json", RUN / "hooks")
    same_set = a["loaded"] == b["loaded"]
    same_count = len(a["loaded"]) == len(b["loaded"]) == 3
    schema_ignored = not a.get("crashed_on_schema")

    payload = {
        "probe": "probe1-schema-neutral",
        "unit_id": UNIT,
        "pass": same_set and same_count and schema_ignored,
        "with_schema": {"count": len(a["loaded"]), "names": sorted(a["loaded"])},
        "without_schema": {"count": len(b["loaded"]), "names": sorted(b["loaded"])},
        "identical_loaded_set": same_set,
        "identical_count": same_count,
        "schema_did_not_crash_loader": schema_ignored,
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 count_with=%d count_without=%d identical_set=%s"
              % (UNIT, len(a["loaded"]), len(b["loaded"]), same_set))
        return 0
    print("FAILED:%s-probe1 with=%d without=%d identical=%s"
          % (UNIT, len(a["loaded"]), len(b["loaded"]), same_set))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P181_2 = r'''#!/usr/bin/env python3
"""TST-0181 probe2 -- detector controls: a removed hook file drops the count and
errors LOUDLY; the $schema-crash regression seed is visible to the probe.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hooks_loader as HL  # noqa: E402

UNIT = "TST-0181"
RUN = HERE / ".run-p2"


def main() -> int:
    import shutil

    if RUN.exists():
        shutil.rmtree(RUN)
    (RUN / "hooks").mkdir(parents=True)
    for i in range(3):
        (RUN / "hooks" / ("h%d.py" % i)).write_text("# hook %d\n" % i)
    cfg = {
        "$schema": "https://json-schema.org/draft-07/schema#",
        "hooks": {
            "alpha": {"command": "run-alpha", "file": "h0.py"},
            "beta": {"command": "run-beta", "file": "h1.py"},
            "gamma": {"command": "run-gamma", "file": "h2.py"},
        },
    }
    (RUN / "cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
    base = HL.load_hooks(RUN / "cfg.json", RUN / "hooks")
    n0 = len(base["loaded"])

    # (a) remove one hook file -> count drops AND the missing hook is a LOUD error
    (RUN / "hooks" / "h1.py").unlink()
    after = HL.load_hooks(RUN / "cfg.json", RUN / "hooks")
    count_dropped = len(after["loaded"]) == n0 - 1
    loud_error = bool(after["errors"]) and any("beta" in e and "missing" in e for e in after["errors"])

    # (b) regression seed: the crash-on-$schema client loads ZERO hooks with $schema
    crashed = HL.load_hooks(RUN / "cfg.json", RUN / "hooks", crash_on_schema=True)
    seed_visible = crashed.get("crashed_on_schema") is True and len(crashed["loaded"]) == 0

    payload = {
        "probe": "probe2-detector-controls",
        "unit_id": UNIT,
        "pass": count_dropped and loud_error and seed_visible,
        "detector_control": {
            "baseline_count": n0,
            "count_after_file_removal": len(after["loaded"]),
            "count_probe_drops": count_dropped,
            "loud_error_listing_missing": after["errors"],
        },
        "regression_seed": {
            "seed": "hooks.json $schema made a client load ZERO hooks (_USER-PROMPTS.md:11014 layer 26)",
            "crash_variant_loaded_zero": len(crashed["loaded"]) == 0,
            "detector_sees_the_zero": seed_visible,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 count_drop=%s loud=%s seed_zero_visible=%s"
              % (UNIT, count_dropped, loud_error, seed_visible))
        return 0
    print("FAILED:%s-probe2 drop=%s loud=%s seed=%s" % (UNIT, count_dropped, loud_error, seed_visible))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

M185 = r'''#!/usr/bin/env python3
"""TST-0185 measured layer: exact parse/emit path for 64-bit ids and precise decimals.

Exact lane: json.loads with parse_int=int (arbitrary precision) and
parse_float=decimal.Decimal; emit via json.dumps (Decimal serialized as its
exact digit string). Lossy lane (negative control): float()-based parsing.
"""
from __future__ import annotations

import json
from decimal import Decimal


class ExactEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return RawNumber(str(o))
        return super().default(o)


class RawNumber(str):
    """Marker: emitted verbatim, without quotes, by emit_exact."""


def emit_exact(doc) -> str:
    text = json.dumps(doc, cls=ExactEncoder)
    # unquote RawNumber markers: "num__<digits>" -> <digits>
    out = []
    i = 0
    token = "\"num__"
    while i < len(text):
        j = text.find(token, i)
        if j < 0:
            out.append(text[i:])
            break
        out.append(text[i:j])
        k = text.find("\"", j + len(token))
        out.append(text[j + len(token):k])
        i = k + 1
    return "".join(out)


def parse_exact(text: str):
    return json.loads(text, parse_int=int, parse_float=Decimal)


def parse_float_lossy(text: str):
    """The known-broken lane: everything through float64."""
    return json.loads(text, parse_int=float, parse_float=float)
'''

P185_1 = r'''#!/usr/bin/env python3
"""TST-0185 probe1 -- property test: generated ids spanning 2^40..2^63 and decimals
with 20 significant digits survive the exact parse/emit path with no loss.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import random
import sys
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import int_roundtrip as IR  # noqa: E402

UNIT = "TST-0185"


def main() -> int:
    rng = random.Random(185185)
    id_failures = []
    dec_failures = []
    n_ids, n_decs = 1000, 500
    for _ in range(n_ids):
        v = rng.randint(2 ** 40, 2 ** 63)
        text = IR.emit_exact({"id": v})
        back = IR.parse_exact(text)["id"]
        if not (isinstance(back, int) and back == v):
            id_failures.append(v)
    for _ in range(n_decs):
        digits = "".join(rng.choice("0123456789") for _ in range(20))
        d = Decimal(digits[0] + "." + digits[1:] + "e" + str(rng.randint(-8, 8)))
        text = IR.emit_exact({"price": d})
        back = IR.parse_exact(text)["price"]
        if not (isinstance(back, Decimal) and back == d):
            dec_failures.append(str(d))

    payload = {
        "probe": "probe1-roundtrip",
        "unit_id": UNIT,
        "pass": not id_failures and not dec_failures,
        "ids_checked": n_ids,
        "id_failures": len(id_failures),
        "decimals_checked": n_decs,
        "decimal_failures": len(dec_failures),
        "span": {"ids": "2^40..2^63", "decimals": "20 significant digits, exponent -8..8"},
        "exact_lane": "json parse_int=int + parse_float=Decimal; Decimal emitted as exact digits",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 ids=%d/1000 exact decimals=%d/500 exact"
              % (UNIT, n_ids - len(id_failures), n_decs - len(dec_failures)))
        return 0
    print("FAILED:%s-probe1 id_fail=%d dec_fail=%d" % (UNIT, len(id_failures), len(dec_failures)))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P185_2 = r'''#!/usr/bin/env python3
"""TST-0185 probe2 -- negative control: a float-based parser MUST fail above 2^53.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import int_roundtrip as IR  # noqa: E402

UNIT = "TST-0185"


def main() -> int:
    failures = 0
    examples = []
    checked = 0
    for delta in [1, 2, 3, 5, 1025, 1 << 20]:
        v = (1 << 53) + delta
        text = IR.emit_exact({"id": v})
        got = IR.parse_float_lossy(text)["id"]
        exact = IR.parse_exact(text)["id"]
        checked += 1
        if got != exact:
            failures += 1
            examples.append({"value": v, "float_got": int(got), "loss": exact - int(got)})
        if float(v) != v:
            pass  # float(v) rounding is the same defect seen through a different door
    # canonical demonstration: 2^53 and 2^53+1 are the SAME float
    collapse = float(1 << 53) == float((1 << 53) + 1)

    payload = {
        "probe": "probe2-float-control",
        "unit_id": UNIT,
        "pass": failures >= 3 and collapse,
        "float_lane_failures_above_2p53": failures,
        "values_checked": checked,
        "examples": examples[:5],
        "float64_collapse_2p53_vs_2p53p1": collapse,
        "note": "the lossy float path losing ids is the negative control that proves the exact lane matters",
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 float_failures=%d/%d collapse=%s"
              % (UNIT, failures, checked, collapse))
        return 0
    print("FAILED:%s-probe2 failures=%d collapse=%s" % (UNIT, failures, collapse))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

D181 = PROBES / "TST-0181"
D185 = PROBES / "TST-0185"
D181.mkdir(parents=True, exist_ok=True)
D185.mkdir(parents=True, exist_ok=True)
(D181 / "hooks_loader.py").write_text(M181, encoding="utf-8", newline="\n")
(D181 / "probe1_schema_neutral.py").write_text(P181_1, encoding="utf-8", newline="\n")
(D181 / "probe2_detector_controls.py").write_text(P181_2, encoding="utf-8", newline="\n")
(D185 / "int_roundtrip.py").write_text(M185, encoding="utf-8", newline="\n")
(D185 / "probe1_roundtrip.py").write_text(P185_1, encoding="utf-8", newline="\n")
(D185 / "probe2_float_control.py").write_text(P185_2, encoding="utf-8", newline="\n")
import ast

for f in [M181, P181_1, P181_2, M185, P185_1, P185_2]:
    ast.parse(f)
print("TST-0181 + TST-0185 written + syntax OK")
