#!/usr/bin/env python3
"""G5 grounding probe: is the /rollback producer gap STILL open, right now?

Independent of the round-1..4 probes: reads the LIVE manifest + LIVE settings.json
directly and counts the thing actually being compared (checks), not the event dict.

Controls (both-states):
  C1  live manifest parses and yields a PLAUSIBLE check count (>=20) -> else fail closed.
  C2  a KNOWN-PRESENT check name ('wire-check' family) must be found by the same
      matcher used to look for edit-checkpoints. If the matcher cannot find a check
      that IS there, its silence about edit-checkpoints means nothing.
  C3  repo manifest must contain edit-checkpoints (the hypothesis under test says
      repo-has / live-lacks). If repo ALSO lacks it, the premise moved.
"""

import json
import os
import sys

LIVE_MANIFEST = r"C:\Users\Prekzursil\.claude\hooks\_dispatch\manifest.json"
LIVE_SETTINGS = r"C:\Users\Prekzursil\.claude\settings.json"
REPO_MANIFEST = (
    r"C:\Users\Prekzursil\source\ast-integrate\hooks\_dispatch\manifest.json"
)
CKPT_INDEX_CANDIDATES = [
    r"C:\Users\Prekzursil\.claude\edit-checkpoints\index.ndjson",
    r"C:\Users\Prekzursil\.claude\checkpoints\index.ndjson",
    r"C:\Users\Prekzursil\.claude\hooks\edit-checkpoints\index.ndjson",
]


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def checks_of(manifest):
    """events -> {event: [check dicts]}. The event VALUE is a dict; hooks live in 'checks'."""
    out = {}
    for ev, val in (manifest.get("events") or {}).items():
        if isinstance(val, dict):
            out[ev] = list(val.get("checks") or [])
        elif isinstance(val, list):  # shape change -> record, do not silently coerce
            out[ev] = list(val)
        else:
            out[ev] = []
    return out


def names(checkmap):
    n = []
    for ev, chks in checkmap.items():
        for c in chks:
            if isinstance(c, dict):
                n.append(
                    (ev, c.get("name") or c.get("id") or c.get("script") or "?", c)
                )
    return n


def main():
    res = {"controls": {}, "verdict": {}}

    live_m = load(LIVE_MANIFEST)
    repo_m = load(REPO_MANIFEST)
    live_c = checks_of(live_m)
    repo_c = checks_of(repo_m)
    live_n = names(live_c)
    repo_n = names(repo_c)

    res["live_check_count"] = len(live_n)
    res["repo_check_count"] = len(repo_n)
    res["live_events"] = {e: len(v) for e, v in live_c.items()}
    res["repo_events"] = {e: len(v) for e, v in repo_c.items()}

    # C1 plausibility / fail-closed
    res["controls"]["C1_live_count_plausible"] = len(live_n) >= 20
    if len(live_n) < 20:
        res["controls"]["C1_note"] = (
            "IMPLAUSIBLE check count -> shape change or wrong key; refusing to report parity"
        )

    # C2 detector control: find a check we KNOW is live
    def has(nn, needle):
        return [(e, n) for (e, n, _c) in nn if needle in (n or "").lower()]

    known = has(live_n, "wire")
    res["controls"]["C2_known_present_found"] = bool(known)
    res["controls"]["C2_known_present_rows"] = known

    # C3 premise
    repo_ckpt = has(repo_n, "checkpoint")
    res["controls"]["C3_repo_has_edit_checkpoints"] = bool(repo_ckpt)
    res["controls"]["C3_repo_rows"] = repo_ckpt

    live_ckpt = has(live_n, "checkpoint")
    live_mcpl = has(live_n, "liveness")
    repo_mcpl = has(repo_n, "liveness")

    res["verdict"]["edit_checkpoints_live"] = bool(live_ckpt)
    res["verdict"]["edit_checkpoints_repo"] = bool(repo_ckpt)
    res["verdict"]["mcp_liveness_live"] = bool(live_mcpl)
    res["verdict"]["mcp_liveness_repo"] = bool(repo_mcpl)

    # set difference on names, both directions
    ls = {n for (_e, n, _c) in live_n}
    rs = {n for (_e, n, _c) in repo_n}
    res["repo_only_checks"] = sorted(rs - ls)
    res["live_only_checks"] = sorted(ls - rs)

    # settings.json: count entries WITHOUT printing any value (file holds live creds)
    try:
        st = load(LIVE_SETTINGS)
        hooks = st.get("hooks") or {}
        ents = 0
        evs = {}
        for ev, arr in hooks.items():
            c = 0
            for matcher in arr or []:
                c += len(matcher.get("hooks") or [])
            evs[ev] = c
            ents += c
        res["live_settings_entries"] = ents
        res["live_settings_events"] = evs
        # does settings.json mention checkpoint anywhere in a command string?
        blob = json.dumps(hooks)
        res["verdict"]["settings_mentions_checkpoint"] = "checkpoint" in blob.lower()
    except Exception as e:  # noqa: BLE001
        res["live_settings_entries"] = f"ERROR {type(e).__name__}"

    # consumer freshness
    idx = None
    for p in CKPT_INDEX_CANDIDATES:
        if os.path.exists(p):
            idx = p
            break
    if idx:
        with open(idx, encoding="utf-8", newline="") as f:
            lines = [ln for ln in f.read().splitlines() if ln.strip()]
        res["ckpt_index_path"] = idx
        res["ckpt_index_records"] = len(lines)
        try:
            last = json.loads(lines[-1])
            res["ckpt_index_last_ts"] = (
                last.get("ts") or last.get("time") or last.get("timestamp")
            )
            res["ckpt_index_last_keys"] = sorted(last.keys())
        except Exception as e:  # noqa: BLE001
            res["ckpt_index_last_ts"] = f"UNPARSED {type(e).__name__}"
    else:
        res["ckpt_index_path"] = None
        res["ckpt_index_records"] = 0

    print(json.dumps(res, indent=2, default=str))
    ok = (
        res["controls"]["C1_live_count_plausible"]
        and res["controls"]["C2_known_present_found"]
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
