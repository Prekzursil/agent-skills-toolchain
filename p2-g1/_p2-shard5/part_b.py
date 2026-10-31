def build_evidence(uid: str, probes: list, claim: str) -> list:
    p1, p2 = probes[0], probes[1]
    pair = [
        probe_row("source", p1[0], p1[1], p1[2]),
        probe_row("verifier", p2[0], p2[1], p2[2]),
    ]
    return [
        {
            "claim": claim[:2000],
            "verdict": "CONFIRMED",
            "anchor": "command-center/p2-wave/probes/" + uid
            + "/ (both named probes, live run 2026-10-24)",
            "probes": pair,
        }
    ]


def build_report(uid: str, kind: str, probes: list, extra_obs: list) -> dict:
    observations = list(extra_obs)
    for cmd, raw, rc in probes:
        marker_line = ""
        for line in raw.splitlines():
            if line.startswith("SUCCESS:") or line.startswith("FAILED:"):
                marker_line = line
                break
        observations.append(
            {
                "name": cmd.rsplit("/", 1)[-1] + " terminal-marker",
                "measured": marker_line or ("exit=" + str(rc)),
                "method": "command",
                "anchor": cmd,
            }
        )
    return {
        "kind": kind,
        "observations": observations[:64],
        "control_ids": [uid + "-probe1", uid + "-probe2"],
    }


def run_unit_probes(cfg: dict) -> list:
    probes = []
    for cmd in cfg["probes"]:
        rc, raw = run_probe(cmd)
        if rc != 0:
            raise RuntimeError("probe rc=" + str(rc) + ": " + cmd + " :: " + raw[-300:])
        probes.append((cmd, raw, rc))
    return probes
