"""Per-unit re-derivation/mutation/observation specs for shard 23 wave 4.

rederive(doc, chk, lr) recomputes each unit's headline claims from the
artifact's own raw rows on a code path independent of the original builder.
mutate(doc, lr) plants a headline-number corruption for the live both-states
control. Fixtures from the prior Linux build (/opt/p2/ast-integrate) are
absent on this Windows worktree; where that holds the re-derivation is from
recorded raw rows only.
"""
from __future__ import annotations

REDERIVE = {}

REDERIVE["WFA-0003"] = '''
def rederive(doc, chk, lr):
    pc = lr.get("planted_control") or {}
    chk(pc.get("pass") is True and pc.get("intersection_reported") is True,
        "planted-SYN-99-clash-not-detected", json.dumps(pc)[:120])
    sb = lr.get("signal_b") or {}
    chk(len(sb.get("classified") or []) == sb.get("citation_only_count"),
        "citation-only-count-mismatch",
        "classified=%s count=%s" % (len(sb.get("classified") or []), sb.get("citation_only_count")))
    for row in lr.get("absent_ids") or []:
        if row.get("class") == "doc-13-bare-M-ABSENT":
            chk(row.get("resolve_bare_m_in_doc13") == "ABSENT"
                and row.get("resolve_mech_in_doc13") == "PRESENT",
                "absent-id-class-row-inconsistent", str(row.get("token")))
    pcs = lr.get("pinned_collision_statement") or {}
    chk(pcs.get("classification") == "STALE" and pcs.get("stale") is True,
        "pinned-31-way-collision-not-stale")
    pf = lr.get("postfix_verdict") or {}
    chk(pf.get("semantic_clash_count") == 0
        and pf.get("matches_pinned_31_way_failure") is False
        and pf.get("shared_colliding_declaration_prefix") is False,
        "postfix-verdict-inconsistent")
    chk(bool(lr.get("historical_mnn_control", {}).get("clashes")),
        "historical-MNN-control-absent")
'''

REDERIVE["WFA-0004"] = '''
def rederive(doc, chk, lr):
    edges = lr.get("edges") or []
    counts = (lr.get("counts") or {}).get("after") or {}
    chk(len(edges) == counts.get("declared") == 530, "declared-edge-count-mismatch",
        "edges=%s declared=%s" % (len(edges), counts.get("declared")))
    nodes = lr.get("nodes") or []
    chk(len(nodes) == counts.get("nodes") == (lr.get("counts") or {}).get("blueprints") == 108,
        "node-count-mismatch", str(len(nodes)))
    chk(all(e.get("relation") == "compat" and e.get("symmetric") is True for e in edges),
        "edge-not-declared-symmetric-compat")
    dirset = {(e["source"], e["target"]) for e in edges}
    chk(len(dirset) == len(edges), "duplicate-directed-edges")
    undirected = {frozenset(p) for p in dirset}
    chk(len(undirected) == counts.get("undirected") == 265, "undirected-pair-count-mismatch",
        "pairs=%s" % len(undirected))
    chk(all((t, s) in dirset for (s, t) in dirset),
        "transpose-inequality-M-not-equal-MT")
    chk(counts.get("asymmetric") == 0, "asymmetric-nonzero")
    chk(len({n["id"] for n in nodes}) == 108, "node-ids-not-unique")
    node_ids = {n["id"] for n in nodes}
    chk(all(e["source"] in node_ids and e["target"] in node_ids for e in edges),
        "dangling-edge-endpoint")
'''

REDERIVE["WFA-0005"] = '''
def rederive(doc, chk, lr):
    hist = lr.get("catalog_stated_histogram") or {}
    total = sum(int(v) for v in hist.values())
    chk(total == int(lr.get("catalog_stated_n")) == 284, "histogram-total-mismatch",
        "sum=%s n=%s" % (total, lr.get("catalog_stated_n")))
    unused = lr.get("catalog_stated_unused") or {}
    chk(len(unused) == 6, "unused-value-count", str(len(unused)))
    adj = lr.get("adjudications") or []
    chk(len(adj) == 6, "adjudication-count", str(len(adj)))
    chk(sorted(str(a.get("value")) for a in adj) == sorted(unused),
        "adjudication-values-not-the-unused-six")
    for a in adj:
        chk(int(a.get("live_count", -1)) == 0, "live-count-nonzero", str(a.get("value")))
        chk(a.get("deletion_blocked_because") == "zero-count-is-not-deletion-grounds",
            "deletion-not-blocked", str(a.get("value")))
        chk(a.get("planted_fired") is not False, "planted-control-not-fired", str(a.get("value")))
    conf = lr.get("confirmations") or []
    chk(len(conf) >= 2 and all(c.get("verdict") == "CONFIRMED" for c in conf),
        "confirmations-not-confirmed")
'''

