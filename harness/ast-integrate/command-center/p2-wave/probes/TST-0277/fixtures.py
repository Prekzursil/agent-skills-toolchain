"""B05-shaped competency taxonomy and scripted cast for TST-0277.

Production bucket B05 and tools/council/simulate.py are absent on this
worktree. This taxonomy is the confirmation substrate: six named
competencies with stable ids. Coverage is exact-id set difference.
A declared synonym such as 'crypto' does not cover 'cryptography'.
"""
from __future__ import annotations

TAXONOMY = {
    "cryptography": "Public-key, HE, padding, and ciphertext side-channels.",
    "threat-modeling": "Attacker models, information leakage, observer capabilities.",
    "legal-compliance": "DPIA, tenant isolation as a legal control, residual risk.",
    "distributed-systems": "Sidecar topology, failure domains, blast radius.",
    "performance-engineering": "Latency, throughput, and cost of a sidecar hop.",
    "ux-accessibility": "Operator UX of the isolation control.",
}

DECISION = {
    "id": "dec-he-sidecar",
    "question": (
        "Ship a homomorphic-encryption sidecar as the tenant-isolation control?"
    ),
    "required_competencies": (
        "cryptography",
        "threat-modeling",
        "legal-compliance",
    ),
}

UNIQUE_CLAIM_ID = "CLAIM-TST0277-FHE17-SIZE-LEAK"
UNIQUE_CLAIM_TEXT = (
    "CLAIM-TST0277-FHE17-SIZE-LEAK: Fixture F-HE-17 packs Paillier ciphertexts "
    "without fixed-width padding, so ciphertext byte-length still encodes tenant "
    "identity. A sidecar that only encrypts payloads does not isolate tenants "
    "until every ciphertext is padded to a constant width. Counterexample: "
    "tenant T-gamma payloads are 17 bytes and T-delta payloads are 4096 bytes; "
    "a network observer recovers the tenant from size alone."
)

LEGAL_CLAIM_ID = "CLAIM-TST0277-DPIA-ABSENT"
LEGAL_CLAIM_TEXT = (
    "CLAIM-TST0277-DPIA-ABSENT: No data-protection impact assessment names the "
    "HE sidecar as a legal isolation control. Shipping it as the isolation "
    "story is a compliance claim without an evidence node."
)

TRIGGER = "missing-expertise"

HOLE_PANEL = (
    {
        "id": "seat-arch",
        "role": "Architect",
        "competencies": ("distributed-systems", "performance-engineering"),
        "vote": "ship-sidecar",
        "brief": (
            "Add an HE sidecar in front of the tenant store. Topology is a "
            "single extra hop; blast radius is the sidecar process."
        ),
        "claims": (
            {
                "id": "CLAIM-ARCH-HOP",
                "text": "A single sidecar hop is an acceptable failure domain.",
            },
        ),
    },
    {
        "id": "seat-ops",
        "role": "Operator",
        "competencies": ("performance-engineering", "ux-accessibility"),
        "vote": "ship-sidecar",
        "brief": (
            "p99 latency budget still holds with one extra hop. Ship this "
            "iteration; isolation is the sidecar's job."
        ),
        "claims": (
            {
                "id": "CLAIM-OPS-P99",
                "text": "p99 stays inside budget with one extra hop.",
            },
        ),
    },
    {
        "id": "seat-product",
        "role": "Product",
        "competencies": ("ux-accessibility",),
        "vote": "ship-sidecar",
        "brief": (
            "Operators already understand sidecars. No UX change is required."
        ),
        "claims": (
            {
                "id": "CLAIM-UX-NOCHANGE",
                "text": "Operator UX is unchanged if we reuse the sidecar pattern.",
            },
        ),
    },
)

COVERED_PANEL = (
    {
        "id": "seat-crypto",
        "role": "Cryptographer",
        "competencies": ("cryptography",),
        "vote": "refuse-he-sidecar",
        "brief": (
            "Envelope encryption with AES-GCM at rest already isolates tenants "
            "at the storage layer. An HE sidecar is the wrong control."
        ),
        "claims": (
            {
                "id": "CLAIM-AES-GCM-ENVELOPE",
                "text": "AES-GCM envelope encryption isolates tenants at rest.",
            },
        ),
    },
    {
        "id": "seat-threat",
        "role": "ThreatModeler",
        "competencies": ("threat-modeling",),
        "vote": "refuse-he-sidecar",
        "brief": (
            "The relevant attacker is a network observer, not a storage "
            "operator. HE on the wire without a threat model is theatre."
        ),
        "claims": (
            {
                "id": "CLAIM-OBSERVER-MODEL",
                "text": "The attacker of record is a network observer, not disk.",
            },
        ),
    },
    {
        "id": "seat-legal",
        "role": "Counsel",
        "competencies": ("legal-compliance",),
        "vote": "refuse-he-sidecar",
        "brief": (
            "Tenant isolation as a legal control is already bound to the "
            "storage encryption appendix. Relabeling a sidecar does not "
            "amend that appendix."
        ),
        "claims": (
            {
                "id": "CLAIM-APPENDIX-BINDS",
                "text": "The storage-encryption appendix already binds isolation.",
            },
        ),
    },
)

SYNONYM_PANEL = (
    {
        "id": "seat-alias",
        "role": "AliasSpeaker",
        "competencies": ("crypto", "threats", "legal"),
        "vote": "ship-sidecar",
        "brief": "We have crypto, threats, and legal covered by alias.",
        "claims": (
            {
                "id": "CLAIM-ALIAS-COVER",
                "text": "Declared synonyms should not count as coverage.",
            },
        ),
    },
)

BENCH = (
    {
        "id": "recruited-crypto-critic",
        "role": "IndependentCryptographer",
        "competencies": ("cryptography", "threat-modeling"),
        "vote": "refuse-until-fixed-width-padding",
        "brief": UNIQUE_CLAIM_TEXT,
        "claims": (
            {"id": UNIQUE_CLAIM_ID, "text": UNIQUE_CLAIM_TEXT},
        ),
    },
    {
        "id": "recruited-legal-critic",
        "role": "IndependentCounsel",
        "competencies": ("legal-compliance",),
        "vote": "refuse-until-dpia",
        "brief": LEGAL_CLAIM_TEXT,
        "claims": (
            {"id": LEGAL_CLAIM_ID, "text": LEGAL_CLAIM_TEXT},
        ),
    },
)

RUBBERSTAMP_BRIEF = (
    "I concur with the seated majority. No additional claim or counterexample."
)

HOLE_SHIP_RECOMMENDATION = (
    "Ship the homomorphic-encryption sidecar as the tenant-isolation control."
)

POST_RECRUIT_RECOMMENDATION = (
    "Do not ship the HE sidecar as the isolation control. "
    "CLAIM-TST0277-FHE17-SIZE-LEAK is open: F-HE-17 ciphertext size leaks "
    "tenant identity for T-gamma versus T-delta until fixed-width padding. "
    "CLAIM-TST0277-DPIA-ABSENT is open: no DPIA names the sidecar."
)

COVERED_RECOMMENDATION = (
    "Do not ship an HE sidecar. AES-GCM envelope encryption already isolates "
    "tenants at rest; the network-observer threat is out of that control's "
    "scope; the legal appendix already binds isolation to storage encryption."
)
