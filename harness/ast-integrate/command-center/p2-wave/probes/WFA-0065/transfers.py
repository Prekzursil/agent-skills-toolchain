"""Proposed cross-domain transfers. Classification is applied later against the live corpus."""

from __future__ import annotations

from ir import IR_KINDS

# collision_policy:
#   already     -> if corpus has hits, disposition is ALREADY-SPECIFIED-IN-CATALOG
#   near-miss-ok -> timeout-readback / typed-handoff do not block adoption
#   none        -> corpus hits do not auto-block (still recorded)

TRANSFERS: list[dict] = [
    {
        "id": "xfer.atc.readback-before-side-effect",
        "domain": "air-traffic-control",
        "source_protocol_id": "src.atc.aim-4-4-7",
        "mechanism": (
            "Before any side-effecting tool call, the executing role must restated "
            "the constrained fields of the instruction (task id, tool allowlist, "
            "stopping expression) in the same order they were issued; the issuing "
            "role must confirm match. Silence is not confirmation."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "controller issues clearance",
                "ir_kind": "stage",
                "ir_node": "stage.issue-instruction",
            },
            {
                "source_role_or_step": "pilot readback of numbers in issued order",
                "ir_kind": "gate",
                "ir_node": "gate.executor-readback",
            },
            {
                "source_role_or_step": "controller hearback / correction",
                "ir_kind": "barrier",
                "ir_node": "barrier.originator-confirm-before-tools",
            },
            {
                "source_role_or_step": "aircraft identification on every readback",
                "ir_kind": "lineage",
                "ir_node": "lineage.actor_id",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "Shared voice radio, certified phraseology, and safety-of-life timing "
                "with a legally responsible controller."
            ),
            "remaining_mapping": (
                "Constrained field echo + originator confirm as a gate/barrier pair "
                "before tool_policy allows side effects."
            ),
        },
        "ir_expressible": True,
        "corpus_signature": "instruction-readback",
        "collision_policy": "near-miss-ok",
        "intended_if_novel": "ADOPTED",
    },
    {
        "id": "xfer.ipass.receiver-synthesis-gate",
        "domain": "clinical-handoff",
        "source_protocol_id": "src.ipass.starmer-2014",
        "mechanism": (
            "A stage boundary packet is not accepted until the receiving role emits "
            "a synthesis covering illness-severity analogue, summary, action list, "
            "and contingencies. Sender-structured fields alone do not close the barrier."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "I/P/A/S fields from sender",
                "ir_kind": "barrier",
                "ir_node": "barrier.handoff-packet",
            },
            {
                "source_role_or_step": "synthesis by receiver",
                "ir_kind": "gate",
                "ir_node": "gate.receiver-synthesis",
            },
            {
                "source_role_or_step": "mismatch retry of the oral/written loop",
                "ir_kind": "loop",
                "ir_node": "loop.handoff-repair",
            },
            {
                "source_role_or_step": "unresolved mismatch escalates to attending",
                "ir_kind": "human_checkpoint",
                "ir_node": "human_checkpoint.handoff-escalation",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "A licensed clinician with legal duty to a continuous patient body, "
                "and in-person observation that can catch omitted physical findings."
            ),
            "remaining_mapping": (
                "Receiver-produced synthesis as a gate on a typed barrier payload, "
                "distinct from a sender-only typed handoff record."
            ),
        },
        "ir_expressible": True,
        "corpus_signature": "receiver-synthesis",
        "collision_policy": "near-miss-ok",
        "intended_if_novel": "ADOPTED",
        "near_miss_signature": "typed-handoff",
        "near_miss_why": (
            "Catalog typed-handoff units reject raw prefix passing; they do not "
            "require the receiver to synthesize."
        ),
    },
    {
        "id": "xfer.ics.unity-of-command",
        "domain": "incident-command",
        "source_protocol_id": "src.ics.fema-is200",
        "mechanism": (
            "Each role has exactly one supervisor pointer. Conflicting directives "
            "from a second issuer fail a gate rather than merging."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "each individual reports to only one supervisor",
                "ir_kind": "role",
                "ir_node": "role.supervisor_id unique",
            },
            {
                "source_role_or_step": "conflicting orders from two bosses",
                "ir_kind": "gate",
                "ir_node": "gate.reject-second-issuer",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "Geographic incident with physical accountability and a single "
                "incident command post."
            ),
            "remaining_mapping": "Unique supervisor pointer + reject-second-issuer gate.",
        },
        "ir_expressible": True,
        "corpus_signature": "unity-of-command",
        "collision_policy": "already",
        "intended_if_novel": "ADOPTED",
    },
    {
        "id": "xfer.ics.numeric-span-3-to-7",
        "domain": "incident-command",
        "source_protocol_id": "src.ics.fema-is200",
        "mechanism": (
            "Cap fan_out at 3-7 subordinates per supervisor because that is the "
            "ICS numeric span-of-control band."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "span of control 3-7, optimal 5",
                "ir_kind": "fan_out",
                "ir_node": "fan_out.max_cardinality",
            }
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "Human attention and radio-net congestion that make five live "
                "subordinates a safety limit. Software agents do not share that "
                "attention cost; the number 3-7 is not justified here."
            ),
            "remaining_mapping": (
                "A declared fan_out cap is IR-expressible, but the specific 3-7 "
                "band is not evidence-backed for agents."
            ),
        },
        "ir_expressible": True,
        "corpus_signature": "span-of-control",
        "collision_policy": "none",
        "intended_if_novel": "SPECULATIVE",
        "force_disposition": "SPECULATIVE",
    },
    {
        "id": "xfer.sterile-cockpit.critical-stage-tool-lock",
        "domain": "air-traffic-control",
        "source_protocol_id": "src.cfr.121-542",
        "mechanism": (
            "While a stage is marked critical, tool_policy is an allowlist of "
            "duty-required tools only; fan_out of non-essential roles is forbidden."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "critical phase of flight",
                "ir_kind": "stage",
                "ir_node": "stage.critical=true",
            },
            {
                "source_role_or_step": "no non-essential activity",
                "ir_kind": "tool_policy",
                "ir_node": "tool_policy.allowlist",
            },
            {
                "source_role_or_step": "no extra crew chatter",
                "ir_kind": "fan_out",
                "ir_node": "fan_out.forbidden_while_critical",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "Altitude below 10,000 feet is an objective physical predicate. "
                "Agent 'critical' is a declared flag, not a measured altitude."
            ),
            "remaining_mapping": (
                "Declared critical stage + allowlist tool_policy + fan_out lock."
            ),
        },
        "ir_expressible": True,
        "corpus_signature": "sterile-cockpit",
        "collision_policy": "already",
        "intended_if_novel": "ADOPTED",
    },
    {
        "id": "xfer.editorial.isolated-parallel-reviews",
        "domain": "editorial-peer-review",
        "source_protocol_id": "src.editorial.icmje",
        "mechanism": (
            "N reviewer roles run under a tool_policy that forbids reviewer-to-"
            "reviewer messages; a barrier joins their artifacts; a synthesizer "
            "role that did not author the work writes the disposition."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "independent referees",
                "ir_kind": "fan_out",
                "ir_node": "fan_out.isolated-reviewers",
            },
            {
                "source_role_or_step": "no inter-reviewer communication",
                "ir_kind": "tool_policy",
                "ir_node": "tool_policy.deny-reviewer-reviewer",
            },
            {
                "source_role_or_step": "editor collects reviews",
                "ir_kind": "barrier",
                "ir_node": "barrier.reviews-in",
            },
            {
                "source_role_or_step": "editor decision letter",
                "ir_kind": "role",
                "ir_node": "role.synthesizer-not-author",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "Human-identity anonymity. Model outputs are fingerprintable; "
                "double-blind identity protection does not transfer."
            ),
            "remaining_mapping": (
                "Channel isolation (no reviewer-reviewer messages) plus a "
                "non-author synthesizer is IR-expressible without claiming anonymity."
            ),
        },
        "ir_expressible": True,
        "corpus_signature": "isolated-peer-review",
        "collision_policy": "already",
        "intended_if_novel": "ADOPTED",
    },
    {
        "id": "xfer.delphi.anonymous-iterated-feedback",
        "domain": "delphi-forecasting",
        "source_protocol_id": "src.delphi.dalkey-helmer-1963",
        "mechanism": (
            "Anonymous iterated estimates with controlled statistical feedback "
            "until a stopping expression on dispersion."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "anonymous questionnaire round",
                "ir_kind": "loop",
                "ir_node": "loop.delphi-round",
            },
            {
                "source_role_or_step": "controlled opinion feedback",
                "ir_kind": "convergence_rule",
                "ir_node": "convergence_rule.statistical-feedback",
            },
            {
                "source_role_or_step": "stop after N rounds or consensus",
                "ir_kind": "stopping_expression",
                "ir_node": "stopping_expression.dispersion-or-max-round",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "True identity anonymity among human experts. Agent transcripts "
                "leak style; anonymity is not guaranteed."
            ),
            "remaining_mapping": "Iterated estimate loop + statistical feedback + stop rule.",
        },
        "ir_expressible": True,
        "corpus_signature": "delphi",
        "collision_policy": "already",
        "intended_if_novel": "ADOPTED",
    },
    {
        "id": "xfer.jury.deciders-without-advocacy",
        "domain": "jury-instruction",
        "source_protocol_id": "src.ics.fema-is200",
        "source_note": "Jury topology is named in CNL-0034; ICS fixture is not the legal source.",
        "mechanism": (
            "Decider roles do not produce the arguments they vote on; advocates "
            "cannot see or write the verdict stage."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "advocates argue",
                "ir_kind": "role",
                "ir_node": "role.advocate",
            },
            {
                "source_role_or_step": "jury that did not argue",
                "ir_kind": "role",
                "ir_node": "role.decider",
            },
            {
                "source_role_or_step": "instruction before deliberation",
                "ir_kind": "gate",
                "ir_node": "gate.instruction-complete",
            },
            {
                "source_role_or_step": "verdict without advocate authorship",
                "ir_kind": "tool_policy",
                "ir_node": "tool_policy.decider-cannot-read-advocate-scratch",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "Voir dire, sequestration, and a shared physical courtroom. Context "
                "windows leak; instruction isolation is incomplete for LLMs."
            ),
            "remaining_mapping": "Advocate vs decider role split + instruction gate + tool_policy partition.",
        },
        "ir_expressible": True,
        "corpus_signature": "jury-deciders",
        "collision_policy": "already",
        "intended_if_novel": "ADOPTED",
    },
    {
        "id": "xfer.consensus.quorum-barrier",
        "domain": "distributed-consensus",
        "source_protocol_id": "src.delphi.rand-four-features",
        "source_note": "Quorum is estate-local (council tally units), not a Raft paper transfer.",
        "mechanism": "A barrier that does not lift until a declared quorum of role acks is present.",
        "mapping_table": [
            {
                "source_role_or_step": "majority/supermajority/unanimity",
                "ir_kind": "barrier",
                "ir_node": "barrier.quorum",
            },
            {
                "source_role_or_step": "abstention vs denominator",
                "ir_kind": "convergence_rule",
                "ir_node": "convergence_rule.tally-policy",
            },
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "Deterministic replica state machines (Paxos/Raft). LLM agents are "
                "not identical replicas; quorum here is a vote barrier, not log replication."
            ),
            "remaining_mapping": "Declared quorum barrier + tally policy. Not Raft.",
        },
        "ir_expressible": True,
        "corpus_signature": "quorum",
        "collision_policy": "already",
        "intended_if_novel": "ADOPTED",
    },
    {
        "id": "xfer.paxos.byzantine-replicas",
        "domain": "distributed-consensus",
        "source_protocol_id": "src.delphi.dalkey-helmer-1963",
        "source_note": "Negative control: Byzantine 3f+1 replication is not an IR kind.",
        "mechanism": (
            "3f+1 deterministic replicas with Byzantine quorum certificates before commit."
        ),
        "mapping_table": [
            {
                "source_role_or_step": "replica identity / 3f+1",
                "ir_kind": "replica_set",
                "ir_node": "NOT-AN-IR-KIND",
            }
        ],
        "falsification": {
            "attempted": True,
            "source_property_that_does_not_hold": (
                "The IR contract has no replica, Byzantine, or certificate kinds. "
                "Mapping cannot be expressed without new IR nodes."
            ),
            "remaining_mapping": "None. Out of scope until WorkflowIR gains replica kinds.",
        },
        "ir_expressible": False,
        "corpus_signature": "paxos-byzantine",
        "collision_policy": "none",
        "intended_if_novel": "OUT-OF-SCOPE",
        "force_disposition": "OUT-OF-SCOPE",
    },
]


def mapping_kinds(xfer: dict) -> set[str]:
    return {str(row.get("ir_kind") or "") for row in xfer.get("mapping_table") or []}


def unknown_kinds(xfer: dict) -> list[str]:
    return sorted(k for k in mapping_kinds(xfer) if k not in IR_KINDS)