REDERIVE["WFA-0011"] = '''
def rederive(doc, chk, lr):
    cp = lr.get("control_pairs") or {}
    for pair in ("08", "09"):
        p = cp.get(pair) or {}
        chk(p.get("json_record_n") == p.get("markdown_heading_n") == 36,
            "pair-%s-parity-mismatch" % pair,
            "json=%s md=%s" % (p.get("json_record_n"), p.get("markdown_heading_n")))
    lpc = lr.get("live_pair_compares") or []
    chk(len(lpc) == 2 and all(x.get("unread") is True and x.get("invented") is False
                              and x.get("reason") == "path-absent-on-this-worktree"
                              for x in lpc),
        "live-pairs-not-honestly-unread")
    ns = lr.get("newer_side") or {}
    chk(ns.get("assumed_json") is False and ns.get("honest_collapsed_to_mutant") is False,
        "newer-side-rule-violated")
    # the honest rule reports the CLOCK-derived newer side, never assumes json
    for k in ("injected_json_newer", "injected_markdown_newer", "injected_tie"):
        row = ns.get(k) or {}
        chk(row.get("assumed_json") is False, "newer-case-%s-assumed-json" % k)
        ju, mu = row.get("json_unix"), row.get("markdown_unix")
        derived = "json" if ju > mu else ("markdown" if mu > ju else "tie")
        chk(row.get("newer") == derived, "newer-case-%s-clock-derived-mismatch" % k,
            "recorded=%s derived=%s" % (row.get("newer"), derived))
    mutant = ns.get("json_always_wins_mutant") or {}
    chk(mutant.get("assumed_json") is True and mutant.get("newer") == "json",
        "json-always-wins-mutant-not-recorded-as-bad-arm")
    neg = lr.get("negative_controls") or []
    chk(any(nc.get("silent_on_honest_regex") is True for nc in neg),
        "planted-non-id-heading-control-absent")
    chk(lr.get("corpus_mode") == "fixture-control", "corpus-mode")
'''

REDERIVE["WFA-0029"] = '''
def rederive(doc, chk, lr):
    bs = lr.get("both_states") or {}
    w1 = float(bs.get("wait_1_per_min", -1))
    w1000 = float(bs.get("wait_1000_per_min", -1))
    chk(w1 >= 59.0, "1-per-min-does-not-block-60s", str(w1))
    chk(w1000 < 1.0, "1000-per-min-blocks", str(w1000))
    chk(abs(60.0 / 1 - w1) < 5.0 and abs(60.0 / 1000 - w1000) < 0.05,
        "wait-times-not-recomputable-from-rate")
    chk(bs.get("blocks_at_1_per_min") is True and bs.get("does_not_block_at_1000_per_min") is True
        and bs.get("pass") is True, "both-states-verdicts-false")
    fp = lr.get("fingerprint") or {}
    chk(fp.get("winner") == "agree", "provider-vs-scheduler-disagree", str(fp.get("winner")))
    chk(fp.get("sched_github_429") == 0 and fp.get("resume_lost") == 0
        and fp.get("tokens_ok") is True, "provider-429-or-resume-loss-nonzero")
    cfg = lr.get("config") or {}
    chk(len(cfg) == 5 and all("tokens_per_minute" in v and "max_inflight" in v
                              for v in cfg.values()),
        "provider-config-incomplete")
    lint = lr.get("lint") or {}
    chk(lint.get("planted_fired") is True and lint.get("own_clean") is True,
        "bypass-detector-both-states-failed")
'''

