#!/usr/bin/env python3
"""Shard0-w2 probe generator.

Emits probes/<uid>/probe1_delivery_predicate.py and probe2_independent_recheck.py
for the 11 deliverable units (the 8 never-probed + the 3 trio units that keep
their content probes). Token-substitution templates (no brace-escaping).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PROBES = REPO / "command-center" / "p2-wave" / "probes"

CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u.get("id"): u for u in CATALOG.get("work_units", []) if isinstance(u, dict)}

IDS = ["ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018", "ADV-0019",
       "ADV-0022", "ADV-0023", "ADV-0024", "ADV-0028", "ADV-0029"]

# per-unit probe1 config
CFG = {
    "ADV-0005": dict(targets_key="targets", min_targets=1, controls=["negative_controls"],
                     evidence_mode=False),
    "ADV-0010": dict(targets_key="targets", min_targets=1, controls=["controls"],
                     evidence_mode=False),
    "ADV-0014": dict(targets_key="targets", min_targets=1, controls=["negative_controls"],
                     evidence_mode=False),
    "ADV-0015": dict(targets_key="targets", min_targets=1, controls=["negative_controls"],
                     evidence_mode=False),
    "ADV-0018": dict(targets_key="targets", min_targets=1, controls=["negative_controls"],
                     evidence_mode=False),
    "ADV-0019": dict(targets_key="verdicts", min_targets=1, controls=["controls"],
                     evidence_mode=False),
    "ADV-0022": dict(targets_key=None, min_targets=0, controls=["negative_controls", "control_ids"],
                     evidence_mode=True),
    "ADV-0023": dict(targets_key=None, min_targets=0, controls=["negative_controls", "control_ids"],
                     evidence_mode=True),
    "ADV-0024": dict(targets_key="targets", min_targets=1, controls=["negative_controls"],
                     evidence_mode=False),
    "ADV-0028": dict(targets_key="targets", min_targets=1, controls=["negative_tests", "controls"],
                     evidence_mode=False),
    "ADV-0029": dict(targets_key="target_verdicts", min_targets=1,
                     controls=["negative_controls"], evidence_mode=False),
}

P1_TEMPLATE = '''#!/usr/bin/env python3
"""@UID@ probe1 -- builder-side delivery predicate (live, fail-closed).

