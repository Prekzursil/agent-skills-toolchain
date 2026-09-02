"""Information-partition fixtures and seat search (ADV-0106)."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Iterable

HONEST = "HONEST"
NAIVE_SUMMARY = "NAIVE_SUMMARY"
NAIVE_SCRATCHPAD = "NAIVE_SCRATCHPAD"
NAIVE_TOOL = "NAIVE_TOOL"
NAIVE_PARAPHRASE = "NAIVE_PARAPHRASE"
DETECTOR_CONTROL = "DETECTOR_CONTROL"
ASSEMBLY_LEAK = "ASSEMBLY_LEAK"
MODES = (
    HONEST,
    NAIVE_SUMMARY,
    NAIVE_SCRATCHPAD,
    NAIVE_TOOL,
    NAIVE_PARAPHRASE,
    DETECTOR_CONTROL,
    ASSEMBLY_LEAK,
)
SEAT_A = "seat-a"
SEAT_B = "seat-b"
ALL_SEATS = (SEAT_A, SEAT_B, "moderator")
WITHHELD_NONCE = "nonce-withheld-adv0106"
ALLOWED_NONCE = "nonce-allowed-adv0106"
WITHHELD_ID = "B-WITHHELD"
ALLOWED_ID = "B-ALLOWED"
SUMMARY_PATH = f"derived/moderator_summary/{WITHHELD_ID}"
PARAPHRASE_PATH = f"derived/moderator_paraphrase/{WITHHELD_ID}"


def mint_canary(kind: str, nonce: str) -> str:
    digest = hashlib.sha256(f"{kind}|{nonce}".encode("utf-8")).hexdigest()[:16]
    return f"CANARY-{kind}-{digest}"


@dataclass
class Artifact:
    path: str
    body: str
    kind: str
    visible_to: tuple[str, ...]


@dataclass
class SearchHit:
    path: str
    snippet: str = ""


@dataclass
class SearchResult:
    hit_count: int
    leaked: bool
    hits: list[SearchHit]
    paths_searched: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "hit_count": self.hit_count,
            "leaked": self.leaked,
            "hits": [{"path": h.path, "snippet": h.snippet} for h in self.hits],
            "paths_searched": list(self.paths_searched),
        }


@dataclass
class FixtureRound:
    withheld_canary: str
    allowed_canary: str
    artifacts: list[Artifact]
    notes: dict[str, Any] = field(default_factory=dict)


class EmptySearchError(RuntimeError):
    pass


def require_real_search(result: SearchResult) -> SearchResult:
    if not result.paths_searched:
        raise EmptySearchError("search ran over an empty artifact set")
    return result


def search_seat(seat_id: str, needle: str, artifacts: Iterable[Artifact]) -> SearchResult:
    arts = list(artifacts)
    hits = []
    searched = []
    for art in arts:
        if seat_id not in art.visible_to:
            continue
        searched.append(art.path)
        if needle and needle in (art.body or ""):
            hits.append(SearchHit(path=art.path, snippet=needle))
    return SearchResult(
        hit_count=len(hits),
        leaked=bool(hits),
        hits=hits,
        paths_searched=searched,
    )


REDACTED_PARAPHRASE = "Moderator paraphrase: [REDACTED:information-partition]"


def paraphrase_privileged(private_body: str, withheld_canary: str) -> str:
    """Return the moderator's paraphrase of privileged material.

    A real moderator restates the substance of the privileged round in their
    own words for every seat. The canary token is stripped (it is an opaque
    string nobody would repeat), so a token search on the paraphrase stays
    silent, while the withheld facts it conveys remain readable. This is the
    leakage channel canary-only detectors miss.
    """
    substance = private_body.replace(withheld_canary, "").strip()
    substance = " ".join(substance.split())
    if not substance:
        return REDACTED_PARAPHRASE
    if substance.endswith("."):
        substance = substance[:-1]
    return f"Moderator paraphrase: {substance}; the closed vendor bid stands as tabled."


def run_fixture(mode: str) -> FixtureRound:
    withheld = mint_canary("WITHHELD", WITHHELD_NONCE)
    allowed = mint_canary("ALLOWED", ALLOWED_NONCE)
    public_body = (
        "Public briefing. Allowed token is public. Closing stock acknowledgement."
    )
    private_body = f"Privileged cost ledger. Secret figure is 17. {withheld}"
    leak = mode != HONEST
    seat_a_body = public_body + (f" {allowed}" if True else "")
    if leak:
        seat_a_body = seat_a_body + " " + private_body
        if mode == ASSEMBLY_LEAK:
            seat_a_body += " You are the partitioned analyst seat-a"
    arts = [
        Artifact("public/briefing.txt", public_body + f" {allowed}", "public", ALL_SEATS),
        Artifact("seat-a/notes.txt", seat_a_body, "seat-notes", (SEAT_A,)),
        Artifact(
            "seat-b/privileged.txt",
            private_body,
            "privileged",
            (SEAT_B,),
        ),
        Artifact(
            "moderator/paraphrase.txt",
            paraphrase_privileged(private_body, withheld),
            "moderator_paraphrase",
            ALL_SEATS,
        ),
    ]
    # Assembled per-seat prompts: seat-a's prompt is built from B-ALLOWED only,
    # seat-b's prompt carries the B-WITHHELD bundle (privileged seat).
    seat_a_prompt = (
        f"You are the partitioned analyst {SEAT_A}. Briefing bundle {ALLOWED_ID}: "
        f"{public_body} {allowed}"
    )
    if mode == DETECTOR_CONTROL:
        # Detector control: the SAME withheld token planted in the ALLOWED bundle
        # must be found by the same search that reports zero hits in HONEST.
        seat_a_prompt += f" Planted-in-{ALLOWED_ID}: {withheld}"
    seat_b_prompt = (
        f"You are the privileged seat {SEAT_B}. Bundle {ALLOWED_ID}: {public_body} "
        f"{allowed} Bundle {WITHHELD_ID}: {private_body}"
    )
    arts.append(Artifact("seat-a/prompt", seat_a_prompt, "assembled-prompt", (SEAT_A,)))
    arts.append(Artifact("seat-b/prompt", seat_b_prompt, "assembled-prompt", (SEAT_B,)))

    # Forced moderator summary of the withheld bundle: it necessarily carries the
    # token, so the honest assembler keeps it privileged (seat-b + moderator) while
    # a naive summary channel exposes it to the partitioned seat.
    summary_body = f"Moderator summary of {WITHHELD_ID}: {private_body}"
    summary_visible: tuple[str, ...] = (SEAT_B, "moderator")
    if mode == NAIVE_SUMMARY:
        summary_visible = ALL_SEATS
    arts.append(Artifact(SUMMARY_PATH, summary_body, "moderator_summary", summary_visible))
    arts.append(
        Artifact(
            PARAPHRASE_PATH,
            paraphrase_privileged(private_body, withheld),
            "moderator_paraphrase",
            ALL_SEATS,
        )
    )
    if mode == NAIVE_SCRATCHPAD:
        arts.append(
            Artifact(
                "shared/scratchpad.md",
                f"Working notes (shared): {private_body}",
                "scratchpad",
                ALL_SEATS,
            )
        )
    if mode == NAIVE_TOOL:
        arts.append(
            Artifact(
                "tools/ledger-lookup/output.json",
                f'{{"tool": "ledger-lookup", "result": "{private_body}"}}',
                "tool-output",
                ALL_SEATS,
            )
        )
    if mode == NAIVE_PARAPHRASE:
        arts.append(
            Artifact(
                "derived/moderator_paraphrase/naive",
                f"Moderator paraphrase (verbatim): {private_body}",
                "moderator_paraphrase",
                ALL_SEATS,
            )
        )
    if mode == DETECTOR_CONTROL:
        arts.append(
            Artifact(
                "seat-a/planted-leak.txt",
                f"planted {withheld}",
                "detector",
                (SEAT_A,),
            )
        )
    notes = {
        "mode": mode,
        "forced_moderator_summary": True,
        "summary_path": SUMMARY_PATH,
        "summary_visible_to": list(summary_visible),
        "withheld_bundle_id": WITHHELD_ID,
        "allowed_bundle_id": ALLOWED_ID,
    }
    return FixtureRound(
        withheld_canary=withheld, allowed_canary=allowed, artifacts=arts, notes=notes
    )
