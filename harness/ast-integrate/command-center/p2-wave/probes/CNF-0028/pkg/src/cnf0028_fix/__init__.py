"""CNF-0028 packaging fixture: corrected behaviour is importlib.resources payload."""

from importlib.resources import files

PAYLOAD_TOKEN = "CNF-0028-PACKAGED-PAYLOAD-v1"


def packaged_payload() -> str:
    return files("cnf0028_fix.data").joinpath("payload.txt").read_text(encoding="utf-8").strip()
