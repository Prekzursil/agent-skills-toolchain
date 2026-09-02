"""Pre-adoption cross-vendor adapter: independent exit-zero completion check (replaced)."""


def check_unit(payload):
    if payload.get("exit_code") == 0:
        return {"verdict": "COMPLETE", "site": "cross_vendor_adapter"}
    return {"verdict": "INCOMPLETE", "site": "cross_vendor_adapter"}
