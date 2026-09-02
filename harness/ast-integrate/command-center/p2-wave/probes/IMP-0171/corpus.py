#!/usr/bin/env python3
"""Planted-mutant corpus for IMP-0171 token-Jaccard calibration.

Classes (each mutant is scored against SEED unless noted):
  exact_rename        identifier phrase swapped; body tokens held
  paraphrase          small vocabulary-retaining synonym swaps
  one_parameter_fork  one gate / cardinality / invariant token changed
  full_rewrite        same mechanism, almost entirely different words
  known_distinct      different mechanism (false-positive control)

A full rewrite is the same *mechanism* as SEED in prose; known_distinct is not.
The instrument is lexical, so those two classes must land in the same low band.
"""
from __future__ import annotations

import re
from typing import Callable

SEED_ID = "seed-harbor-review-gate"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


SEED = _norm(
    """
candidate identifier harbor review gate
purpose withhold merge publication until two independent reviewers record pass
verdicts on the same change set and a named gate predicate holds true
mechanisms include intake assignment parallel review gate merge reject
intake stage accepts a change set identifier plus a declared risk class from
the submitter
assignment stage binds two reviewer roles drawn from a disjoint pool so the
same person cannot occupy both reviewer seats during one evaluation
parallel review stage collects one verdict from each bound reviewer without
sequential blocking
gate stage evaluates the predicate both verdicts are pass and risk class
below limit
merge stage publishes the change set only when the gate predicate holds
reject stage returns the change set to intake when either recorded verdict
is fail
roles are submitter reviewer alpha reviewer beta gate keeper merger
tools are diff reader comment ledger verdict recorder predicate eval merge
publisher
gates are both verdicts are pass risk class below limit reviewers are disjoint
topology is intake then assignment then parallel review then gate then either
merge or reject
invariants reviewers remain disjoint throughout evaluation and the merger
cannot also be a reviewer
evidence each verdict is stored with reviewer identity change set identifier
and timestamp
"""
)


def _word_sub(text: str, mapping: dict[str, str]) -> str:
    """Replace whole words (and multi-word phrases, longest first)."""
    items = sorted(mapping.items(), key=lambda kv: len(kv[0]), reverse=True)
    out = _norm(text)
    for src, dst in items:
        out = re.sub(rf"\b{re.escape(_norm(src))}\b", dst, out)
    return _norm(out)


def _rename(new_ident: str) -> str:
    return _word_sub(SEED, {"harbor review gate": new_ident})


# Exact rename: three-token identifier swap only.
EXACT_RENAME: list[tuple[str, str]] = [
    ("rename-quay-audit-latch", _rename("quay audit latch")),
    ("rename-jetty-inspect-lock", _rename("jetty inspect lock")),
    ("rename-marina-check-bolt", _rename("marina check bolt")),
    ("rename-wharf-examine-clamp", _rename("wharf examine clamp")),
    ("rename-dock-survey-hasp", _rename("dock survey hasp")),
]

# Vocabulary-retaining paraphrase: a handful of 1:1 synonym swaps per mutant.
PARAPHRASE: list[tuple[str, str]] = [
    (
        "para-withhold-delay",
        _word_sub(
            SEED,
            {
                "withhold": "delay",
                "independent": "separate",
                "record": "log",
            },
        ),
    ),
    (
        "para-publication-release",
        _word_sub(
            SEED,
            {
                "publication": "release",
                "named": "listed",
                "holds": "remains",
            },
        ),
    ),
    (
        "para-accepts-takes",
        _word_sub(
            SEED,
            {
                "accepts": "takes",
                "binds": "ties",
                "collects": "gathers",
            },
        ),
    ),
    (
        "para-evaluates-tests",
        _word_sub(
            SEED,
            {
                "evaluates": "tests",
                "publishes": "emits",
                "returns": "sends",
            },
        ),
    ),
    (
        "para-stored-kept",
        _word_sub(
            SEED,
            {
                "stored": "kept",
                "occupy": "fill",
                "blocking": "stalling",
            },
        ),
    ),
]

