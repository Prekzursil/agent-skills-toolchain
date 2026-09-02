#!/usr/bin/env python3
"""Patch remaining APIs after impl a/b."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def w(rel: str, text: str) -> None:
    path = REPO / rel.replace("\\", "/")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    print("wrote", rel, path.stat().st_size)


def main() -> int:
    w(
        "tools/council/antifail/strategic.py",
        '''"""Strategic-vote / pivotal-abstention detector (IMP-0347)."""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

_STANCE = re.compile(r"STANCE:(AYE|NAY|ABSTAIN)", re.I)
POLICY_ID = "majority-of-seated:include-abstain-in-denominator"


def _stances(text_or_hist) -> list[str]:
    texts: list[str] = []
    if isinstance(text_or_hist, str):
        texts = [text_or_hist]
    elif isinstance(text_or_hist, list):
        for item in text_or_hist:
            if isinstance(item, dict):
                texts.append(str(item.get("text") or ""))
            else:
                texts.append(str(item))
    out = []
    for t in texts:
        out.extend(m.group(1).lower() for m in _STANCE.finditer(t))
    return out


def evaluate_ballot(pair: Mapping[str, Any]) -> dict[str, Any]:
    hist = pair.get("reasoning_history") or pair.get("history") or pair.get("text") or []
    stances = _stances(hist)
    implied = stances[-1] if stances else None
    ballot = str(pair.get("ballot") or pair.get("vote") or "").lower()
    change = len(set(stances)) > 1
    strategic_vote = bool(
        implied and ballot and implied != ballot and implied != "abstain" and ballot not in {"abstain", ""}
    )
    if change and implied == ballot:
        strategic_vote = False
    return {
        "id": pair.get("id"),
        "participant_id": pair.get("participant_id") or pair.get("id"),
        "strategic": strategic_vote,
        "strategic_vote": strategic_vote,
        "strategic_abstention": False,
        "pivotal_abstention": False,
        "change_of_mind": change,
        "implied_stance": implied,
        "ballot": ballot,
        "honest_counterfactual": None,
    }


def score_corpus(corpus: Mapping[str, Any]) -> dict[str, Any]:
    pairs = list(corpus.get("pairs") or [])
    rows = []
    tp = fp = fn = tn = 0
    cm_n = 0
    cm_fp = 0
    for p in pairs:
        det = evaluate_ballot(p)
        label = str(p.get("label") or "")
        pred = bool(det["strategic_vote"])
        truth = label == "strategic_vote"
        if truth and pred:
            tp += 1
        elif (not truth) and pred:
            fp += 1
        elif truth and not pred:
            fn += 1
        else:
            tn += 1
        if label == "change_of_mind":
            cm_n += 1
            if pred:
                cm_fp += 1
        rows.append({**det, "pred_strategic": pred, "label": label})
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    return {
        "n_pairs": len(pairs),
        "precision": prec,
        "recall": rec,
        "metrics": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "change_of_mind_n": cm_n,
        "change_of_mind_false_positives": cm_fp,
        "change_of_mind_fpr": (cm_fp / cm_n) if cm_n else 0.0,
        "profile_reports": [],
        "rows": rows,
    }


def _outcome(aye: int, nay: int, *, need: int) -> dict[str, Any]:
    if aye >= need:
        return {"outcome": "PASS", "winner": "aye", "aye": aye, "nay": nay, "need": need}
    if nay >= need:
        return {"outcome": "PASS", "winner": "nay", "aye": aye, "nay": nay, "need": need}
    return {"outcome": "FAIL", "winner": None, "aye": aye, "nay": nay, "need": need}


def tally(profile_or_ballots, *args, **kwargs) -> dict[str, Any]:
    if isinstance(profile_or_ballots, Mapping) and "seats" in profile_or_ballots:
        ballots = [str(s.get("ballot") or "abstain").lower() for s in profile_or_ballots.get("seats") or []]
        n_seats = int(profile_or_ballots.get("n_seats") or len(ballots))
        quorum = int(profile_or_ballots.get("quorum") or ((n_seats // 2) + 1))
        threshold = str(profile_or_ballots.get("threshold") or "majority_of_seated")
        policy = str(profile_or_ballots.get("abstention_policy") or "include_in_denominator")
    else:
        ballots = [str(b).lower() for b in list(profile_or_ballots)]
        n_seats = int(kwargs.get("n_seats") or len(ballots))
        quorum = int(kwargs.get("quorum") or ((n_seats // 2) + 1))
        threshold = str(kwargs.get("threshold") or "majority_of_seated")
        policy = str(kwargs.get("abstention_policy") or "include_in_denominator")
    aye = sum(1 for b in ballots if b in {"aye", "yes", "for"})
    nay = sum(1 for b in ballots if b in {"nay", "no", "against"})
    abstain = n_seats - aye - nay
    need = quorum if threshold == "majority_of_seated" else quorum
    actual = _outcome(aye, nay, need=need)
    actual.update(
        {
            "policy_id": POLICY_ID,
            "quorum": quorum,
            "threshold": threshold,
            "abstention_policy": policy,
            "n_seats": n_seats,
            "abstain": abstain,
        }
    )
    return actual


def _honest_vote(implied: str | None, ballot: str) -> str:
    if implied in {"aye", "nay"}:
        return implied
    return ballot or "abstain"


def quorum_sensitivity(profile: Mapping[str, Any]) -> dict[str, Any]:
    seats = list(profile.get("seats") or [])
    actual = tally(profile)
    need = int(actual["need"])
    pivotal_ids: list[str] = []
    enriched = []
    for s in seats:
        det = evaluate_ballot(
            {
                "id": s.get("participant_id"),
                "participant_id": s.get("participant_id"),
                "ballot": s.get("ballot"),
                "reasoning_history": s.get("reasoning_history") or [],
            }
        )
        ballot = det["ballot"]
        implied = det["implied_stance"]
        aye = actual["aye"]
        nay = actual["nay"]
        if ballot in {"aye", "yes"}:
            aye -= 1
        elif ballot in {"nay", "no"}:
            nay -= 1
        hv = _honest_vote(implied, ballot)
        if hv in {"aye", "yes"}:
            aye2 = aye + 1
            nay2 = nay
        elif hv in {"nay", "no"}:
            aye2, nay2 = aye, nay + 1
        else:
            aye2, nay2 = aye, nay
        honest = _outcome(aye2, nay2, need=need)
        flips = honest["outcome"] != actual["outcome"]
        is_abs = ballot in {"abstain", ""}
        pivotal = bool(is_abs and flips)
        if pivotal:
            pivotal_ids.append(str(s.get("participant_id")))
        det["pivotal_abstention"] = pivotal
        det["strategic_abstention"] = bool(pivotal and implied in {"aye", "nay"})
        det["strategic"] = det["strategic_abstention"] or det["strategic_vote"]
        det["honest_counterfactual"] = {**honest, "flips_vs_actual": flips}
        enriched.append(det)
    return {
        "profile_id": profile.get("profile_id"),
        "policy_id": POLICY_ID,
        "actual": actual,
        "pivotal_ids": pivotal_ids,
        "detections": enriched,
    }


def evaluate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    q = quorum_sensitivity(profile)
    return {
        "profile_id": profile.get("profile_id"),
        "detections": q["detections"],
        "tally": q["actual"],
        "pivotal_ids": q["pivotal_ids"],
        "policy_id": POLICY_ID,
    }
''',
    )

    w(
        "tools/plugin/errors.py",
        '''"""Plugin install errors."""
from __future__ import annotations


class DigestMismatchError(Exception):
    """Handoff digest does not match live payload_digest."""


class InstallError(Exception):
    """Install refused."""


class PermissionWideningBlocked(InstallError):
    """Candidate permissions are a strict widening of the installed set."""

    def __init__(self, added, *, installed=None, candidate=None, rendered_diff: str | None = None):
        self.added = list(added)
        self.installed = list(installed or [])
        self.candidate = list(candidate or [])
        self.status = "blocked"
        self.halt = True
        self.warn = False
        self.rendered_diff = rendered_diff or ("added permissions: " + ", ".join(self.added))
        super().__init__(self.rendered_diff + " " + " ".join(self.added))
''',
    )

    pdiff = REPO / "tools/plugin/permission_diff.py"
    t = pdiff.read_text(encoding="utf-8")
    if "methods_agree" not in t:
        t = t.replace(
            "    lattice_verdict: str = \"\"\n",
            "    lattice_verdict: str = \"\"\n\n    @property\n    def methods_agree(self) -> bool:\n        return self.lattice_atom_agree\n",
        )
    t = t.replace(
        '''def decide(installed, candidate) -> str:
    inst, cand = set(installed or []), set(candidate or [])
    if not cand <= inst:
        return "widen"
    if cand == inst:
        return "same"
    return "narrow"
''',
        '''def decide(installed, candidate) -> Delta:
    return compute_delta(installed, candidate)
''',
    )
    pdiff.write_text(t, encoding="utf-8", newline="\n")
    print("patched permission_diff")

    inst = REPO / "tools/marketplace/install.py"
    it = inst.read_text(encoding="utf-8")
    if "def install_plugin_tree" not in it:
        helper = '''

def install_plugin_tree(payload: Path, dest: Path, *, owner_consent=None) -> dict:
    """Directory-shaped plugin install used by TST-0214."""
    import json
    import shutil
    from plugin.errors import PermissionWideningBlocked
    from plugin.permission_diff import compute_delta, UNCHANGED, NARROW, WIDEN

    payload = Path(payload)
    dest = Path(dest)
    src_manifest = json.loads((payload / "plugin.json").read_text(encoding="utf-8"))
    name = str(src_manifest.get("name") or payload.name)
    live_dir = dest / "plugins" / name
    live_manifest_path = live_dir / "plugin.json"
    candidate_perms = list(src_manifest.get("permissions") or [])
    if live_manifest_path.is_file():
        installed = json.loads(live_manifest_path.read_text(encoding="utf-8"))
        installed_perms = list(installed.get("permissions") or [])
        delta = compute_delta(installed_perms, candidate_perms)
        if delta.verdict == WIDEN:
            raise PermissionWideningBlocked(
                sorted(delta.added),
                installed=installed_perms,
                candidate=candidate_perms,
            )
        verdict = delta.verdict
        halt = False
    else:
        verdict = "first-install"
        halt = False
        delta = None
    live_dir.mkdir(parents=True, exist_ok=True)
    if live_dir.exists():
        for p in list(live_dir.rglob("*")):
            if p.is_file():
                p.unlink()
    shutil.copytree(payload, live_dir, dirs_exist_ok=True)
    gate = {
        "verdict": verdict,
        "halt": halt,
        "warn": False,
        "added": list(delta.added) if delta else [],
        "owner_consent": owner_consent,
    }
    return {"result": {"permission_gate": gate, "ok": True}, "ok": True}


'''
        it = it.replace(
            "def install(\n    package_id: str,\n    payload: dict[str, Any],\n    home: Path,\n    ledger: Ledger,",
            helper
            + "def install(\n    package_id,\n    payload=None,\n    home=None,\n    ledger=None,",
        )
        # dispatch at start of install
        needle = "    *, \n    guard: bool = True,\n    case_insensitive: bool = False,\n) -> InstallResult:\n    home = Path(home)\n"
        # simpler: insert after def line block
        it = it.replace(
            "    case_insensitive: bool = False,\n) -> InstallResult:\n    home = Path(home)\n",
            "    case_insensitive: bool = False,\n    owner_consent=None,\n) -> InstallResult | dict:\n"
            "    from pathlib import Path as _P\n"
            "    if ledger is None and home is None and payload is not None and not isinstance(payload, dict):\n"
            "        return install_plugin_tree(_P(package_id), _P(payload), owner_consent=owner_consent)\n"
            "    if ledger is None and isinstance(package_id, _P):\n"
            "        return install_plugin_tree(_P(package_id), _P(payload), owner_consent=owner_consent)\n"
            "    home = Path(home)\n",
        )
        inst.write_text(it, encoding="utf-8", newline="\n")
        print("patched marketplace.install")

    print("impl-c done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
