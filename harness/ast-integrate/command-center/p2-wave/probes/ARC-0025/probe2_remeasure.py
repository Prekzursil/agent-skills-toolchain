#!/usr/bin/env python3
"""Probe 2: mechanically different remeasure + reviewer re-derivation.

Different shell / data field: bytes via `wc -c` (not Python len).
Tokens via a fresh python3 subprocess importing the pinned tokenizer
(not the in-process measure.measure() totals).

Re-derives always_on.tokens (headline) and must land within 10 percent of
COST.json. If wc -c and Python len disagree, fail rather than pick one.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as INV  # noqa: E402
import measure as M  # noqa: E402
import tokenizer as TOK  # noqa: E402

COST = REPO / "command-center" / "phase3" / "A4" / "COST.json"
OUT = HERE / "probe2-remeasure.raw.json"
BAND = 10.0


def subprocess_token_count(path: Path) -> int:
    rel = path.relative_to(REPO).as_posix()
    code = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, 'command-center/p2-wave/probes/ARC-0025'); "
        "import tokenizer as T; "
        f"p = Path({rel!r}); "
        "print(T.count_bytes(p.read_bytes()))"
    )
    p = subprocess.run(
        [sys.executable, "-B", "-c", code],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=True,
    )
    return int(p.stdout.strip())


def pct_delta(a: float, b: float) -> float:
    if b == 0:
        return 0.0 if a == 0 else 100.0
    return abs(a - b) / abs(b) * 100.0


def main() -> int:
    bag = INV.materialize()
    files = bag["files"]
    fail = False
    reasons: list[str] = []

    py_bytes = {}
    wc_bytes = M.remeasure_shell_bytes(files)
    sub_tokens = {}
    py_tokens = {}
    for f in files:
        path = REPO / f["path"]
        raw = M.read_norm(path)
        py_bytes[f["id"]] = len(raw)
        py_tokens[f["id"]] = TOK.count_bytes(raw)
        sub_tokens[f["id"]] = subprocess_token_count(path)
        if wc_bytes[f["id"]] != py_bytes[f["id"]]:
            fail = True
            reasons.append(
                f"wc-c/python-len disagree {f['id']}: "
                f"{wc_bytes[f['id']]} vs {py_bytes[f['id']]}"
            )
        if sub_tokens[f["id"]] != py_tokens[f["id"]]:
            fail = True
            reasons.append(
                f"subprocess/in-process tokens disagree {f['id']}: "
                f"{sub_tokens[f['id']]} vs {py_tokens[f['id']]}"
            )

    body_ids = [f["id"] for f in files if f["role"] == "catalogue"]
    act_ids = list(bag["activated_ids"])
    always_b = sum(wc_bytes[i] for i in body_ids)
    always_t = sum(sub_tokens[i] for i in body_ids)
    act_b = sum(wc_bytes[i] for i in act_ids)
    act_t = sum(sub_tokens[i] for i in act_ids)
    bdir = M.direction(always_b, act_b)
    tdir = M.direction(always_t, act_t)
    agree = bdir == tdir == "gt"
    if not agree:
        fail = True
        reasons.append(f"shell two-signal disagree bytes={bdir} tokens={tdir}")

    headline_live = always_t
    within = None
    cost_tokens = None
    if not COST.is_file():
        fail = True
        reasons.append("COST.json absent")
    else:
        cost = json.loads(COST.read_text(encoding="utf-8"))
        cost_tokens = int(cost["always_on"]["tokens"])
        delta = pct_delta(headline_live, cost_tokens)
        within = delta <= BAND
        if not within:
            fail = True
            reasons.append(
                f"reviewer always_on.tokens {headline_live} vs COST {cost_tokens} "
                f"delta={delta:.3f}% > {BAND}%"
            )
        nstar_cost = cost["break_even"]["first_net_positive_integer_n"]
        live2 = M.measure(include_latency=False)
        if live2["break_even"]["first_net_positive_integer_n"] != nstar_cost:
            fail = True
            reasons.append("re-derived first_net_positive_integer_n != COST")
        if cost["arc0004_cross_check"]["same_tokenizer"] is not True:
            fail = True
            reasons.append("cross-check tokenizer pin missing")
        if cost["arc0004_cross_check"]["config_first_tokens"] != cost_tokens:
            fail = True
            reasons.append("ARC-0004 stand-in is not identical to always_on tokens")

    raw = {
        "wc_bytes_always_on": always_b,
        "python_bytes_always_on": sum(py_bytes[i] for i in body_ids),
        "subprocess_tokens_always_on": always_t,
        "activated_wc_bytes": act_b,
        "activated_subprocess_tokens": act_t,
        "bytes_direction": bdir,
        "tokens_direction": tdir,
        "agree": agree,
        "headline_field": "always_on.tokens",
        "headline_rederived": headline_live,
        "cost_always_on_tokens": cost_tokens,
        "error_band_pct": BAND,
        "within_band": within,
        "fail": fail,
        "reasons": reasons,
        "shell": "wc -c",
        "token_path": "python3 -B -c tokenizer.count_bytes (subprocess)",
    }
    OUT.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wc-c always_on_bytes={always_b} python_len={raw['python_bytes_always_on']} "
        f"subproc_tokens={always_t} cost_tokens={cost_tokens} "
        f"within_band={within} agree={agree}"
    )
    if fail:
        print("FAILED:ARC-0025-probe2 " + "; ".join(reasons))
        return 1
    print("SUCCESS:ARC-0025-probe2 shell wc-c remeasure and reviewer re-derivation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
