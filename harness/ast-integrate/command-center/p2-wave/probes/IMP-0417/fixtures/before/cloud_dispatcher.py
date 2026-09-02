"""Pre-adoption cloud dispatcher: independent exit-zero completion check (replaced)."""


def check_unit(payload):
    if payload.get("exit_code") == 0:
        return {"verdict": "COMPLETE", "site": "cloud_dispatcher"}
    return {"verdict": "INCOMPLETE", "site": "cloud_dispatcher"}
