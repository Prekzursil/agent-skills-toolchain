"""D1 CLOSE - re-run the 45-pair vendor matrix and report EVERY row.

Why this file exists
-------------------
Wave 3's audit (``command-center/wave3_floor_audit.py`` subcommand ``d1``) proved the D1 false
green was gone: **0 of 24 same-vendor alias pairs are accepted as cross-vendor**. But the fix
OVER-CORRECTED into ``NOT-COMPUTABLE``: three same-vendor rows returned NOT-COMPUTABLE (a
REFUSAL) instead of SAME-VENDOR, because the reviewer's real-world vendor spelling did not
resolve in ``platform/registry/VENDOR-REGISTRY.json``.

This runner imports the audit's OWN ``D1_PAIRS`` table rather than restating it, so the
before/after comparison is against the same 45 rows the audit measured - no re-scoped matrix,
no moved goalposts. It then adds an EXTENDED block whose job is the other direction: prove the
new alias/normalization rules cannot over-fold an unknown or a hosting plane into a vendor.

Terminal states (AGENTS.md section 4): ``SUCCESS:d1-close-matrix`` / ``FAILED:d1-close-matrix``.

Run:
    python command-center/d1_close_matrix.py --out command-center/D1-CLOSE-MATRIX.before.json
    python command-center/d1_close_matrix.py --out command-center/D1-CLOSE-MATRIX.after.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
BUILD = REPO / "platform"
CC = REPO / "command-center"

for _p in (str(BUILD), str(BUILD / "lib"), str(CC)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import completion_predicate as cp  # noqa: E402
import vendor_identity as vi  # noqa: E402
from wave3_floor_audit import D1_PAIRS  # noqa: E402  - the audit's own 45 rows, verbatim

# ---------------------------------------------------------------------------------------------
# EXTENDED rows. Two jobs, both stated so neither can be over-read:
#   SAME  - real-world spellings that MUST now fold (legal-entity suffix, descriptor, punctuation)
#   NC    - the over-fold guard: a suffix/descriptor strip must NEVER invent a vendor identity
# ---------------------------------------------------------------------------------------------
EXTENDED_PAIRS: tuple[tuple[Any, Any, str, str], ...] = (
    # --- legal-entity suffixes (the reported gap) ---
    ("anthropic", "Anthropic PBC", "SAME", "legal-entity suffix PBC"),
    ("anthropic", "Anthropic, PBC", "SAME", "comma punctuation + suffix"),
    ("anthropic", "Anthropic P.B.C.", "SAME", "dotted legal suffix"),
    ("openai", "OpenAI, Inc.", "SAME", "Inc. with comma and period"),
    ("openai", "OpenAI L.L.C.", "SAME", "dotted LLC"),
    ("google", "Google LLC", "SAME", "LLC"),
    ("mistral", "Mistral AI", "SAME", "descriptor AI - the reported gap"),
    ("mistral", "Mistral AI SAS", "SAME", "descriptor + French legal form"),
    ("microsoft", "Microsoft Corporation", "SAME", "Corporation"),
    ("meta", "Meta Platforms, Inc.", "SAME", "full legal name"),
    ("cohere", "Cohere Labs", "SAME", "descriptor Labs"),
    ("alibaba", "Alibaba Cloud Ltd", "SAME", "registered alias + Ltd"),
    ("deepseek", "DeepSeek AI Ltd.", "SAME", "registered alias + descriptor + Ltd"),
    ("xai", "xAI Corp", "SAME", "Corp must not strip xai down to x"),
    ("xai", "x.ai", "SAME", "shipped row - dotted domain still resolves"),
    # --- zero-width / format-character smuggling of ONE identity ---
    ("anthropic", "anthropic\u200b", "SAME", "U+200B ZERO WIDTH SPACE (Cf)"),
    ("anthropic", "anth\u00adropic", "SAME", "U+00AD SOFT HYPHEN mid-token (Cf)"),
    ("anthropic", "\u200eanthropic", "SAME", "U+200E LEFT-TO-RIGHT MARK (Cf)"),
    ("openai", "open\ufeffai", "SAME", "U+FEFF BOM mid-token (Cf)"),
    ("anthropic", "Anthropic\u00a0", "SAME", "U+00A0 NBSP (Zs) - shipped behaviour"),
    # --- OVER-FOLD GUARD: these must stay NOT-COMPUTABLE (a refusal), not become a vendor ---
    ("anthropic", "Acme Inc", "NC", "unknown vendor + suffix stays unknown"),
    ("anthropic", "Acme AI Ltd", "NC", "unknown + descriptor + suffix stays unknown"),
    ("anthropic", "Anthropic Killer Inc", "NC", "a longer name is NOT the vendor"),
    ("anthropic", "Inc", "NC", "a bare legal suffix is not an identity"),
    ("anthropic", "Ltd.", "NC", "a bare legal suffix with a period"),
    ("anthropic", "AI", "NC", "a bare descriptor is not an identity"),
    ("anthropic", "Google Cloud", "NC", "hosting plane: Vertex/GCP also serves Claude"),
    ("anthropic", "AWS Bedrock Inc", "NC", "hosting plane + suffix is still a plane"),
    ("anthropic", "Amazon Web Services", "NC", "the plane, not vendor amazon"),
    ("anthropic", "Azure AI", "NC", "hosting plane + descriptor is still a plane"),
    ("anthropic", "openai-ish", "NC", "near-miss garbage must not resolve"),
    ("anthropic", "!!!", "NC", "punctuation-only garbage must not fold to empty-match"),
    ("anthropic", "...", "NC", "period-only garbage"),
    ("anthropic", "n/a", "NC", "placeholder is not an identity"),
    ("anthropic", "unknown-vendor-inc", "NC", "unknown token that ENDS in a suffix"),
    # --- the good direction must survive: genuine cross-vendor with real-world spellings ---
    ("Anthropic PBC", "OpenAI, Inc.", "CROSS", "both legal names, genuinely distinct"),
    ("Mistral AI", "Cohere Labs", "CROSS", "two descriptor-suffixed vendors"),
    ("anthropic\u200b", "openai", "CROSS", "a Cf char must not block a VALID pair"),
    ("Meta Platforms, Inc.", "Google LLC", "CROSS", "distinct"),
)


def _receipt(exec_vendor: Any, rev_vendor: Any) -> dict[str, Any]:
    """Identical shape to the Wave 3 audit's receipt - only the vendor pair varies."""
    return {
        "produced_by": {"vendor": exec_vendor, "agent_id": "exec-1"},
        "reviewer": {
            "reviewer_id": "rev-1",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev_vendor,
        },
    }


