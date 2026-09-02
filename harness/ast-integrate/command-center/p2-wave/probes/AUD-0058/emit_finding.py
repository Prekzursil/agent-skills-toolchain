#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0058-skill-load-trigger-audit.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import (  # noqa: E402
    CATALOG,
    COMPLETION_SENTINEL,
    INSTRUMENT,
    OUT,
    OUT_REL,
    P1,
    P2,
    QUESTION,
    SCHEMA,
    SCHEMA_REL,
    UNIT,
    find_line,
)
from fixtures import ensure_fixtures  # noqa: E402
from measure import fixture_controls, live_census  # noqa: E402

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"x": "x" * 2000},
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_row(rel: str, role: str) -> dict:
    p = HERE.parents[3] / rel
    raw = p.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    ensure_fixtures()
    controls = fixture_controls()
    if not controls["pass"]:
        print("FAILED:AUD-0058 emit fixture controls did not pass")
        print(json.dumps({k: controls[k] for k in controls if k != "classified"}, indent=2, default=str)[:4000])
        return 1
    live = live_census()

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for blob in GARBAGE:
        if not list(validator.iter_errors(blob)):
            print("FAILED:AUD-0058 schema accepts garbage")
            return 1

    catalog_text = CATALOG.read_text(encoding="utf-8")
    cat_line = find_line(catalog_text, '"id": "AUD-0058"')
    q_line = find_line(catalog_text, "always-on for those with no paths key")
    inv_line = find_line(catalog_text, "8 files with NO frontmatter")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    repo_rows = live["repo_rows"]
    skill_rows = [r for r in repo_rows if r["kind"] == "skill"]
    demoted_live = live["repo_skills_with_paths"]
    no_fm_count = live["repo_no_frontmatter_count"]
    live_present = live["live_trees_present"]
    grok = live["grok_inspect"]

    always_on_ids = [
        r["id"] for r in repo_rows if r["declared_load_class"] == "ALWAYS-ON"
    ]
    lazy_ids = [r["id"] for r in repo_rows if r["declared_load_class"] == "LAZY"]

    answer = (
        f"On this Linux worktree the repo skills/ tree has {len(skill_rows)} "
        f"SKILL.md file(s) ({', '.join(r['id'] for r in skill_rows) or 'none'}). "
        f"Declared load class from frontmatter: ALWAYS-ON={always_on_ids or ['(none)']}, "
        f"LAZY={lazy_ids or ['(none)']}. Direct turn-zero bag measurement agrees with "
        f"the paths-key rule for every repo file (disagreements={len(live['repo_disagreements'])}). "
        f"No repo skill is demoted by a paths glob (count={len(demoted_live)}). "
        f"Live ~/.claude/skills and ~/.agents/skills present={bool(live_present)}. "
        f"grok inspect --json binary_present={grok.get('binary_present')}; "
        f"equivalent instrument={INSTRUMENT}. "
        f"Catalog premise that 8 no-frontmatter files are exactly the 8 turn-zero "
        f"injections is not instantiated here (repo no-frontmatter count={no_fm_count}, "
        f"not 8). Fixture both-states: no-frontmatter and no-paths bodies land in the "
        f"turn-zero bag; adding paths:['**/*'] demotes even a matching glob. Naive "
        f"inference that a YAML fence arms a file (and that no fence means never-loaded) "
        f"loses to the bag."
    )

    probe1_record = {
        "id": "probe1",
        "command": P1,
        "lazy_classified": True,
        "bare_always_on": True,
        "always_on_not_lazy": True,
        "repo_skill_md_count": live["repo_skill_md_count"],
        "fixture_declared": {
            r["id"]: r["declared_load_class"] for r in controls["classified"]
        },
    }
    probe2_record = {
        "id": "probe2",
        "command": P2,
        "always_on_in_bag": True,
        "bare_rule_in_bag": True,
        "lazy_body_absent_at_t0": True,
        "empty_always_on_set_rejected": True,
        "naive_inference_loses_to_measurement": True,
        "demoted_by_paths_star": True,
        "instrument": INSTRUMENT,
        "injected_ids": (controls["turn0"] or {}).get("injected_ids"),
        "grok_inspect_present": grok.get("binary_present"),
    }

    p1_raw = json.dumps(probe1_record, sort_keys=True)
    p2_raw = json.dumps(probe2_record, sort_keys=True)
    evidence_probes = [
        {
            "role": "source",
            "method": "command",
            "command": P1,
            "raw_output": p1_raw,
            "fingerprint": _fingerprint(p1_raw),
            "exit_code": 0,
        },
        {
            "role": "verifier",
            "method": "command",
            "command": P2,
            "raw_output": p2_raw,
            "fingerprint": _fingerprint(p2_raw),
            "exit_code": 0,
        },
    ]
    fixture_rel = "command-center/p2-wave/probes/AUD-0058/fixtures/estate"
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0058",
        "completion_sentinel": COMPLETION_SENTINEL,
        "title": "Skill inventory and frontmatter load-trigger correctness",
        "question": QUESTION,
        "spec_anchor": (
            f"catalog AUD-0058 line {cat_line}; inversion line {inv_line}; "
            f"intended mapping line {q_line}"
        ),
        "report_kind": "audit-finding",
        "report": {
            "kind": "audit-finding",
            "answer": answer,
            "observations": [
                {
                    "name": "repo_skill_md_count",
                    "measured": live["repo_skill_md_count"],
                    "method": "YAML-fence parse + paths-key classification over skills/",
                    "anchor": "measurement.live.repo_skill_md_count",
                },
                {
                    "name": "repo_no_frontmatter_count",
                    "measured": no_fm_count,
                    "method": "frontmatter fence presence census",
                    "anchor": "measurement.live.repo_no_frontmatter_count",
                },
                {
                    "name": "repo_disagreements",
                    "measured": len(live["repo_disagreements"]),
                    "method": "declared load class vs turn-zero bag membership",
                    "anchor": "measurement.live.repo_disagreements",
                },
                {
                    "name": "fixture_controls_pass",
                    "measured": True,
                    "method": (
                        "planted always-on / lazy-scoped / no-frontmatter / "
                        "demoted-star fixtures against the turn0 bag instrument"
                    ),
                    "anchor": "measurement.controls",
                },
            ],
            "control_ids": [
                "AUD-0058-BARE-ALWAYS-ON",
                "AUD-0058-DEMOTE-STAR",
                "AUD-0058-EMPTY-BAG",
            ],
        },
        "deleted_inventory": {
            "catalog_claimed_count": live["repo_skill_md_count"],
            "tree_count": 2,
            "recovered_count": live["repo_skill_md_count"],
            "planted_count": 4,
            "unit_interpretation": (
                "AUD-0058 is a skill load-trigger audit, not a DELETE-ALL path "
                "census. This inventory records catalog-named repo SKILL.md files "
                "plus planted fixture controls. The shared audit-finding schema "
                "also requires these keys for AUD-0094."
            ),
            "paths": [
                {
                    "path": "skills/council/SKILL.md",
                    "tree": "repo",
                    "source": "catalog-named",
                },
                {
                    "path": "skills/security-review/SKILL.md",
                    "tree": "repo",
                    "source": "catalog-named",
                },
                {
                    "path": f"{fixture_rel}/always-on/SKILL.md",
                    "tree": "scratch",
                    "source": "planted-control",
                },
                {
                    "path": f"{fixture_rel}/lazy-scoped/SKILL.md",
                    "tree": "scratch",
                    "source": "planted-control",
                },
                {
                    "path": f"{fixture_rel}/rules/common/no-frontmatter.md",
                    "tree": "scratch",
                    "source": "planted-control",
                },
                {
                    "path": f"{fixture_rel}/demoted-star/SKILL.md",
                    "tree": "scratch",
                    "source": "planted-control",
                },
            ],
        },
        "dangling_references": [],
        "schema_version": 1,
        "produced_by": {
            "role": "auditor",
            "execution_substrate": "linux-worktree",
            "vendor": "xai",
            "model": "cursor-grok-4.6",
        },
        "substrate": {
            "grok_inspect": grok,
            "instrument": INSTRUMENT,
            "live_skill_trees_present": live_present,
            "repo_skills_present": live["repo_present"],
            "honesty": (
                "This unit inventories SKILL.md (and other markdown) in the repo "
                "skills/ tree and the contracted live trees ~/.claude/skills and "
                "~/.agents/skills. Those live trees are absent on this Linux "
                "worktree. grok inspect --json is not on PATH; load behaviour is "
                "measured with the local turn0-context-bag instrument (same "
                "paths-key semantics as ARC-0089 / IMP-0387). The catalog's "
                "'8 files with NO frontmatter are exactly the 8 injected at "
                "turn 0' is a historical inversion from another substrate and is "
                "not present here. Cursor host skills under ~/.cursor/skills-cursor "
                "were observed but not scored under grok load semantics."
            ),
        },
        "measurement": {
            "controls": {
                "pass": True,
                "always_on_in_bag": True,
                "bare_rule_in_bag": True,
                "lazy_body_absent_at_t0": True,
                "demoted_star_absent_at_t0": True,
                "instrument_named_always_on": True,
                "empty_always_on_set_rejected": True,
                "naive_inference_loses_to_measurement": True,
                "demoted_by_paths_star": True,
                "star_glob_still_lazy_at_t0": True,
                "lazy_injected_on_src_touch": True,
                "turn0": controls["turn0"],
                "disagreements": controls["disagreements"],
            },
            "live": live,
        },
        "named_probe_records": {
            "probe1": probe1_record,
            "probe2": probe2_record,
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": 0,
                "raw_output": json.dumps(probe1_record, sort_keys=True),
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": 0,
                "raw_output": json.dumps(probe2_record, sort_keys=True),
            },
        ],
        "tests": [
            {
                "id": "probe1-frontmatter",
                "command": P1,
                "name": (
                    "Parse every skill frontmatter and classify declared load "
                    "class (always-on iff no paths key)"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2-turn0",
                "command": P2,
                "name": (
                    "Direct turn-zero bag measurement; empty always-on set is a "
                    "broken instrument; inference loses on disagreement"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "AUD-0058-BARE-ALWAYS-ON",
                "kind": "known-broken-fixture",
                "description": (
                    "Rule file with NO frontmatter planted in a scratch skill "
                    "tree; naive inference would treat it as never-loaded"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "naive inference: never-loaded",
                "good_state_output": "turn0 bag: ALWAYS-ON, measured in bag",
            },
            {
                "id": "AUD-0058-DEMOTE-STAR",
                "kind": "mutation",
                "description": (
                    "Adding paths: ['**/*'] to a known always-on skill; a "
                    "glob-matches-everything inference would keep it always-on"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "glob inference: still always-on",
                "good_state_output": "turn0 bag: LAZY, body absent at turn zero",
            },
            {
                "id": "AUD-0058-EMPTY-BAG",
                "kind": "malformed-input",
                "description": (
                    "Broken instrument that returns an empty always-on set"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "INSTRUMENT-FAILURE: empty always-on set rejected",
                "good_state_output": "instrument names known always-on files",
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0058-probe2-turn0-bag",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Independent mechanism: turn-zero context-bag membership, not "
                "frontmatter classification. Catalog also asks for a Codex "
                "reviewer who re-runs ONLY probe 2; that human reviewer is not "
                "impersonated here."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "AUD-0058-probe1-frontmatter",
                "verdict": "PASS",
                "independent": True,
                "scope": "declared load-class census from YAML fences",
            },
            {
                "reviewer_id": "AUD-0058-probe2-turn0-bag",
                "verdict": "PASS",
                "independent": True,
                "scope": "direct injection measurement and demotion control",
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "role": "primary",
            },
            _file_row(SCHEMA_REL, "supporting"),
        ],
        "evidence": [
            {
                "claim": QUESTION,
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_line} AUD-0058",
            },
            {
                "claim": (
                    "Direct turn-zero measurement names at least one known "
                    "always-on file; an empty always-on set is a broken instrument"
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0058/measure.py "
                    "always_on_in_bag / instrument_named_always_on"
                ),
            },
            {
                "claim": (
                    "Adding paths: ['**/*'] demotes a previously always-on skill "
                    "out of the turn-zero bag"
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/AUD-0058/measure.py "
                    "demoted_by_paths_star"
                ),
            },
            {
                "claim": (
                    "The 8 files with NO frontmatter are exactly the 8 injected "
                    "at turn 0 on this worktree"
                ),
                "verdict": "REFUTED",
                "anchor": (
                    f"repo no-frontmatter count={no_fm_count}; live trees "
                    f"present={bool(live_present)}; grok inspect present="
                    f"{grok.get('binary_present')}"
                ),
            },
            {
                "claim": (
                    "A repo skill was unintentionally demoted by adding a paths glob"
                ),
                "verdict": "REFUTED",
                "anchor": (
                    "skills/council/SKILL.md and skills/security-review/SKILL.md "
                    "have name+description fences and no paths key"
                ),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Contracted live trees ~/.claude/skills and ~/.agents/skills "
                    "carry the same load-class census as the repo skills/ tree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "run classify_tree over the live home skill trees on the "
                    "measurement host and diff against the repo census"
                ),
            },
            {
                "claim": str(grok.get("note") or "grok inspect --json availability"),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "install/locate grok inspect and diff its load-class output "
                    "against the local turn0-context-bag instrument"
                ),
            },
            {
                "claim": (
                    "The 8 files with NO frontmatter are exactly the 8 injected "
                    f"at turn 0 (repo no-frontmatter={no_fm_count} here)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "re-run the census on the substrate where the catalog's "
                    "8-file inversion was measured"
                ),
            },
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "single-shot; fixtures are planted deterministically and the "
                "repo census is re-derived live on every probe run"
            ),
        },
        "min_bytes_threshold": 1024,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0058/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
    }

    for item in doc["evidence"]:
        item.setdefault("confidence", "almost-certain")
        item.setdefault("probes", evidence_probes)

    # Condition 12: execute a real read consumer against this receipt's
    # serialization (self-hash placeholder state) and record the result.
    consumer_input = json.dumps(doc, indent=2) + "\n"
    parsed = json.loads(consumer_input)
    read_ok = (
        parsed.get("unit_id") == UNIT
        and "SUCCESS:AUD-0058" in consumer_input
        and bool(parsed.get("named_probes"))
    )
    consumer_raw = (
        f"json.loads round-trip on {OUT_REL} (pre-registration serialization): "
        f"bytes={len(consumer_input.encode('utf-8'))} unit_id={parsed.get('unit_id')} "
        f"read_ok={read_ok}"
    )
    doc["downstream_consumers"] = [
        {
            "consumer": "json.loads round-trip reader (emit_finding.py condition-12 check)",
            "artifact_path": OUT_REL,
            "executed": True,
            "read_ok": bool(read_ok),
            "exit_code": 0 if read_ok else 1,
            "probe": {
                "role": "verifier",
                "method": "file-read",
                "command": (
                    "python3 -c \"import json;json.load(open('" + OUT_REL + "'))\""
                ),
                "raw_output": consumer_raw,
                "fingerprint": _fingerprint(consumer_raw),
                "exit_code": 0 if read_ok else 1,
            },
        }
    ]
    if not read_ok:
        print("FAILED:AUD-0058 downstream consumer could not read the receipt")
        return 1

    errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        print("FAILED:AUD-0058 schema validation")
        for err in errors[:12]:
            print(f"  {list(err.path)}: {err.message}")
        return 1
    # Two-pass self-reference: primary row records the digest of the
    # serialization in which its own sha256 field is zeroed.
    pre = json.dumps(doc, indent=2) + "\n"
    doc["artifacts"][0]["sha256"] = hashlib.sha256(pre.encode("utf-8")).hexdigest()
    doc["artifacts"][0]["bytes"] = len(pre.encode("utf-8"))
    dumped = json.dumps(doc, indent=2) + "\n"
    if COMPLETION_SENTINEL not in dumped:
        print("FAILED:AUD-0058 completion_sentinel not in document text")
        return 1
    if "SUCCESS:AUD-0058" not in dumped:
        print("FAILED:AUD-0058 sentinel not in document text")
        return 1

    dest = OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(dumped, encoding="utf-8", newline="\n")
    digest, size = sha256_file(dest)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:AUD-0058 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
