"""Observational properties of agent-produced JSON artifacts (RES-0091).

These predicates are mechanical. They do not ask whether a claim inside the
artifact is true, insightful, or what the user meant. A property that needed
that judgment is listed in UNTESTABLE, not here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
REAL_ARTIFACT_REL = "command-center/receipts/IMP-0167.json"
TRIALS = 48
UNIT_ID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
CRED_RE = re.compile(
    r"(?:sk-ant-[A-Za-z0-9_-]{16,}"
    r"|sk-proj-[A-Za-z0-9_-]{16,}"
    r"|AKIA[A-Z0-9]{16}"
    r"|ghp_[A-Za-z0-9]{36,}"
    r"|xox[baprs]-[A-Za-z0-9-]{20,}"
    r"|-----BEGIN [A-Z ]{0,40}PRIVATE KEY-----)"
)
# Planted only inside this probe package; never copied into the research record.
PLANTED_CREDENTIAL = "sk-ant-PLANTEDRES0091FAKE0000"
STATES_CLOSED = (
    "SUCCESS",
    "PARTIAL",
    "BLOCKED",
    "FAILED",
    "TIMEOUT",
    "SEVERED",
    "IMPORTED",
)

UNTESTABLE = [
    {
        "id": "U1-semantic-truth-of-claims",
        "name": "Semantic truth of the agent's claims (the model's opinion)",
        "why": (
            "A property 'every evidence.claim is factually true' needs an oracle "
            "the artifact does not contain. Property-based tests quantify over "
            "decidable predicates on inputs (Claessen & Hughes, QuickCheck, ICFP "
            "2000). Asserting claim-truth would be asserting the model's opinion, "
            "which this unit forbids. No known-broken fixture can be built from "
            "bytes alone without smuggling in that oracle."
        ),
    },
    {
        "id": "U2-user-intent-alignment",
        "name": "That the artifact is what the user intended / is maximally helpful",
        "why": (
            "Intent and preference are not observational fields on the byte "
            "string. A 'known-broken' fixture for unhelpfulness is a human "
            "judgment, not a mechanical mutant. Re-running the checker cannot "
            "fail closed on a wrong-intent artifact without that judgment."
        ),
    },
    {
        "id": "U3-live-secret-versus-quoted-fixture",
        "name": "That a credential-shaped token is a live secret rather than a quote",
        "why": (
            "Regex absence is observational. Distinguishing a live key from a "
            "quoted AWS-shaped test fixture requires an oracle (vendor, entropy, "
            "context) the artifact bytes do not carry. That judgment is not a "
            "property-based test."
        ),
    },
]


def canonical(doc: Any) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def schema_validity(doc: Any) -> dict[str, Any]:
    """Structural shape only. state=FAILED is valid; we do not require SUCCESS."""
    reasons: list[str] = []
    if not isinstance(doc, dict):
        return {
            "pass": False,
            "reasons": ["not-a-json-object"],
            "asserts_opinion": False,
        }
    uid = doc.get("unit_id")
    if not isinstance(uid, str) or not UNIT_ID_RE.match(uid):
        reasons.append("unit_id-missing-or-malformed")
    st = doc.get("state")
    if not isinstance(st, str) or not st.strip():
        reasons.append("state-missing-or-not-string")
    elif st not in STATES_CLOSED:
        reasons.append(f"state-not-in-closed-vocab:{st}")
    sent = doc.get("sentinel")
    if sent is not None and not isinstance(sent, str):
        reasons.append("sentinel-not-string")
    return {"pass": not reasons, "reasons": reasons, "asserts_opinion": False}


def rerun_idempotence(producer: Callable[[], Any], repeats: int = 2) -> dict[str, Any]:
    blobs = [canonical(producer()) for _ in range(repeats)]
    stable = len(set(blobs)) == 1
    return {
        "pass": stable,
        "reasons": [] if stable else ["producer-not-byte-stable-across-reruns"],
        "n_distinct": len(set(blobs)),
        "repeats": repeats,
        "asserts_opinion": False,
    }


def file_load_idempotence(path: Path) -> dict[str, Any]:
    first = canonical(load_json(path))
    second = canonical(load_json(path))
    return {
        "pass": first == second,
        "reasons": [] if first == second else ["double-load-canonical-mismatch"],
        "canonical_chars": len(first),
        "asserts_opinion": False,
    }


def credential_absence(blob: str) -> dict[str, Any]:
    hits = CRED_RE.findall(blob)
    return {
        "pass": not hits,
        "reasons": [] if not hits else [f"credential-pattern:{len(hits)}-hit(s)"],
        "hit_count": len(hits),
        "asserts_opinion": False,
    }


def counter_monotonicity(seq: list[int]) -> dict[str, Any]:
    dips = [i for i in range(1, len(seq)) if seq[i] < seq[i - 1]]
    return {
        "pass": not dips,
        "reasons": [] if not dips else [f"non-monotone-at-index:{dips[:8]}"],
        "n": len(seq),
        "dip_count": len(dips),
        "asserts_opinion": False,
    }


def good_receipt(seed: int, state: str = "SUCCESS") -> dict[str, Any]:
    if state == "mix":
        chosen = STATES_CLOSED[seed % len(STATES_CLOSED)]
    else:
        chosen = state
    return {
        "unit_id": "IMP-0167" if seed % 17 == 0 else f"RES-{seed % 10000:04d}",
        "state": chosen,
        "sentinel": f"SUCCESS:RES-{seed % 10000:04d}",
        "payload": {"n": seed % 9, "items": list(range(seed % 5))},
    }


def broken_schema_not_object(_seed: int) -> list[int]:
    return [1, 2, 3]


def broken_schema_bad_unit_id(seed: int) -> dict[str, Any]:
    doc = good_receipt(seed)
    doc["unit_id"] = 91
    return doc


def broken_schema_missing_state(seed: int) -> dict[str, Any]:
    doc = good_receipt(seed)
    del doc["state"]
    return doc


def producer_good(seed: int) -> Callable[[], dict[str, Any]]:
    def _p() -> dict[str, Any]:
        return good_receipt(seed)

    return _p


def producer_broken_time(seed: int) -> Callable[[], dict[str, Any]]:
    n = {"i": 0}

    def _p() -> dict[str, Any]:
        n["i"] += 1
        doc = good_receipt(seed)
        doc["nonce"] = n["i"]
        return doc

    return _p


def mono_good(seed: int, n: int = 8) -> list[int]:
    x = seed % 7
    out: list[int] = []
    for i in range(n):
        x += (seed + i) % 4
        out.append(x)
    return out


def mono_broken(seed: int, n: int = 8) -> list[int]:
    seq = mono_good(seed, n)
    i = 1 + (seed % (n - 1))
    seq[i] = seq[i - 1] - 1 - (seed % 3)
    return seq


def planted_credential_doc(seed: int) -> dict[str, Any]:
    doc = good_receipt(seed)
    doc["note"] = f"token={PLANTED_CREDENTIAL}"
    return doc


def receipts_dir() -> Path:
    return REPO / "command-center" / "receipts"


def real_artifact_path() -> Path:
    return REPO / REAL_ARTIFACT_REL


def scan_receipts_credentials() -> dict[str, Any]:
    """Estate scan is observational only. It does not gate P3.

    P3 is a property of one agent artifact (and inline fixtures). Other
    receipts may quote AWS-shaped test tokens; treating those hits as a
    P3 failure would assert 'live secret' rather than 'pattern present'.
    """
    root = receipts_dir()
    files = sorted(root.glob("*.json")) if root.is_dir() else []
    dirty: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if CRED_RE.search(text):
            dirty.append(path.relative_to(REPO).as_posix())
    return {
        "pass": True,
        "gates_property": False,
        "pattern_hits": dirty,
        "scanned": len(files),
        "dirty": dirty,
        "asserts_opinion": False,
        "note": (
            "Estate-wide regex hits are recorded, not gated. Live-vs-quoted "
            "is U3 (untestable). P3 gates only fixtures plus the subject "
            "artifact."
        ),
    }


def run_property_battery() -> dict[str, Any]:
    """Run implemented properties on fixtures and one real on-disk artifact."""
    real_path = real_artifact_path()
    if not real_path.is_file():
        raise FileNotFoundError(REAL_ARTIFACT_REL)
    real_doc = load_json(real_path)
    real_blob = real_path.read_text(encoding="utf-8")

    schema_good_hits = 0
    schema_broken_hits = 0
    schema_good_fails: list[dict[str, Any]] = []
    schema_broken_passes: list[dict[str, Any]] = []
    for seed in range(TRIALS):
        g = schema_validity(good_receipt(seed, state="mix"))
        if g["pass"]:
            schema_good_hits += 1
        else:
            schema_good_fails.append({"seed": seed, **g})
        mutants = [
            broken_schema_not_object(seed),
            broken_schema_bad_unit_id(seed),
            broken_schema_missing_state(seed),
        ]
        for mutant in mutants:
            b = schema_validity(mutant)
            if not b["pass"]:
                schema_broken_hits += 1
            else:
                schema_broken_passes.append({"seed": seed, **b})

    real_schema = schema_validity(real_doc)
    failed_state_ok = schema_validity(good_receipt(1, state="FAILED"))
    failed_still_valid = failed_state_ok["pass"] is True

    idemp_good = 0
    idemp_broken = 0
    for seed in range(TRIALS):
        if rerun_idempotence(producer_good(seed), repeats=3)["pass"]:
            idemp_good += 1
        if not rerun_idempotence(producer_broken_time(seed), repeats=3)["pass"]:
            idemp_broken += 1
    real_idemp = file_load_idempotence(real_path)

    cred_good = 0
    cred_broken = 0
    for seed in range(TRIALS):
        if credential_absence(canonical(good_receipt(seed)))["pass"]:
            cred_good += 1
        if not credential_absence(canonical(planted_credential_doc(seed)))["pass"]:
            cred_broken += 1
    real_cred = credential_absence(real_blob)
    receipt_scan = scan_receipts_credentials()

    mono_good_n = 0
    mono_broken_n = 0
    sample_good = mono_good(0)
    sample_broken = mono_broken(0)
    for seed in range(TRIALS):
        if counter_monotonicity(mono_good(seed))["pass"]:
            mono_good_n += 1
        if not counter_monotonicity(mono_broken(seed))["pass"]:
            mono_broken_n += 1

    expect_good = TRIALS
    expect_schema_broken = TRIALS * 3
    p_schema = (
        schema_good_hits == expect_good
        and schema_broken_hits == expect_schema_broken
        and real_schema["pass"]
        and failed_still_valid
        and not schema_good_fails
        and not schema_broken_passes
    )
    p_idemp = (
        idemp_good == expect_good
        and idemp_broken == expect_good
        and real_idemp["pass"]
    )
    p_cred = (
        cred_good == expect_good
        and cred_broken == expect_good
        and real_cred["pass"] is True
    )
    p_mono = mono_good_n == expect_good and mono_broken_n == expect_good

    implemented = [
        {
            "id": "P1-schema-validity",
            "name": "Schema validity without requiring SUCCESS",
            "asserts_model_opinion": False,
            "pass": p_schema,
            "both_states": {
                "known_good_pass": schema_good_hits,
                "known_broken_fail": schema_broken_hits,
                "trials_good": expect_good,
                "trials_broken": expect_schema_broken,
                "silent_in_both_states": False,
            },
            "real_artifact": {"path": REAL_ARTIFACT_REL, "result": real_schema},
            "opinion_control": {
                "id": "FAILED-state-still-schema-valid",
                "pass": failed_still_valid,
                "detail": (
                    "A receipt with state=FAILED is schema-valid. Requiring "
                    "state=SUCCESS would assert delivery opinion, not shape."
                ),
            },
        },
        {
            "id": "P2-rerun-idempotence",
            "name": "Idempotence of re-runs (canonical bytes stable)",
            "asserts_model_opinion": False,
            "pass": p_idemp,
            "both_states": {
                "known_good_pass": idemp_good,
                "known_broken_fail": idemp_broken,
                "trials_good": expect_good,
                "trials_broken": expect_good,
                "silent_in_both_states": False,
            },
            "real_artifact": {"path": REAL_ARTIFACT_REL, "result": real_idemp},
        },
        {
            "id": "P3-credential-absence",
            "name": "Absence of a credential in artifact bytes",
            "asserts_model_opinion": False,
            "pass": p_cred,
            "both_states": {
                "known_good_pass": cred_good,
                "known_broken_fail": cred_broken,
                "trials_good": expect_good,
                "trials_broken": expect_good,
                "silent_in_both_states": False,
            },
            "real_artifact": {"path": REAL_ARTIFACT_REL, "result": real_cred},
            "receipts_population": receipt_scan,
            "scope": (
                "inline fixtures plus the subject artifact; estate regex hits "
                "are observational (U3 covers live-vs-quoted)"
            ),
        },
        {
            "id": "P4-counter-monotonicity",
            "name": "Monotonicity of a counter across a revision trace",
            "asserts_model_opinion": False,
            "pass": p_mono,
            "both_states": {
                "known_good_pass": mono_good_n,
                "known_broken_fail": mono_broken_n,
                "trials_good": expect_good,
                "trials_broken": expect_good,
                "silent_in_both_states": False,
                "sample_good": sample_good,
                "sample_broken": sample_broken,
            },
            "note": (
                "Run on generated revision traces (the observational type an "
                "agent artifact can carry). IMP-0167 is a single snapshot, not "
                "a trace, so this property does not pretend to read a history "
                "the file does not contain."
            ),
        },
    ]
    return {
        "unit_id": "RES-0091",
        "trials": TRIALS,
        "all_pass": all(row["pass"] for row in implemented),
        "implemented_count": len(implemented),
        "implemented_properties": implemented,
        "untestable_properties": UNTESTABLE,
        "untestable_count": len(UNTESTABLE),
        "real_artifact": REAL_ARTIFACT_REL,
        "planted_credential_kept_out_of_record": True,
    }