# One-parameter forks: a single gate, cardinality, or invariant changes.
ONE_PARAMETER_FORK: list[tuple[str, str]] = [
    (
        "fork-strict-ceiling",
        _word_sub(SEED, {"risk class below limit": "risk class below strict ceiling"}),
    ),
    (
        "fork-majority-verdict",
        _word_sub(SEED, {"both verdicts are pass": "majority verdicts are pass"}),
    ),
    (
        "fork-three-reviewers",
        _word_sub(SEED, {"two independent reviewers": "three independent reviewers"}),
    ),
    (
        "fork-nested-reviewers",
        _word_sub(SEED, {"reviewers remain disjoint": "reviewers remain nested"}),
    ),
    (
        "fork-merger-may-review",
        _word_sub(
            SEED, {"merger cannot also be a reviewer": "merger may also be a reviewer"}
        ),
    ),
]

# Same mechanism, different words. Shared function words are unavoidable English.
FULL_REWRITE: list[tuple[str, str]] = [
    (
        "rewrite-park-patch",
        """
this procedure parks a proposed patch until a pair of people who do not share
a roster seat each mark the patch acceptable and until the stated hazard
bucket stays under the published ceiling arrival records the patch handle and
hazard bucket seating draws two examiners from non overlapping pools each
examiner files a mark a boolean check requires both marks acceptable and the
hazard bucket under the ceiling publication proceeds only if that check
succeeds otherwise the patch goes back to arrival
""".strip(),
    ),
    (
        "rewrite-hold-proposal",
        """
a hold is placed on a proposal while two unaffiliated examiners each stamp
approval and while the declared danger band remains beneath the posted cap
ingress notes the proposal handle plus danger band seating picks two readers
from non intersecting benches every reader deposits a stamp a boolean test
demands both stamps approval and the danger band beneath the cap shipping
occurs solely when that test succeeds else the proposal rewinds to ingress
""".strip(),
    ),
    (
        "rewrite-quarantine-delta",
        """
quarantine keeps a delta unpublished while twin inspectors who never share a
badge each certify the delta and while the labeled threat rung stays inside
the advertised bound reception logs the delta handle and threat rung pairing
selects two inspectors from exclusive benches each inspector certifies a
boolean clause insists both certifications succeed and the threat rung stays
inside the bound shipment happens only after that clause holds otherwise the
delta reenters reception
""".strip(),
    ),
    (
        "rewrite-freeze-bundle",
        """
freeze keeps a bundle off the trunk until two unaffiliated readers each
endorse the bundle and the posted danger rung sits inside the advertised
limit reception writes the bundle handle and danger rung pairing pulls two
readers from exclusive benches each reader endorses a boolean clause wants
both endorsements true and the danger rung inside the limit shipment runs
only after that clause is true otherwise the bundle reenters reception
""".strip(),
    ),
    (
        "rewrite-shelf-commit",
        """
shelf a commit until a duo of unaffiliated inspectors each bless the commit
and the stated danger rung remains inside the advertised bound reception
writes the commit handle plus danger rung pairing pulls two inspectors from
exclusive benches each inspector blesses a boolean clause wants both
blessings true and the danger rung inside the bound shipment runs only after
that clause is true otherwise the commit reenters reception
""".strip(),
    ),
]

