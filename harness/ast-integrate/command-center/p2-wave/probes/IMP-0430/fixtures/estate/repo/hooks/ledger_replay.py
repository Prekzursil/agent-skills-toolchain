STORE_NAME = "ledger_replay"
KEY_SHAPE = "session"
KEY_TEMPLATE = "{store}|{project_id}|{session_id}"


def note() -> str:
    return "ledger_replay session-keyed"