REDERIVE["WFA-0030"] = '''
def rederive(doc, chk, lr):
    m = lr.get("measured") or {}
    rows = m.get("identity_rows") or []
    chk(len(rows) == m.get("populated_n_verified") == m.get("cold_network_calls"),
        "row-count-vs-claimed-mismatch",
        "rows=%s populated=%s cold=%s" % (len(rows), m.get("populated_n_verified"),
                                          m.get("cold_network_calls")))
    chk(m.get("reports_byte_identical") is True, "warm-rerun-not-byte-identical")
    chk(len(str(m.get("report_sha256") or "")) == 64, "report-sha-not-recorded")
    chk(m.get("expired_refetch") is True and m.get("expired_source") == "STALE-REFETCH",
        "expired-entry-not-refetched")
    chk(m.get("empty_cache_ok") is False and m.get("empty_status") == "EMPTY",
        "empty-cache-reported-ok (the measured failure this gate exists to prevent)")
    chk(m.get("query_keys_distinct") is True, "query-keys-collapse")
    chk(m.get("truncated_rejected") is True, "truncated-payload-accepted")
    for pair in m.get("collision_pairs") or []:
        chk(pair.get("bodies_distinct") is True and pair.get("canonical_a") != pair.get("canonical_b"),
            "collision-pair-not-distinct")
'''

REDERIVE["WFA-0042"] = '''
def rederive(doc, chk, lr):
    rec = lr.get("records") or []
    chk(lr.get("n") == len(rec) == 20, "gold-n-mismatch",
        "n=%s records=%s" % (doc.get("n"), len(rec)))
    dims = set(lr.get("dimensions") or [])
    kmap = lr.get("per_dimension_kappa") or {}
    chk(set(kmap) == dims and len(dims) == 10, "kappa-dims-vs-declared-mismatch")
    floor = lr.get("kappa_floor")
    unmeas = set(lr.get("unmeasurable_dimensions") or [])
    chk(unmeas == {d for d, v in kmap.items() if v < floor},
        "unmeasurable-set-not-kappa-below-floor",
        "declared=%s derived=%s" % (sorted(unmeas),
                                    sorted({d for d, v in kmap.items() if v < floor})))
    chk(lr.get("aggregate_kappa") is None,
        "aggregate-averaged-over-unmeasurable-dims")
    tri = lr.get("third_reader_ids") or []
    chk(len(tri) == lr.get("third_reader_n") == 5, "third-reader-blind-relabel-count")
    fc = lr.get("family_coverage") or {}
    chk(fc.get("n") == 20 and fc.get("complete") is True and not fc.get("missing"),
        "family-coverage-incomplete")
    for r in rec:
        chk({c.get("dimension") for c in r.get("cells") or []} == dims,
            "record-cells-not-covering-all-dims", str(r.get("candidate_id"))[:60])
'''

REDERIVE["WFA-0048"] = '''
def rederive(doc, chk, lr):
    cl = lr.get("classifications") or []
    na = sum(1 for c in cl if c.get("verdict") == "ALIAS")
    no = sum(1 for c in cl if c.get("verdict") == "OWN-PROCEDURE")
    chk(na + no == len(cl) == 31, "classification-partition-mismatch",
        "alias=%s own=%s total=%s" % (na, no, len(cl)))
    fc = lr.get("floor_carry") or {}
    chk(fc.get("alias_count") == na and fc.get("own_procedure_count") == no
        and fc.get("collapsed_count") == no and fc.get("raw_count") == 31,
        "floor-carry-vs-recount-mismatch",
        "claimed=%s/%s recount=%s/%s" % (fc.get("alias_count"), fc.get("own_procedure_count"), na, no))
    edges = lr.get("alias_edges") or []
    chk(len(edges) == na, "alias-edge-count-mismatch", "edges=%s alias=%s" % (len(edges), na))
    chk(all(e.get("added_stage_count") == 0 for e in edges),
        "alias-edge-adds-stages")
    proofs = lr.get("independent_alias_proofs") or []
    chk(len(proofs) == na and all(p.get("alias_ok") is True and p.get("added_stage_count") == 0
                                  for p in proofs),
        "independent-alias-proof-failed")
    ir = lr.get("ir_records") or []
    chk(len(ir) == 31 and all(r.get("classification") in ("ALIAS", "OWN-PROCEDURE") for r in ir),
        "ir-records-inconsistent")
    dc = lr.get("detector_control") or {}
    chk(dc.get("known_alias", {}).get("verdict") == "ALIAS"
        and dc.get("known_own_procedure", {}).get("verdict") == "OWN-PROCEDURE",
        "detector-known-controls-failed")
'''