# Genuinely different mechanisms (false-positive control). Same schema words
# (candidate/identifier/purpose/stage) appear so the control is not a free
# win from dropping the schema; the mechanism vocabulary still diverges.
KNOWN_DISTINCT: list[tuple[str, str]] = [
    (
        "distinct-kiln-sign-pipeline",
        """
candidate identifier kiln sign pipeline
purpose compile a pinned source revision into an artifact then attach a
detached signature before any publish step may run
mechanisms include fetch compile sign publish abort
fetch stage materialises the pinned source revision from the mirror
compile stage invokes the language toolchain and writes an artifact digest
sign stage creates a detached signature over that digest with a hardware key
publish stage uploads artifact plus signature only when the signature verifies
abort stage discards the artifact when compile fails or the signature mismatches
roles are builder signer publisher auditor
tools are toolchain hasher hardware key verifier uploader
gates are compile exit zero signature verifies digest matches signed bytes
topology is fetch then compile then sign then either publish or abort
invariants the signing key never leaves the hardware module and the publisher
cannot also be the signer
evidence each digest is stored with toolchain identity revision pin and timestamp
""".strip(),
    ),
    (
        "distinct-tape-restore-drill",
        """
candidate identifier tape restore drill
purpose prove a nightly backup can be restored onto a dark host before the
retention window closes
mechanisms include snapshot ship restore boot verify
snapshot stage freezes the live volume and writes a catalogued tape image
ship stage moves the image to an offsite vault with an integrity checksum
restore stage hydrates the image onto a dark host that shares no network
with production
boot stage brings the restored host to a login prompt
verify stage checksums restored files against the catalog and records a pass
roles are operator vault clerk restore lead auditor
tools are snapshotter tape writer checksummer dark host boot probe
gates are checksum matches catalog boot reaches login restore host is isolated
topology is snapshot then ship then restore then boot then verify
invariants production credentials never reach the dark host and the vault
clerk cannot also operate production
evidence each drill stores catalog identity tape serial checksum and timestamp
""".strip(),
    ),
    (
        "distinct-canary-rollout",
        """
candidate identifier canary rollout lane
purpose shift a fraction of live traffic onto a new binary and roll back if
error budgets burn
mechanisms include build stage canary observe promote revert
build stage produces the new binary with a reproducible digest
stage stage loads the binary on a shadowed fleet sharing no customer traffic
canary stage sends a stated percent of live requests to the new binary
observe stage watches error budget latency and saturation against a baseline
promote stage raises the percent only while budgets remain healthy
revert stage returns all traffic to the previous binary when a budget burns
roles are releaser observer budget owner pager
tools are builder load balancer metric probe rollback switch
gates are digest reproducible error budget healthy canary percent stated
topology is build then stage then canary then observe then either promote or revert
invariants the previous binary remains bootable until promote completes and
the releaser cannot also silence the budget probe
evidence each shift stores binary digest canary percent budget reading and timestamp
""".strip(),
    ),
    (
        "distinct-secret-rotation",
        """
candidate identifier secret rotation mill
purpose replace a live credential with a newly issued one without dropping
in-flight sessions
mechanisms include issue dual write drain retire
issue stage creates a new credential in the hardware module
dual write stage installs both old and new credentials on every consumer
drain stage waits until in-flight sessions no longer present the old credential
retire stage deletes the old credential from the module and every consumer
roles are issuer consumer owner auditor
tools are hardware module session probe dual writer retire broom
gates are both credentials present drain window elapsed old credential absent
topology is issue then dual write then drain then retire
invariants the issuer cannot also retire and a consumer with only the new
credential is never left unreachable during drain
evidence each rotation stores credential ids drain window and timestamp
""".strip(),
    ),
    (
        "distinct-schema-expand-contract",
        """
candidate identifier schema expand contract
purpose add a column to a live table without locking readers then drop the
legacy column after dual write
mechanisms include expand backfill dual write cutover contract
expand stage adds a nullable column with a default that existing readers ignore
backfill stage copies legacy values into the new column in bounded batches
dual write stage updates both columns on every write path
cutover stage points readers at the new column
contract stage drops the legacy column after a full soak
roles are migrator writer reader batch runner
tools are migrator batch copier dual writer soak probe
gates are expand lock free backfill complete dual write live soak elapsed
topology is expand then backfill then dual write then cutover then contract
invariants readers never block on expand and contract never runs before soak
evidence each migration stores table name column names batch counts and timestamp
""".strip(),
    ),
]

KNOWN_DISTINCT_CONTROL_ID = "distinct-kiln-sign-pipeline"

HIGH_BAND_CLASSES = ("exact_rename", "paraphrase", "one_parameter_fork")
LOW_BAND_CLASSES = ("full_rewrite", "known_distinct")


def all_candidates() -> list[dict]:
    rows = [{"id": SEED_ID, "class": "seed", "text": SEED, "pair_with_seed": False}]
    groups = (
        ("exact_rename", EXACT_RENAME),
        ("paraphrase", PARAPHRASE),
        ("one_parameter_fork", ONE_PARAMETER_FORK),
        ("full_rewrite", FULL_REWRITE),
        ("known_distinct", KNOWN_DISTINCT),
    )
    for cls, items in groups:
        for cid, text in items:
            rows.append(
                {
                    "id": cid,
                    "class": cls,
                    "text": text,
                    "pair_with_seed": True,
                }
            )
    return rows


def seed_pairs() -> list[dict]:
    return [r for r in all_candidates() if r["pair_with_seed"]]


def candidate_map() -> dict[str, str]:
    return {r["id"]: r["text"] for r in all_candidates()}


def apply_transform(text: str, fn: Callable[[str], str]) -> str:
    return fn(text)
