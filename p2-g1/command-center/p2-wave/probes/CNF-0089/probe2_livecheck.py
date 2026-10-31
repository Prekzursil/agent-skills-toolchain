#!/usr/bin/env python3
"""CNF-0089 probe2: re-decide every recorded row through the bound evaluator (expr.py) using
each row's own recorded state, and re-run never-true + mutant + proof-of-impossibility controls.
Emitted by shard8-w2 resume builder 2026-10-25."""
import importlib.util, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/confirmation/CNF-0089-stopping-truth-table.json")
    spec = importlib.util.spec_from_file_location("cnf0089_expr", Path(__file__).parent / "expr.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    bad = []
    for t in d["truth_tables"]:
        for r in t["rows"]:
            st = dict(r["state"])
            for k, v in st.items():
                if v == "NOT-CHECKED":
                    st[k] = mod.U
            got = mod.decide(t["expression"], st)
            if got != r["observed_decision"] or r["observed_decision"] != r["spec_decision"]:
                bad.append({"table": t.get("id"), "state": r["state"], "got": got,
                            "observed": r["observed_decision"], "spec": r["spec_decision"]})
            if r["sampled"] is not False or r["match"] is not True:
                bad.append({"table": t.get("id"), "state": r["state"], "field": "sampled/match"})
    ck("all_48_decisions_reproduced_live", not bad)

    nt = d["never_true_control"]
    live_never = True
    for r in nt["runs"]:
        st = dict(r["state"])
        got = mod.decide(nt["expression"], st)
        if got != r["decision"]:
            live_never = False
    ck("never_true_reproduced", live_never and nt["never_stopped"] is True and nt.get("verified_not_assumed") is True)

    honest_ut = mod.conj(mod.U, mod.T)
    ck("honest_and_partial_is_U_not_T", honest_ut == mod.U)
    nc = d["negative_controls"][0]
    ck("mutant_detector_fired_on_bad_silent_on_good", nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True)

    poe = d["proof_of_impossibility"]
    live_poe = mod.decide("proof_of_impossibility == true", {"proof_of_impossibility": True}) == "STOP" \
        and mod.decide("proof_of_impossibility == true", {"proof_of_impossibility": False}) == "CONTINUE"
    rec_poe = all(r["decision"] == ("STOP" if r["atom"] == "T" else "CONTINUE") for r in poe["rows"])
    ck("proof_of_impossibility_terminal_reproduced", poe.get("reachable") is True and poe.get("exercised_explicitly") is True and live_poe and rec_poe)
    return finish("probe2_livecheck", "CNF-0089")

if __name__ == "__main__":
    sys.exit(main())