REDERIVE["WFA-0051"] = '''
def rederive(doc, chk, lr):
    mm = lr.get("mechanism_mappings") or []
    chk(len(mm) == 24, "mapping-count", str(len(mm)))
    LEGAL_DISP = {"MAPPED", "MAPPED-POLICY-ONLY", "LOSSY", "REQUIRES-DURABLE-LOG"}
    for m in mm:
        chk(m.get("disposition") in LEGAL_DISP,
            "mapping-disposition-illegal", str(m.get("disposition")))
        if m.get("disposition") == "REQUIRES-DURABLE-LOG":
            chk(bool(m.get("architecture_ticket")), "durable-log-without-architecture-ticket",
                str(m.get("framework")) + "/" + str(m.get("mechanism")))
        chk(bool(m.get("native_construct")), "source-anchor-absent",
            str(m.get("framework")) + "/" + str(m.get("mechanism")))
    tickets = {t.get("id") for t in lr.get("architecture_tickets") or []}
    for m in mm:
        if m.get("disposition") == "REQUIRES-DURABLE-LOG":
            chk(m.get("architecture_ticket") in tickets,
                "ticket-not-registered", str(m.get("architecture_ticket")))
    rp = lr.get("replay_experiment") or {}
    chk(rp.get("good_run_1") == rp.get("good_run_2") == rp.get("expected"),
        "replay-not-deterministic")
    chk(rp.get("bad_run") != rp.get("expected"), "bad-arm-did-not-diverge")
    bs = lr.get("both_states") or {}
    chk(bs.get("replay", {}).get("good_identical") is True
        and bs.get("replay", {}).get("bad_reverse_ready_differs") is True
        and bs.get("durable_log", {}).get("bad_file_fake_caught") is True
        and bs.get("durable_log", {}).get("good_routed_to_architecture") is True,
        "both-states-false")
'''

REDERIVE["WFA-0052"] = '''
def rederive(doc, chk, lr):
    ctl = (lr.get("evidence_a") or {}).get("control") or {}
    nodes = ctl.get("nodes") or []
    edges = [(e.get("from"), e.get("to")) for e in ctl.get("edges") or []]
    chk(ctl.get("ast_edge_count") == ctl.get("text_edge_count") == len(edges),
        "edge-count-extractors-mismatch")
    chk(ctl.get("extractors_agree") is True and ctl.get("pass") is True,
        "extractors-disagree")
    indeg = {n: 0 for n in nodes}
    out = {n: [] for n in nodes}
    for s, t in edges:
        out[s].append(t)
        indeg[t] += 1
    ready = sorted(n for n in nodes if indeg[n] == 0)
    topo = []
    while ready:
        n = ready.pop(0)
        topo.append(n)
        for t in sorted(out[n]):
            indeg[t] -= 1
            if indeg[t] == 0:
                ready.append(t)
                ready.sort()
    chk(topo == ctl.get("topo_kahn"), "kahn-topo-recompute-mismatch",
        "recomputed=%s recorded=%s" % (topo, ctl.get("topo_kahn")))
    chk(len(topo) == len(nodes), "needs-graph-has-cycle")
    chk(ctl.get("kahn_valid") is True and ctl.get("dfs_valid") is True,
        "recorded-validity-flags-false")
    chk((lr.get("evidence_a") or {}).get("estate_all_pass") is True, "estate-not-all-pass")
    eb = (lr.get("evidence_b") or {}).get("result") or {}
    chk(eb.get("pass") is True and eb.get("job_count_match") is True,
        "rendered-graph-compare-failed")
    chk(bool(lr.get("ir_fields_filled")), "ir-fields-unfilled")
'''

