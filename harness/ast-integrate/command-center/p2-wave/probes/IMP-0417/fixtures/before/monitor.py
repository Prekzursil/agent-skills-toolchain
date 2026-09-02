"""Pre-adoption monitor: independent exit-zero completion check (replaced)."""


def check_unit(payload):
    exit_code = payload.get("exit_code")
    if exit_code == 0:
        return {"verdict": "COMPLETE", "site": "monitor"}
    return {"verdict": "INCOMPLETE", "site": "monitor"}
