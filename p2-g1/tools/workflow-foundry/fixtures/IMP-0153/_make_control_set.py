"""Generate the hand-labelled 30-doc control set for IMP-0153.

Labels are assigned HERE, by the builder, from the doc's communicative role -
before any detector run - and are frozen into labels.json. 15 docs are USE
(how-to prose that instructs a reader to adopt a workflow) and 15 are
MENTION (the workflow appears only to criticize, forbid, or warn).

Re-run: python tools/workflow-foundry/fixtures/IMP-0153/_make_control_set.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

USE_DOCS = {
    "u01-coverage-rebuild.md": (
        "Rebuild the coverage index after every wave. First run the census script, then "
        "validate each row against the catalog, and finally record the row count in the "
        "index. When done, verify the index parses before you emit the summary."
    ),
    "u02-probe-discipline.md": (
        "To measure a claim, write the probe first. Run the probe against the good state, "
        "then run the same probe against the planted bad state, and record both outputs "
        "verbatim. Next, compare exit codes; only a 0/1 pair counts as a measurement."
    ),
    "u03-receipt-hygiene.md": (
        "Emit the receipt only after the artifact passes schema validation. Generate the "
        "manifest row by hashing the file, then record the hash in the manifest. Verify "
        "the receipt parses before you close the unit."
    ),
    "u04-mutation-control.md": (
        "Calibrate every detector with a planted mutant. Build the mutant by mutating one "
        "field, run the detector on the mutant, then re-run it on the clean twin. Record "
        "both outputs so the reviewer can recompute the band."
    ),
    "u05-hash-registry.md": (
        "Register every artifact by its content hash. Execute the hashing command, then "
        "write the digest into the registry, and finally check the registry parses. "
        "After that, recompute one row by hand to confirm the tool."
    ),
    "u06-fanout-replay.md": (
        "Replay a failed fan-out by re-reading the worktree list. First fetch each unit's "
        "receipt, then validate it against the schema, and record any drift in the replay "
        "log. When done, summarize the drift counts and emit the report."
    ),
    "u07-stopwatch-budget.md": (
        "Measure the budget per unit. Start the timer before the build, stop it after the "
        "probes, then write both timestamps into the receipt. Verify the duration is under "
        "the declared ceiling and record the number."
    ),
    "u08-corpus-curation.md": (
        "Curate the corpus in strata. Generate ten cases per difficulty band, then hash "
        "each case id to assign its partition, and finally check that the held-out slice "
        "is empty of development runs by scanning the access log."
    ),
    "u09-diff-protocol.md": (
        "Diff two workflow specs stage by stage. Extract each stage's role, gate, and "
        "tool, then compute added, removed, and changed entries, and record the diff in "
        "both directions. Verify the diff is antisymmetric before you file it."
    ),
    "u10-splice-check.md": (
        "Splice a better stage into a workflow only after the contract check. Validate "
        "the donor's inputs and outputs against the neighbours, then emit the fused "
        "workflow, and finally run it on the fake rail to record the plan hash."
    ),
    "u11-gap-synthesis.md": (
        "Close coverage gaps by synthesis. Run the gap finder, pick the cited gap, then "
        "generate the missing workflow, and re-run the gap finder to show the gap is "
        "absent. Record both runs in the receipt."
    ),
    "u12-retirement-protocol.md": (
        "Retire a workflow by supersession. Name the successor, write the migration note, "
        "then keep the old entry resolvable, and check that pinned consumers still "
        "execute while emitting the typed warning."
    ),
    "u13-confirmation-gate.md": (
        "Confirm a benchmark claim from raw sources. Open each cited artifact, prove it "
        "exists on disk, then recompute the digest, and record the confirmation with the "
        "cited paths before reading any summary."
    ),
    "u14-mention-audit.md": (
        "Audit the corpus for mention-only hits. Extract candidates, classify each "
        "sentence, then check the mention-only control yields zero candidates, and record "
        "the precision and recall of the control set as numbers."
    ),
    "u15-provenance-reread.md": (
        "Prove provenance by re-fetching. Sample ten records, re-read each file from the "
        "record alone, then compare the fresh hash to the recorded hash, and finally "
        "record the reproduction count in the receipt."
    ),
}

MENTION_DOCS = {
    "m01-hash-worship.md": (
        "Recording a hash proves nothing by itself. Teams that treat the digest as the "
        "work ship bytes nobody can re-fetch. The hash registry pattern is an anti-pattern "
        "when the recorded path is never re-read; it is a harmless ritual otherwise."
    ),
    "m02-probe-theatre.md": (
        "Writing the probe after the fix is probe theatre. The failure mode is familiar: "
        "the probe validates the fix instead of the claim, and the green exit code is a "
        "forgone conclusion. Do not mistake an exit code for a measurement."
    ),
    "m03-coverage-myth.md": (
        "Coverage numbers mislead when the index is rebuilt from its own output. That "
        "rebuild loop is a classic anti-pattern; the census ends up validating the "
        "generator, not the tree. Beware any summary that cites it."
    ),
    "m04-mutant-charity.md": (
        "A planted mutant that the detector was tuned to catch is charity, not "
        "calibration. The mutation control must be able to fail; a mutant chosen after "
        "reading the detector is a mistake that manufactures a green band."
    ),
    "m05-receipt-bloat.md": (
        "Bloating the receipt with unverifiable fields is a waste. Every asserted field "
        "the reviewer cannot re-derive is a liability, and the schema-valid-but-empty "
        "receipt is the canonical failure mode of this program."
    ),
    "m06-replay-fiction.md": (
        "Replaying a fan-out from a cached receipt list is fiction, not replay. The "
        "replay log must be regenerated from live reads; citing yesterday's drift counts "
        "as today's is the misleading move this unit exists to stop."
    ),
    "m07-timer-gaming.md": (
        "Starting the timer after the build games the budget. The stopwatch protocol "
        "sounds neutral but the timestamps are self-reported; never treat a duration "
        "recorded by the timed party as evidence."
    ),
    "m08-strata-fixation.md": (
        "Stratifying the corpus is not the hard part; keeping the held-out slice held out "
        "is. The convention-based partition is a known pitfall - teams tune on the test "
        "slice and then report surprise. Avoid any partition you cannot recompute from a "
        "hash."
    ),
    "m09-one-sided-diff.md": (
        "A one-directional diff cannot see two-directional divergence. That defect "
        "produced thirty-one data-loss-pointing misclassifications here. Diffing only "
        "what the new side adds is wrong; the both-sides-unique fixture is the classic "
        "counterexample."
    ),
    "m10-splice-rot.md": (
        "Splicing stages without a contract check is how workflows rot. The donor runs "
        "green alone and silently breaks its new neighbours; the mismatch surfaces at "
        "dispatch, far from the cause. Critics of the splice strategy are right about "
        "this failure mode."
    ),
    "m11-gap-chasing.md": (
        "Chasing every gap the finder cites produces shovelware. Synthesizing a workflow "
        "per gap without re-running the finder is a mistake; the cited gap often closes "
        "itself in the next pass, and the synthesis claims credit."
    ),
    "m12-delete-retirement.md": (
        "Retiring a workflow by deleting its entry breaks every pinned consumer. Silent "
        "removal is the failure mode; the rollback class exists precisely because someone "
        "shipped a hard break. Do not do this."
    ),
    "m13-digest-confession.md": (
        "A confirmation that cites only the author's summary is a digest, not a receipt. "
        "The gate exists because reviewers kept confirming claims they never traced to "
        "raw sources; it is a dangerous habit, not a shortcut."
    ),
    "m14-extractor-overreach.md": (
        "Candidate extraction over-collects. Treating every imperative sentence as a "
        "workflow-to-build harvests criticism as endorsement - the use-vs-mention "
        "confusion hit this estate eight times in one session. Beware extractors without "
        "a mention guard."
    ),
    "m15-refetch-ritual.md": (
        "Re-fetching from a record that embeds its own answer proves nothing. If the "
        "record carries the expected hash and the verifier compares to it without "
        "re-deriving, the ritual is theatre; the mismatch detector that never fired is "
        "the tell."
    ),
}


def main() -> int:
    labels = {}
    for name, body in USE_DOCS.items():
        (HERE / name).write_text(body + "\n", encoding="utf-8", newline="\n")
        labels[name] = "USE"
    for name, body in MENTION_DOCS.items():
        (HERE / name).write_text(body + "\n", encoding="utf-8", newline="\n")
        labels[name] = "MENTION"
    # The standalone mention-only control document for acceptance signal (2):
    # it describes a build pipeline ONLY to criticize it.
    mention_control = (
        "# Post-mortem: the nightly pipeline that ate our receipts\n\n"
        "The nightly pipeline looked impeccable on paper: fetch the receipts, then "
        "validate each one against the schema, then emit the summary index. In practice "
        "it was a disaster. Fetching meant re-downloading gigabytes; validating used a "
        "stale schema snapshot; and the emitted index silently overwrote the previous "
        "day's. Do not adopt this pipeline. Its every step is an anti-pattern worth "
        "naming so the next reader avoids it."
    )
    (HERE / "mention-only-control.md").write_text(
        mention_control + "\n", encoding="utf-8", newline="\n")
    (HERE / "labels.json").write_text(
        json.dumps(labels, indent=1, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    print("wrote {} labelled docs + mention-only-control.md".format(len(labels)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
