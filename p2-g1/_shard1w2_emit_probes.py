#!/usr/bin/env python3
"""Shard1 wave-2 probe emitter (9 from-scratch units).

For each unit writes:
  probes/<id>/probe1_delivery_predicate.py  (structural + sentinel + verdict/controls completeness; schema-drift surfaced as note)
  probes/<id>/probe2_independent_recheck.py (manifest sha byte-compare + unit-specific re-derivation + mutation negative control -> nc_live.json)

Run from repo root:  python _shard1w2_emit_probes.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
PROBES = REPO / "command-center" / "p2-wave" / "probes"

UNITS = {
    "ADV-0040": "command-center/adversarial/ADV-0040-corpus-pii-recall-calibrated-sweep.json",
    "ADV-0090": "command-center/adversarial/ADV-0090-rerun-until-green-laundering.json",
    "ADV-0091": "command-center/adversarial/ADV-0091-instant-unanimity-trigger.json",
    "ADV-0100": "command-center/adversarial/ADV-0100-conflict-of-interest-self-review.json",
    "ADV-0109": "command-center/adversarial/ADV-0109-dissent-omission-differential.json",
    "ADV-0110": "command-center/adversarial/ADV-0110-root-cause-hierarchy-falsifiability.json",
    "ADV-0117": "command-center/adversarial/ADV-0117-windows-hostile-path-matrix.json",
    "ADV-0119": "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json",
    "ADV-0123": "command-center/adversarial/ADV-0123-concurrent-session-index-and-lease-race.json",
}

# Per-unit re-derivation body for probe2. Each body defines `checks: list[tuple[str, bool, str]]`.
REDERIVE = {
"ADV-0040": '''
    rec = doc.get("recall") or {}
    tp = doc.get("text_plants") or {}
    np_ = doc.get("nontext_plants") or {}
    found = int(tp.get("found_n", -1)) + int(np_.get("found_n", -1))
    np_planted = int(np_.get("planted_n", len(np_.get("planted_categories") or [])) if (np_.get("planted_n") is not None or np_.get("planted_categories")) else -1)
    planted = int(tp.get("planted_n", -1)) + np_planted
    checks.append((
        "found_n re-derived: text 6/6 + nontext 2/2 = recall.found_n",
        found == int(rec.get("found_n", -2)) and planted == int(rec.get("planted_n", -2)),
        f"text {tp.get('found_n')}/{tp.get('planted_n')} + nontext {np_.get('found_n')}/{np_.get('planted_n')} -> {found}/{planted} vs recall {rec.get('found_n')}/{rec.get('planted_n')}",
    ))
    want_recall = (found / planted) if planted else 0.0
    checks.append((
        "planted_pii_recall == found/planted",
        abs(float(rec.get("planted_pii_recall", -1)) - want_recall) < 1e-9,
        f"recorded {rec.get('planted_pii_recall')} vs recomputed {want_recall}",
    ))
    ct = (doc.get("corpus_text") or {}).get("by_category") or {}
    t2 = next((t for t in doc.get("targets") or [] if str(t.get("id")) == "T2"), None)
    checks.append((
        "T2 email-hit count == corpus_text.by_category.email",
        t2 is not None and int(t2.get("hits", -1)) == int(ct.get("email", -2)),
        f"T2 hits={t2.get('hits') if t2 else None} vs by_category.email={ct.get('email')}",
    ))
''',
"ADV-0090": '''
    nc = next((c for c in doc.get("negative_controls") or [] if c.get("id") == "synthetic-6-of-10-flaky-fixture"), None)
    bad = str((nc or {}).get("bad_state_output", ""))
    good = str((nc or {}).get("good_state_output", ""))
    checks.append((
        "flaky fixture both-states: bad fires flaky 6/10, good silent 10/10",
        bool(nc) and "passes=6/10" in bad and "flaky_by_contract=True" in bad
        and "passes=10/10" in good and "flaky_by_contract=False" in good
        and nc.get("fired_on_bad_state") is True and nc.get("silent_on_good_state") is True,
        f"bad[:60]={bad[:60]!r} good[:60]={good[:60]!r}",
    ))
    rep = doc.get("report") or {}
    checks.append((
        "report.overall_verdict == top-level overall_verdict (PARTIAL, no green-laundering)",
        rep.get("overall_verdict") == doc.get("overall_verdict") == "PARTIAL",
        f"report={rep.get('overall_verdict')} top={doc.get('overall_verdict')}",
    ))
    checks.append((
        "probe1_answer == report.answer (single source of truth, no drift)",
        doc.get("probe1_answer") == rep.get("answer") and bool(doc.get("probe1_answer")),
        f"len={len(str(doc.get('probe1_answer', '')))}",
    ))
    det = [t for t in doc.get("tests") or [] if "deterministic-control-10-of-10" in str(t.get("id", ""))]
    checks.append((
        "deterministic control recorded PASS 10/10",
        len(det) >= 1 and det[0].get("result") == "PASS",
        f"rows={len(det)} result={det[0].get('result') if det else None}",
    ))
''',
"ADV-0091": '''
    primed = doc.get("primed_run") or {}
    delta = primed.get("delta") or {}
    key = [str(x) for x in (delta.get("consumer_key_live") or [])]
    checks.append((
        "primed round-1 zero-brief unanimity trigger FIRES (key carries UNANIMITY, hold-for-revaluation live)",
        "UNANIMITY" in key and delta.get("hold_for_revaluation_live") is True,
        f"key={key} hold={delta.get('hold_for_revaluation_live')}",
    ))
    late = (doc.get("late_legitimate_run") or {}).get("live") or {}
    checks.append((
        "late legitimate unanimity after real disagreement does NOT fire",
        late.get("instant_unanimity_trigger") is False,
        f"late.instant_unanimity_trigger={late.get('instant_unanimity_trigger')}",
    ))
    li = doc.get("outcome_delta") or {}
    listed = li.get("listed_interventions_executed") or {}
    checks.append((
        "NO listed intervention was executed on the ceremonial path",
        bool(listed) and all(v is False for v in listed.values()),
        f"{sorted(listed.items())}",
    ))
    verd = {str(v.get("id")): v.get("verdict") for v in doc.get("verdicts") or []}
    checks.append((
        "verdicts consistent with mechanism: trigger CONFIRMED on primed, interventions REFUTED (none ran)",
        verd.get("T-TRIGGER-FIRES-ON-PRIMED") == "CONFIRMED"
        and verd.get("T-LISTED-INTERVENTIONS-EXECUTE") == "REFUTED",
        f"trigger={verd.get('T-TRIGGER-FIRES-ON-PRIMED')} listed={verd.get('T-LISTED-INTERVENTIONS-EXECUTE')}",
    ))
''',
"ADV-0100": '''
    det = doc.get("detector_control") or {}
    checks.append((
        "COI detector proven both-states: known-present self-author FIRES and is excluded",
        det.get("control_status") == "FIRE"
        and det.get("known_present_id") in (det.get("control_excluded") or [])
        and det.get("fired_before_absence_reported") is True,
        f"status={det.get('control_status')} excluded={det.get('control_excluded')}",
    ))
    dc = doc.get("direct_case") or {}
    checks.append((
        "direct self-review case: author eligible under configured exclude = the CONFIRMED pathology",
        dc.get("configured_action") == "exclude" and dc.get("excluded_by_conflict_check") is False,
        f"action={dc.get('configured_action')} excluded={dc.get('excluded_by_conflict_check')}",
    ))
    files = ((doc.get("production_census") or {}).get("files") or {})
    bad = [k for k, v in files.items() if not (isinstance(v, dict) and v.get("present") is True and int(v.get("bytes", 0)) > 0)]
    checks.append((
        "production census files all recorded present with bytes>0",
        bool(files) and not bad,
        f"rows={len(files)} bad={bad[:3]}",
    ))
    first = sorted(files.items())[0] if files else None
    live_ok = False
    live_note = "no census row"
    if first:
        rel, meta = first
        p = REPO / rel
        live_ok = p.is_file() and p.stat().st_size == int(meta.get("bytes", -1))
        live_note = f"{rel} live_bytes={p.stat().st_size if p.is_file() else 'ABSENT'} census={meta.get('bytes')}"
    checks.append((
        "census row byte-count re-verified LIVE on this worktree",
        live_ok,
        live_note,
    ))
''',
"ADV-0109": '''
    fr = ((doc.get("forward_accounting") or {}).get("ratio") or {})
    den = int(fr.get("denominator", -1))
    ssum = int(fr.get("represented", -1)) + int(fr.get("resolved_with_reason", -1)) + int(fr.get("silently_dropped", -1))
    checks.append((
        "forward ratio components sum to the denominator",
        ssum == den,
        f"1+1+3 recorded -> {ssum} vs denominator {den}",
    ))
    want_rate = round(int(fr.get("silently_dropped", 0)) / den, 6) if den else None
    checks.append((
        "drop_rate == silently_dropped / denominator",
        want_rate is not None and abs(float(fr.get("drop_rate", -1)) - want_rate) < 1e-9,
        f"recorded {fr.get('drop_rate')} vs recomputed {want_rate}",
    ))
    ctl = {str(c.get("id")): c for c in doc.get("controls") or []}
    rep_ctl = (ctl.get("CTRL-REPRESENTED") or {}).get("result") or ctl.get("CTRL-REPRESENTED") or {}
    pd_ctl = (ctl.get("CTRL-PLANTED-DROP") or {}).get("result") or ctl.get("CTRL-PLANTED-DROP") or {}
    checks.append((
        "represented contradiction classified correctly and planted silent drop CAUGHT",
        (rep_ctl.get("pass") is True)
        and (pd_ctl.get("want") == "silently-dropped" and pd_ctl.get("got") == "silently-dropped"),
        f"represented={rep_ctl.get('pass')} planted got={pd_ctl.get('got')} want={pd_ctl.get('want')}",
    ))
''',
"ADV-0110": '''
    tg = {str(t.get("id") or t.get("target")): t.get("verdict") for t in doc.get("targets") or []}
    en = {str(t.get("id") or t.get("target")): t.get("verdict") for t in doc.get("enumerated_targets") or []}
    checks.append((
        "targets == enumerated_targets (same id->verdict map, no double counting)",
        tg and tg == en,
        f"{len(tg)} vs {len(en)} targets",
    ))
    vocab = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    badv = [k for k, v in tg.items() if v not in vocab]
    checks.append((
        "exactly one in-vocabulary verdict per target",
        tg and not badv,
        f"bad={badv[:3]}",
    ))
    sch_rel = str(doc.get("output_schema", ""))
    checks.append((
        "declared output_schema file present live (output_schema_present re-checked)",
        (REPO / sch_rel).is_file() and doc.get("output_schema_present") is True,
        sch_rel,
    ))
    import re as _re
    checks.append((
        "audit_sha256 well-formed (links the refuted audit by content address)",
        bool(_re.fullmatch(r"[0-9a-f]{64}", str(doc.get("audit_sha256", "")))),
        str(doc.get("audit_sha256", ""))[:16] + "...",
    ))
''',
"ADV-0117": '''
    cs = doc.get("count_summary") or {}
    cm = doc.get("component_matrix") or []
    checks.append((
        "count_summary total == component_matrix row count",
        sum(int(v) for v in cs.values()) == len(cm),
        f"{sorted(cs.items())} sum={sum(int(v) for v in cs.values())} vs rows={len(cm)}",
    ))
    rows_ordinary = [r for r in cm if r.get("path_class") == "ordinary"]
    correct_ordinary = [r for r in rows_ordinary if r.get("outcome") == "correct"]
    pc = (doc.get("per_class") or [{}])[0]
    checks.append((
        "ordinary-class correct re-derived from raw matrix == per_class claim (7)",
        len(correct_ordinary) == int((pc.get("outcomes") or {}).get("correct", -1)) == 7,
        f"recomputed {len(correct_ordinary)} vs per_class {pc.get('outcomes')}",
    ))
    vocab = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    badv = [r.get("target_id") for r in cm if r.get("verdict") not in vocab]
    checks.append((
        "every matrix row carries one in-vocabulary verdict",
        cm and not badv,
        f"rows={len(cm)} bad={badv[:3]}",
    ))
''',
"ADV-0119": '''
    tp = doc.get("three_point_inventory") or {}
    empties = all(
        (tp.get(k) == []) for k in ("missing_files", "altered_files", "missing_commands", "leftover_commands")
    )
    checks.append((
        "three-point inventory: byte-identical user data, commands restored, zero N-only residue",
        tp.get("user_byte_identical") is True and tp.get("commands_restored") is True
        and tp.get("no_n_only_leftover") is True and empties,
        f"user_byte_identical={tp.get('user_byte_identical')} commands={tp.get('commands_restored')} "
        f"residue={tp.get('no_n_only_leftover')} empty_lists={empties}",
    ))
    gj = doc.get("golden_journeys") or {}
    pre_rows = ((gj.get("pre_upgrade") or {}).get("rows")) or []
    checks.append((
        "golden journeys pass after rollback; pre-upgrade rows all rc=0",
        gj.get("post_rollback_pass") is True and pre_rows and all(r.get("rc") == 0 and r.get("ok") is True for r in pre_rows),
        f"post={gj.get('post_rollback_pass')} pre_rows={len(pre_rows)}",
    ))
    tg = doc.get("enumerated_targets") or []
    checks.append((
        "all five enumerated targets CONFIRMED",
        len(tg) == 5 and all(t.get("verdict") == "CONFIRMED" for t in tg),
        f"targets={len(tg)} verdicts={[t.get('verdict') for t in tg]}",
    ))
''',
"ADV-0123": '''
    tg = doc.get("targets") or []
    ev = doc.get("evidence") or []
    checks.append((
        "four enumerated targets, one verdict each, evidence aligned 1:1",
        len(tg) == len(ev) == 4 and all(t.get("verdict") in {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"} for t in tg),
        f"targets={len(tg)} evidence={len(ev)}",
    ))
    ctl = doc.get("controls") or []
    checks.append((
        "three controls recorded, all PASS",
        len(ctl) == 3 and all(c.get("result") == "PASS" for c in ctl),
        f"{[c.get('id') for c in ctl]}",
    ))
    broad = next((t for t in tg if t.get("target_id") == "TARGET-BROAD-STAGE-SWEEPS-SIBLING"), None)
    checks.append((
        "broad-stage sweep target CONFIRMED with non-empty sibling contamination oracle output",
        broad is not None and broad.get("verdict") == "CONFIRMED" and bool(broad.get("sibling_in_cached")),
        f"verdict={broad.get('verdict') if broad else None} sibling_in_cached={broad.get('sibling_in_cached') if broad else None}",
    ))
    fnd = doc.get("findings") or []
    sev = {f.get("severity") for f in fnd}
    checks.append((
        "findings F1/F2 recorded with P0+P1 severities",
        len(fnd) == 2 and sev == {"P0", "P1"},
        f"{[(f.get('id'), f.get('severity')) for f in fnd]}",
    ))
''',
}

PROBE1_TMPL = '''#!/usr/bin/env python3
"""{uid} probe1 -- structural + sentinel delivery predicate (live, fail-closed).