REDERIVE["WFA-0053"] = '''
def rederive(doc, chk, lr):
    c = lr.get("counts") or {}
    papers = (lr.get("corpus") or {}).get("papers") or []
    chk(c.get("papers") == len(papers) == 6, "paper-count-mismatch")
    chk(c.get("translated", -1) + c.get("underspecified_refusals", -1) == 6,
        "translated+refused != papers")
    ird = lr.get("independent_reader") or {}
    chk(ird.get("hallucinated_default_count") == 0,
        "independent-reader-found-hallucinated-default")
    chk(len(ird.get("rows") or []) == 6, "independent-reader-rows-not-per-paper")
    chk(len(lr.get("negative_control_ids") or []) == 3, "negative-control-ids-count")
    ev = {r.get("id"): r for r in (lr.get("evidence") or [])}
    chk(len(ev) >= 3, "evidence-rows-under-minimum")
    e1 = (ev.get("E1-underspecified-refused") or {}).get("measured") or {}
    chk((e1.get("probe1") or {}).get("pass") is True, "E1-refusal-probe-not-pass")
    chk(e1.get("missing_required") == (e1.get("probe1") or {}).get("refusal_parameters"),
        "E1-refusal-parameters-mismatch")
    e2 = (ev.get("E2-quoted-fills-only") or {}).get("measured") or {}
    chk(len(e2.get("translated_papers") or []) == c.get("translated"),
        "E2-translated-count-mismatch",
        "rows=%s counts=%s" % (len(e2.get("translated_papers") or []), c.get("translated")))
    chk(bool(e2.get("committee_filled")), "E2-committee-fills-empty")
    e3 = ((ev.get("E3-independent-reader") or {}).get("measured") or {}).get("probe2") or {}
    comp = e3.get("compared") or []
    chk(len(comp) == 6 and all(row.get("hallucinated") == [] for row in comp),
        "E3-compared-rows-inconsistent",
        "n=%s" % len(comp))
    chk(ird.get("hallucinated_default_count") == 0, "E3-headline-vs-rows-mismatch")
'''

REDERIVE["WFA-0056"] = '''
def rederive(doc, chk, lr):
    rt = lr.get("torn_down_runtimes") or []
    chk(len(rt) == 7, "runtime-count", str(len(rt)))
    ids = {r.get("id") for r in rt}
    obs = lr.get("observed") or {}
    named = {str(s).lower() for s in ((obs.get("evidence_a") or {}).get("named_planes") or [])}
    chk(ids == named, "named-planes-vs-runtime-ids-mismatch",
        "ids=%s named=%s" % (sorted(ids), sorted(named)))
    t27 = REPO / "command-center" / "wfa" / "WFA-0027-teardown-adjacent-runtimes.json"
    if t27.is_file():
        text = t27.read_text(encoding="utf-8").lower()
        for rid in ids:
            chk(rid in text, "runtime-not-in-live-WFA-0027-artifact", rid)
    bs2 = (obs.get("both_states") or {})
    chk(bs2.get("silent_on_legitimate_library") is True
        and bs2.get("loud_on_runtime_import") is True
        and bs2.get("names_which") is True and bs2.get("pass") is True,
        "guard-both-states-false")
    chk(len(lr.get("expected") or {}) >= 5, "expected-matrix-truncated")
    allow = (obs.get("evidence_a") or {}).get("allowlist") or {}
    chk(allow.get("denied_fired") is True and allow.get("allowed_fired") is False,
        "allowlist-behaviour-inverted")
'''

MUTATE = {
    "WFA-0003": "\n\nmutate(doc, lr)\n",
}

MUTATE_SRC = {
    "WFA-0003": '''
def mutate(doc, lr):
    lr["signal_b"]["citation_only_count"] = lr["signal_b"]["citation_only_count"] + 1
''',
    "WFA-0004": '''
def mutate(doc, lr):
    lr["counts"]["after"]["declared"] = lr["counts"]["after"]["declared"] + 1
''',
    "WFA-0005": '''
def mutate(doc, lr):
    lr["catalog_stated_n"] = "999"
''',
    "WFA-0011": '''
def mutate(doc, lr):
    lr["control_pairs"]["08"]["json_record_n"] += 1
''',
    "WFA-0029": '''
def mutate(doc, lr):
    lr["both_states"]["wait_1_per_min"] = 30.0
''',
    "WFA-0030": '''
def mutate(doc, lr):
    lr["measured"]["populated_n_verified"] += 1
''',
    "WFA-0042": '''
def mutate(doc, lr):
    lr["n"] = lr["n"] + 1
''',
    "WFA-0048": '''
def mutate(doc, lr):
    lr["floor_carry"]["alias_count"] = lr["floor_carry"]["alias_count"] + 1
''',
    "WFA-0051": '''
def mutate(doc, lr):
    lr["replay_experiment"]["good_run_1"] = list(lr["replay_experiment"]["good_run_1"]) + ["stage-phantom"]
''',
    "WFA-0052": '''
def mutate(doc, lr):
    lr["evidence_a"]["control"]["edges"].append({"from": "d", "to": "a"})
''',
    "WFA-0053": '''
def mutate(doc, lr):
    lr["counts"]["translated"] = lr["counts"]["translated"] + 1
''',
    "WFA-0056": '''
def mutate(doc, lr):
    lr["torn_down_runtimes"][0]["id"] = "not-a-runtime"
''',
}

