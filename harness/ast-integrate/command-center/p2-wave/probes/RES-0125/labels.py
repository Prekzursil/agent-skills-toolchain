"""RES-0125 obligation labels. Catalog tests_required names these three."""

ALLOWED_LABELS = (
    "required-by-terms",
    "required-by-law-somewhere",
    "proposed-norm",
)

SENTINEL = (
    "SUCCESS:RES-0125 in the receipt AND an obligation table "
    "with a required-versus-proposed label per row"
)

UNIT = "RES-0125"
OUT_REL = "command-center/research/RES-0125.json"
SCHEMA_DECLARED = "command-center/schema/research-claim-record.schema.json"