Checks the completion-sentinel contract on the live artifact: parses, unit_id,
state not self-declaring non-delivery, sentinel text present, one in-vocabulary
verdict per enumerated target, controls and negative controls recorded, and
min-bytes floor. Current-schema drift is surfaced as a NOTE, never folded into
a pass (the delivered predicate is the sentinel list, not the moved schema).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "{out_rel}"
UNIT = "{uid}"
NOT_DELIVERING = {{"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}}
VOCAB = {{"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}}


def main() -> int:
    fails = []
    notes = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(label + (f": {{detail}}" if detail else ""))

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{{UNIT}}-probe1 artifact unreadable/unparseable: {{type(exc).__name__}}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:{uid}-probe1 artifact is not a JSON object")
        return 1

    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING, "self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold", f"{{OUT.stat().st_size}} < {{minb}}")
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel absent from artifact text")

    tgt = doc.get("targets") or doc.get("verdicts") or doc.get("enumerated_targets") or doc.get("component_matrix") or []
    if not tgt and doc.get("overall_verdict"):
        tgt = [{{"id": doc.get("question_or_target") or "overall", "verdict": doc.get("overall_verdict")}}]
    verdicts = [
        t.get("verdict") for t in tgt
        if isinstance(t, dict) and t.get("verdict") is not None
    ]
    check(len(tgt) >= 1, "no enumerated targets recorded")
    check(all(v in VOCAB for v in verdicts), "target verdict outside vocabulary", str(verdicts[:6]))

    ctrls = doc.get("controls") or doc.get("negative_controls") or []
    check(len(ctrls) >= 1, "no control results recorded")
    ncs = doc.get("negative_controls") or []
    if not ncs:
        ncs = [
            c for c in ctrls
            if isinstance(c, dict) and (
                c.get("fired_on_bad_state") is not None
                or "negative" in str(c.get("id", "")).lower()
                or "blind" in str(c.get("id", "")).lower()
                or "silent" in str(c.get("id", "")).lower()
                or "drop" in str(c.get("id", "")).lower()
            )
        ]
    check(len(ncs) >= 1, "no negative controls recorded")
    bad_nc = [
        str(c.get("id")) for c in ncs
        if isinstance(c, dict)
        and c.get("fired_on_bad_state") is not None
        and (c.get("fired_on_bad_state") is not True or c.get("silent_on_good_state") is not True)
    ]
    check(not bad_nc, "negative control failed a both-states field", str(bad_nc[:3]))

    # informational: schema drift note (never folded into the verdict)
    sch_rel = str(doc.get("output_schema") or doc.get("declared_schema") or "")
    if sch_rel:
        sp = REPO / sch_rel.split(" profile=")[0].split("#")[0]
        if sp.is_file():
            try:
                import jsonschema
                errs = list(
                    jsonschema.Draft202012Validator(json.loads(sp.read_text(encoding="utf-8"))).iter_errors(doc)
                )
                if errs:
                    notes.append(f"schema-drift-note: {{len(errs)}} error(s) against {{sp.name}} (schema moved post-delivery)")
            except Exception as exc:
                notes.append(f"schema-note: {{type(exc).__name__}}")
        else:
            notes.append("schema-note: declared schema file absent on this worktree")

    report = {{
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "targets": len(tgt),
        "verdicts": verdicts,
        "controls": len(ctrls),
        "negative_controls": len(ncs),
        "notes": notes,
        "fails": fails,
    }}
    print(json.dumps(report, indent=1))
    if fails:
        print(f"FAILED:{{UNIT}}-probe1 {{'; '.join(fails)}}")
        return 1
    print(f"SUCCESS:{{UNIT}}-probe1 predicate holds ({{len(tgt)}} targets, {{len(ctrls)}}+{{len(ncs)}} controls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

PROBE2_TMPL = '''#!/usr/bin/env python3
"""{uid} probe2 -- mechanically different independent recheck (live, fail-closed).

Lane 1: byte-compare the per-unit manifest sha (LF-normalized) against the
live artifact. Lane 2: re-derive the unit's headline claims from artifact
internals. Lane 3: mutation negative control - the structural predicate must
FIRE on a tampered copy and stay SILENT on the real artifact. Writes nc_live.json.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "{out_rel}"
UNIT = "{uid}"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
VOCAB = {{"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}}


def digest_norm(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()


def structural_fires(text: str) -> tuple[bool, str]:
    """The minimal predicate probe1 embodies; used for the mutation control."""
    try:
        doc = json.loads(text)
    except Exception:
        return True, "parse-error"
    if not isinstance(doc, dict):
        return True, "not-an-object"
    if doc.get("unit_id") != UNIT:
        return True, "unit-id-mismatch"
    tgt = (
        doc.get("targets")
        or doc.get("verdicts")
        or doc.get("enumerated_targets")
        or doc.get("component_matrix")
    )
    if not tgt:
        if not doc.get("overall_verdict"):
            return True, "targets-collapsed"
    else:
        vocab = {{"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}}
        vs = [t.get("verdict") for t in tgt if isinstance(t, dict) and t.get("verdict") is not None]
        if not vs or any(v not in vocab for v in vs):
            return True, "verdict-vocabulary"
    return False, "clean"


def main() -> int:
    fails = []
    checks = []

    # Lane 1: manifest byte-compare
    if not MANIFEST.is_file():
        fails.append("manifest-absent")
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == UNIT]
        live = digest_norm(OUT)
        match = [
            a for a in rows
            if str(a.get("path", "")).replace("\\\\", "/") == "{out_rel}"
            and str(a.get("sha256", "")) == live
            and a.get("present") is True
        ]
        checks.append((
            "manifest sha row matches live artifact (LF-normalized)",
            bool(match),
            f"sha={{live[:16]}}... rows={{len(rows)}}",
        ))
        if not match:
            fails.append("manifest-sha-mismatch")

    # Lane 2: unit-specific re-derivation
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAILED:{{UNIT}}-probe2 artifact unparseable: {{type(exc).__name__}}")
        return 1
{rederive_body}
    for label, ok, detail in checks:
        if not ok:
            fails.append(f"{{label}} ({{detail}})")

    # Lane 3: mutation negative control (both-states)
    real_doc = json.loads(OUT.read_text(encoding="utf-8"))
    real_doc["unit_id"] = "XXXX-0000"
    tamper = json.dumps(real_doc, ensure_ascii=False, indent=1)
    fired_t, why_t = structural_fires(tamper)
    fired_r, why_r = structural_fires(OUT.read_text(encoding="utf-8"))
    control_ok = fired_t and not fired_r
    nc = {{
        "id": "NC-STRUCTURAL-PREDICTOR-BOTH-STATES",
        "kind": "mutation",
        "description": "predicate must fire on a unit-id-tampered copy and stay silent on the real artifact",
        "fired_on_bad_state": fired_t,
        "silent_on_good_state": not fired_r,
        "bad_state_why": why_t,
        "good_state_why": why_r,
    }}
    (HERE / "nc_live.json").write_text(json.dumps(nc, indent=1), encoding="utf-8", newline="\\n")
    if not control_ok:
        fails.append(f"mutation control: tampered-fired={{fired_t}} real-fired={{fired_r}} ({{why_t}}/{{why_r}})")

    report = {{
        "probe": "probe2-independent-recheck",
        "unit_id": UNIT,
        "lanes": {{
            "manifest_byte_compare": "ok" if not any("manifest" in f for f in fails) else "fail",
            "rederivations": [{{"label": lb, "ok": ok, "detail": dt}} for lb, ok, dt in checks],
            "mutation_control": nc,
        }},
        "fails": fails,
    }}
    print(json.dumps(report, indent=1))
    if fails:
        print(f"FAILED:{{UNIT}}-probe2 {{'; '.join(fails)}}")
        return 1
    print(f"SUCCESS:{{UNIT}}-probe2 manifest sha match, {{len(checks)}} rederivations hold, mutation control both-states ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def emit(uid: str, out_rel: str) -> None:
    d = PROBES / uid
    d.mkdir(parents=True, exist_ok=True)
    p1 = d / "probe1_delivery_predicate.py"
    p1.write_text(
        PROBE1_TMPL.format(uid=uid, out_rel=out_rel), encoding="utf-8", newline="\n"
    )
    body = REDERIVE[uid]
    p2 = d / "probe2_independent_recheck.py"
    p2.write_text(
        PROBE2_TMPL.format(uid=uid, out_rel=out_rel, rederive_body=body),
        encoding="utf-8",
        newline="\n",
    )
    print("emitted", p1)
    print("emitted", p2)


def main() -> int:
    for uid, out_rel in UNITS.items():
        emit(uid, out_rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