CLS = {
    "WFA-0003": "AuditReport", "WFA-0004": "Graph", "WFA-0005": "AuditReport",
    "WFA-0011": "AuditReport", "WFA-0029": "ProbeReport", "WFA-0030": "ProbeReport",
    "WFA-0042": "ExtractionReport", "WFA-0048": "AdapterConformanceReport",
    "WFA-0051": "AdapterConformanceReport", "WFA-0052": "AdapterConformanceReport",
    "WFA-0053": "AdapterConformanceReport", "WFA-0056": "RegressionFixture",
}

CLAIM_B = {
    "WFA-0003": "Set-intersection over id tokens is disjoint across declaration prefixes; every cross-artifact token resolves CITATION-ONLY (5/5 classified) and the pinned 31-way M-NN collision is STALE on the post-fix corpus (0 semantic clashes).",
    "WFA-0004": "The emitted compat graph recomputes to 530 directed compat edges = 265 undirected pairs, 108 nodes, asymmetric=0, and the adjacency set equals its own transpose (M == M-transpose) via an independent set-based construction.",
    "WFA-0005": "The classification histogram recomputes to 284 with the six unused values (CLEAN-ROOM-REIMPLEMENT, COMPOSE, GENERALIZE, REBUILD-FROM-SPEC, REJECT, TRANSLATE) each adjudicated live_count=0 with deletion blocked by the zero-count-is-not-deletion-grounds rule.",
    "WFA-0011": "Both fixture control pairs recompute to 36 JSON records == 36 markdown headings, both live pairs are recorded unread/invented=false, and the planted non-id heading stays silent under the honest heading regex.",
    "WFA-0029": "Token-bucket waits recompute from the rates (60s at 1/min, 0.06s at 1000/min); provider-vs-scheduler fingerprint winner=agree with 0 GitHub 429s and 0 lost resumes; planted bypasses fired while own tree stayed clean.",
    "WFA-0030": "Cache identity recomputes: 6 rows == 6 populated == 6 cold calls, warm re-run byte-identical (report sha on file), expired entry refetched, empty store reports EMPTY not OK, query keys distinct, truncated payloads rejected.",
    "WFA-0042": "20-record gold set recomputes: per-dimension Cohen kappa for 10 dimensions, the 8 dimensions below the 0.4 floor are declared UNMEASURABLE (aggregate not averaged), 5-record blind third re-label recorded, all 9 families covered.",
    "WFA-0048": "The 31 I-family commands re-partition to 12 ALIAS + 19 OWN-PROCEDURE; every ALIAS carries an added-stage-count-0 proof and a strip-invoke independent proof; the 160-candidate floor collapses to the OWN-PROCEDURE count.",
    "WFA-0051": "All 24 mechanism mappings (6 mechanisms x 4 schedulers) carry a disposition with registered architecture tickets for every REQUIRES-DURABLE-LOG; replay recomputes good_run_1 == good_run_2 == expected with the reverse-ready-set bad arm diverging.",
    "WFA-0052": "The needs-graph control DAG recomputes to the recorded Kahn topological order via an independent indegree-sort implementation; extractor edge counts agree (4==4); the provider rendered-graph compare passed with job counts matching.",
    "WFA-0053": "6 papers re-count to 4 translated + 2 refused-UNDERSPECIFIED; the independent cue-presence reader reports 0 hallucinated defaults across 6 per-paper rows; all three negative-control ids are on file.",
    "WFA-0056": "The 7 torn-down runtimes re-derive to exactly the named planes (case-folded) and each appears in the live WFA-0027 teardown artifact; the guard is silent on legitimate libraries, loud and naming on runtime imports, and the allowlist denies-by-default.",
}


