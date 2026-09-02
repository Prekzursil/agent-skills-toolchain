"""Load 284 candidates + 108 blueprints, or reconstruct the catalog contract.

Live Windows harness-restore paths are tried first. On this Linux worktree they
are absent, so a deterministic reconstructed corpus matching the published
family counts is used. Reconstruction is labelled; it is not a live-registry
read. Planted controls for the three required tests are always present in
the reconstructed corpus and also as standalone fixtures in extractor.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parents[3]

CANDIDATE_FAMILY_COUNTS: tuple[tuple[str, int], ...] = (
    ("A-saved-workflow", 10),
    ("B-repo-workflow", 4),
    ("C-repo-tool", 25),
    ("D-harness-runtime", 6),
    ("E-agent", 19),
    ("F-plugin", 21),
    ("G-skill", 96),
    ("H-executed-corpus", 72),
    ("I-command", 31),
)
assert sum(n for _, n in CANDIDATE_FAMILY_COUNTS) == 284

# 20 blueprint families D01-D20; 8 families with 6 records, 12 with 5 = 108.
BLUEPRINT_FAMILY_COUNTS: tuple[tuple[str, int], ...] = tuple(
    (f"D{i:02d}", 6 if i <= 8 else 5) for i in range(1, 21)
)
assert sum(n for _, n in BLUEPRINT_FAMILY_COUNTS) == 108

A_SAVED_IDS = (
    "wf-saved-agentic-repair-reliability",
    "wf-saved-bc-stage-compendium-enrichment",
    "wf-saved-codex-auth-research-fanout",
    "wf-saved-design-gate",
    "wf-saved-harness-self-improve-sweep",
    "wf-saved-owner-signoff-packet",
    "wf-saved-license-scan-gate",
    "wf-saved-resume-from-ledger",
    "wf-saved-mention-only-catalog",
    "wf-saved-zero-mechanism-empty",
)

FAMILY_PREFIX = {
    "B-repo-workflow": "wf-repo",
    "C-repo-tool": "wf-tool",
    "D-harness-runtime": "wf-harness",
    "E-agent": "wf-agent",
    "F-plugin": "wf-plugin",
    "G-skill": "wf-skill",
    "H-executed-corpus": "wf-exec",
    "I-command": "wf-cmd",
}

# What the definition (does + stages) actually implements, per family.
FAMILY_IMPL: dict[str, tuple[str, ...]] = {
    "A-saved-workflow": ("mech:human-checkpoint", "mech:typed-stopping-rule"),
    "B-repo-workflow": ("mech:provenance-anchor", "mech:deterministic-replay"),
    "C-repo-tool": ("mech:fire-and-forget-dispatch", "mech:idempotent-retry"),
    "D-harness-runtime": ("mech:blocking-fan-in-barrier", "mech:typed-stopping-rule"),
    "E-agent": ("mech:shared-context-deliberation", "mech:information-partition"),
    "F-plugin": ("mech:fusion-decompose", "mech:fire-and-forget-dispatch"),
    "G-skill": ("mech:blind-independent-first-pass", "mech:information-partition"),
    "H-executed-corpus": ("mech:deterministic-replay", "mech:provenance-anchor"),
    "I-command": ("mech:human-checkpoint", "mech:typed-stopping-rule"),
}

# Exclusive partner used to plant prose/definition disagreement.
DISAGREE_PARTNER: dict[str, str] = {
    "mech:blind-independent-first-pass": "mech:shared-context-deliberation",
    "mech:shared-context-deliberation": "mech:blind-independent-first-pass",
    "mech:deterministic-replay": "mech:nondeterministic-sampling",
    "mech:nondeterministic-sampling": "mech:deterministic-replay",
    "mech:fire-and-forget-dispatch": "mech:blocking-fan-in-barrier",
    "mech:blocking-fan-in-barrier": "mech:fire-and-forget-dispatch",
    "mech:typed-stopping-rule": "mech:human-checkpoint",
    "mech:human-checkpoint": "mech:typed-stopping-rule",
    "mech:information-partition": "mech:shared-context-deliberation",
    "mech:provenance-anchor": "mech:fusion-decompose",
    "mech:idempotent-retry": "mech:fire-and-forget-dispatch",
    "mech:fusion-decompose": "mech:provenance-anchor",
}

# Definition-field text. Must contain vocabulary impl_needles.
IMPL_TEXT: dict[str, dict[str, str]] = {
    "mech:blind-independent-first-pass": {
        "does": (
            "Runs a blind independent first pass: raters produce scores "
            "without seeing other ballots via an independent-rating stage."
        ),
        "stage": "independent-rating",
    },
    "mech:shared-context-deliberation": {
        "does": (
            "Runs shared transcript deliberation: later speakers update a "
            "joint position from a common transcript in a shared-deliberation stage."
        ),
        "stage": "shared-deliberation",
    },
    "mech:deterministic-replay": {
        "does": (
            "Pinned replay: the same pinned inputs and seed yield byte-identical "
            "outputs in a deterministic-replay stage."
        ),
        "stage": "deterministic-replay",
    },
    "mech:nondeterministic-sampling": {
        "does": (
            "A sampling step draws from a distribution via a temperature "
            "sampling draw in a stochastic-sample stage."
        ),
        "stage": "stochastic-sample",
    },
    "mech:fire-and-forget-dispatch": {
        "does": (
            "Work is sent by dispatch without waiting; there is no join at "
            "the call site (fire-forget-dispatch)."
        ),
        "stage": "fire-forget-dispatch",
    },
    "mech:blocking-fan-in-barrier": {
        "does": (
            "A join waits for every dispatched branch at a wait-for-all "
            "barrier (blocking-fan-in)."
        ),
        "stage": "blocking-fan-in",
    },
    "mech:typed-stopping-rule": {
        "does": (
            "Stop is an evaluable stop expression; the stop compiles to a "
            "predicate over run state in a typed-stop-eval stage."
        ),
        "stage": "typed-stop-eval",
    },
    "mech:information-partition": {
        "does": (
            "Judges are denied author identity; author identity stripped "
            "before the score (info-partition)."
        ),
        "stage": "info-partition",
    },
    "mech:provenance-anchor": {
        "does": (
            "Each node carries a dereferenceable source anchor (commit sha "
            "plus file:line) in a provenance-pin stage."
        ),
        "stage": "provenance-pin",
    },
    "mech:human-checkpoint": {
        "does": (
            "The stage blocks until a named human records a decision; owner "
            "accept required (human-gate)."
        ),
        "stage": "human-gate",
    },
    "mech:idempotent-retry": {
        "does": (
            "Failed work is replay-safe on failure; a second success is "
            "observationally equal to the first (idempotent-retry)."
        ),
        "stage": "idempotent-retry",
    },
    "mech:fusion-decompose": {
        "does": (
            "A fused graph can be decomposed back into the source components; "
            "recover source component ids (fusion-decompose)."
        ),
        "stage": "fusion-decompose",
    },
}

PROSE_NAME: dict[str, str] = {
    "mech:blind-independent-first-pass": "blind independent first pass",
    "mech:shared-context-deliberation": "shared-context deliberation",
    "mech:deterministic-replay": "deterministic replay",
    "mech:nondeterministic-sampling": "nondeterministic sampling",
    "mech:fire-and-forget-dispatch": "fire-and-forget dispatch",
    "mech:blocking-fan-in-barrier": "blocking fan-in barrier",
    "mech:typed-stopping-rule": "typed stopping rule",
    "mech:information-partition": "information partition",
    "mech:provenance-anchor": "provenance anchor",
    "mech:human-checkpoint": "human checkpoint",
    "mech:idempotent-retry": "idempotent retry",
    "mech:fusion-decompose": "fusion decompose",
}

CANDIDATE_SEARCH = (
    Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    REPO / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    REPO / "command-center" / "_wfa2_entries.json",
)
BLUEPRINT_SEARCH = (
    Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json"),
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/09-WORKFLOW-BLUEPRINT-LIBRARY.json"),
    REPO / "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    REPO / "command-center" / "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)


def _records(doc: Any) -> list[Any]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "blueprints", "records", "items", "workflows"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def _try_load(paths: tuple[Path, ...]) -> tuple[Path | None, list[dict[str, Any]]]:
    for path in paths:
        try:
            if not path.is_file() or path.stat().st_size <= 0:
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        recs = _records(doc)
        if recs:
            return path, recs
    return None, []


def _impl_body(mech_ids: tuple[str, ...]) -> tuple[str, list[dict[str, str]]]:
    does_parts = []
    stages = []
    for mid in mech_ids:
        spec = IMPL_TEXT[mid]
        does_parts.append(spec["does"])
        stages.append({"id": spec["stage"], "kind": spec["stage"], "role": "implement"})
    return " ".join(does_parts), stages


def _candidate(fid: str, family: str, idx: int, n_family: int) -> dict[str, Any]:
    """Build one reconstructed candidate.

    Controls (frozen before extraction):
      * A-saved-workflow index 8 (wf-saved-mention-only-catalog): notes mention
        a blocking fan-in barrier; definition implements only human-checkpoint.
      * A-saved-workflow index 9 (wf-saved-zero-mechanism-empty): empty
        definition and empty self-description.
      * even idx (except those two controls): prose names the exclusive
        partner, not the implemented pair.
    """
    if family == "A-saved-workflow" and idx == 8:
        return {
            "id": fid,
            "kind": "candidate",
            "family": family,
            "name": "mention-only-catalog.js",
            "does": IMPL_TEXT["mech:human-checkpoint"]["does"],
            "stages": [{"id": "human-gate", "kind": "human-gate", "role": "implement"}],
            "mechanisms": ["human checkpoint"],
            "notes": (
                "This catalog entry documents a blocking fan-in barrier for "
                "operators; it does not run one. See also: wait-for-all barrier."
            ),
            "planted": "use-versus-mention",
            "family_index": idx,
            "family_n": n_family,
        }
    if family == "A-saved-workflow" and idx == 9:
        return {
            "id": fid,
            "kind": "candidate",
            "family": family,
            "name": "empty-definition.js",
            "does": "",
            "stages": [],
            "mechanisms": [],
            "notes": "",
            "planted": "zero-extractable",
            "family_index": idx,
            "family_n": n_family,
        }
    impl = FAMILY_IMPL[family]
    extra: tuple[str, ...] = ()
    if idx % 5 == 0 and family != "A-saved-workflow":
        extra = ("mech:idempotent-retry",)
    mech_ids = tuple(dict.fromkeys(impl + extra))
    does, stages = _impl_body(mech_ids)
    if idx % 2 == 0 and not extra:
        prose = [PROSE_NAME[DISAGREE_PARTNER[impl[0]]], PROSE_NAME[impl[1]]]
        planted: str | None = "prose-definition-disagreement"
    else:
        prose = [PROSE_NAME[m] for m in mech_ids]
        planted = None
    rec: dict[str, Any] = {
        "id": fid,
        "kind": "candidate",
        "family": family,
        "name": fid + ".js",
        "does": does,
        "stages": stages,
        "mechanisms": prose,
        "notes": "",
        "family_index": idx,
        "family_n": n_family,
    }
    if planted:
        rec["planted"] = planted
    return rec


def _blueprint(fid: str, family: str, idx: int) -> dict[str, Any]:
    cycle = (
        "mech:typed-stopping-rule",
        "mech:blocking-fan-in-barrier",
        "mech:provenance-anchor",
        "mech:fusion-decompose",
        "mech:deterministic-replay",
        "mech:human-checkpoint",
        "mech:information-partition",
        "mech:idempotent-retry",
        "mech:fire-and-forget-dispatch",
        "mech:blind-independent-first-pass",
        "mech:shared-context-deliberation",
        "mech:nondeterministic-sampling",
    )
    primary = cycle[idx % len(cycle)]
    secondary = cycle[(idx + 3) % len(cycle)]
    if primary == secondary:
        secondary = cycle[(idx + 1) % len(cycle)]
    mech_ids = (primary, secondary)
    does, stages = _impl_body(mech_ids)
    if idx % 7 == 0:
        prose = [PROSE_NAME[DISAGREE_PARTNER.get(primary, primary)], PROSE_NAME[secondary]]
        planted: str | None = "prose-definition-disagreement"
    else:
        prose = [PROSE_NAME[m] for m in mech_ids]
        planted = None
    rec: dict[str, Any] = {
        "id": fid,
        "kind": "blueprint",
        "family": family,
        "name": fid,
        "does": does,
        "stages": stages,
        "mechanisms": prose,
        "notes": "",
        "gates": [{"id": "g0", "kind": stages[0]["kind"]}],
        "stop": {"kind": "typed-stop-eval"} if "mech:typed-stopping-rule" in mech_ids else {},
        "size_class": "BUILD-SMALL" if (int(family[1:]) - 1) * 5 + idx < 52 else "BUILD-LARGE",
    }
    if planted:
        rec["planted"] = planted
    return rec


def reconstruct() -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for family, n in CANDIDATE_FAMILY_COUNTS:
        for idx in range(n):
            if family == "A-saved-workflow":
                fid = A_SAVED_IDS[idx]
            else:
                fid = f"{FAMILY_PREFIX[family]}-{idx:03d}"
            candidates.append(_candidate(fid, family, idx, n))
    # Second zero-extractable candidate (inspect: 2 of 284 have empty mechanisms).
    last = candidates[-1]
    last["does"] = ""
    last["stages"] = []
    last["mechanisms"] = []
    last["notes"] = ""
    last["planted"] = "zero-extractable"
    last["id"] = "wf-cmd-030-zero"
    last["name"] = "wf-cmd-030-zero.js"

    blueprints: list[dict[str, Any]] = []
    for family, n in BLUEPRINT_FAMILY_COUNTS:
        for idx in range(n):
            fid = f"bp-{family.lower()}-{idx:03d}"
            blueprints.append(_blueprint(fid, family, idx))
    return {
        "mode": "reconstructed-catalog-contract",
        "reason": (
            "Live 08-WORKFLOW-CANDIDATE-REGISTRY.json and "
            "09-WORKFLOW-BLUEPRINT-LIBRARY.json are absent on this Linux "
            "worktree; corpus matches published counts A10 B4 C25 D6 E19 F21 "
            "G96 H72 I31 and 108 blueprints across D01-D20."
        ),
        "candidates": candidates,
        "blueprints": blueprints,
    }


def _normalize(rec: dict[str, Any], kind: str) -> dict[str, Any]:
    fid = str(rec.get("id") or rec.get("name") or "")
    family = str(rec.get("family") or rec.get("family_id") or "UNKNOWN")
    does = rec.get("does") or rec.get("description") or rec.get("what") or ""
    if not isinstance(does, str):
        does = json.dumps(does, sort_keys=True)
    stages = rec.get("stages") or rec.get("code") or rec.get("runtime") or []
    if isinstance(stages, dict):
        stages = stages.get("stages") or [stages]
    mechs = rec.get("mechanisms") or []
    if isinstance(mechs, str):
        mechs = [mechs]
    notes = rec.get("notes") or rec.get("documentation") or ""
    if not isinstance(notes, str):
        notes = json.dumps(notes, sort_keys=True)
    return {
        "id": fid,
        "kind": kind,
        "family": family,
        "name": str(rec.get("name") or fid),
        "does": does,
        "stages": stages if isinstance(stages, list) else [],
        "mechanisms": list(mechs),
        "notes": notes,
        "gates": rec.get("gates") or [],
        "stop": rec.get("stop") or rec.get("stop_rules") or {},
        "source": "live-registry",
    }


def load_corpus() -> dict[str, Any]:
    c_path, c_recs = _try_load(CANDIDATE_SEARCH)
    b_path, b_recs = _try_load(BLUEPRINT_SEARCH)
    if (
        c_path is not None
        and len(c_recs) == 284
        and b_path is not None
        and len(b_recs) == 108
    ):
        return {
            "mode": "live-registry",
            "reason": f"loaded {c_path} and {b_path}",
            "live_candidate_path": str(c_path),
            "live_blueprint_path": str(b_path),
            "candidates": [_normalize(r, "candidate") for r in c_recs],
            "blueprints": [_normalize(r, "blueprint") for r in b_recs],
        }
    built = reconstruct()
    built["live_candidate_path"] = str(c_path) if c_path else None
    built["live_blueprint_path"] = str(b_path) if b_path else None
    built["live_candidate_n"] = len(c_recs)
    built["live_blueprint_n"] = len(b_recs)
    return built


def all_artifacts(corpus: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = corpus if corpus is not None else load_corpus()
    return list(doc["candidates"]) + list(doc["blueprints"])


def sample_30_ids(artifacts: list[dict[str, Any]]) -> list[str]:
    """Sampling rule written before selection.

    Take the first two candidates of each of the nine families (18), then the
    first twelve blueprints in id order (12), totaling 30. Families are walked
    in CANDIDATE_FAMILY_COUNTS order. This rule is frozen; it is not adjusted
    after looking at disagreement rates.
    """
    chosen: list[str] = []
    for family, _n in CANDIDATE_FAMILY_COUNTS:
        fam = [
            a["id"]
            for a in artifacts
            if a.get("kind") == "candidate" and a.get("family") == family
        ]
        chosen.extend(fam[:2])
    bps = [a["id"] for a in artifacts if a.get("kind") == "blueprint"]
    chosen.extend(bps[:12])
    if len(chosen) != 30:
        raise RuntimeError(f"sample_30 produced {len(chosen)} ids, want 30")
    return chosen
