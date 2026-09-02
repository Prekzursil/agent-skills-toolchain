"""Mini no-regression gate. Probe 2 mutates THESE flags, never the tests."""

REQUIRE_COMPLETE_DEFAULT = True
REJECT_PARTIAL_WITHOUT_SENTINEL = True
LOG_SECRETS = False
MISSING_ARTIFACT_EXIT = 1
REJECT_GARBAGE = True

SENTINEL = "SUCCESS:gate"
REQUIRED_FIELD = "required_field"


def validate_payload(payload, require_complete=None):
    if require_complete is None:
        require_complete = REQUIRE_COMPLETE_DEFAULT
    if not isinstance(payload, dict):
        return {"ok": False, "reason": "not-an-object"}
    if require_complete and REQUIRED_FIELD not in payload:
        return {"ok": False, "reason": "missing-required-field"}
    if REJECT_PARTIAL_WITHOUT_SENTINEL and REQUIRED_FIELD in payload:
        text = str(payload.get("text") or "")
        if SENTINEL not in text:
            return {"ok": False, "reason": "partial-without-sentinel"}
    return {"ok": True, "reason": "ok"}


def maybe_log(event, secret=None):
    if LOG_SECRETS and secret:
        return f"{event} secret={secret}"
    return str(event)


def missing_artifact_exit():
    return int(MISSING_ARTIFACT_EXIT)


def accept_record(obj):
    if REJECT_GARBAGE and not (
        isinstance(obj, dict) and obj.get("kind") == "refutation-record"
    ):
        return False
    return True
