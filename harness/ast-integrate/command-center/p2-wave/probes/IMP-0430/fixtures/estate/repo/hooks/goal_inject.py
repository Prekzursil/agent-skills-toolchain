STORE_NAME = "goal_inject"
KEY_SHAPE = "session"
KEY_TEMPLATE = "{store}|{project_id}|{session_id}"


def note() -> str:
    return "goal_inject session-keyed"