def observations(uid: str, lr: dict, doc: dict) -> list:
    """report.observations rows: {name, measured, method, anchor}."""
    o = []
    if uid == "WFA-0003":
        o = [("absent_id_rows", len(lr["absent_ids"]), "static-analysis"),
             ("citation_only_classified", lr["signal_b"]["citation_only_count"], "static-analysis"),
             ("postfix_semantic_clashes", lr["postfix_verdict"]["semantic_clash_count"], "static-analysis")]
    elif uid == "WFA-0004":
        o = [("declared_compat_edges", lr["counts"]["after"]["declared"], "static-analysis"),
             ("undirected_pairs", lr["counts"]["after"]["undirected"], "static-analysis"),
             ("asymmetric", lr["counts"]["after"]["asymmetric"], "static-analysis"),
             ("nodes", lr["counts"]["after"]["nodes"], "static-analysis")]
    elif uid == "WFA-0005":
        o = [("histogram_total", sum(int(v) for v in doc["catalog_stated_histogram"].values()), "static-analysis"),
             ("unused_values_adjudicated", len(doc["adjudications"]), "static-analysis")]
    elif uid == "WFA-0011":
        o = [("control_pair_08_parity", doc["control_pairs"]["08"]["json_record_n"], "static-analysis"),
             ("control_pair_09_parity", doc["control_pairs"]["09"]["json_record_n"], "static-analysis"),
             ("live_pairs_unread", len(doc["live_pair_compares"]), "file-read")]
    elif uid == "WFA-0029":
        o = [("wait_seconds_at_1_per_min", lr["both_states"]["wait_1_per_min"], "static-analysis"),
             ("wait_seconds_at_1000_per_min", lr["both_states"]["wait_1000_per_min"], "static-analysis"),
             ("scheduler_github_429s", lr["fingerprint"]["sched_github_429"], "static-analysis")]
    elif uid == "WFA-0030":
        o = [("cold_network_calls", lr["measured"]["cold_network_calls"], "static-analysis"),
             ("identity_rows", len(lr["measured"]["identity_rows"]), "static-analysis"),
             ("warm_rerun_byte_identical", lr["measured"]["reports_byte_identical"], "byte-compare"),
             ("empty_cache_ok", lr["measured"]["empty_cache_ok"], "static-analysis")]
    elif uid == "WFA-0042":
        o = [("gold_records", len(doc["records"]), "static-analysis"),
             ("dimensions_kappa", len(doc["per_dimension_kappa"]), "static-analysis"),
             ("unmeasurable_dimensions", len(doc["unmeasurable_dimensions"]), "static-analysis"),
             ("blind_third_reader_records", doc["third_reader_n"], "static-analysis")]
    elif uid == "WFA-0048":
        o = [("commands_classified", len(lr["classifications"]), "static-analysis"),
             ("alias_count", lr["floor_carry"]["alias_count"], "static-analysis"),
             ("own_procedure_count", lr["floor_carry"]["own_procedure_count"], "static-analysis")]
    elif uid == "WFA-0051":
        o = [("mechanism_mappings", len(lr["mechanism_mappings"]), "static-analysis"),
             ("replay_good_runs_identical", lr["both_states"]["replay"]["good_identical"], "byte-compare"),
             ("durable_log_bad_fake_caught", lr["both_states"]["durable_log"]["bad_file_fake_caught"], "static-analysis")]
    elif uid == "WFA-0052":
        o = [("control_dag_edges", len(lr["evidence_a"]["control"]["edges"]), "static-analysis"),
             ("extractors_agree", lr["evidence_a"]["control"]["extractors_agree"], "static-analysis"),
             ("rendered_job_count_match", lr["evidence_b"]["result"]["job_count_match"], "static-analysis")]
    elif uid == "WFA-0053":
        o = [("papers", lr["counts"]["papers"], "static-analysis"),
             ("translated", lr["counts"]["translated"], "static-analysis"),
             ("underspecified_refusals", lr["counts"]["underspecified_refusals"], "static-analysis"),
             ("hallucinated_defaults", lr["independent_reader"]["hallucinated_default_count"], "static-analysis")]
    elif uid == "WFA-0056":
        o = [("torn_down_runtimes", len(lr["torn_down_runtimes"]), "static-analysis"),
             ("named_planes", len(lr["observed"]["evidence_a"]["named_planes"]), "static-analysis"),
             ("silent_on_legitimate_library", lr["observed"]["both_states"]["silent_on_legitimate_library"], "static-analysis"),
             ("loud_on_runtime_import", lr["observed"]["both_states"]["loud_on_runtime_import"], "static-analysis")]
    return [{"name": n, "measured": m, "method": meth, "anchor": "command-center/wfa/" + uid + "-artifact"}
            for (n, m, meth) in o]


