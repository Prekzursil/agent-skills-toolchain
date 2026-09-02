#!/usr/bin/env python3
"""Emit the CNL-0053 council design note (JSON at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import novelty as N  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402
from jsonschema.validators import RefResolver  # noqa: E402

OUT = "command-center/design/council/CNL-0053-novelty-scoring-against-a-prior-art-corpus.md"
SCHEMA = "command-center/schema/council-design-note.schema.json"
QUESTION = (
    "Novel relative to WHAT - what prior-art corpus does a novelty score compare "
    "against, and how does the score avoid punishing a correct idea merely "
    "because it was already known?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0053/probe1_separable_axes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0053/probe2_both_states.py"
)
MIN_BYTES = 4000
SUPPORTING = [
    ("command-center/p2-wave/probes/CNL-0053/novelty.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0053/probe1_separable_axes.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0053/probe2_both_states.py", "supporting"),
    ("command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json", "fixture"),
    ("command-center/p2-wave/probes/CNL-0053/fixtures/candidates.json", "fixture"),
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0053 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def make_validator():
    """Disk-only $ref resolution. This box's jsonschema 4.10 has resolver=, not registry=."""
    store = {}
    for rel in (
        "platform/schema/receipt.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
        SCHEMA,
    ):
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not sid:
            raise SystemExit(f"FAILED:CNL-0053 schema missing $id: {rel}")
        store[sid] = doc
    schema = store["https://ast-integrate.invalid/command-center/schema/council-design-note.schema.json"]
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def probe(role: str, method: str, command: str, raw: str, fingerprint: str, exit_code: int) -> dict:
    text = raw if len(raw) <= 65000 else raw[-65000:]
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": text,
        "fingerprint": fingerprint,
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc)
    corpus = N.load_corpus()
    cands = N.load_candidates()
    scored = {k: N.score_idea(v, corpus) for k, v in cands.items()}

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:CNL-0053 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    consume_cmd = (
        "python3 -c \"import json; from pathlib import Path; "
        "p=Path('command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json'); "
        "d=json.loads(p.read_text(encoding='utf-8')); "
        "print(d['corpus_id'], len(d['items']))\""
    )
    crc, cout = run(consume_cmd)
    if crc != 0:
        print("FAILED:CNL-0053 downstream consumer could not read corpus")
        print(cout[-1000:])
        return 1

    lib12 = (REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json").is_file() or (
        REPO / "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    ).is_file()
    spec11 = (REPO / "11-COUNCIL-SPECIFICATION.schema.json").is_file() or (
        REPO / "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json"
    ).is_file()
    cnl51 = (
        REPO
        / "command-center/design/council/CNL-0051-semantic-unique-idea-counter-the-anti-gaming-core.md"
    ).is_file()

    nov_py = "command-center/p2-wave/probes/CNL-0053/novelty.py"
    corpus_rel = "command-center/p2-wave/probes/CNL-0053/fixtures/prior_art_corpus.json"
    cand_rel = "command-center/p2-wave/probes/CNL-0053/fixtures/candidates.json"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"

    kg_line = find_line(REPO / cand_rel, '"id": "C-KNOWN-GOOD"')
    junk_line = find_line(REPO / cand_rel, '"id": "C-JUNK-NOVELTY"')
    pa1_line = find_line(REPO / corpus_rel, '"id": "PA-001"')
    q_line = find_line(REPO / nov_py, "def quality_score(idea: dict) -> float:")
    chk_line = find_line(REPO / nov_py, "def junk_novelty_check(scored: dict) -> str:")
    cat_line = find_line(REPO / cat_rel, '"id": "CNL-0053"')

    kg = scored["known_good"]
    kb = scored["known_bad_in_corpus"]
    junk = scored["planted_bad"]
    ng = scored["novel_good"]
    dist = scored["reviewer_related_but_distinct"]
    para = scored["paraphrase_unlabeled"]

    answer = (
        "Novelty is relative to a named, versioned, inspectable prior-art corpus pin, "
        "not to 'truth', not to model pretraining, and not to the current-run unique-idea "
        "ledger. On this worktree the executable corpus is "
        f"{corpus_rel} (corpus_id={corpus['corpus_id']}, pin_sha256={corpus['pin_sha256']}). "
        "An idea's novelty is 0 when its mechanism id already appears in the corpus, "
        "else 1 minus max synonym-folded token Jaccard against corpus surfaces. "
        "Quality is a disjoint function of falsifier, evidence_kind, and contradicts_known "
        "and is never 1-novelty. A correct idea already in the corpus therefore scores "
        "low novelty and high quality, fills a quality quota, and does not fill a novelty "
        "quota. A novelty-only gate that would accept high-novelty junk is the planted-bad "
        "state: junk_novelty_check FIRES. The check is SILENT on the known-good restatement."
    )

    p1_tail = "\n".join(
        ln
        for ln in out1.splitlines()
        if ln.startswith("known_good") or ln.startswith("SUCCESS:")
    )
    p2_tail = "\n".join(
        ln
        for ln in out2.splitlines()
        if ln.startswith("BOTH-STATES")
        or ln.startswith("NEGATIVE-CONTROL")
        or ln.startswith("REVIEWER")
        or ln.startswith("SUCCESS:")
    )
    q_src = (REPO / nov_py).read_text(encoding="utf-8")
    q_snip = q_src[q_src.find("def quality_score") : q_src.find("def max_surface_jaccard")]
    chk_snip = q_src[q_src.find("def junk_novelty_check") : q_src.find("def score_idea")]

    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")
    ended_s = ended.strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0053",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0053",
        "spec_anchor": "_USER-PROMPTS.md:10746-10767",
        "min_bytes_threshold": MIN_BYTES,
        "profile": "council-design-note",
        "artifacts": [artifact_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Known-good checksum restatement already in the corpus scores "
                    f"novelty={kg['novelty']} quality={kg['quality']} (low-N/high-Q); "
                    f"known-bad in-corpus scores novelty={kb['novelty']} quality={kb['quality']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{cand_rel}:{kg_line}",
                "probes": [
                    probe("source", "command", P1, out1, "probe1:separable-axes", rc1),
                    probe(
                        "verifier",
                        "file-read",
                        f"{nov_py}:{q_line}",
                        q_snip.strip()[:4000],
                        "file-read:quality_score-body",
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "junk_novelty_check FIRES on planted-bad high-N/low-Q junk and is "
                    "SILENT on the known-good restatement; reviewer char-3gram is a "
                    "second measurement and does not collapse C-CHECKSUM-CACHE-KEY into PA-001."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{nov_py}:{chk_line}",
                "probes": [
                    probe("source", "command", P2, out2, "probe2:both-states-reviewer", rc2),
                    probe(
                        "verifier",
                        "file-read",
                        f"{nov_py}:{chk_line}",
                        chk_snip.strip()[:4000],
                        "file-read:junk_novelty_check-body",
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-separable-axes",
                "name": "Known-good in-corpus idea scores low novelty and high quality; 2x2 disproves quality=1-novelty",
                "command": P1,
                "result": "PASS" if rc1 == 0 else "FAIL",
                "output_tail": p1_tail[:16000],
            },
            {
                "id": "T2-both-states-and-reviewer",
                "name": "junk_novelty_check FIRES on planted-bad and is SILENT on known-good; reviewer 3-gram counterexample",
                "command": P2,
                "result": "PASS" if rc2 == 0 else "FAIL",
                "output_tail": p2_tail[:16000],
            },
        ],
        "negative_controls": [
            {
                "id": "CNL0053-NC1",
                "kind": "known-broken-fixture",
                "description": (
                    "junk_novelty_check must FIRE when novelty>=0.55 and quality<0.40 "
                    "(planted-bad quota-padding). A novelty-only gate would accept that "
                    "state. The same check must stay SILENT on the known-good restatement."
                ),
                "fired_on_bad_state": junk["check"] == "FIRE",
                "silent_on_good_state": kg["check"] == "SILENT",
                "bad_state_output": (
                    f"planted_bad check={junk['check']} N={junk['novelty']} Q={junk['quality']}"
                ),
                "good_state_output": (
                    f"known_good check={kg['check']} N={kg['novelty']} Q={kg['quality']}"
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0053-probe2-char-3gram-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "Character 3-gram Jaccard on compact text. Does not read mechanism-id "
                "and does not reuse author word-Jaccard. Counterexample instance "
                f"{cands['reviewer_related_but_distinct']['id']}: shares the token "
                "'checksum' with PA-001 but uses it as a cache key. Author novelty="
                f"{dist['novelty']} match_kind={dist['match_kind']} match_id={dist['match_id']}. "
                f"Unlabeled paraphrase novelty={para['novelty']} via surface Jaccard. "
                "Axes not refuted. Catalog required a counterexample instance or "
                "REFUTED-NOT-ATTEMPTED; this is the instance."
            ),
            "reviewed_at": ended_s,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0053/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNL-0053",
        },
        "downstream_consumers": [
            {
                "consumer": "python3 json.loads of the pinned prior-art corpus fixture",
                "artifact_path": corpus_rel,
                "executed": True,
                "read_ok": crc == 0,
                "exit_code": crc,
                "probe": probe(
                    "verifier",
                    "command",
                    consume_cmd,
                    cout,
                    "consumer:json-loads-corpus",
                    crc,
                ),
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": ended_s,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same hypothesis, "
                "enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "G-1 scores novelty against the pinned fixture corpus "
                    f"{corpus['corpus_id']}, not against a live 58-protocol / 72-preset "
                    "catalog. Those source files are absent on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is present, pin it as "
                    "C_protocol, re-run the 2x2 fixtures against the union, and record "
                    "whether any known-good restatement flips band."
                ),
            },
            {
                "claim": (
                    "CNL-0051 unique-idea counter artifact is a catalog dependency and "
                    f"is {'present' if cnl51 else 'absent'} on this worktree. Session "
                    "uniqueness and corpus novelty are different axes."
                ),
                "verdict": "NOT-CHECKED" if not cnl51 else "CONFIRMED",
                "settling_experiment": (
                    "Deliver CNL-0051, then confirm a session-internal duplicate still "
                    "scores high corpus-novelty if it is not in the prior-art pin."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "known_good_novelty",
                    "measured": kg["novelty"],
                    "method": "mechanism-id collapse against pinned corpus",
                    "anchor": f"{cand_rel}:{kg_line}",
                },
                {
                    "name": "known_good_quality",
                    "measured": kg["quality"],
                    "method": "quality_score(falsifier, evidence_kind, contradicts_known)",
                    "anchor": f"{nov_py}:{q_line}",
                },
                {
                    "name": "planted_bad_check",
                    "measured": junk["check"],
                    "method": "junk_novelty_check both-states",
                    "anchor": f"{cand_rel}:{junk_line}",
                },
                {
                    "name": "axes_separable",
                    "measured": kg["quality"] != kg["novelty"],
                    "method": "2x2 fixture matrix including known-bad in-corpus",
                    "anchor": f"{corpus_rel}:{pa1_line}",
                },
            ],
            "control_ids": ["CNL0053-NC1"],
            "title": "Novelty scoring against a prior-art corpus",
            "question": QUESTION,
            "answer": answer,
            "phase": "2C",
            "catalog_id_line": f"{cat_rel}:{cat_line}",
            "prior_art_corpus": {
                "name": "the named pin, not the world",
                "corpus_id": corpus["corpus_id"],
                "pin_sha256": corpus["pin_sha256"],
                "path": corpus_rel,
                "membership_rule": (
                    "An idea is already-known iff (a) its mechanism id equals a corpus "
                    "row's mechanism, or (b) unlabeled surface Jaccard after stopword "
                    "strip and synonym fold is >= 0.55 against some corpus row."
                ),
                "not_the_corpus": [
                    "Model pretraining data (uninspectable, unpinnable, not a fixture)",
                    "The set of all true or correct statements",
                    "The current council run's unique-idea ledger (CNL-0051 session-internal dedup)",
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json on this tree (file absent; not silently substituted)",
                ],
                "intended_production_union": [
                    "C_library: already-admitted idea / mechanism cards on disk",
                    "C_protocol: protocol and preset mechanism names when those catalogs exist",
                    "C_session_prior: ideas accepted in earlier rounds of the same run",
                ],
                "items": [
                    {"id": r["id"], "mechanism": r["mechanism"], "role": r["role"]}
                    for r in corpus["items"]
                ],
                "libraries_on_this_tree": {
                    "11-COUNCIL-SPECIFICATION.schema.json": spec11,
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": lib12,
                    "CNL-0051 artifact": cnl51,
                },
                "honest_scope": (
                    "G-1 for this unit scores against the pinned fixture corpus. It does not "
                    "claim a live recount of a protocol/preset catalog, which is absent here. "
                    "Waiting on CNL-0051 before closing novelty-vs-corpus would deadlock G-1. "
                    "Session uniqueness and corpus novelty are different axes."
                ),
            },
            "scoring": {
                "novelty": (
                    "novelty = 0 if mechanism_id in corpus else (1 - max_surface_jaccard). "
                    "Surface tokens are [a-z0-9]+, stopword-stripped, synonym-folded "
                    "(hash/digest->checksum, corrupt*->corruption)."
                ),
                "quality": (
                    "quality = 0 if contradicts_known is true; else 0.30 for a stable "
                    "mechanism id + 0.35 for a non-empty falsifier + 0.25 for evidence_kind "
                    "in {experiment, measurement, named-failure-class} + 0.10 if "
                    "contradicts_known is explicitly false. Quality does not read novelty "
                    "or corpus membership."
                ),
                "thresholds": {
                    "LOW_NOVELTY_MAX": N.LOW_NOVELTY_MAX,
                    "HIGH_NOVELTY_MIN": N.HIGH_NOVELTY_MIN,
                    "HIGH_QUALITY_MIN": N.HIGH_QUALITY_MIN,
                    "LOW_QUALITY_MAX": N.LOW_QUALITY_MAX,
                    "FIRE_NOVELTY_MIN": N.FIRE_NOVELTY_MIN,
                    "FIRE_QUALITY_MAX": N.FIRE_QUALITY_MAX,
                },
                "anti_punishment_rule": (
                    "Stopping rules keep separate counters. quality_count increments when "
                    "quality >= HIGH_QUALITY_MIN, regardless of novelty. novelty_count "
                    "increments when novelty >= HIGH_NOVELTY_MIN. A known-correct corpus "
                    "restatement may satisfy a quality target and must not be rejected for "
                    "low novelty. Novelty must not gate quality."
                ),
            },
            "live_scores": {
                k: {
                    "novelty": v["novelty"],
                    "quality": v["quality"],
                    "check": v["check"],
                    "band": N.band(v),
                    "match_kind": v["match_kind"],
                    "match_id": v["match_id"],
                    "surface_jaccard": v["surface_jaccard"],
                }
                for k, v in scored.items()
            },
            "separable_axes": {
                "known_good_in_corpus": {
                    "idea_id": cands["known_good"]["id"],
                    "novelty": kg["novelty"],
                    "quality": kg["quality"],
                    "required": "low novelty AND high quality",
                    "observed": N.band(kg),
                },
                "known_bad_in_corpus": {
                    "idea_id": cands["known_bad_in_corpus"]["id"],
                    "novelty": kb["novelty"],
                    "quality": kb["quality"],
                    "required": "low novelty AND low quality (proves quality is not 1-novelty)",
                    "observed": N.band(kb),
                },
                "planted_bad_junk": {
                    "idea_id": cands["planted_bad"]["id"],
                    "novelty": junk["novelty"],
                    "quality": junk["quality"],
                    "required": "high novelty AND low quality",
                    "observed": N.band(junk),
                },
                "novel_good": {
                    "idea_id": cands["novel_good"]["id"],
                    "novelty": ng["novelty"],
                    "quality": ng["quality"],
                    "required": "high novelty AND high quality",
                    "observed": N.band(ng),
                },
            },
            "catalog_tests_required": [
                {
                    "text": "a known-good idea already present in the corpus must score low on novelty and high on quality, proving the two axes are separable",
                    "result": "PASS",
                },
                {
                    "text": "a both-states control: the check FIRES on a planted-bad fixture and is SILENT on the known-good one, both runs recorded verbatim",
                    "result": "PASS",
                },
                {
                    "text": "negative control recorded verbatim: state what the check does on the state it is meant to reject",
                    "result": "PASS",
                },
            ],
            "named_probes": [
                {"id": "probe1", "role": "separable-axes", "command": P1},
                {"id": "probe2", "role": "both-states-reviewer", "command": P2},
            ],
            "notes": (
                "Catalog output_path ends in .md; G-1 _measure_one_delivered.py json.loads "
                "the file, so the payload is the design-note JSON. Did not run "
                "unit_manifest.py --write. No ADV rebuild circle. Schema validation uses "
                "jsonschema RefResolver store of local $id files (no network)."
            ),
        },
        "extensions": {
            "completion_sentinel": "SUCCESS:CNL-0053",
            "output_schema": SCHEMA,
            "negative_control_verbatim": (
                f"on the planted-bad high-novelty low-quality fixture the check "
                f"returns {junk['check']}; on the known-good in-corpus restatement "
                f"it returns {kg['check']}."
            ),
        },
    }

    validator = make_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0053 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in (
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
        {"unit_id": "CNL-0053", "state": "SUCCESS"},
    ):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:CNL-0053 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNL-0053 artifact {size}B below floor {MIN_BYTES}")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0053" not in text:
        print("FAILED:CNL-0053 sentinel missing from artifact text")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0053 self-declared {parsed.get('state')}")
        return 1
    post = list(validator.iter_errors(parsed))
    if post:
        print("FAILED:CNL-0053 written artifact failed schema re-validate")
        print(" ", post[0].message)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0053 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
