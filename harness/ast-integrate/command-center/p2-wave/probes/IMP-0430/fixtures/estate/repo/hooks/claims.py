STORE_NAME = "claims"
KEY_SHAPE = "session"
KEY_TEMPLATE = "{store}|{project_id}|{session_id}"


def note() -> str:
    return "claims session-keyed"
