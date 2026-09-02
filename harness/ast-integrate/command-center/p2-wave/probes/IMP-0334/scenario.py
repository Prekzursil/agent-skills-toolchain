"""Shared roster and question for IMP-0334 probes."""

from tools.council.protocol.hats import (
    DEFAULT_PARTICIPANTS,
    DEFAULT_QUESTION,
    SIX_HATS,
)

PARTICIPANTS = DEFAULT_PARTICIPANTS
QUESTION = DEFAULT_QUESTION
LENS_IDS = tuple(lens.lens_id for lens in SIX_HATS)
ARTIFACT = "command-center/receipts/IMP-0334.json"
SENTINEL = "SUCCESS:IMP-0334"