def _opts() -> Any:
    return cp.PredicateOptions(
        repo_root=REPO,
        require_cross_vendor_review=True,
        require_fresh_context_review=False,
    )


def _run_rows(
    pairs: tuple[tuple[Any, ...], ...], registry: Any = None
) -> list[dict[str, Any]]:
    opts = _opts()
    rows: list[dict[str, Any]] = []
    for row in pairs:
        ex, rv, expect = row[0], row[1], row[2]
        why = row[3] if len(row) > 3 else ""
        comparison, cmp_reason, _detail = vi.compare(ex, rv, registry)
        if registry is None:
            outcome, reason, _d = cp._c9_reviewer(_receipt(ex, rv), opts)
            outcome_v, reason_v = outcome.value, reason
        else:  # a mutated-registry control probes the resolver only
            outcome_v, reason_v = "n/a-control", cmp_reason
        passed_as_cross = outcome_v == "SATISFIED"
        if expect == "SAME":
            correct = (not passed_as_cross) and comparison.value == "SAME-VENDOR"
        elif expect == "CROSS":
            correct = passed_as_cross and comparison.value == "CROSS-VENDOR"
        else:
            correct = (not passed_as_cross) and comparison.value == "NOT-COMPUTABLE"
        if (
            registry is not None
        ):  # control: predicate not consulted, judge the resolver alone
            correct = (
                comparison.value
                == {
                    "SAME": "SAME-VENDOR",
                    "CROSS": "CROSS-VENDOR",
                    "NC": "NOT-COMPUTABLE",
                }[expect]
            )
        rows.append(
            {
                "executor": ex if isinstance(ex, str) else repr(ex),
                "reviewer": rv if isinstance(rv, str) else repr(rv),
                "why": why,
                "expected": expect,
                "comparison": comparison.value,
                "predicate_outcome": outcome_v,
                "accepted_as_cross_vendor": passed_as_cross,
                "correct": correct,
                "reason": reason_v[:220],
            }
        )
    return rows