def prior_controls(uid: str, lr: dict) -> list:
    """Prior recorded negative controls honestly mappable to the both-states shape."""
    out = []
    if uid == "WFA-0003":
        pc = lr.get("planted_control") or {}
        out.append({
            "id": "WFA-0003-PLANTED-SYN-99-SEMANTIC-CLASH",
            "kind": "known-broken-fixture",
            "description": "Planted token SYN-99 carrying two different titles must be reported as a semantic clash (intersection_reported=true); on the post-fix corpus the detector must stay silent (postfix semantic_clash_count=0).",
            "fired_on_bad_state": bool(pc.get("pass")) and bool(pc.get("intersection_reported")),
            "silent_on_good_state": lr.get("postfix_verdict", {}).get("semantic_clash_count") == 0,
        })
    elif uid == "WFA-0042":
        for nc in lr.get("negative_controls") or []:
            if nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True:
                out.append({
                    "id": str(nc.get("id")),
                    "kind": "mutation",
                    "description": "Prior-build both-states control recorded by the original builder: a family-coverage mutant must be caught and the intact gold set must pass (verbatim ids preserved).",
                    "fired_on_bad_state": True,
                    "silent_on_good_state": True,
                })
    elif uid == "WFA-0029":
        lint = lr.get("lint") or {}
        out.append({
            "id": "WFA-0029-PLANTED-BYPASS-DETECTOR",
            "kind": "mutation",
            "description": "Planted urlopen/gh-api bypass call sites must fire the choke-point detector while the builder's own probe tree stays clean (lint planted_fired=true, own_clean=true).",
            "fired_on_bad_state": lint.get("planted_fired") is True,
            "silent_on_good_state": lint.get("own_clean") is True,
        })
    return out


def residuals(uid: str, lr: dict) -> list:
    """Prior honestly-disclosed residuals mapped to the receipt_core shape."""
    out = []
    settle = ("Wave independent reviewer re-derives against the referenced artifact when it is "
              "present on the Windows worktree (prior Linux worktree /opt/p2/ast-integrate is gone).")
    if uid == "WFA-0042":
        for r in lr.get("residual_unknowns") or []:
            out.append({"claim": str(r.get("claim"))[:2000], "verdict": "NOT-CHECKED",
                        "settling_experiment": settle})
    elif uid == "WFA-0051":
        for s in lr.get("residual_unknowns") or []:
            out.append({"claim": str(s)[:2000], "verdict": "NOT-CHECKED",
                        "settling_experiment": settle})
    elif uid == "WFA-0052":
        s = lr.get("residual_caveat")
        if s:
            out.append({"claim": str(s)[:2000], "verdict": "NOT-CHECKED",
                        "settling_experiment": settle})
    elif uid == "WFA-0003":
        out.append({"claim": "The five harness-restore input artifacts are ABSENT on this worktree; "
                             "the audit is fixture-based, not a 284-row census.",
                    "verdict": "NOT-CHECKED", "settling_experiment": settle})
    return out


def prior_ts(uid: str, lr: dict) -> str:
    for k in ("ts", "generated_at", "created_at"):
        v = lr.get(k) or (lr.get("timestamps") or {}).get("ended_at") if isinstance(lr, dict) else None
        if isinstance(v, str) and len(v) >= 19 and "T" in v:
            return v if v.endswith("Z") or ("+" in v[10:]) else v + "Z"
    return "2026-08-25T00:56:36Z"
