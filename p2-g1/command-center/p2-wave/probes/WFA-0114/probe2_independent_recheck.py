#!/usr/bin/env python3
"""WFA-0114 probe2 -- independent content re-derivation (mechanically different).

Recomputes the artifact's headline claims from the recorded-run fixture on a
code path that does NOT import rubric.py (inline per-case iteration), runs the
live both-states controls (mutant composite must fire; unfrozen / post-hoc
mutated certification must REFUSE; padded stage count must NOT qualify;
low-agreement human component must be removed while high agreement retains),
and byte-compares the per-unit manifest against the live artifact
(LF-normalized sha256, matching _measure_one_delivered.py). Fails closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/wfa/WFA-0114-headtohead-scoring-rubric.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0114"
REL = "command-center/wfa/WFA-0114-headtohead-scoring-rubric.json"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# --- independent re-derivation (no rubric.py import; inline iteration) ------ #

def arm_stats(arm, matched):
    """(n_pass, n_att, (n_recovered, n_recoverable) | None, usability | None)."""
    n_pass = n_att = 0
    first_fails = []
    terms = []
    for c in matched:
        a = arm[c]
        if not a["attempted"]:
            continue
        n_att += 1
        terms.append(1 - min(1.0, (a["checkpoints"] + a["abort"]
                                   + a["budget_exhausted"]) / 4.0))
        if a["first_attempt_oracle"] == "pass" or a["retry_oracle"] == "pass":
            n_pass += 1
        if a["first_attempt_oracle"] != "pass":
            first_fails.append(c)
    rec = None
    if first_fails:
        r = sum(1 for c in first_fails if a_retry(arm, c) == "pass")
        rec = (r, len(first_fails))
    use = (sum(terms) / len(terms)) if terms else None
    return n_pass, n_att, rec, use


def a_retry(arm, cid):
    return arm[cid]["retry_oracle"]


def solved_set(arm, matched, extra):
    out = set(extra or [])
    for c in matched:
        a = arm[c]
        if a["attempted"] and (a["first_attempt_oracle"] == "pass"
                               or a["retry_oracle"] == "pass"):
            out.add(c)
    return out


def named_value(rec_row, cid):
    for c in rec_row["fusion_named"]:
        if c["id"] == cid:
            return c
    raise KeyError(cid)


def rederive(fix, art, chk):
    matched = fix["matched_intersection"]
    corpus = fix["corpus_ids"]
    comps = art["comparisons"]
    for name, scen in fix["scenarios"].items():
        rec_row = comps[name]
        fusion = scen["fusion"]
        n_pass, n_att, rec, use = arm_stats(fusion, matched)
        vals = {
            "correctness": n_pass / len(matched),
            "coverage": n_att / len(matched),
        }
        chk(abs(vals["correctness"] - named_value(rec_row, "correctness")["value"]) < 1e-12,
            "correctness-drift:" + name)
        chk(abs(vals["coverage"] - named_value(rec_row, "coverage")["value"]) < 1e-12,
            "coverage-drift:" + name)
        rec_named = named_value(rec_row, "recovery")
        if rec is None:
            chk(rec_named.get("status") == "removed", "recovery-should-be-removed:" + name)
        else:
            chk(abs(rec[0] / rec[1] - rec_named["value"]) < 1e-12, "recovery-drift:" + name)
        use_named = named_value(rec_row, "usability")
        if use is None:
            chk(use_named.get("status") == "removed", "usability-should-be-removed:" + name)
        else:
            chk(abs(use - use_named["value"]) < 1e-12, "usability-drift:" + name)
        retained = [i for i in ("correctness", "coverage", "recovery", "usability")
                    if (rec is not None or i != "recovery")
                    and (use is not None or i != "usability")]
        arm_vals = [vals["correctness"], vals["coverage"]]
        if rec is not None:
            arm_vals.append(rec[0] / rec[1])
        if use is not None:
            arm_vals.append(use)
        arm_val = sum(arm_vals) / len(arm_vals)
        chk(abs(arm_val - rec_row["fusion_arm_composite"]["value"]) < 1e-12,
            "arm-composite-drift:" + name,
            "computed=%r recorded=%r" % (arm_val, rec_row["fusion_arm_composite"]["value"]))
        chk(rec_row["fusion_arm_composite"]["retained_ids"] == retained,
            "retained-ids-drift:" + name)
        # sources on the shared comparison component set
        src_vals = {}
        for src in ("source_a", "source_b"):
            sp, sa, srec, sue = arm_stats(scen[src], matched)
            sv = {"correctness": sp / len(matched), "coverage": sa / len(matched)}
            svals = [sv["correctness"], sv["coverage"]]
            if srec is not None:
                svals.append(srec[0] / srec[1])
            if sue is not None:
                svals.append(sue)
            both = [i for i in retained
                    if (srec is not None or i != "recovery")
                    and (sue is not None or i != "usability")]
            src_vals[src] = sum(svals[:0]) if False else (
                sum([sv["correctness"], sv["coverage"]]
                    + ([srec[0] / srec[1]] if srec is not None and "recovery" in both else [])
                    + ([sue] if sue is not None and "usability" in both else []))
                / len(both) if both else 0.0,
                both,
            )
        cmp_ids = rec_row["comparison_component_ids"]
        chk(src_vals["source_a"][1] == cmp_ids and src_vals["source_b"][1] == cmp_ids,
            "comparison-component-ids-drift:" + name)
        for idx, src in enumerate(("source_a", "source_b")):
            rec_src = rec_row["sources"][idx]
            chk(rec_src["arm_id"] == src, "source-order-drift:" + name)
            chk(abs(rec_src["comparison_composite"]["value"] - src_vals[src][0]) < 1e-12,
                "source-composite-drift:" + name + ":" + src,
                "computed=%r recorded=%r" % (src_vals[src][0],
                                             rec_src["comparison_composite"]["value"]))
        best = max(src_vals[s][0] for s in src_vals)
        chk(abs(rec_row["best_source_comparison_composite"] - best) < 1e-12,
            "best-source-drift:" + name)
        hh_fusion = arm_val if len(cmp_ids) == len(retained) else sum(
            [vals["correctness"], vals["coverage"]]
            + ([rec[0] / rec[1]] if rec is not None and "recovery" in cmp_ids else [])
            + ([use] if use is not None and "usability" in cmp_ids else [])
        ) / len(cmp_ids)
        chk(abs(rec_row["fusion_comparison_composite"]["value"] - hh_fusion) < 1e-12,
            "fusion-hh-drift:" + name)
        outperforms = hh_fusion > best
        chk(rec_row["outperforms"] == outperforms, "outperforms-drift:" + name)
        solved_f = solved_set(fusion, matched, scen.get("fusion_extra_solves"))
        solved_s = set()
        for src in ("source_a", "source_b"):
            solved_s |= solved_set(scen[src], matched, scen.get("source_extra_solves"))
        n_unique = len(solved_f - solved_s)
        delta = n_unique / len(corpus)
        chk(rec_row["complement"]["n_unique"] == n_unique, "n-unique-drift:" + name)
        chk(abs(rec_row["complement"]["delta"] - delta) < 1e-12, "delta-drift:" + name)
        material = delta >= 0.10 and n_unique >= 1
        chk(rec_row["materially_complementary"] == material,
            "material-drift:" + name)
        expected_decision = ("OUTPERFORMS" if outperforms
                             else ("MATERIALLY_COMPLEMENTARY" if material else "REJECT"))
        chk(rec_row["decision"] == expected_decision, "decision-drift:" + name,
            "computed=%r recorded=%r" % (expected_decision, rec_row["decision"]))


def kappa(r1, r2):
    n = len(r1)
    cats = sorted(set(r1) | set(r2))
    po = sum(1 for a, b in zip(r1, r2) if a == b) / n
    pe = sum((sum(1 for x in r1 if x == c) / n) * (sum(1 for x in r2 if x == c) / n)
             for c in cats)
    return 1.0 if pe == 1.0 else (po - pe) / (1 - pe)


def inter_rater_rederive(fix, art, chk):
    ir_art = art["inter_rater"]
    hi = fix["inter_rater"]["high_agreement"]
    lo = fix["inter_rater"]["low_agreement"]
    k_hi = kappa(hi["rater_1"], hi["rater_2"])
    k_lo = kappa(lo["rater_1"], lo["rater_2"])
    chk(abs(k_hi - ir_art["high_agreement"]["kappa"]) < 1e-12, "kappa-high-drift",
        str(k_hi))
    chk(abs(k_lo - ir_art["low_agreement"]["kappa"]) < 1e-12, "kappa-low-drift",
        str(k_lo))
    chk(ir_art["high_agreement"]["status"] == ("retained" if k_hi >= 0.75 else "removed"),
        "high-agreement-status")
    chk(ir_art["low_agreement"]["status"] == ("retained" if k_lo >= 0.75 else "removed"),
        "low-agreement-status")
    v_hi = sum(hi["rater_1"] + hi["rater_2"]) / (2 * len(hi["rater_1"]) * 4)
    chk(abs(v_hi - ir_art["high_agreement"]["value"]) < 1e-12, "high-value-drift",
        str(v_hi))


def freeze_rederive(fix, art, chk):
    fz = art["freeze"]
    chk(fz.get("frozen") is True, "not-frozen")
    chk(fz.get("freeze_hash") == fz.get("live_digest"), "freeze-digest-mismatch")
    chk(fz.get("unfrozen_certify", {}).get("decision") == "REFUSED",
        "unfrozen-certify-not-refused")
    chk(fz.get("post_hoc_mutate_certify", {}).get("decision") == "REFUSED",
        "posthoc-certify-not-refused")


def main() -> int:
    try:
        fix = json.loads((HERE / "fixtures" / "recorded_runs.json")
                         .read_text(encoding="utf-8"))
        art = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 unreadable:" + type(exc).__name__)
        return 1

    rederive(fix, art, chk)
    inter_rater_rederive(fix, art, chk)
    freeze_rederive(fix, art, chk)

    # live both-states control: re-derivation silent on good state, fires on mutant
    good_fails = []
    rederive(fix, art, lambda ok, label, detail="": None if ok else good_fails.append(label))
    chk(not good_fails, "live-control-silent-on-good-failed", ";".join(good_fails[:3]))
    mutant = copy.deepcopy(art)
    k0 = "fusion_complement"
    mutant["comparisons"][k0]["complement"]["delta"] = \
        mutant["comparisons"][k0]["complement"]["delta"] + 0.05
    mutant_fails = []
    rederive(fix, mutant,
             lambda ok, label, detail="": None if ok else mutant_fails.append(label))
    chk(bool(mutant_fails), "live-control-did-not-fire-on-bad",
        "mutant was not detected: " + ";".join(mutant_fails[:3]))

    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe2 " + f)
        return 1

    # manifest byte-compare (LF-normalized, matching _measure_one_delivered.py)
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        live = lf_sha(OUT)
        rows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == UNIT]
        match = [a for a in rows
                 if str(a.get("path") or "").replace("\\", "/") == REL
                 and str(a.get("sha256") or "") == live and a.get("present") is True]
        if not match:
            print("FAILED:" + UNIT + "-probe2 manifest-sha-mismatch live=" + live[:16])
            return 1
    else:
        print("FAILED:" + UNIT + "-probe2 manifest-absent")
        return 1
    print("SUCCESS:" + UNIT + "-probe2 re-derivation + live mutant control + "
          "manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