Checks the measured DELIVERED bar: artifact parses, not self-declared
BLOCKED/FAILED/SEVERED/TIMEOUT, unit_id, completion sentinel present, one
legal verdict per enumerated target/evidence row, controls recorded, named
probes recorded, min-bytes threshold. The receipt_core SUCCESS battery
(reviewer PASS+independent, downstream-executed, zero open P0/P1) is the
independent reviewer's closure job and is deliberately not fabricated by a
builder: the builder terminal is BLOCKED/reviewer-absent on the receipt
(program contract). This predicate fails closed on any builder-side gap.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "@OUT@"
SENTINEL = json.loads(r\'\'\'@SENTINEL_JSON@\'\'\')
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
LEGAL = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
UNIT = "@UID@"
TARGETS_KEY = @TARGETS_KEY@
MIN_TARGETS = @MIN_TARGETS@
CONTROLS_KEYS = @CONTROLS_KEYS@
EVIDENCE_MODE = @EVIDENCE_MODE@
MIN_BYTES = @MIN_BYTES@

fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:@UID@-probe1 artifact-unreadable:" + type(exc).__name__)
        return 1
    chk(OUT.stat().st_size >= MIN_BYTES, "artifact-under-min-bytes",
        str(OUT.stat().st_size))
    st = str(doc.get("state") or "").upper()
    chk(st not in NOT_DELIVERING, "self-declared", st)
    uid_field = str(doc.get("unit_id") or doc.get("id") or "")
    chk(uid_field == UNIT, "unit-id", uid_field)
    chk(SENTINEL in text, "completion-sentinel-absent")

    if TARGETS_KEY is not None:
        targets = doc.get(TARGETS_KEY) or []
        chk(len(targets) >= MIN_TARGETS, "targets-under-minimum", str(len(targets)))
        for i, t in enumerate(targets):
            v = str(t.get("verdict") or "")
            chk(v in LEGAL, "target-verdict-illegal", f"[{i}]={v!r}")
        verdicts = [str(t.get("verdict")) for t in targets]
        if verdicts and len(set(verdicts)) != len(verdicts):
            # duplicates are allowed across targets, but zero-verdict rows are not
            chk(all(verdicts), "empty-verdict-row")

    if EVIDENCE_MODE:
        ev = doc.get("evidence") or []
        chk(len(ev) >= 2, "evidence-under-minimum", str(len(ev)))
        for i, item in enumerate(ev):
            probes = item.get("probes") or []
            roles = {p.get("role") for p in probes if isinstance(p, dict)}
            fps = {p.get("fingerprint") for p in probes if isinstance(p, dict)}
            v = str(item.get("verdict") or "")
            chk(len(probes) >= 1, f"evidence[{i}]-probes-absent")
            if v in ("CONFIRMED", "REFUTED"):
                # two mechanically independent signals for decisive rows;
                # degraded rows (PARTIAL/NOT-CHECKED) honestly carry the
                # single leg that ran - that is what makes them degraded.
                chk("source" in roles, f"evidence[{i}]-source-probe-absent")
                chk("verifier" in roles, f"evidence[{i}]-verifier-probe-absent")
            chk(len(fps) == len(probes) and len(probes) >= 1,
                f"evidence[{i}]-fingerprints-not-distinct")

    controls_present = any(
        isinstance(doc.get(k), (list, dict)) and len(doc.get(k) or {}) > 0
        for k in CONTROLS_KEYS
    )
    chk(controls_present, "controls-absent", ",".join(CONTROLS_KEYS))

    probe_cmds = re.findall(
        r"command-center/p2-wave/probes/@UID@/[A-Za-z0-9_./-]+\\.py",
        text,
    )
    np_entries = [p for p in (doc.get("named_probes") or [])
                  if isinstance(p, dict) and (p.get("command") or p.get("raw_output"))]
    chk(len(set(probe_cmds)) >= 2 or len(np_entries) >= 2,
        "named-probes-under-recorded-minimum",
        f"cmds={len(set(probe_cmds))} entries={len(np_entries)}")

    if fails:
        for f in fails[:10]:
            print("FAILED:@UID@-probe1 " + f)
        return 1
    print("SUCCESS:@UID@-probe1 delivery predicate: parses, state=" + st
          + ", sentinel present, verdicts legal, controls recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

P2_HEADER = '''#!/usr/bin/env python3
"""@UID@ probe2 -- independent content re-derivation (mechanically different).

Recomputes the artifact's claims from its own raw rows and live inputs
(counts, census, internal consistency, live referenced files) and
byte-compares the per-unit manifest registration against the live artifact
(LF-normalized sha256, matching _measure_one_delivered.py). Fails closed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "@OUT@"
MANIFEST = REPO / "command-center/p2-wave/probes/@UID@/UNIT-ARTIFACT-MANIFEST.json"
UNIT = "@UID@"
LEGAL = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}

fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\\r\\n", b"\\n")).hexdigest()


def manifest_byte_compare(doc: dict) -> None:
    chk(MANIFEST.is_file(), "manifest-absent")
    if not MANIFEST.is_file():
        return
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = lf_sha(OUT)
    rows = [a for a in (man.get("artifacts") or [])
            if isinstance(a, dict) and a.get("unit_id") == UNIT]
    chk(bool(rows), "manifest-row-absent")
    match = [a for a in rows
             if str(a.get("path") or "").replace("\\\\", "/") == "@OUT@"
             and str(a.get("sha256") or "") == live
             and a.get("present") is True]
    chk(bool(match), "manifest-sha-mismatch-live",
        f"live={live[:16]} rows={[str(a.get('sha256'))[:16] for a in rows]}")


@BODY@

def main() -> int:
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:@UID@-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    manifest_byte_compare(doc)
    rederive(doc)
    if fails:
        for f in fails[:12]:
            print("FAILED:@UID@-probe2 " + f)
        return 1
    print("SUCCESS:@UID@-probe2 content re-derived live; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

BODY_0010 = '''
def rederive(doc: dict) -> None:
    mutations = doc.get("mutations") or []
    k = int(doc.get("killed_count") or 0)
    s = int(doc.get("survived_count") or 0)
    chk(k + s == len(mutations), "killed+survived!=mutations",
        f"{k}+{s}!={len(mutations)}")
    recomputed_k = sum(1 for m in mutations if str(m.get("status")) == "KILLED")
    recomputed_s = len(mutations) - recomputed_k
    chk(recomputed_k == k and recomputed_s == s, "mutation-census-mismatch",
        f"rows: KILLED={recomputed_k} other={recomputed_s} vs {k}/{s}")
    survivors = [m for m in mutations if str(m.get("status")) != "KILLED"]
    for m in survivors:
        # fail_open may be a true fail-open proof (true) or a strictness flip
        # that survives trivially (false) - the field must be RECORDED either
        # way, and every survivor must carry its suite evidence row
        chk(m.get("fail_open") is not None, "survivor-fail-open-unrecorded",
            str(m.get("id")))
        chk(bool(m.get("failed_tests")) or bool(m.get("suite")),
            "survivor-evidence-absent", str(m.get("id")))
    controls = doc.get("controls") or []
    names = {str(c.get("id") or c) for c in controls} if isinstance(controls, list) else set(controls)
    for need in ("unmutated_baseline_green", "killed_mutation_proves_suite_ran",
                 "both_named_probes_recorded"):
        chk(any(need in n for n in names), "control-absent", need)
    gate = str(doc.get("gate_under_test") or "")
    chk(bool(gate), "gate-under-test-absent")
'''


BODY_0014 = '''
def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    chk(len(targets) == 21, "target-count", str(len(targets)))
    for t in targets:
        v = str(t.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"{t.get('id')}={v}")
        if v in ("REFUTED", "NOT-CHECKED"):
            chk(bool(t.get("reason")), "reason-absent-for-degraded-verdict",
                str(t.get("id")))
        if str(t.get("kind")) == "vendor-cli":
            chk(int(t.get("live_flag_count") or 0) > 0 or v == "NOT-CHECKED",
                "cli-live-flag-count-absent", str(t.get("id")))
    cli = doc.get("cli_summary") or {}
    mcp = doc.get("mcp_summary") or {}
    for label, summary in (("cli", cli), ("mcp", mcp)):
        control = summary.get("control") or {}
        chk(control.get("fired_on_bad_state") is True,
            f"{label}-control-not-both-states",
            json.dumps(control)[:120])
    chk(bool(doc.get("named_probes")), "named-probes-absent")
'''


BODY_0015 = '''
def rederive(doc: dict) -> None:
    counts = doc.get("counts") or {}
    diffs = doc.get("diffs") or []
    targets = doc.get("targets") or []
    chk(len(diffs) == int(counts.get("n_table_rows") or -1), "diffs!=n_table_rows",
        f"{len(diffs)} vs {counts.get('n_table_rows')}")
    # every diff row in this sweep is a stale-table row; stale_models is the
    # per-model unique list (n_stale counts rows, stale_models counts models)
    chk(len(diffs) == int(counts.get("n_stale") or -1), "stale-rows!=n_stale",
        f"{len(diffs)} vs {counts.get('n_stale')}")
    chk(len(targets) == int(counts.get("n_targets") or -1), "targets!=n_targets",
        f"{len(targets)} vs {counts.get('n_targets')}")
    stale_models = doc.get("stale_models") or []
    models = {str(r.get("model")) for r in diffs}
    chk(len(models) == len(stale_models), "unique-models-mismatch",
        f"diffs models={len(models)} stale_models={len(stale_models)}")
    chk(int(counts.get("n_match") or 0) == 0 or bool(doc.get("matching_models")),
        "match-count-inconsistent")
    for t in targets:
        chk(str(t.get("verdict")) in LEGAL, "verdict-illegal", f"{t.get('id')}={t.get('verdict')}")
        if str(t.get("id")) == "CTRL-SURFACE-MATCHING-ROW":
            chk(str(t.get("verdict")) == "REFUTED",
                "planted-matching-control-not-refuted")
    ov = str(doc.get("overall_verdict") or "")
    chk(ov in LEGAL, "overall-verdict-illegal", ov)
    chk(ov == "PARTIAL" if int(counts.get("n_stale") or 0) else True,
        "overall-verdict-vs-stale-count", ov)
'''


BODY_0018 = '''
def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    chk(len(targets) == 8, "target-count", str(len(targets)))
    for t in targets:
        chk(str(t.get("verdict")) in LEGAL, "verdict-illegal", f"{t.get('id')}={t.get('verdict')}")
    con = doc.get("contradicted_ids") or []
    raw_notes = doc.get("contradicted_notes") or []
    chk(bool(raw_notes) and len(con) >= 2, "contradiction-set-empty")
    note_bodies = [n.get("contradicted") for n in raw_notes if isinstance(n, dict)]
    chk(bool(note_bodies), "contradiction-note-bodies-absent")
    for n in note_bodies:
        chk(isinstance(n, list) and len(n) >= 1,
            "contradiction-note-empty-body")
    recall = set(doc.get("still_recallable_ids") or [])
    chk(recall <= set(con), "recallable-not-subset-contradicted",
        str(recall - set(con))[:120])
    chk(int(doc.get("notes_loaded") or 0) > 0, "notes-loaded-zero")
    chk(bool(doc.get("frontmatter_audit")), "frontmatter-audit-absent")
    chk(bool(doc.get("vault_method") or doc.get("vault_roots")), "vault-method-absent")
'''


BODY_0022 = '''
def rederive(doc: dict) -> None:
    ev = doc.get("evidence") or []
    chk(len(ev) >= 5, "evidence-under-minimum", str(len(ev)))
    for i, item in enumerate(ev):
        v = str(item.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"[{i}]={v}")
        probes = item.get("probes") or []
        fps = [p.get("fingerprint") for p in probes if isinstance(p, dict)]
        chk(len(fps) == len(set(fps)) and len(fps) >= 1,
            "fingerprints-not-per-item-distinct", f"[{i}]")
    for d in doc.get("defects") or []:
        chk(bool(d.get("id")) and bool(d.get("severity")) and bool(d.get("status")),
            "defect-row-incomplete", str(d.get("id")))
    chk(bool(doc.get("control_ids")), "control-ids-absent")
    chk(bool(doc.get("residual_unknowns")), "residual-unknowns-absent")
    chk(bool(doc.get("downstream_consumers")), "downstream-consumers-absent")
'''


BODY_0023 = '''
def rederive(doc: dict) -> None:
    vpt = doc.get("verdict_per_target") or {}
    chk(len(vpt) >= 1, "verdict-per-target-absent")
    for tid, v in vpt.items():
        chk(str(v) in LEGAL, "verdict-illegal", f"{tid}={v}")
    recall = doc.get("recall_summary") or {}
    def ratio(n_total: int, missed: list) -> float:
        return round((n_total - len(missed)) / n_total, 6)
    missed_wf = recall.get("gitleaks_missed_wellformed") or []
    chk(abs(float(recall.get("gitleaks_recall_wellformed_18", 0))
            - ratio(18, missed_wf)) < 1e-3, "recall-wellformed-mismatch",
        f"stored={recall.get('gitleaks_recall_wellformed_18')} recompute={ratio(18, missed_wf)}")
    canary = doc.get("canary_design") or doc.get("corpus_scope") or {}
    chk(bool(canary), "canary-design-absent")
    defects = doc.get("defects") or []
    chk(any(str(d.get("id")) == "ADV-0023-D1" and str(d.get("severity")) == "P0"
            and str(d.get("status")) == "open" for d in defects),
        "defect-D1-open-P0-recorded-absent")
    chk(bool(doc.get("control_ids")), "control-ids-absent")
    chk(bool(doc.get("negative_controls")), "negative-controls-absent")
'''


BODY_0024 = '''
def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    counts = doc.get("counts") or {}
    census: dict[str, int] = {}
    for t in targets:
        v = str(t.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"{t.get('target_id')}={v}")
        census[v] = census.get(v, 0) + 1
    chk(census == {k: counts.get(k, 0) for k in census},
        "census-vs-counts-mismatch", f"{census} vs {counts}")
    chk(len(targets) == int(counts.get("targets") or -1), "targets!=counts.targets",
        f"{len(targets)} vs {counts.get('targets')}")
    ov = str(doc.get("overall_verdict") or "")
    chk(ov in LEGAL, "overall-verdict-illegal", ov)
    chk(bool(doc.get("negative_controls")), "negative-controls-absent")
    chk(bool(doc.get("packager_rows")) and bool(doc.get("member_rows")),
        "raw-rows-absent")
'''


BODY_TRIO = '''
def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    if not targets:
        for key in ("verdicts", "target_verdicts"):
            if doc.get(key):
                targets = doc.get(key)
                break
    ev = doc.get("evidence") or []
    for i, t in enumerate(targets):
        v = str(t.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"[{i}]={v}")
        dn = t.get("dead_names")
        if dn is not None:
            chk(bool(dn), "dead-names-absent", str(t.get("id")))
        obs = t.get("observed")
        if obs is not None and t.get("expected_fail_closed") is not None:
            accepted = t.get("accepted")
            expect = str(t.get("verdict")) == "CONFIRMED"
            got = (str(obs) == "accepted") is bool(accepted)
            chk(got is expect or bool(accepted) == (str(obs) == "accepted"),
                "signature-matrix-inconsistent", str(t.get("id")))
    for i, item in enumerate(ev):
        v = str(item.get("verdict") or "")
        if v:
            chk(v in LEGAL, "evidence-verdict-illegal", f"[{i}]={v}")
    ov = str(doc.get("overall_verdict") or doc.get("verdict") or "")
    chk(ov in LEGAL, "overall-verdict-illegal", ov)
'''


BODY_0005 = '''
def rederive(doc: dict) -> None:
    targets = doc.get("targets") or []
    chk(len(targets) == 10, "target-count", str(len(targets)))
    planted_false = [t for t in targets if t.get("planted_kind") == "false"]
    chk(bool(planted_false), "planted-false-calibration-absent")
    for t in targets:
        v = str(t.get("verdict") or "")
        chk(v in LEGAL, "verdict-illegal", f"{t.get('id')}={v}")
        if v == "REFUTED":
            # vote counting is banned: a refutation must name its settling
            # tiebreak; CONFIRMED calibration rows may legitimately lack one
            chk(bool(t.get("tiebreak")), "tiebreak-absent-for-refutation",
                str(t.get("id")))
        if t.get("planted_kind") is not None:
            # planted calibration rows carry the blind/implementer/settling trace;
            # real claim rows carry prose summaries instead.
            summary = str(t.get("summary") or "")
            chk("final=" in summary, "summary-final-absent", str(t.get("id")))
            final = summary.rsplit("final=", 1)[-1].strip()
            chk(final == v, "summary-final-disagrees",
                f"{t.get('id')}: final={final} verdict={v}")
    for t in planted_false:
        chk(str(t.get("verdict")) == "REFUTED",
            "planted-false-not-refuted", str(t.get("id")))
    chk(bool(doc.get("blinding")) and bool(doc.get("unblind")),
        "blinding/unblind-absent")
    chk(bool(doc.get("named_registry")), "named-registry-absent")
    chk(bool(doc.get("negative_controls")), "negative-controls-absent")
'''


def gen() -> None:
    for uid in IDS:
        u = UNITS[uid]
        out_rel = str(u["output_path"]).replace("\\\\", "/")
        sentinel = str(u["completion_sentinel"])
        c = CFG[uid]
        pdir = PROBES / uid
        pdir.mkdir(parents=True, exist_ok=True)
        code = (P1_TEMPLATE
                .replace("@UID@", uid)
                .replace("@OUT@", out_rel)
                .replace("@SENTINEL_JSON@", json.dumps(sentinel))
                .replace("@TARGETS_KEY@", repr(c["targets_key"]))
                .replace("@MIN_TARGETS@", str(c["min_targets"]))
                .replace("@CONTROLS_KEYS@", repr(c["controls"]))
                .replace("@EVIDENCE_MODE@", repr(c["evidence_mode"]))
                .replace("@MIN_BYTES@", "1024"))
        (pdir / "probe1_delivery_predicate.py").write_text(code, encoding="utf-8", newline="\n")
        body = {
            "ADV-0005": BODY_0005,
            "ADV-0010": BODY_0010,
            "ADV-0014": BODY_0014,
            "ADV-0015": BODY_0015,
            "ADV-0018": BODY_0018,
            "ADV-0019": BODY_TRIO,
            "ADV-0022": BODY_0022,
            "ADV-0023": BODY_0023,
            "ADV-0024": BODY_0024,
            "ADV-0028": BODY_TRIO,
            "ADV-0029": BODY_TRIO,
        }.get(uid)
        if body is None:
            raise SystemExit(f"no probe2 body for {uid}")
        code2 = (P2_HEADER.replace("@UID@", uid).replace("@OUT@", out_rel)
                 .replace("@BODY@", body))
        (pdir / "probe2_independent_recheck.py").write_text(code2, encoding="utf-8", newline="\n")
        print(f"gen {uid} probe1+probe2")


if __name__ == "__main__":
    gen()
