"""ADV-0027: fail-closed probe guard instead of the provisional-BLOCKED cycle.

The probes must run against a SUCCESS-shaped artifact (probe1 asserts state,
probe2 validates the SUCCESS schema branch which requires an executed
downstream consumer and a fired negative control). The delivery contract is
therefore: write the SUCCESS artifact, run the probes IMMEDIATELY, and on any
probe failure OVERWRITE the artifact with a fail-closed BLOCKED receipt so no
lying green file survives.
"""
from pathlib import Path

p = Path(
    __file__).resolve().parents[1] / "command-center/p2-wave/probes/ADV-0027/write_receipts.py"
src = p.read_text(encoding="utf-8")

# 1. drop the provisional machinery (state is always the real claim)
old = '''def build_receipt(
    live: dict,
    now: str,
    probes: list[dict] | None = None,
    provisional: bool = False,
) -> dict:'''
new = '''def build_receipt(
    live: dict,
    now: str,
    probes: list[dict] | None = None,
) -> dict:'''
assert old in src, "signature anchor"
src = src.replace(old, new, 1)

old = '''        "state": "BLOCKED" if provisional else "SUCCESS",'''
new = '''        "state": "SUCCESS",'''
assert old in src, "state anchor"
src = src.replace(old, new, 1)

old = '''        **(
            {
                "failure": {
                    "classification": ["provisional-pre-probe"],
                    "reason": (
                        "Pass-1 provisional artifact: written before the named "
                        "probes execute so probe2 can validate the file on disk; "
                        "flipped to SUCCESS after both probes pass."
                    ),
                }
            }
            if provisional
            else {}
        ),
        "retry": {'''
new = '''        "retry": {'''
assert old in src, "failure anchor"
src = src.replace(old, new, 1)

old = '''    receipt = build_receipt(live, now, probes=None, provisional=True)
    validate_schema(receipt)'''
new = '''    receipt = build_receipt(live, now, probes=None)
    validate_schema(receipt)'''
assert old in src, "main pass1 anchor"
src = src.replace(old, new, 1)

old = '''    receipt = build_receipt(live, now2, probes=probes, provisional=False)
    receipt["timestamps"]["ended_at"] = now2'''
new = '''    receipt = build_receipt(live, now2, probes=probes)
    receipt["timestamps"]["ended_at"] = now2'''
assert old in src, "main pass2 anchor"
src = src.replace(old, new, 1)

# 2. fail-closed guard: a probe failure must not leave a green artifact
old = '''    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0027 probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1'''
new = '''    def fail_closed(msg: str) -> int:
        # No lying green artifact may survive a failed verification: overwrite
        # with a BLOCKED receipt before returning failure.
        try:
            doc = json.loads((REPO / OUT).read_text(encoding="utf-8"))
            doc["state"] = "BLOCKED"
            doc["failure"] = {
                "classification": ["probe-failure"],
                "reason": msg[:900],
            }
            (REPO / OUT).write_text(
                json.dumps(doc, indent=1, sort_keys=True) + "\\n", encoding="utf-8"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED:ADV-0027 fail-closed overwrite also failed: {exc}")
        print(f"FAILED:ADV-0027 {msg}")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        return fail_closed(f"probes c1={c1} c2={c2}; {t1[-400:]} | {t2[-400:]}")'''
assert old in src, "probe run anchor"
src = src.replace(old, new, 1)

old = '''    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:ADV-0027 probes after receipt update c1={c1b} c2={c2b}")
        print(t1b[-3000:])
        print(t2b[-3000:])
        return 1'''
new = '''    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        return fail_closed(
            f"probes after receipt update c1={c1b} c2={c2b}; {t1b[-400:]} | {t2b[-400:]}"
        )'''
assert old in src, "re-run anchor"
src = src.replace(old, new, 1)

p.write_text(src, encoding="utf-8")
import ast
ast.parse(src)
print("fail-closed guard in place")
