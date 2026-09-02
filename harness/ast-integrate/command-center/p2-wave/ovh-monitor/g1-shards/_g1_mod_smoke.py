#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "command-center"))
sys.path.insert(0, str(REPO / "command-center" / "freeze"))
sys.path.insert(0, str(REPO / "command-center" / "confirmation"))
sys.path.insert(0, str(REPO / "command-center" / "sampling"))
sys.path.insert(0, str(REPO / "command-center" / "lib"))


def main() -> int:
    from completion.reducer import judge
    from completion.sites import SITE_FILES, load_all
    mods = load_all()
    assert len(SITE_FILES) == 7
    assert all(m.judge is judge for m in mods.values()), "judge identity"
    print("completion-ok", len(mods))

    import lib as F
    ledger = F.activate(REPO)
    print("freeze-activate", ledger.get("frozen_count"), ledger.get("schema_count"))
    gate = F.evaluate_gate(REPO)
    print("freeze-gate", gate.get("ok"), gate.get("silent_count"), gate.get("rejections"))

    import curtailed_sprt as CS
    params = CS.default_params()
    p0 = CS.CurtailedSPRT(params, severity="P0", population_n=40, stratum_id="S-P0")
    try:
        p0.try_declare_stop("ACCEPT_H0")
        print("FAIL p0 try_declare_stop")
        return 1
    except CS.CensusGuardError:
        pass
    st = CS.CurtailedSPRT(params, severity="P0", population_n=40).consume([True] * 40)
    print("sprt-p0", st.n, st.decision, st.truncated)
    bad = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    stb = bad.consume([True] * params.n_max)
    print("sprt-bad", stb.n, stb.decision, stb.truncated)
    good = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    stg = good.consume([False] * params.n_max)
    print("sprt-good", stg.n, stg.decision, stg.truncated)
    path = CS.make_continuation_path(params)
    border = CS.CurtailedSPRT(params, severity="P2", population_n=10**6)
    stc = border.consume(path)
    print("sprt-border", stc.n, stc.truncated, stc.decision)

    from expansion_proof import both_states, run_all
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = both_states(REPO, Path(td) / "both")
        print("expand-both", r["pass"], r["fire"]["decision"], r["silent"]["decision"], len(r["fire"]["created_unit_ids"]))
        proofs = run_all(REPO, Path(td) / "all")
        print("expand-all", proofs["all_pass"], {k: proofs[k].get("pass") for k in proofs if isinstance(proofs[k], dict)})

    import test_registry_bind as bind
    u = bind.bind_row("t", "c", "CC-0014")
    print("bind-unproven", u["status"], bind.coverage_summary([u]))

    from cnf0136.scheduler import Clock, ConfirmationQueueScheduler
    try:
        ConfirmationQueueScheduler(arrival_rate_hz=0)
        print("FAIL arrival 0")
        return 1
    except ValueError:
        print("cnf-arrival-required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