def _tally(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    same = [r for r in rows if r["expected"] == "SAME"]
    cross = [r for r in rows if r["expected"] == "CROSS"]
    nc = [r for r in rows if r["expected"] == "NC"]
    wrong = [r for r in rows if not r["correct"]]
    return {
        "label": label,
        "rows_total": len(rows),
        "same_vendor_rows": len(same),
        "same_vendor_rows_UNSATISFIED_correctly": sum(
            1 for r in same if r["comparison"] == "SAME-VENDOR"
        ),
        "same_vendor_rows_NOT_COMPUTABLE": sum(
            1 for r in same if r["comparison"] == "NOT-COMPUTABLE"
        ),
        "same_vendor_rows_ACCEPTED_as_cross_vendor": sum(
            1 for r in same if r["accepted_as_cross_vendor"]
        ),
        "cross_vendor_rows": len(cross),
        "cross_vendor_rows_SATISFIED": sum(
            1 for r in cross if r["comparison"] == "CROSS-VENDOR"
        ),
        "refusal_rows": len(nc),
        "refusal_rows_blocked": sum(
            1 for r in nc if r["comparison"] == "NOT-COMPUTABLE"
        ),
        "refusal_rows_that_LEAKED": sum(1 for r in nc if r["accepted_as_cross_vendor"]),
        "rows_total_NOT_COMPUTABLE": sum(
            1 for r in rows if r["comparison"] == "NOT-COMPUTABLE"
        ),
        "incorrect_rows": len(wrong),
        "ALL_ROWS_CORRECT": not wrong,
    }


def _mutated_registry(drop: str) -> Any:
    """Load the registry with ONE of the new capabilities removed - the known-broken state."""
    raw = json.loads(vi.REGISTRY_PATH.read_text(encoding="utf-8"))
    if drop == "normalization":
        raw.pop("normalization", None)
        raw["normalization"] = {
            "legal_entity_suffix_tokens": [],
            "descriptor_suffix_tokens": [],
            "domain_suffixes": [],
            "punctuation_folded_to_separator": "",
        }
    elif drop == "new_aliases":
        for entry in raw["identities"]:
            entry["aliases"] = [
                a for a in entry.get("aliases", []) if a not in _NEW_ALIASES
            ]
    # A temp dir, NOT the repo: a deliverable that litters the tree makes the next lane's
    # untracked-file census lie.
    tmpdir = Path(tempfile.mkdtemp(prefix="d1-control-"))
    try:
        tmp = tmpdir / f"registry_{drop}.json"
        tmp.write_text(json.dumps(raw), encoding="utf-8")
        return vi.load_registry(tmp)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


#: Aliases this unit ADDED. Used only by the both-states control, to strip them back out.
_NEW_ALIASES = {
    "anthropic-pbc",
    "mistral-ai",
    "meta-platforms",
    "cohere-labs",
    "amazon-web-services",
}


def _prefix_gate(ex: Any, rv: Any) -> bool:
    """The PRE-FIX D1 gate verbatim. True == accepted as cross-vendor."""
    return str(ex or "") != str(rv or "")


def build() -> dict[str, Any]:
    audit45 = _run_rows(D1_PAIRS)
    extended = _run_rows(EXTENDED_PAIRS)
    combined = audit45 + extended

    # ---- CONTROL 1 (both-states): the pre-fix gate must LEAK the same-vendor rows -----------
    same_rows = [r for r in combined if r["expected"] == "SAME"]
    leaked_by_prefix = [
        r for r in same_rows if _prefix_gate(r["executor"], r["reviewer"])
    ]
    control_prefix = {
        "seeded_defect": "re-implement the pre-fix gate `str(exec or '') != str(rev or '')`",
        "same_vendor_rows": len(same_rows),
        "leaked_by_the_broken_gate": len(leaked_by_prefix),
        "leaked_by_the_shipped_gate": sum(
            1 for r in same_rows if r["accepted_as_cross_vendor"]
        ),
        "probe_FIRED_on_seeded_defect": len(leaked_by_prefix) > 0,
        "probe_silent_on_shipped_code": all(
            not r["accepted_as_cross_vendor"] for r in same_rows
        ),
    }
    control_prefix["both_states_valid"] = (
        control_prefix["probe_FIRED_on_seeded_defect"]
        and control_prefix["probe_silent_on_shipped_code"]
    )

    # ---- CONTROL 2 (both-states): empty the normalization DATA -> the new rows must regress --
    controls_data: dict[str, Any] = {}
    for drop in ("normalization", "new_aliases"):
        try:
            reg = _mutated_registry(drop)
            rows = _run_rows(EXTENDED_PAIRS, reg)
            tally = _tally(rows, f"EXTENDED with {drop} removed")
            controls_data[drop] = {
                "same_vendor_rows_NOT_COMPUTABLE_when_removed": tally[
                    "same_vendor_rows_NOT_COMPUTABLE"
                ],
                "incorrect_rows_when_removed": tally["incorrect_rows"],
                "probe_FIRED_on_seeded_defect": tally["incorrect_rows"] > 0,
                "regressed_rows": [
                    f"{r['executor']!r} vs {r['reviewer']!r} -> {r['comparison']}"
                    for r in rows
                    if not r["correct"]
                ][:20],
            }
        except (
            Exception
        ) as exc:  # a control that cannot run is reported, never swallowed
            controls_data[drop] = {
                "CONTROL_CRASHED": True,
                "error": f"{type(exc).__name__}: {exc}",
                "probe_FIRED_on_seeded_defect": False,
            }

    tally45 = _tally(audit45, "WAVE-3 AUDIT 45-PAIR MATRIX (imported verbatim)")
    tally_ext = _tally(extended, "EXTENDED rows added by this unit")
    tally_all = _tally(combined, "ALL rows")

    ok = (
        tally45["ALL_ROWS_CORRECT"]
        and tally_ext["ALL_ROWS_CORRECT"]
        and control_prefix["both_states_valid"]
        and all(c.get("probe_FIRED_on_seeded_defect") for c in controls_data.values())
    )
    return {
        "unit": "close/d1-registry-gap",
        "registry_id": vi.load_registry().registry_id,
        "resolver_id": vi.RESOLVER_ID,
        "recognized_token_count": len(vi.recognized_tokens()),
        "canonical_id_count": len(vi.canonical_ids()),
        "tally_audit45": tally45,
        "tally_extended": tally_ext,
        "tally_all": tally_all,
        "control_prefix_gate": control_prefix,
        "control_registry_data_removed": controls_data,
        "rows_audit45": audit45,
        "rows_extended": extended,
        "ok": ok,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="path for the JSON result")
    ns = ap.parse_args(argv)
    result = build()
    out = Path(ns.out)
    out.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    for key in ("tally_audit45", "tally_extended", "tally_all"):
        print(json.dumps(result[key], indent=2))
    print(json.dumps(result["control_prefix_gate"], indent=2))
    print(json.dumps(result["control_registry_data_removed"], indent=2))
    bad = [
        r for r in result["rows_audit45"] + result["rows_extended"] if not r["correct"]
    ]
    for r in bad:
        print(
            f"INCORRECT {r['expected']:5s} {r['executor']!r} vs {r['reviewer']!r} "
            f"-> {r['comparison']} ({r['predicate_outcome']})"
        )
    print(f"wrote {out}")
    if result["ok"]:
        print("SUCCESS:d1-close-matrix all rows correct, both-states controls valid")
        return 0
    print(f"FAILED:d1-close-matrix incorrect_rows={len(bad)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
