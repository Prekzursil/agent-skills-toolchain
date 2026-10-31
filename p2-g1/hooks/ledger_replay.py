"""Session-keyed store declaration for the ledger_replay harness state store.

Delivered by IMP-0430 (session-keying audit): every harness state store is
keyed by session, never by project alone, so two concurrent sessions in the
same project cannot read each other's state. The audit probes
(command-center/p2-wave/probes/IMP-0430/) scan this declaration.
"""

STORE_NAME = "ledger_replay"
KEY_SHAPE = "session"
KEY_TEMPLATE = "{store}|{project_id}|{session_id}"


def note() -> str:
    return "ledger_replay session-keyed"
