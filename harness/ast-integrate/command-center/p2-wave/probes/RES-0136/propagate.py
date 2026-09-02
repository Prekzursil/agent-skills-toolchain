"""Map rider clauses onto distribution acts.

Acts named by the catalog: vendoring, linking, invoking, publishing.
Verdicts are derived from the quoted operative sentences, not from a
policy overlay.
"""
from __future__ import annotations

ACTS = ("vendoring", "linking", "invoking", "publishing")

# Sherman-Kent verbal bands (CIA, 1964 / Sherman Kent).
BANDS = {
    "almost_certain": {
        "band": "almost certain",
        "p_low": 0.93,
        "p_high": 0.99,
    },
    "probable": {"band": "probable", "p_low": 0.75, "p_high": 0.85},
    "even_chance": {"band": "even chance", "p_low": 0.45, "p_high": 0.55},
}


def mcp_agent_mail_acts() -> list[dict]:
    """Propagation of the OpenAI/Anthropic rider on mcp_agent_mail."""
    quote_dist = (
        "You may not provide, disclose, distribute, sublicense, sell, lease, lend, "
        "host, make available, or otherwise permit access to the Software or any "
        "derivative work of the Software"
    )
    quote_include = (
        "any distribution of the Software or any Derivative Works must include "
        "this rider provision unmodified"
    )
    quote_use = (
        'For purposes of this rider, "use" includes, without limitation: copying, '
        "modifying, merging, publishing, distributing, sublicensing, selling, "
        "transferring, making available, hosting, deploying, executing, benchmarking, "
        "testing, analyzing, indexing, or incorporating the Software or any Derivative "
        "Works into any dataset, training corpus, evaluation harness, or pipeline for "
        "machine learning or other automated systems."
    )
    return [
        {
            "act": "vendoring",
            "triggers": True,
            "why": (
                "Copying upstream source into a redistributed tree is distribution "
                "of the Software. The rider must travel unmodified. Providing that "
                "copy to or for a Restricted Party is forbidden."
            ),
            "clause": quote_dist,
            "also": quote_include,
            "confidence": BANDS["almost_certain"],
        },
        {
            "act": "linking",
            "triggers": True,
            "why": (
                "Shipping a combined binary or importable tree that contains the "
                "Software is distribution of the Software or a Derivative Work. "
                "Same rider-inclusion and Restricted-Party bars as vendoring. "
                "Linking at runtime against a user-local install, without shipping "
                "the library, is treated as invoking instead."
            ),
            "clause": quote_dist,
            "also": quote_include,
            "confidence": BANDS["probable"],
        },
        {
            "act": "invoking",
            "triggers": False,
            "why": (
                "A client that speaks MCP/HTTP to a separately running local "
                "server does not copy the Software into the client package, so "
                "the client's distribution is not distribution of the Software. "
                "The operator who executes the server is using the Software; if "
                "that operator is a Restricted Party, that execution is in-scope "
                "of the rider's definition of use. Whether an Anthropic- or "
                "OpenAI-directed agent calling a user-owned local process counts "
                "as Restricted-Party use is legal-uncertainty, not settled here."
            ),
            "clause": quote_use,
            "restricted_party_execution": "LEGAL-UNCERTAINTY",
            "confidence": BANDS["probable"],
            "uncertainty_on": "restricted-party-directed-local-execution",
            "uncertainty_band": BANDS["even_chance"],
        },
        {
            "act": "publishing",
            "triggers": "IF-ARTIFACT-CONTAINS-SOFTWARE",
            "why": (
                "A marketplace listing that contains the Software or a Derivative "
                "Work is distribution (same as vendoring). A listing that is only "
                "client/config pointing at a user-installed server is not."
            ),
            "clause": quote_include,
            "confidence": BANDS["almost_certain"],
        },
    ]


def llama_acts() -> list[dict]:
    return [
        {
            "act": "vendoring",
            "triggers": True,
            "why": (
                "Distributing Llama Materials or a product that contains them "
                "requires providing the Agreement and 'Built with Llama' "
                "attribution. Additional Commercial Terms (700 million MAU on "
                "the 2024-07-23 release date) are a field-of-use gate on the "
                "licence itself, not an OSI rider."
            ),
            "confidence": BANDS["almost_certain"],
        },
        {
            "act": "linking",
            "triggers": True,
            "why": "A product that contains Llama Materials is redistribution of those materials.",
            "confidence": BANDS["probable"],
        },
        {
            "act": "invoking",
            "triggers": False,
            "why": (
                "Calling a hosted Llama-3.1 API does not redistribute Llama "
                "Materials; it is the host's service. This tree does not vendor "
                "weights."
            ),
            "confidence": BANDS["probable"],
        },
        {
            "act": "publishing",
            "triggers": "IF-ARTIFACT-CONTAINS-WEIGHTS-OR-DERIVATIVE-MODEL",
            "why": "Publishing weights or a derivative model is redistribution under §1.b.i.",
            "confidence": BANDS["almost_certain"],
        },
    ]


def jsonschema_acts() -> list[dict]:
    return [
        {
            "act": act,
            "triggers": False,
            "why": "Plain OSI MIT: no rider to propagate under any of the four acts.",
            "confidence": BANDS["almost_certain"],
        }
        for act in ACTS
    ]
