#!/usr/bin/env python3
"""Emit CNL-0007 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anonymity as A  # noqa: E402

OUT = "command-center/design/council/CNL-0007-anonymity-levels-and-their-effect-on-attribution.md"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0007/probe1_deanonymisation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0007/probe2_both_states.py"
)
QUESTION = (
    "What anonymity levels does the runtime need (named / pseudonymous / "
    "fully blind / blind-then-revealed), and for each, how are votes and "
    "dissent attributed in the audit record without defeating the anonymity "
    "that made the round independent?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0007 emit cannot cite {needle} in {path}")


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    A.dump_fixtures()
    table = A.both_states()
    attack = A.deanonymisation_states()
    if not table["pass"] or not attack["pass"]:
        print("FAILED:CNL-0007 emit mechanism did not discriminate")
        print(json.dumps({"table": table, "attack": attack}, indent=2)[:4000])
        return 1
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0007 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    planted = A.check_bundle(A.build_fixture("bad-name-in-dissent"))
    good = A.check_bundle(A.build_fixture("good-pseudonymous"))
    good_attack = attack["good_pseudonymous"]
    bad_attack = attack["bad_name_in_dissent"]

    anon_py = HERE / "anonymity.py"
    loc_check = line_of(anon_py, "def check_bundle(bundle: dict[str, Any]) -> dict[str, Any]:")
    loc_attack = line_of(anon_py, "def attack_bundle(bundle: dict[str, Any]) -> dict[str, Any]:")
    v1_schema = REPO / "11-COUNCIL-SPECIFICATION.schema.json"
    v1_prompts = REPO / "_USER-PROMPTS.md"
    catalogue = REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    v2_shim = REPO / "command-center/schema/councilspec.v2.schema.json"
    cnl0001 = (
        REPO
        / "command-center/design/council/"
        "CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json"
    )
    cnl0006 = (
        REPO
        / "command-center/design/council/CNL-0006-information-partition-lattice-who-may-see-what-when.md"
    )
    v2_shim_present = v2_shim.is_file()
    cnl0001_present = cnl0001.is_file()
    cnl0006_present = cnl0006.is_file()

    doc = {
        "unit_id": "CNL-0007",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "council-design-note",
        "format": "json-document-at-md-path (G-1 json.loads)",
        "title": "Anonymity levels and their effect on attribution",
        "question": QUESTION,
        "sentinel": "SUCCESS:CNL-0007",
        "completion_sentinel": "SUCCESS:CNL-0007",
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0007",
        "depends_on": ["CNL-0006"],
        "dependency_status": {
            "CNL-0006": (
                "present" if cnl0006_present else "absent-on-this-worktree"
            ),
            "note": (
                "Anonymity (who is speaking) is orthogonal to the CNL-0006 "
                "partition lattice (who may see which evidence). This unit "
                "consumes partition_id as an opaque field and does not wait "
                "on the lattice artifact."
            ),
        },
        "inputs_on_this_worktree": {
            "11-COUNCIL-SPECIFICATION.schema.json": v1_schema.is_file(),
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": catalogue.is_file(),
            "_USER-PROMPTS.md": v1_prompts.is_file(),
            "command-center/schema/councilspec.v2.schema.json": v2_shim_present,
            "CNL-0001-envelope": cnl0001_present,
            "CNL-0006-artifact": cnl0006_present,
        },
        "answer": (
            "The runtime needs exactly four anonymity levels -- named, "
            "pseudonymous, fully_blind, and blind_then_revealed -- because "
            "those are the four distinct publishable-handle rules a council "
            "round actually uses. Votes and dissent are attributed on a "
            "split audit: the participant-facing publishable log carries "
            "only the handle the level allows (real id / per-round token / "
            "null), and a keeper-only sealed binder holds the join to real "
            "ids. The binder is never concatenated into the transcript "
            "during the independence window. A scheduled reveal, when the "
            "level is blind_then_revealed, APPENDS a join table after the "
            "last independent act; it must not rewrite historical actor "
            "fields, because rewriting would destroy the proof that the "
            "round was independent when the votes were cast."
        ),
        "anonymity_levels": [
            {
                "id": "named",
                "publishable_actor": "real participant id",
                "votes": (
                    "Each ballot stores actor=real_id and choice. Dissent "
                    "stores actor=real_id and body. Attribution is immediate "
                    "and public."
                ),
                "sealed_binder": "not required; identity is already public",
                "independence_window": (
                    "None. First-speaker anchoring and vote-copying are in "
                    "scope. Named is for after-action review, owner-visible "
                    "escalation, and protocols that require accountable seats."
                ),
                "what_would_defeat_it": (
                    "A named round that omits actor on votes (unattributed "
                    "named) is an attribution hole, not anonymity. The "
                    "checker fires named_vote_unattributed."
                ),
                "audit_record": {
                    "publishable.votes[]": {
                        "ballot_id": "opaque",
                        "actor": "real_id",
                        "choice": "enum",
                    },
                    "publishable.dissent[]": {
                        "statement_id": "opaque",
                        "actor": "real_id",
                        "body": "text",
                    },
                    "sealed_binder": "absent",
                },
            },
            {
                "id": "pseudonymous",
                "publishable_actor": (
                    "per-round HMAC token mint_token(real_id, round_id, salt) "
                    "with salt withheld from participants"
                ),
                "votes": (
                    "Each ballot stores actor=round-token and choice. Dissent "
                    "stores actor=round-token. Debate can refer to 'R1-a7f2...' "
                    "inside the round without exposing the real seat."
                ),
                "sealed_binder": (
                    "keeper-only map {token, ballot_id} -> real_id. Must not "
                    "appear on the participant-facing channel."
                ),
                "independence_window": (
                    "Tokens are stable within a round so claims can be cited, "
                    "and MUST change across rounds (fresh salt) so positions "
                    "cannot be linked. Emission order MUST be shuffled off "
                    "the invite-list order. Wall-clock, token-count, and "
                    "home-path tool traces are forbidden in the publishable log."
                ),
                "what_would_defeat_it": (
                    "Embedding the binder, putting a real_id substring in "
                    "dissent, reusing a token across rounds, or emitting in "
                    "roster order. The de-anonymisation probe joins all four."
                ),
                "audit_record": {
                    "publishable.votes[]": {
                        "ballot_id": "unlinkable receipt",
                        "actor": "per-round token",
                        "choice": "enum",
                    },
                    "publishable.dissent[]": {
                        "statement_id": "opaque",
                        "actor": "per-round token",
                        "body": "text without identifiers",
                    },
                    "sealed_binder": "keeper-only",
                },
            },
            {
                "id": "fully_blind",
                "publishable_actor": "null -- no speaker handle",
                "votes": (
                    "Ballots store actor=null, ballot_id=HMAC receipt, and "
                    "choice. Counts remain auditable (N approve / M reject) "
                    "without who. Dissent is a content-addressed blob with "
                    "actor=null."
                ),
                "sealed_binder": (
                    "keeper-only map ballot_id -> real_id, opened only for "
                    "post-round forensic audit (self-review, owner incident), "
                    "never to other seats during the round."
                ),
                "independence_window": (
                    "The entire round. No handle, no token, no reveal event."
                ),
                "what_would_defeat_it": (
                    "Any actor handle on an independence-epoch record, a "
                    "binder on the participant-facing channel, or a real_id "
                    "substring in a blob."
                ),
                "residual_channel": (
                    "Free-text dissent remains a stylometric channel. This "
                    "unit's checker does not run a style classifier; a "
                    "style-only leak without identifiers is NOT-CHECKED here "
                    "and is named as residual, not claimed solved. Vote-only "
                    "independence rounds close that channel."
                ),
                "audit_record": {
                    "publishable.votes[]": {
                        "ballot_id": "unlinkable receipt",
                        "actor": None,
                        "choice": "enum",
                    },
                    "publishable.dissent[]": {
                        "statement_id": "opaque",
                        "actor": None,
                        "body": "text without identifiers",
                    },
                    "sealed_binder": "keeper-only",
                },
            },
            {
                "id": "blind_then_revealed",
                "publishable_actor": (
                    "null during epoch=independence; a join table is appended "
                    "after the last independent act"
                ),
                "votes": (
                    "Independence-epoch votes stay actor=null forever. The "
                    "reveal_event.join_table maps ballot_id -> real_id as a "
                    "NEW object. Later rounds may cite revealed identities. "
                    "The historical vote rows are not rewritten."
                ),
                "sealed_binder": (
                    "Promoted to reveal_event after the window; until then "
                    "keeper-only."
                ),
                "independence_window": (
                    "Closes at last_independent_act (typically the last "
                    "blind vote). Reveal before that point is a leak."
                ),
                "what_would_defeat_it": (
                    "Backfilling real_ids into independence-epoch actor "
                    "fields. That erases the proof the round was blind when "
                    "cast. The checker fires independence_epoch_rewritten."
                ),
                "audit_record": {
                    "independence.publishable.votes[]": {
                        "actor": None,
                        "choice": "enum",
                    },
                    "reveal_event": {
                        "type": "anonymity_reveal",
                        "join_table": [{"ballot_id": "...", "real_id": "..."}],
                        "does_not_rewrite_historical_actors": True,
                    },
                },
            },
        ],
        "audit_split": {
            "rule": (
                "Two objects, never one. publishable_log is what other seats "
                "and later readers see during the independence window. "
                "sealed_binder is the identity join, held by the audit keeper."
            ),
            "participant_facing_forbidden": [
                "real_id (except named, or reveal_event after the window)",
                "display_name",
                "plaintext binder",
                "round salt",
                "invite-list emission order",
                "wall-clock timestamps",
                "token counts",
                "home-path tool traces",
                "model_id when it uniquely identifies a seat",
            ],
            "why_split_not_rewrite": (
                "Attribution after a blind round is a join, not a mutation. "
                "Mutating historical actor fields makes the independence "
                "window unverifiable."
            ),
        },
        "leak_check": {
            "name": "check_bundle",
            "path": "command-center/p2-wave/probes/CNL-0007/anonymity.py",
            "line": loc_check,
            "fires_on": [
                "real_id_in_publishable (non-named)",
                "binder_embedded_in_publishable",
                "cross_round_token_reuse",
                "roster_order_preserved",
                "actor_present_under_blind",
                "independence_epoch_rewritten",
                "named_vote_unattributed",
            ],
            "silent_on": [
                "good-named (real ids are the point)",
                "good-pseudonymous (per-round tokens, shuffled, no binder)",
                "good-fully-blind (null actors, no binder)",
                "good-blind-then-revealed (history unrewritten; join is a sibling event)",
            ],
        },
        "councilspec_v2_fragment": {
            "block": "integrity.anonymity",
            "note": (
                "Typed fragment for the CNL-0001 envelope. The catalog "
                "output_schema path command-center/schema/councilspec.v2."
                "schema.json is a generated shim ($ref only) on this tree. "
                "The CNL-0001 envelope artifact is "
                f"{'present' if cnl0001_present else 'absent'}; the "
                "reconstructed CNL-0001 preset field is anonymity:string, "
                "not this four-level enum. This fragment is the contract "
                "this unit needs."
            ),
            "properties": {
                "anonymity_level": {
                    "type": "string",
                    "enum": [
                        "named",
                        "pseudonymous",
                        "fully_blind",
                        "blind_then_revealed",
                    ],
                },
                "epoch": {
                    "type": "string",
                    "enum": ["open", "independence", "revealed"],
                },
                "publishable": {"type": "object"},
                "sealed_binder": {
                    "description": "keeper-only; additionalProperties plaintext_map forbidden on participant_facing",
                },
                "reveal_event": {
                    "type": "object",
                    "properties": {
                        "type": {"const": "anonymity_reveal"},
                        "does_not_rewrite_historical_actors": {"const": True},
                    },
                },
            },
            "required": ["anonymity_level", "epoch", "publishable"],
        },
        "relation_to_partition_lattice": (
            "CNL-0006 asks how a blind first pass, staged evidence release, "
            "and fishbowl observer ring are one lattice type. That lattice "
            "answers who may see which evidence. This unit answers who is "
            "allowed to be identified as the speaker of a vote or dissent. "
            "They compose: a fully_blind seat can still be denied a partition "
            "of evidence. A named seat can still be partitioned. Mixing the "
            "two into one enum would make leak checks untestable."
        ),
        "evidence": [
            {
                "signal": 1,
                "mechanism": "leak-checker field census (string scan + order + binder presence)",
                "anchor": f"command-center/p2-wave/probes/CNL-0007/anonymity.py:{loc_check}",
                "command": P2,
                "verbatim": t2,
                "claim": (
                    "check_bundle fires on every planted-bad fixture and is "
                    "silent on every known-good fixture, including named "
                    "(ids allowed) versus pseudonymous (ids forbidden)."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "signal": 2,
                "mechanism": "de-anonymisation attack accuracy versus chance (join attempt, not a scan)",
                "anchor": f"command-center/p2-wave/probes/CNL-0007/anonymity.py:{loc_attack}",
                "command": P1,
                "verbatim": t1,
                "claim": (
                    "Given a pseudonymous transcript plus vote history plus "
                    "the invite list, an adversary records zero confident "
                    "joins on the known-good fixture (chance baseline "
                    f"{good_attack['chance_baseline']}) and records "
                    f"{bad_attack['confident_join_count']} confident join(s) "
                    f"at accuracy {bad_attack['confident_accuracy']} on "
                    "planted name-in-dissent."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "tests": [
            {
                "id": "T-DEANONYMISATION",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "T-BOTH-STATES",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-NAME-IN-DISSENT",
                "state_meant_to_reject": "bad-name-in-dissent",
                "what_the_check_does": (
                    "check_bundle returns fired=true with "
                    "real_id_in_publishable; the attack records confident "
                    "token->id joins. Silence here would be uncontrolled."
                ),
                "verbatim": (
                    "check_bundle(bad-name-in-dissent) fired="
                    f"{planted['fired']} reasons={json.dumps(planted['reasons'])}"
                ),
                "fired_on_bad": True,
                "silent_on_good": True,
                "good_verbatim": (
                    "check_bundle(good-pseudonymous) fired="
                    f"{good['fired']} silent={good['silent']} "
                    f"reasons={json.dumps(good['reasons'])}"
                ),
            }
        ],
        "both_states_table": table,
        "deanonymisation": {
            "chance_baseline": good_attack["chance_baseline"],
            "population_n": good_attack["population_n"],
            "good_supports_anonymity": good_attack["supports_anonymity"],
            "good_confident_join_count": good_attack["confident_join_count"],
            "bad_name_confident_join_count": bad_attack["confident_join_count"],
            "bad_name_confident_accuracy": bad_attack["confident_accuracy"],
            "bad_order_forced_position_accuracy": attack["bad_unshuffled_order"][
                "forced_position_accuracy"
            ],
            "pass": attack["pass"],
        },
        "residual_unknowns": [
            "Stylometric re-identification of free-text dissent without identifier substrings is NOT-CHECKED by this detector.",
            "Timing and token-count quasi-identifiers are specified as forbidden but not instrumented in the fixture clock (fixtures have no timestamps).",
            (
                "Fragment is not schema-validated against a live CNL-0001 "
                "envelope (envelope artifact "
                f"{'present' if cnl0001_present else 'absent'}; v2 shim "
                f"{'present' if v2_shim_present else 'absent'})."
            ),
            "11-COUNCIL-SPECIFICATION.schema.json and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this Linux worktree; level names are taken from the catalog question, not re-derived from those files.",
            "No production council runtime rounds exist here; probes run against executable fixtures, not live transcripts.",
        ],
        "strongest_surviving_counterargument": (
            "A determined adversary with a style model could still re-identify "
            "fully_blind dissent. That does not refute the four-level split or "
            "the binder/rewrite rules; it bounds fully_blind free-text. Vote-only "
            "independence rounds are the operational mitigation. Claiming "
            "stylometry is solved would be an overclaim; it is listed residual."
        ),
        "reviewer": {
            "reviewer_id": "CNL-0007-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "G-1 probe2 re-runs the both-states control on disk. Catalog "
                "scoring by a cross-vendor reviewer is independent of G-1 "
                "probe-green and was not forged here."
            ),
        },
        "scope": {
            "proof_surface": (
                "executable mint/check/attack on nine fixtures under "
                "command-center/p2-wave/probes/CNL-0007/"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "production anonymity.py at tools/council/integrity/ is implemented (IMP-0276)",
                "CNL-0006 lattice artifact exists",
                "CNL-0001 envelope artifact exists on this worktree",
                "stylometry is solved",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "named_probes": [
            {"id": "probe1", "role": "de-anonymisation", "command": P1},
            {"id": "probe2", "role": "both-states-leak-check", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/CNL-0007/anonymity.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "prose_markdown": (
            "# Anonymity levels and their effect on attribution\n\n"
            "The runtime needs four levels, not a boolean anonymous flag.\n\n"
            "## named\n"
            "Publishable actor is the real id. Votes and dissent are attributed "
            "immediately. There is no independence window to protect.\n\n"
            "## pseudonymous\n"
            "Publishable actor is a per-round HMAC token. Votes and dissent cite "
            "the token. The keeper binder is not on the participant-facing "
            "channel. Tokens must not be reused across rounds; emission must not "
            "preserve invite-list order.\n\n"
            "## fully_blind\n"
            "Publishable actor is null. Votes are unlinkable receipts plus a "
            "choice. Counts are auditable; who is not. Free-text style remains "
            "a residual channel.\n\n"
            "## blind_then_revealed\n"
            "Independence epoch follows fully_blind. After the last independent "
            "act, a reveal_event join table is appended. Historical actor "
            "fields stay null. Rewriting them fires independence_epoch_rewritten.\n\n"
            "SUCCESS:CNL-0007\n"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0007 artifact {size}B below floor")
        return 1
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0007 self-declared not delivering")
        return 1
    if "SUCCESS:CNL-0007" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0007 sentinel absent")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0007 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
