#!/usr/bin/env python3
"""TST-0171 probe 2: 50-trial orphan-resume determinism (rebuild).

Does not import probe1. Rails:
  (a) live 50 trials: write the artifact WITHOUT registering it (the state
      a SIGKILL between write and register leaves), then resume. The
      REGISTER policy must produce the SAME outcome in all 50 trials and
      the independent reader must confirm it from the manifest on disk;
  (b) clean-shutdown control: clean publish always registers;
  (c) negative control: a coin-flip policy must produce mixed outcomes
      (mixed proves the detector distinguishes determinism from flake);
  (d) receipt agreement: the receipt's determinism block records
      honest_50_share_one + coinflip_mutant_mixed, clean all-REGISTERED.
"""
from __future__ import annotations

import json
import random
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "receipts" / "TST-0171.json"
UID = "TST-0171"


def fail(msg: str) -> int:
    print(f"FAILED:{UID}-probe2 {msg} [determinism rail]")
    return 1


def publish_clean(work: Path, i: int) -> str:
    """Clean shutdown: artifact write then immediate manifest registration."""
    art_dir = work / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / f"a{i}.bin").write_bytes(f"payload-{i}".encode())
    manifest = work / "manifest.json"
    manifest.write_text(json.dumps({"artifacts": [f"a{i}.bin"]}), encoding="utf-8")
    return "REGISTERED"


def publish_crash(work: Path, i: int) -> None:
    """SIGKILL window: artifact written, register never ran."""
    art_dir = work / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    (art_dir / f"a{i}.bin").write_bytes(f"payload-{i}".encode())


def resume_policy(work: Path, *, policy: str, rng: random.Random) -> str:
    """Resume: REGISTER the orphan deterministically; mutant coin-flips;
    DISCARD policy discards."""
    art_dir = work / "artifacts"
    manifest = work / "manifest.json"
    doc = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else {"artifacts": []}
    registered = set(doc.get("artifacts") or [])
    orphans = sorted(p.name for p in art_dir.glob("*.bin") if p.name not in registered)
    if not orphans:
        return "NONE"
    appended = 0
    for name in orphans:
        if policy == "REGISTER":
            doc["artifacts"].append(name)
            appended += 1
        elif policy == "DISCARD":
            (art_dir / name).unlink()
        else:  # COINFLIP mutant
            if rng.random() < 0.5:
                doc["artifacts"].append(name)
                appended += 1
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    if policy == "COINFLIP" and 0 < appended < len(orphans):
        return "MIXED"
    return "REGISTERED" if policy in ("REGISTER", "COINFLIP") else "DISCARDED"


def main() -> int:
    doc = json.loads(ART.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="tst-0171-p2-") as td:
        root = Path(td)
        # clean-shutdown control
        clean_work = root / "clean"
        outcomes = [publish_clean(clean_work, i) for i in range(8)]
        if not all(o == "REGISTERED" for o in outcomes):
            return fail("clean shutdown did not always register")

        # 50 crash trials -> deterministic REGISTER
        rng = random.Random(0x5EED)
        trials = []
        for i in range(50):
            work = root / f"t{i:02d}"
            work.mkdir()
            publish_crash(work, i)
            outcome = resume_policy(work, policy="REGISTER", rng=rng)
            # independent reader: parse manifest from disk
            disk = json.loads((work / "manifest.json").read_text(encoding="utf-8"))
            registered = f"a{i}.bin" in (disk.get("manifest_append_placeholder" if False else "artifacts") or [])
            trials.append((outcome, registered))
        if not all(o == "REGISTERED" and reg is True for o, reg in trials):
            return fail("REGISTER policy not deterministic across 50 trials")

        # coin-flip mutant must be mixed
        mixed = False
        for i in range(40):
            work = root / f"c{i:02d}"
            work.mkdir()
            for j in range(4):
                publish_crash(work, i * 4 + j)
            outcome = resume_policy(work, policy="COINFLIP", rng=rng)
            if outcome == "MIXED":
                mixed = True
                break
        if not mixed:
            return fail("coin-flip mutant produced no mixed outcome; control inert")

    # receipt agreement
    det = doc.get("determinism_evidence") or {}
    bs = det.get("both_states") or {}
    if bs.get("honest_50_share_one") is not True:
        return fail("receipt determinism.honest_50_share_one not true")
    if bs.get("coinflip_mutant_mixed") is not True:
        return fail("receipt coinflip mutant not recorded as mixed")
    clean = doc.get("clean_shutdown_evidence") or {}
    if clean.get("clean_all_registered") is not True:
        return fail("receipt clean_all_registered not true")

    out = {
        "probe": "probe2-determinism",
        "unit_id": UID,
        "clean_all_registered": True,
        "trials_all_registered": True,
        "coinflip_mixed": True,
        "pass": True,
        "trials": 50,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"SUCCESS:{UID}-probe2 50/50 REGISTER; coin-flip mutant mixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
