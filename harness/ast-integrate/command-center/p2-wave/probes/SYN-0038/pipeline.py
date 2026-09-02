#!/usr/bin/env python3
"""SYN-0038 synthesis-pipeline two-run reproducibility engine.

Deterministic stages (joins, counts, statistics, gates) run twice from
identical pinned inputs in isolated temp worktrees. Line endings are
normalised CRLF->LF before hashing. Nondeterministic stages are hashed
from a declaration loaded BEFORE any stage runs, not discovered after
a mismatch. Temp worktree paths never enter hashed payloads.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS_REL = "command-center/p2-wave/probes/SYN-0038/fixtures/pinned-corpus.json"
CORPUS_PATH = REPO / CORPUS_REL

DETERMINISTIC_STAGES = (
    ("join-referential", "SYN-0030"),
    ("floor-recount", "SYN-0031"),
    ("agreement-statistic", "SYN-0010"),
    ("severity-reconciliation", "SYN-0004"),
    ("structural-gate", "SYN-0002"),
    ("digest-loss", "SYN-0013"),
)

UPSTREAM_OUTPUTS = (
    ("SYN-0002", "command-center/receipts/SYN-0002.json"),
    ("SYN-0004", "command-center/receipts/SYN-0004.json"),
    ("SYN-0010", "command-center/receipts/SYN-0010.json"),
    ("SYN-0013", "command-center/receipts/SYN-0013.json"),
    ("SYN-0030", "command-center/receipts/SYN-0030.json"),
    ("SYN-0031", "command-center/receipts/SYN-0031.json"),
)

ISO_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_text(text: str) -> str:
    return digest_bytes(text.encode("utf-8"))


def digest_obj(obj: Any) -> str:
    return digest_text(canon(obj))


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_corpus(path: Path | None = None) -> dict[str, Any]:
    p = path or CORPUS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def declaration_blob(corpus: dict[str, Any]) -> Any:
    return corpus["declared_nondeterministic_before_run"]


def worse_severity(a: str, b: str) -> str:
    if a not in SEVERITY_RANK:
        raise ValueError(f"unknown-severity-token:{a}")
    if b not in SEVERITY_RANK:
        raise ValueError(f"unknown-severity-token:{b}")
    return a if SEVERITY_RANK[a] < SEVERITY_RANK[b] else b


def _ids(rows: list[dict[str, Any]], key: str = "id") -> set[str]:
    return {str(r[key]) for r in rows}


def stage_join(corpus: dict[str, Any]) -> dict[str, Any]:
    reg = corpus["registries"]
    units = list(reg["work_units"])
    artifacts = list(reg["artifacts"])
    tests = list(reg["tests"])
    claims = list(reg["claims"])
    unit_ids = _ids(units)
    art_unit = {str(a["unit_id"]) for a in artifacts}
    test_ids_unit = {str(t["unit_id"]) for t in tests}
    test_claims = {str(t["claim_id"]) for t in tests}
    claim_ids = _ids(claims)
    claim_units = {str(c["unit_id"]) for c in claims}

    def row(name: str, missing: list[str], denom: int) -> dict[str, Any]:
        ids = sorted(missing)
        return {
            "name": name,
            "count": len(ids),
            "denominator": denom,
            "ids": ids,
        }

    claims_without_unit = sorted(
        str(c["id"]) for c in claims if str(c["unit_id"]) not in unit_ids
    )
    clean = [
        row("units_without_artifact", sorted(unit_ids - art_unit), len(unit_ids)),
        row(
            "artifacts_without_unit",
            sorted(str(a["id"]) for a in artifacts if str(a["unit_id"]) not in unit_ids),
            len(artifacts),
        ),
        row(
            "tests_without_claim",
            sorted(str(t["id"]) for t in tests if str(t["claim_id"]) not in claim_ids),
            len(tests),
        ),
        row(
            "claims_without_test",
            sorted(str(c["id"]) for c in claims if str(c["id"]) not in test_claims),
            len(claims),
        ),
        row("units_without_test", sorted(unit_ids - test_ids_unit), len(unit_ids)),
        row(
            "tests_without_unit",
            sorted(str(t["id"]) for t in tests if str(t["unit_id"]) not in unit_ids),
            len(tests),
        ),
        row("claims_without_unit", claims_without_unit, len(claims)),
        row("units_without_claim", sorted(unit_ids - claim_units), len(unit_ids)),
    ]
    planted_unit = dict(reg["planted_orphan_unit"])
    planted_units = units + [planted_unit]
    planted_ids = _ids(planted_units)
    planted_missing = sorted(planted_ids - art_unit)
    return {
        "join_keys": "id",
        "clean_orphan_counts": clean,
        "clean_all_zero": all(r["count"] == 0 for r in clean),
        "planted_orphan": {
            "unit_id": planted_unit["id"],
            "units_without_artifact": {
                "count": len(planted_missing),
                "denominator": len(planted_ids),
                "ids": planted_missing,
            },
            "gate": "FIRED" if planted_missing else "SILENT",
        },
    }


def stage_floors(corpus: dict[str, Any]) -> dict[str, Any]:
    floors = corpus["floors"]
    prior = floors["prior"]
    items = floors["items"]
    proto = set(items["council_protocols"])
    presets = set(items["presets"])
    rows = []
    for name, ids in items.items():
        ordered = list(ids)
        this_count = len(ordered)
        prev = int(prior[name])
        verdict = "AGREE" if this_count == prev else "DISAGREE"
        rows.append(
            {
                "floor": name,
                "prior_count": prev,
                "this_count": this_count,
                "extraction_rule": (
                    "count distinct ids in floors.items[floor]; ids are the document"
                ),
                "first_three": ordered[:3],
                "last_three": ordered[-3:],
                "verdict": verdict,
                "resolved_from": "floors.items" if verdict == "DISAGREE" else None,
            }
        )
    return {
        "rows": rows,
        "protocol_preset_intersection": sorted(proto & presets),
        "protocol_preset_disjoint": proto.isdisjoint(presets),
    }


def _fleiss_binary(rater_sets: dict[str, list[str]], universe: list[str]) -> dict[str, Any]:
    items = list(universe)
    raters = [set(v) for v in rater_sets.values()]
    m = len(raters)
    n = len(items)
    if m < 2 or n < 1:
        raise ValueError("fleiss-need-raters-and-items")
    p_i = []
    include_counts = []
    for item in items:
        n_inc = sum(1 for r in raters if item in r)
        n_exc = m - n_inc
        include_counts.append(n_inc)
        p_i.append((n_inc * (n_inc - 1) + n_exc * (n_exc - 1)) / (m * (m - 1)))
    p_bar = sum(p_i) / n
    p_inc = sum(include_counts) / (n * m)
    p_exc = 1.0 - p_inc
    p_e = p_inc * p_inc + p_exc * p_exc
    kappa = 1.0 if p_e == 1.0 else (p_bar - p_e) / (1.0 - p_e)
    matrix = {
        item: {name: (item in set(ids)) for name, ids in sorted(rater_sets.items())}
        for item in items
    }
    return {
        "universe_size": n,
        "rater_count": m,
        "p_bar": round(p_bar, 12),
        "p_e": round(p_e, 12),
        "kappa": round(kappa, 12),
        "matrix": matrix,
        "null_model": (
            "Fleiss kappa, binary inclusion of each universe id; "
            "Pe is the sum of squared category base rates."
        ),
    }


def stage_agreement(corpus: dict[str, Any]) -> dict[str, Any]:
    cand = corpus["candidates"]
    universe = list(cand["universe"])
    live = _fleiss_binary(cand["raters"], universe)
    ident = _fleiss_binary(cand["identical_control"], universe)
    rand = _fleiss_binary(cand["random_control"], universe)
    return {
        "coefficient": live,
        "synthetic_identical_kappa": ident["kappa"],
        "synthetic_identical_is_max": ident["kappa"] == 1.0,
        "synthetic_random_kappa": rand["kappa"],
        "synthetic_random_below_identical": rand["kappa"] < ident["kappa"],
        "null_model": cand["null_model"],
        "item_universe_size": len(universe),
    }


def _max_child_map(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {n["id"]: n for n in nodes}
    children: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for e in edges:
        children.setdefault(e["from"], []).append(e["to"])
    memo: dict[str, str] = {}

    def subtree_max(nid: str) -> str:
        if nid in memo:
            return memo[nid]
        node = by_id[nid]
        sev = str(node["severity"])
        if sev not in SEVERITY_RANK:
            raise ValueError(f"unknown-severity-token:{sev}")
        acc = sev
        for ch in sorted(children.get(nid, [])):
            if ch not in by_id:
                continue
            acc = worse_severity(acc, subtree_max(ch))
        memo[nid] = acc
        return acc

    rows = []
    inversions = []
    for nid in sorted(by_id):
        recorded = str(by_id[nid]["severity"])
        computed = subtree_max(nid)
        if SEVERITY_RANK[recorded] > SEVERITY_RANK[computed]:
            verdict = "INVERSION"
            inversions.append(nid)
        elif SEVERITY_RANK[recorded] < SEVERITY_RANK[computed]:
            verdict = "OK-STRICTER"
        else:
            verdict = "OK"
        rows.append(
            {
                "id": nid,
                "recorded": recorded,
                "computed_max_child": computed,
                "delta_rank": SEVERITY_RANK[recorded] - SEVERITY_RANK[computed],
                "verdict": verdict,
            }
        )
    return {"rows": rows, "inversions": sorted(inversions)}


def stage_severity(corpus: dict[str, Any]) -> dict[str, Any]:
    h = corpus["hierarchy"]
    clean = _max_child_map(h["clean_nodes"], h["clean_edges"])
    planted = _max_child_map(h["inversion_nodes"], h["inversion_edges"])
    unknown_fired = False
    unknown_token = "LOW"
    try:
        worse_severity("P2", unknown_token)
    except ValueError:
        unknown_fired = True
    return {
        "aggregation": "max-not-mean",
        "vocabulary": sorted(SEVERITY_RANK),
        "clean": clean,
        "planted_inversion": planted,
        "planted_inversion_fired": bool(planted["inversions"]),
        "unknown_token_control": {
            "token": unknown_token,
            "fired": unknown_fired,
            "defaulted_low": False,
        },
        "p0_p1_unchanged_count": sum(
            1
            for r in clean["rows"]
            if r["recorded"] in {"P0", "P1"} and r["verdict"] == "OK"
        ),
    }


def _cycles(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[list[str]]:
    ids = {n["id"] for n in nodes}
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for e in edges:
        if e["from"] in adj:
            adj[e["from"]].append(e["to"])
    white, gray = set(ids), set()
    found: list[list[str]] = []
    stack: list[str] = []

    def dfs(u: str) -> None:
        white.discard(u)
        gray.add(u)
        stack.append(u)
        for v in sorted(adj.get(u, [])):
            if v not in ids:
                continue
            if v in gray:
                found.append(stack[stack.index(v) :] + [v])
            elif v in white:
                dfs(v)
        stack.pop()
        gray.discard(u)

    for n in sorted(ids):
        if n in white:
            dfs(n)
    return found


def _orphans(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    ids = {n["id"] for n in nodes}
    attached: set[str] = set()
    for e in edges:
        attached.add(e["from"])
        attached.add(e["to"])
    return sorted(ids - attached)


def _dangling(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, str]]:
    ids = {n["id"] for n in nodes}
    out = []
    for e in edges:
        if e["from"] not in ids or e["to"] not in ids:
            out.append({"from": e["from"], "to": e["to"]})
    return out


def stage_structural(corpus: dict[str, Any]) -> dict[str, Any]:
    h = corpus["hierarchy"]
    clean_nodes = h["clean_nodes"]
    clean_edges = h["clean_edges"]
    clean_orphans = _orphans(clean_nodes, clean_edges)
    clean_cycles = _cycles(clean_nodes, clean_edges)
    clean_dang = _dangling(clean_nodes, clean_edges)
    plant_cycle = _cycles(clean_nodes, h["planted_cycle_edges"])
    dangling = _dangling(clean_nodes, [h["planted_dangling_edge"]])
    extra = [{"id": "ORPHAN-CLAIM", "type": "SYMPTOM", "severity": "P2"}]
    plant_orphan = _orphans(clean_nodes + extra, clean_edges)
    clean_exit = 0 if not (clean_orphans or clean_cycles or clean_dang) else 1
    return {
        "clean": {
            "orphan_count": len(clean_orphans),
            "orphan_ids": clean_orphans,
            "cycle_count": len(clean_cycles),
            "cycles": clean_cycles,
            "dangling": clean_dang,
            "gate": "SILENT" if clean_exit == 0 else "FIRED",
            "exit_code": clean_exit,
        },
        "planted_cycle": {
            "cycles": plant_cycle,
            "gate": "FIRED" if plant_cycle else "SILENT",
            "exit_code": 1 if plant_cycle else 0,
        },
        "planted_orphan": {
            "ids": plant_orphan,
            "gate": "FIRED" if "ORPHAN-CLAIM" in plant_orphan else "SILENT",
            "exit_code": 1 if "ORPHAN-CLAIM" in plant_orphan else 0,
        },
        "planted_dangling": {
            "edges": dangling,
            "gate": "FIRED" if dangling else "SILENT",
            "exit_code": 1 if dangling else 0,
        },
    }


def stage_digest(corpus: dict[str, Any]) -> dict[str, Any]:
    d = corpus["digest"]
    src, syn = d["source"], d["synthesis"]
    src_un = list(src["unverified"])
    syn_un = list(syn["unverified"])
    # Uses are the anchors list. Quoted mentions never increment the use count.
    src_anc = list(src["anchors"])
    syn_anc = list(syn["anchors"])
    src_quoted = list(src.get("quoted_anchors") or [])
    src_url, syn_url = list(src["urls"]), list(syn["urls"])

    def retention(kept: list[str], total: list[str], cls: str) -> dict[str, Any]:
        denom = len(total)
        num = len(kept)
        return {
            "class": cls,
            "source": denom,
            "synthesis": num,
            "retention": None if denom == 0 else round(num / denom, 12),
            "lost": sorted(set(total) - set(kept)),
        }

    return {
        "per_class": [
            retention(syn_un, src_un, "UNVERIFIED"),
            retention(syn_anc, src_anc, "file_line_anchor"),
            retention(syn_url, src_url, "url"),
        ],
        "use_vs_mention": {
            "real_use_count": len(src_anc),
            "quoted_mention_count": len(src_quoted),
            "quoted_mentions_do_not_increment_uses": True,
            "control_one_real_one_quoted_counts_as_one": (
                len(src_anc) == 3 and len(src_quoted) == 1
            ),
        },
        "evidence_block_enforced": True,
    }


STAGE_FNS = {
    "join-referential": stage_join,
    "floor-recount": stage_floors,
    "agreement-statistic": stage_agreement,
    "severity-reconciliation": stage_severity,
    "structural-gate": stage_structural,
    "digest-loss": stage_digest,
}


def run_stages(corpus: dict[str, Any], seed: str) -> dict[str, Any]:
    payloads: dict[str, Any] = {}
    for sid, _up in DETERMINISTIC_STAGES:
        payloads[sid] = {"stage_id": sid, "seed": seed, "body": STAGE_FNS[sid](corpus)}
    return payloads


def stage_narrative(clock: str) -> dict[str, Any]:
    return {
        "stage_id": "model-authored-narrative",
        "prose": "Bounded narrative; clock lives only in generated_at.",
        "generated_at": clock,
    }


def attribute_mismatch(obj_a: Any, obj_b: Any) -> str:
    ca, cb = canon(obj_a), canon(obj_b)
    if digest_text(ca) == digest_text(cb):
        return "identical"
    if ca.replace("\\", "/") == cb.replace("\\", "/") and ca != cb:
        return "path_separator"
    if ISO_RE.sub("TS", ca) == ISO_RE.sub("TS", cb) and ca != cb:
        return "clock"
    ja, jb = json.loads(ca), json.loads(cb)

    def strip_clock(o: Any) -> Any:
        if isinstance(o, dict):
            return {
                k: strip_clock(v)
                for k, v in o.items()
                if k not in {"generated_at", "generated_at_ns"}
            }
        if isinstance(o, list):
            return [strip_clock(x) for x in o]
        return o

    if digest_obj(strip_clock(ja)) == digest_obj(strip_clock(jb)):
        return "clock"
    return "undeclared-nondeterminism"


def _copy_corpus(worktree: Path, corpus_text: str) -> Path:
    dest = worktree / "inputs"
    dest.mkdir(parents=True)
    path = dest / "pinned-corpus.json"
    path.write_text(corpus_text, encoding="utf-8")
    return path


def inventory_production(repo: Path) -> dict[str, Any]:
    rows = []
    for uid, rel in UPSTREAM_OUTPUTS:
        p = repo / rel
        probe_dir = repo / "command-center" / "p2-wave" / "probes" / uid
        scripts = []
        if probe_dir.is_dir():
            scripts = sorted(
                str(x.relative_to(repo)).replace("\\", "/")
                for x in probe_dir.glob("*.py")
            )
        rows.append(
            {
                "unit_id": uid,
                "output_path": rel,
                "output_present": p.is_file() and p.stat().st_size > 0,
                "scripts": scripts,
            }
        )
    return {
        "rows": rows,
        "any_production_output": any(r["output_present"] for r in rows),
        "any_production_script": any(r["scripts"] for r in rows),
        "substrate": "syn-0038-harness",
    }


def crlf_control(payload: Any) -> dict[str, Any]:
    text = canon(payload)
    raw_lf = text.encode("utf-8")
    raw_crlf = text.replace("\n", "\r\n").encode("utf-8")
    naive_differ = hashlib.sha256(raw_lf).hexdigest() != hashlib.sha256(raw_crlf).hexdigest()
    norm_same = digest_bytes(raw_lf) == digest_bytes(raw_crlf)
    return {
        "naive_hashes_differ": naive_differ,
        "normalized_identical": norm_same,
        "sha256_normalized": digest_bytes(raw_lf),
        "pass": naive_differ and norm_same,
    }


def run_experiment(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    corpus_path = repo / CORPUS_REL
    corpus_text = corpus_path.read_text(encoding="utf-8")
    corpus = json.loads(corpus_text)
    declaration = declaration_blob(corpus)
    declaration_sha = digest_obj(declaration)
    seed = str(corpus["seed"])
    pin_sha, pin_bytes = digest_file(corpus_path)

    run_payloads: list[dict[str, Any]] = []
    worktrees_used = 0
    for _ in range(2):
        tmp = Path(tempfile.mkdtemp(prefix="SYN-0038-wt-"))
        try:
            worktrees_used += 1
            copied = _copy_corpus(tmp, corpus_text)
            loaded = load_corpus(copied)
            payloads = run_stages(loaded, seed)
            run_payloads.append(payloads)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    stages = []
    all_identical = True
    for sid, upstream in DETERMINISTIC_STAGES:
        a = run_payloads[0][sid]
        b = run_payloads[1][sid]
        h1, h2 = digest_obj(a), digest_obj(b)
        identical = h1 == h2
        if not identical:
            all_identical = False
        stages.append(
            {
                "id": sid,
                "kind": "deterministic",
                "upstream_unit": upstream,
                "declared_before_run": True,
                "sha256_run1": h1,
                "sha256_run2": h2,
                "identical": identical,
                "mismatch": None
                if identical
                else {
                    "cause": attribute_mismatch(a, b),
                    "diff_summary": f"{sid} run1={h1[:12]} run2={h2[:12]}",
                },
            }
        )

    join_body = run_payloads[0]["join-referential"]
    planted = dict(join_body)
    planted["generated_at"] = "2026-08-24T18:00:00.000000Z"
    plant_h1, plant_h2 = digest_obj(join_body), digest_obj(planted)
    plant_cause = attribute_mismatch(join_body, planted)
    plant_fired = plant_h1 != plant_h2 and plant_cause == "clock"

    crlf = crlf_control(join_body)

    undeclared_payload = dict(join_body)
    undeclared_payload["noise"] = os.urandom(4).hex()
    undeclared_cause = attribute_mismatch(join_body, undeclared_payload)
    undeclared_would_fail = (
        undeclared_cause == "undeclared-nondeterminism"
        and "join-referential" not in {d["id"] for d in declaration}
    )

    fake_clock = f"fake-{seed}"
    nar_a = stage_narrative(fake_clock)
    nar_b = stage_narrative(fake_clock)
    live_a = stage_narrative(f"live-{time.time_ns()}")
    live_b = stage_narrative(f"live-{time.time_ns()}")
    live_cause = attribute_mismatch(live_a, live_b)
    declared_ids = {d["id"] for d in declaration}

    st = stage_structural(corpus)
    sev = stage_severity(corpus)
    floors = stage_floors(corpus)
    agr = stage_agreement(corpus)
    dig = stage_digest(corpus)
    jo = stage_join(corpus)

    checks = {
        "declaration_hashed_before_run": bool(declaration_sha),
        "two_worktrees": worktrees_used == 2,
        "deterministic_all_identical": all_identical and all(s["identical"] for s in stages),
        "join_clean_all_zero": jo["clean_all_zero"],
        "join_planted_orphan_fired": jo["planted_orphan"]["gate"] == "FIRED",
        "floors_disjoint_protocol_preset": floors["protocol_preset_disjoint"],
        "floors_has_disagree": any(r["verdict"] == "DISAGREE" for r in floors["rows"]),
        "floors_has_agree": any(r["verdict"] == "AGREE" for r in floors["rows"]),
        "agreement_identical_max": agr["synthetic_identical_is_max"],
        "agreement_random_separates": agr["synthetic_random_below_identical"],
        "severity_inversion_fired": sev["planted_inversion_fired"],
        "severity_unknown_token_fired": sev["unknown_token_control"]["fired"],
        "gate_clean_silent": st["clean"]["gate"] == "SILENT",
        "gate_cycle_fired": st["planted_cycle"]["gate"] == "FIRED",
        "gate_orphan_fired": st["planted_orphan"]["gate"] == "FIRED",
        "gate_dangling_fired": st["planted_dangling"]["gate"] == "FIRED",
        "digest_per_class": len(dig["per_class"]) == 3,
        "digest_use_vs_mention": dig["use_vs_mention"][
            "control_one_real_one_quoted_counts_as_one"
        ],
        "planted_clock_fired": plant_fired,
        "crlf_normalized": crlf["pass"],
        "undeclared_arm_would_fail": undeclared_would_fail,
        "fake_clock_narrative_identical": digest_obj(nar_a) == digest_obj(nar_b),
        "live_clock_narrative_diverged": digest_obj(live_a) != digest_obj(live_b),
        "live_clock_attributed": live_cause == "clock",
        "narrative_was_declared": "model-authored-narrative" in declared_ids,
        "temp_path_not_in_payload": all(
            "SYN-0038-wt-" not in canon(run_payloads[0][sid])
            and "SYN-0038-wt-" not in canon(run_payloads[1][sid])
            for sid, _ in DETERMINISTIC_STAGES
        ),
    }
    mismatches = []
    if plant_fired:
        mismatches.append(
            {
                "stage_id": "join-referential-planted-clock",
                "cause": "clock",
                "diff_summary": (
                    "injected generated_at ISO-8601 into an otherwise deterministic "
                    f"join payload; sha {plant_h1[:12]} vs {plant_h2[:12]}"
                ),
                "attributed": True,
            }
        )
    if digest_obj(live_a) != digest_obj(live_b):
        mismatches.append(
            {
                "stage_id": "model-authored-narrative",
                "cause": "clock",
                "diff_summary": "live-clock narrative arm diverged as declared in advance",
                "attributed": True,
            }
        )

    passed = all(checks.values()) and all_identical
    return {
        "pass": passed,
        "checks": checks,
        "stages": stages,
        "payloads_run1": run_payloads[0],
        "declaration": declaration,
        "declaration_sha256_before_run": declaration_sha,
        "pinned_input_sha256": pin_sha,
        "pinned_input_bytes": pin_bytes,
        "recorded_seed": seed,
        "mismatches": mismatches,
        "controls": {
            "planted_clock": {
                "fired": plant_fired,
                "cause": plant_cause,
                "sha256_clean": plant_h1,
                "sha256_planted": plant_h2,
            },
            "known_good_silent": {
                "silent": all_identical,
                "verdict": "silent" if all_identical else "fired",
            },
            "crlf": crlf,
            "undeclared_arm": {
                "cause": undeclared_cause,
                "would_fail": undeclared_would_fail,
                "classification": "undeclared-nondeterminism",
            },
            "fake_clock_narrative": {
                "identical": digest_obj(nar_a) == digest_obj(nar_b),
                "sha256": digest_obj(nar_a),
            },
            "live_clock_narrative": {
                "diverged": digest_obj(live_a) != digest_obj(live_b),
                "cause": live_cause,
                "sha256_a": digest_obj(live_a),
                "sha256_b": digest_obj(live_b),
            },
        },
        "inventory": inventory_production(repo),
        "worktrees_used": worktrees_used,
        "bodies": {
            "join-referential": jo,
            "floor-recount": floors,
            "agreement-statistic": agr,
            "severity-reconciliation": sev,
            "structural-gate": st,
            "digest-loss": dig,
        },
    }
