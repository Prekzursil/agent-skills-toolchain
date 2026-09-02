"""Pre-adoption final synthesis: independent exit-zero completion check (replaced)."""


def check_unit(payload):
    exit_code = payload.get("synth_rc", 1)
    if exit_code == 0:
        return {"verdict": "COMPLETE", "site": "final_synthesis"}
    return {"verdict": "INCOMPLETE", "site": "final_synthesis"}
