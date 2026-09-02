STORE_NAME = "caches"
KEY_SHAPE = "session"
KEY_TEMPLATE = "{store}|{project_id}|{session_id}"


def note() -> str:
    return "caches session-keyed"
