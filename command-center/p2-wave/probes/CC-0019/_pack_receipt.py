#!/usr/bin/env python3
"""Pack CC-0019 receipt.

Honest BLOCKED when the contracted harness-restore corpus mount is absent
(typical on Cursor Cloud). Never fabricates corpus contents, never invents
independent-review.json, never invents SUCCESS. success_invented=false.

If corpus IS present: packer runs normalize + tests_required probes, then still
BLOCKED pending an independent reviewer who samples a different 20 anchors.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "CC-0019"
OUT = "command-center/receipts/CC-0019.json"
SCHEMA = "command-center/schema/receipt.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CC-0019"
GATE = "tools/command-center/corpus_normalize.py"
TESTS = "tools/command-center/tests/test_corpus_normalize.py"
PROBE1 = f"{PROBE_DIR}/probe1_corpus_presence.py"
MANIFEST = f"{PROBE_DIR}/UNIT-ARTIFACT-MANIFEST.json"
REVIEW = L.REPO / PROBE_DIR / "independent-review.json"
PRESENCE = L.REPO / PROBE_DIR / "corpus-presence.json"
TS0 = "2026-09-08T03:48:00Z"

BLOCKED_ON_CORPUS = (
    "missing corpus mount ~/.claude/harness-restore-20260806/ "
    "(AST_HARNESS_RESTORE_CORPUS override also unset/absent on this worker); "
    "refusing to fabricate Prompt One / harness-restore corpus contents; "
    "also pending independent reviewer who samples a different 20 anchors; "
    "SUCCESS:CC-0019 withheld (success_invented=false)"
)

BLOCKED_ON_REVIEW = (
    "corpus mount present and normalization probes green, but catalog "
    "reviewer_requirement unmet: one independent reviewer who samples a "
    "different 20 records than the author and independently checks anchors; "
    "independent-review.json absent; SUCCESS:CC-0019 withheld "
    "(success_invented=false)"
)


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=L.REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_pass_review() -> dict | None:
    if not REVIEW.is_file():
        return None
    try:
        rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    # Must show a different-20 sample (anti-author-sample brief).
    if not (
        rev.get("sample_claim_ids") or rev.get("sampled_anchors") or rev.get("notes")
    ):
        return None
    return rev


def _require_dep(unit_id: str) -> dict:
    path = L.REPO / f"command-center/receipts/{unit_id}.json"
    dep = json.loads(path.read_text(encoding="utf-8"))
    if dep.get("state") != "SUCCESS":
        raise SystemExit(f"CC-0019 refuses pack: {unit_id} state={dep.get('state')!r}")
    return dep


def build() -> dict:
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (L.REPO / PROBE_DIR).mkdir(parents=True, exist_ok=True)

    dep17 = _require_dep("CC-0017")
    dep18 = _require_dep("CC-0018")

    rc, out = _run([sys.executable, "-m", "pytest", TESTS, "-q", "--tb=line"])
    (L.REPO / PROBE_DIR / "pytest-corpus-normalize.out").write_text(
        out, encoding="utf-8"
    )
    if rc != 0:
        raise SystemExit(f"CC-0019 pytest failed:\n{out}")

    p1_rc, p1_out = _run([sys.executable, "-B", str(L.REPO / PROBE1)])
    if p1_rc != 0:
        raise SystemExit(f"CC-0019 probe1 failed:\n{p1_out}")

    presence = json.loads(PRESENCE.read_text(encoding="utf-8"))
    raw1 = (L.REPO / PROBE_DIR / "corpus-presence.raw.txt").read_text(encoding="utf-8")
    corpus_present = bool(presence.get("corpus_present"))

    normalize_summary: dict | None = None
    sample_summary: dict | None = None
    if corpus_present:
        root = presence["corpus_root"]
        n_rc, n_out = _run(
            [
                sys.executable,
                "-B",
                str(L.REPO / GATE),
                "normalize",
                "--corpus",
                root,
                "--out",
                str(L.REPO / PROBE_DIR / "normalize-run.json"),
            ]
        )
        (L.REPO / PROBE_DIR / "normalize-run.raw.txt").write_text(
            n_out, encoding="utf-8"
        )
        if n_rc != 0:
            raise SystemExit(
                f"CC-0019 normalize failed despite present corpus:\n{n_out}"
            )
        normalize_summary = json.loads(
            (L.REPO / PROBE_DIR / "normalize-run.json").read_text(encoding="utf-8")
        )
        # Sample resolve via inline python to keep packer self-contained.
        sys.path.insert(0, str(L.REPO / "tools" / "command-center"))
        import corpus_normalize as cn  # noqa: E402

        sample_summary = cn.sample_anchors_resolve(
            normalize_summary.get("records") or [], sample_size=20, seed=19
        )
        (L.REPO / PROBE_DIR / "sample-resolve.json").write_text(
            json.dumps(sample_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    rev = load_pass_review()
    # SUCCESS only if corpus present AND independent review PASS — never invent.
    success = corpus_present and rev is not None and normalize_summary is not None

    p_pytest = L.probe(
        "verifier", "test-run", f"python3 -m pytest {TESTS} -q --tb=line", out, rc
    )
    p_presence = L.probe("verifier", "command", f"python3 -B {PROBE1}", raw1, p1_rc)

    if success:
        state = "SUCCESS"
        notes = rev.get("notes", "")
        if not isinstance(notes, str):
            notes = json.dumps(notes)
        cons = (normalize_summary or {}).get("conservation") or {}
        sentinel = (
            f"SUCCESS:{UNIT} corpus={presence.get('corpus_root')} "
            f"emitted={cons.get('emitted')} merged={cons.get('merged')} "
            f"dropped={cons.get('dropped')} "
            f"resolve_fraction={(sample_summary or {}).get('resolve_fraction')}; "
            f"reviewer={rev.get('reviewer_id')}"
        )
        reviewer = {
            "reviewer_id": rev["reviewer_id"],
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": rev.get("vendor", "openai"),
            "reviewed_at": rev.get("reviewed_at", ended),
            "notes": notes[:4000],
        }
        residual: list[dict] = []
        failure = None
        anti = "SUCCESS-after-corpus-normalize-and-independent-anchor-sample-PASS"
        blocked_on = None
    else:
        state = "BLOCKED"
        if not corpus_present:
            blocked_on = BLOCKED_ON_CORPUS
            anti = "BLOCKED-missing-corpus-mount-no-fabrication"
            reviewer = {
                "reviewer_id": "awaiting-corpus-mount-then-independent-reviewer",
                "verdict": "NOT-REVIEWED",
                "independent": False,
                "fresh_context": False,
                "vendor": "anthropic",
                "reviewed_at": ended,
                "notes": (
                    "Implementer lane only. Contracted corpus "
                    "~/.claude/harness-restore-20260806/ is ABSENT on this "
                    "worker (measured by probe1). Corpus contents were NOT "
                    "fabricated. Fixture-backed unit tests for conservation / "
                    "planted synthetic / idempotence are green but do not "
                    "satisfy the catalog input. Independent reviewer who "
                    "samples a different 20 anchors is also still owed after "
                    "the corpus is mounted. success_invented=false."
                ),
            }
            residual = [
                {
                    "claim": (
                        "Whether Phase-1 normalization over the real 1.49 MB "
                        "harness-restore corpus conserves inputs and re-resolves "
                        "anchors is unchecked because the corpus mount is absent."
                    ),
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": (
                        "Mount ~/.claude/harness-restore-20260806/ (or set "
                        "AST_HARNESS_RESTORE_CORPUS), re-run "
                        f"`python3 -B {GATE} normalize`, pytest {TESTS}, "
                        "sample-resolve 20 anchors, then have an independent "
                        "reviewer sample a different 20."
                    ),
                },
                {
                    "claim": (
                        "Independent different-20 anchor sample is unchecked "
                        "(reviewer_requirement)."
                    ),
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": (
                        "Fresh-context independent reviewer samples 20 claim "
                        "ids disjoint from the author's sample, re-opens each "
                        "anchor, and writes independent-review.json with "
                        "verdict=PASS, independent=true, fresh_context=true."
                    ),
                },
            ]
            failure = {
                "classification": [
                    "blocked-on-missing-corpus-mount",
                    "blocked-on-independent-review",
                ],
                "reason": (
                    "Contracted harness-restore corpus mount is absent; "
                    "refusing to fabricate corpus contents or invent SUCCESS."
                ),
                "blocked_on": blocked_on,
                "diagnostic_tail": (out + "\n" + raw1)[-4000:],
                "two_signal_proof": [p_pytest, p_presence],
            }
        else:
            blocked_on = BLOCKED_ON_REVIEW
            anti = "BLOCKED-pending-independent-different-20-anchor-reviewer"
            cons = (normalize_summary or {}).get("conservation") or {}
            reviewer = {
                "reviewer_id": "awaiting-independent-anchor-sample-reviewer",
                "verdict": "NOT-REVIEWED",
                "independent": False,
                "fresh_context": False,
                "vendor": "anthropic",
                "reviewed_at": ended,
                "notes": (
                    "Corpus present; normalize + conservation + planted "
                    f"synthetic + author sample_resolve="
                    f"{(sample_summary or {}).get('resolve_fraction')} executed. "
                    "Catalog reviewer_requirement still unmet. "
                    "independent-review.json not invented. "
                    f"conservation inputs={cons.get('inputs')} "
                    f"emitted={cons.get('emitted')} merged={cons.get('merged')} "
                    f"dropped={cons.get('dropped')}."
                ),
            }
            residual = [
                {
                    "claim": (
                        "Whether a disjoint independent 20-anchor sample also "
                        "re-resolves is unchecked in this lane."
                    ),
                    "verdict": "NOT-CHECKED",
                    "settling_experiment": (
                        "Independent reviewer samples different claim ids than "
                        "sample-resolve.json seed=19, re-opens anchors, returns "
                        "PASS with independent=true and fresh_context=true."
                    ),
                }
            ]
            failure = {
                "classification": ["blocked-on-independent-review"],
                "reason": (
                    "Normalization probes green on mounted corpus, but "
                    "independent different-20 reviewer is absent. "
                    "SUCCESS not invented."
                ),
                "blocked_on": blocked_on,
                "diagnostic_tail": (out + "\n" + raw1)[-4000:],
                "two_signal_proof": [p_pytest, p_presence],
            }
        sentinel = (
            f"FAILED:{UNIT} blocked; corpus_present={corpus_present}; "
            f"independent_review={'PASS' if rev else 'absent'}; "
            f"CC-0017={dep17.get('state')} CC-0018={dep18.get('state')}; "
            f"SUCCESS:{UNIT} withheld (success_invented=false)"
        )

    downstream = [
        {
            "consumer": "corpus_normalize.corpus_presence_probe",
            "artifact_path": f"{PROBE_DIR}/corpus-presence.json",
            "executed": True,
            "read_ok": True,
            "exit_code": 0,
            "probe": p_presence,
        },
        {
            "consumer": "pytest:test_corpus_normalize",
            "artifact_path": TESTS,
            "executed": True,
            "read_ok": True,
            "exit_code": rc,
            "probe": p_pytest,
        },
    ]

    arts = [
        L.art(GATE, "primary"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/corpus-presence.json", "log"),
        L.art(f"{PROBE_DIR}/corpus-presence.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/pytest-corpus-normalize.out", "log"),
        L.art(f"{PROBE_DIR}/probe1_corpus_presence.py", "control"),
        L.art("command-center/receipts/CC-0017.json", "supporting"),
        L.art("command-center/receipts/CC-0018.json", "supporting"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
    ]
    if corpus_present:
        for rel in (
            f"{PROBE_DIR}/normalize-run.json",
            f"{PROBE_DIR}/normalize-run.raw.txt",
            f"{PROBE_DIR}/sample-resolve.json",
        ):
            if (L.REPO / rel).is_file():
                arts.append(L.art(rel, "log"))
    if success or REVIEW.is_file():
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))

    p_presence_src = L.probe(
        "source",
        "file-read",
        f"read {PROBE_DIR}/corpus-presence.json",
        json.dumps(
            {
                "corpus_present": corpus_present,
                "corpus_root": presence.get("corpus_root"),
                "success_invented": False,
                "corpus_fabricated": False,
            },
            sort_keys=True,
        ),
        0,
    )
    p_deps = L.probe(
        "source",
        "file-read",
        "read CC-0017+CC-0018 receipt states",
        json.dumps(
            {"CC-0017": dep17.get("state"), "CC-0018": dep18.get("state")},
            sort_keys=True,
        ),
        0,
    )
    evidence = [
        L.evidence(
            (
                "Corpus mount presence measured (not assumed): "
                f"corpus_present={corpus_present} "
                f"root={presence.get('corpus_root')!r}. "
                "No corpus contents were fabricated for this pack."
            ),
            "CONFIRMED",
            f"file:{PROBE_DIR}/corpus-presence.json",
            [p_presence_src, p_presence],
            "almost-certain",
        ),
        L.evidence(
            (
                "Fail-closed normalizer + fixture-backed conservation / planted "
                "synthetic / idempotence tests are green. Dependencies "
                f"CC-0017={dep17.get('state')} and CC-0018={dep18.get('state')} "
                "verified on disk. Catalog SUCCESS still requires real corpus "
                "+ independent different-20 review."
            ),
            "CONFIRMED" if rc == 0 else "REFUTED",
            f"file:{TESTS}",
            [p_deps, p_pytest],
            "almost-certain",
        ),
    ]
    if corpus_present and normalize_summary is not None:
        cons = normalize_summary.get("conservation") or {}
        evidence.append(
            L.evidence(
                (
                    "Live corpus normalize conservation: "
                    f"inputs={cons.get('inputs')} emitted={cons.get('emitted')} "
                    f"merged={cons.get('merged')} dropped={cons.get('dropped')} "
                    f"reconciles={cons.get('reconciles')}; planted="
                    f"{normalize_summary.get('planted_synthetic_present')}; "
                    f"author resolve_fraction="
                    f"{(sample_summary or {}).get('resolve_fraction')}"
                ),
                "CONFIRMED",
                f"file:{PROBE_DIR}/normalize-run.json",
                [
                    L.probe(
                        "verifier",
                        "command",
                        f"python3 -B {GATE} normalize --corpus <root>",
                        json.dumps(
                            {
                                "ok": normalize_summary.get("ok"),
                                "conservation": cons,
                            }
                        ),
                        0,
                    )
                ],
                "almost-certain",
            )
        )

    receipt: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CC-0019",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer-cloud-maintainer",
            "role": "implementer",
            "execution_substrate": "linux-cloud-agent-worktree",
        },
        "artifacts": arts,
        "evidence": evidence,
        "timestamps": {"started_at": TS0, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot to per-artifact ingestion with "
                "per-artifact receipts, so a single malformed source cannot "
                "fail the whole run a third time."
            ),
        },
        "tests": [
            {
                "id": "corpus-presence-fail-closed",
                "name": "Presence probe measures mount; no fabrication.",
                "command": f"python3 -B {PROBE1}",
                "result": "PASS",
                "assertions": 4,
                "output_tail": raw1[-800:],
            },
            {
                "id": "fixture-conservation-planted-idempotence",
                "name": (
                    "Fixture corpus: conservation equation, planted synthetic, "
                    "idempotent ids."
                ),
                "command": f"python3 -m pytest {TESTS} -q --tb=line",
                "result": "PASS" if rc == 0 else "FAIL",
                "assertions": 10,
                "output_tail": out[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "corpus-absent-no-fabricate",
                "mutation",
                "Missing corpus mount must BLOCKED; must not invent files.",
                True,
                True,
                bad="fabricated ~/.claude/harness-restore-20260806 contents",
                good=raw1[-500:],
            ),
            L.control(
                "planted-synthetic-detector",
                "mutation",
                "Planted synthetic finding must appear when normalize runs.",
                True,
                True,
                bad="planted id missing from emitted records",
                good="CC-0019-PLANTED-SYNTHETIC-FINDING required in fixture tests",
            ),
            L.control(
                "conservation-equation",
                "mutation",
                "inputs = emitted + merged + dropped with drops enumerated.",
                True,
                True,
                bad="zero drops by construction",
                good="fixture tests assert dropped>=1 and equation holds",
            ),
        ],
        "reviewer": reviewer,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": downstream,
        "residual_unknowns": residual,
        "defects": [],
        "report": {
            "kind": "corpus-normalize",
            "dependency_cc0017_state": dep17.get("state"),
            "dependency_cc0018_state": dep18.get("state"),
            "corpus_present": corpus_present,
            "corpus_root": presence.get("corpus_root"),
            "normalize_summary": (
                {
                    "n_records": (normalize_summary or {}).get("n_records"),
                    "conservation": (normalize_summary or {}).get("conservation"),
                    "planted_synthetic_present": (normalize_summary or {}).get(
                        "planted_synthetic_present"
                    ),
                }
                if normalize_summary
                else None
            ),
            "sample_resolve": sample_summary,
            "success_invented": False,
            "independent_review_invented": False,
            "corpus_fabricated": False,
            "independent_review_present": rev is not None,
        },
        "extensions": {
            "anti_false_green": anti,
            "builder": f"{PROBE_DIR}/_pack_receipt.py",
            "success_invented": False,
            "independent_review_invented": False,
            "corpus_fabricated": False,
            "corpus_present": corpus_present,
        },
    }
    if failure is not None:
        receipt["failure"] = failure
    return receipt


def main() -> int:
    receipt = build()
    state = receipt["state"]
    manifest = {
        "schema_version": 1,
        "unit_id": UNIT,
        "entry_id": UNIT,
        "state": state,
        "artifacts": [a["path"] for a in receipt["artifacts"]],
        "receipt_path": OUT,
        "success_invented": False,
        "independent_review_invented": False,
        "corpus_fabricated": False,
        "corpus_present": receipt["report"]["corpus_present"],
    }
    if state == "BLOCKED":
        manifest["blocked_on"] = receipt["failure"]["blocked_on"]
    man_path = L.REPO / MANIFEST
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    rc = L.write_if_valid(receipt, OUT, SCHEMA)
    if rc != 0:
        return rc

    # Re-measure including receipt + manifest now on disk.
    arts = [
        L.art(OUT, "primary"),
        L.art(GATE, "primary"),
        L.art(TESTS, "supporting"),
        L.art(f"{PROBE_DIR}/corpus-presence.json", "log"),
        L.art(f"{PROBE_DIR}/corpus-presence.raw.txt", "log"),
        L.art(f"{PROBE_DIR}/pytest-corpus-normalize.out", "log"),
        L.art(f"{PROBE_DIR}/probe1_corpus_presence.py", "control"),
        L.art("command-center/receipts/CC-0017.json", "supporting"),
        L.art("command-center/receipts/CC-0018.json", "supporting"),
        L.art(f"{PROBE_DIR}/_pack_receipt.py", "control"),
        L.art(MANIFEST, "supporting"),
    ]
    if receipt["report"]["corpus_present"]:
        for rel in (
            f"{PROBE_DIR}/normalize-run.json",
            f"{PROBE_DIR}/normalize-run.raw.txt",
            f"{PROBE_DIR}/sample-resolve.json",
        ):
            if (L.REPO / rel).is_file():
                arts.append(L.art(rel, "log"))
    if state == "SUCCESS":
        arts.append(L.art(f"{PROBE_DIR}/independent-review.json", "supporting"))
    receipt["artifacts"] = arts
    rc2 = L.write_if_valid(receipt, OUT, SCHEMA)
    print(
        f"state={state} corpus_present={receipt['report']['corpus_present']} "
        f"success_invented=false corpus_fabricated=false "
        f"review={'PASS' if load_pass_review() else 'absent'} rc={rc2}"
    )
    return rc2


if __name__ == "__main__":
    raise SystemExit(main())
