"""Pre-adoption workflow fan-in: independent exit-zero completion check (replaced)."""


def check_unit(payload):
    exit_code = int(payload.get("exit_code") or 1)
    if exit_code == 0:
        return {"verdict": "COMPLETE", "site": "workflow_fanin"}
    return {"verdict": "INCOMPLETE", "site": "workflow_fanin"}
