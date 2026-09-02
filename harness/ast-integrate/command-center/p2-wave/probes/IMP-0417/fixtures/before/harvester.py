"""Pre-adoption harvester: independent exit-zero completion check (replaced)."""


def check_unit(payload):
    if payload.get("exit_code") == 0:
        return {"verdict": "COMPLETE", "site": "harvester"}
    return {"verdict": "INCOMPLETE", "site": "harvester"}
