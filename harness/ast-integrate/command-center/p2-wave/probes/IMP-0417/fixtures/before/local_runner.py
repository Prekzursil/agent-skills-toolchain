"""Pre-adoption local runner: independent exit-zero completion check (replaced)."""


def check_unit(payload):
    if payload.get("exit_code") == 0:
        return {"verdict": "COMPLETE", "site": "local_runner"}
    return {"verdict": "INCOMPLETE", "site": "local_runner"}
