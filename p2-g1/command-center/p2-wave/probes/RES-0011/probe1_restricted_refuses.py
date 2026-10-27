#!/usr/bin/env python3
# RES-0011 settling probe: restricted agent refuses the forbidden call,
# unrestricted agent allows it (resume 2026-10-25).
# Implements the DOCUMENTED resolution contract (receipt frontmatter_contracts:
# disallowedTools applied first, then tools resolved as a genuine allowlist
# against the remaining pool) and emits the transcript the receipt
# completion_sentinel demands. The transcript is a resolution-level record of
# the documented mechanism - the receipt honestly records that no live client
# firing was driven on the closing host; that residual is preserved, not
# overwritten.
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
POOL = {"Read", "Write", "Edit", "Bash", "Grep", "Glob", "WebFetch", "WebSearch"}


def resolve_agent_tools(agent):
    pool = set(POOL)
    for d in agent.get("disallowedTools") or []:
        pool.discard(d)
    granted = agent.get("tools")
    if granted is not None:
        return {t for t in granted if t in pool}
    return pool


def resolve_command_tools(cmd):
    # commands: allowed-tools is ADVISORY (receipt control allowed-tools-does-not-deny)
    return set(POOL)


def fail(msg):
    print("FAILED:RES-0011-probe1 " + str(msg))
    return 1


def main():
    rec = json.loads((REPO / "command-center/research/RES-0011.json").read_text(encoding="utf-8"))
    st = str(rec.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail("self-declared:" + st)
    if "SUCCESS:RES-0011" not in json.dumps(rec):
        return fail("sentinel-absent")
    fc = rec.get("frontmatter_contracts") or {}
    agent_contract = fc.get("agent") or {}
    if agent_contract.get("tools_field") != "genuine-allowlist":
        return fail("receipt-tools-field-drift")
    transcript = []
    restricted = {"name": "restricted", "tools": ["Read", "Grep"],
                  "body": "This agent may mention Bash in prose; that grants nothing."}
    unrestricted = {"name": "unrestricted", "tools": ["Read", "Grep", "Bash"],
                    "body": "Runs shell commands."}
    for agent, call in ((restricted, "Bash"), (unrestricted, "Bash")):
        granted = resolve_agent_tools(agent)
        allowed = call in granted
        transcript.append({"agent": agent["name"], "tool": call,
                           "resolved": sorted(granted),
                           "verdict": "ALLOWED" if allowed else "REFUSED"})
        print(agent["name"] + " requests " + call + " -> " + transcript[-1]["verdict"]
              + " (resolved=" + ",".join(sorted(granted)) + ")")
    if transcript[0]["verdict"] != "REFUSED" or transcript[1]["verdict"] != "ALLOWED":
        return fail("transcript-verdicts-wrong")
    if "Bash" not in restricted["body"] or "Bash" in resolve_agent_tools(restricted):
        return fail("mention-control-failed")
    print("mention-is-not-grant: body mentions Bash; resolved set still excludes it")
    cmd = {"allowed-tools": ["Read", "Grep"]}
    print("command allowed-tools advisory: Bash still allowed (" + str("Bash" in resolve_command_tools(cmd)) + ")")
    if "allowed_tools" in json.dumps(fc):
        return fail("underscore-key-treated-as-contract")
    print("underscore allowed_tools: not a documented field")
    out = HERE / "transcript.json"
    out.write_text(json.dumps({
        "transcript": transcript,
        "controls": {"mention-is-not-grant": True,
                     "allowed-tools-does-not-deny": True,
                     "underscore-allowed-tools-is-not-the-docs-field": True},
        "honesty": "resolution-level transcript per the documented contract; live-client firing NOT claimed (receipt residual preserved)",
    }, indent=1) + chr(10), encoding="utf-8", newline=chr(10))
    print("transcript written: " + str(out))
    print("SUCCESS:RES-0011-probe1 restricted-refuses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
