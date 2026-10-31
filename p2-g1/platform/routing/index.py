#!/usr/bin/env python
"""Phase 8 capability INDEX - discover every routable unit of the repertoire.

Spec: `_USER-PROMPTS.md:10948-10963` ("index all skills/plugins/workflows/tools").

WHY THIS EXISTS ALONGSIDE `hooks/semantic-router/` (reconciliation, no duplication)
----------------------------------------------------------------------------------
`hooks/semantic-router/build_index.py` already indexes the LIVE trees -- measured
358 rows: 238 skill / 65 command / 39 mcp / 16 agent (`hooks/semantic-router/index/meta.json`).
It does NOT index the platform inventory at all: 0 workflow blueprints, 0 council
protocols, 0 council presets, 0 registry candidates. It also requires a live Ollama
embedding endpoint (`hooks/semantic-router/embed.py`), so it fails open to a lexical
lane when the network is absent and cannot back a hermetic regression gate.

This module is the SUPERSET INDEX: it folds the live trees AND the platform inventory
into one normalized record shape, with no network dependency, so the router below it
is deterministic and gateable. It does not replace, unregister, or edit the hook
router; the hook stays the live UserPromptSubmit path.

THE ANTI-FLOODING CONTRACT
--------------------------
Every record carries two disjoint text fields:

  * `routing_text` -- everything the matchers score against. Never injected. Long is
    free here; it costs CPU, not context.
  * `card` -- the ONLY bytes injected when the capability is selected, hard-capped at
    `budget.CARD_BYTE_CAP`.

A router that achieves recall by injecting descriptions has failed the spec. Keeping
the two apart is what makes "high recall" and "low context cost" simultaneously
satisfiable rather than a trade-off.

FAIL-CLOSED (ci-hygiene.md 1)
-----------------------------
Each source is individually fail-soft (a malformed JSON file is skipped, not fatal),
but `discover()` records per-source counts and `verify_floors()` FAILS when a source
that should be populated yields fewer records than its floor. An empty walk reported
as success is the no-op-gate defect class.
"""

from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- roots

REPO = Path(__file__).resolve().parents[2]
PLATFORM = REPO / "platform"
HOME = Path(os.environ.get("ROUTING_HOME") or Path.home())

#: Per-source minimum record counts. A source below its floor is a DETECTOR FAILURE,
#: not an empty inventory -- these directories are committed and non-empty at HEAD.
#: Measured at HEAD before the floors were written (see MEASUREMENTS.json).
SOURCE_FLOORS = {
    "workflow": 97,
    "protocol": 45,
    "preset": 60,
    "candidate": 150,
    "skill": 60,
    "mcp": 10,
    "plugin": 5,
}


@dataclass
class Roots:
    """Injectable filesystem seam. Tests point this at a fixture tree; production
    uses `Roots.live()`. D3's lesson: a hardcoded literal leaves nothing to redirect."""

    workflows: Path | None = None
    protocols: Path | None = None
    presets: Path | None = None
    registry: Path | None = None
    skills: list[Path] = field(default_factory=list)
    plugins_json: Path | None = None
    mcp_json: Path | None = None
    agents: Path | None = None
    commands: Path | None = None

    @classmethod
    def live(cls) -> Roots:
        return cls(
            workflows=PLATFORM / "workflows",
            protocols=PLATFORM / "council" / "protocols",
            presets=PLATFORM / "council" / "presets",
            registry=PLATFORM / "registry",
            skills=[HOME / ".agents" / "skills", HOME / ".claude" / "skills"],
            plugins_json=HOME / ".claude" / "plugins" / "installed_plugins.json",
            mcp_json=HOME / ".mcp.json",
            agents=HOME / ".claude" / "agents",
            commands=HOME / ".claude" / "commands",
        )


# --------------------------------------------------------------------------- record


@dataclass
class Capability:
    """One routable unit. Mirrors `schema/capability-record.schema.json`."""

    id: str
    cls: str
    name: str
    anchor: str
    routing_text: str
    card: str
    card_bytes: int
    invoke: str = ""
    #: The capability's OWN declared description, verbatim, before any routing_extra
    #: (body headings, stage text, structural aliases) was folded in. This is the
    #: always-loaded surface a skill listing pays for every turn, so budget.py must
    #: price it separately from routing_text -- conflating the two would credit the
    #: card with a saving against a number nobody actually pays.
    desc_source: str = ""
    tags: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    family: str = ""
    triggers: tuple[str, ...] = ()
    anti_triggers: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    superseded_by: str = ""
    rarity: str = "common"
    #: Shared key for records that are the SAME underlying capability mirrored into a
    #: second tree. Empty when the record is unique. Populated by
    #: `Index.link_equivalents()`, which VERIFIES the duplication by content similarity
    #: rather than trusting the naming convention.
    equiv_key: str = ""
    classification: str = ""
    license: str = ""
    desc_quality: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "cls": self.cls,
            "name": self.name,
            "anchor": self.anchor,
            "routing_text": self.routing_text,
            "card": self.card,
            "card_bytes": self.card_bytes,
        }
        for k in (
            "invoke",
            "family",
            "superseded_by",
            "classification",
            "license",
            "rarity",
        ):
            v = getattr(self, k)
            if v:
                d[k] = v
        for k in ("tags", "categories", "triggers", "anti_triggers", "supersedes"):
            v = getattr(self, k)
            if v:
                d[k] = list(v)
        if self.desc_quality:
            d["desc_quality"] = self.desc_quality
        return d


# --------------------------------------------------------------------------- helpers

_WS = re.compile(r"\s+")

#: Trigger mining. Deliberately conservative: a false trigger pollutes the labelled
#: query set, which is worse than a missed one.
_TRIGGER_RX = (
    re.compile(
        r"\bUse (?:this skill )?when\b(.{8,400}?)(?=(?:\.\s)|(?:\bDo NOT\b)|$)", re.I
    ),
    re.compile(r"\bTriggers?(?: include| are|:)\b(.{8,400}?)(?=(?:\.\s)|$)", re.I),
    # NEGATIVE LOOKBEHIND is load-bearing. Without it, "Do NOT use for ordinary
    # code-quality review (use code-review)" was mined as a POSITIVE trigger for
    # `skill:acceptance-review` -- the author's explicit scope EXCLUSION indexed as an
    # inclusion. Measured: that inverted trigger became query L1a-skill-02, whose gold
    # label was therefore a capability the text says not to use, and it failed at every
    # k. A polarity error in trigger mining corrupts the router AND the query set built
    # from it, so it fails twice and looks like a routing weakness.
    re.compile(
        r"(?<!not )(?<!NOT )(?<!don't )\bUse (?:it )?(?:to|for)\b"
        r"(.{8,300}?)(?=(?:\.\s)|(?:\bDo NOT\b)|$)",
        re.I,
    ),
)

#: Naming convention the live harness uses when mirroring a command/agent into the skill
#: vault: `~/.claude/commands/aside.md` -> `~/.agents/skills/source-command-aside/SKILL.md`.
#: Detection is convention-based but the resulting grouping is CONTENT-VERIFIED in
#: `Index.link_equivalents()`; the convention alone is not treated as proof.
_MIRROR_RX = re.compile(r"^source-(command|agent|skill)-(.+)$")

#: Any mined POSITIVE trigger whose surrounding clause is a negation is discarded
#: outright. The lookbehind above catches the adjacent form; this catches
#: "NOT for X ... use for Y" where the negation is further left in the same sentence.
_NEGATED_CLAUSE_RX = re.compile(r"\b(?:do\s+not|don't|never|NOT)\b[^.;]{0,60}$", re.I)
_ANTI_RX = (
    re.compile(r"\b(?:Do NOT|Don't|Do not) use\b(.{6,300}?)(?=(?:\.\s)|$)", re.I),
    re.compile(r"\bNOT for\b(.{6,300}?)(?=(?:\.\s)|$)", re.I),
    re.compile(r"\bNOT a\b(.{6,200}?)(?=(?:\.\s)|$)", re.I),
)
_SUPERSEDE_RX = (
    re.compile(
        r"\bSUPERSEDES?\s+(?:the\s+)?(?:lexical\s+)?([a-z0-9][a-z0-9/._-]{2,})", re.I
    ),
    re.compile(r"\brenamed to\s+([a-z0-9][a-z0-9._-]{2,})", re.I),
    re.compile(r"\bUse the\s+([a-z0-9][a-z0-9._-]{2,})\s+skill instead\b", re.I),
)


def norm(s: Any) -> str:
    """Collapse whitespace; tolerate None/non-str."""
    return _WS.sub(" ", str(s or "")).strip()


def flatten(v: Any, cap: int = 12) -> str:
    """Flatten a heterogeneous JSON value to routing text.

    The registry corpus is NOT shape-uniform: `tools` is a list of strings in some
    candidate rows and a dict-of-lists in others (measured -- a bare `[:10]` slice on
    the dict raised `KeyError: slice(None, 10, None)`). Anything that reaches
    routing_text must survive every shape the real corpus actually holds.
    """
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        parts = []
        for k in list(v)[:cap]:
            parts.append(str(k))
            parts.append(flatten(v[k], cap))
        return " ".join(parts)
    if isinstance(v, (list, tuple)):
        return " ".join(flatten(x, cap) for x in list(v)[:cap])
    return str(v)


def _mine(text: str, patterns) -> tuple[str, ...]:
    out: list[str] = []
    for rx in patterns:
        for m in rx.finditer(text):
            frag = norm(m.group(1)).strip(" .,;:-")
            if len(frag) >= 6 and frag.lower() not in {o.lower() for o in out}:
                out.append(frag)
    return tuple(out[:6])


def mine_triggers(text: str) -> tuple[str, ...]:
    """Positive triggers only. A match whose left context is a negation is dropped."""
    out: list[str] = []
    for rx in _TRIGGER_RX:
        for m in rx.finditer(text):
            if _NEGATED_CLAUSE_RX.search(text[: m.start()]):
                continue
            frag = norm(m.group(1)).strip(" .,;:-")
            if len(frag) >= 6 and frag.lower() not in {o.lower() for o in out}:
                out.append(frag)
    return tuple(out[:6])


def mine_anti_triggers(text: str) -> tuple[str, ...]:
    return _mine(text, _ANTI_RX)


def mine_supersedes(text: str) -> tuple[str, ...]:
    return _mine(text, _SUPERSEDE_RX)


def _read(p: Path | str) -> str:
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json(p: Path | str) -> Any:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None


def _frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Minimal YAML-frontmatter split. Only scalar `key: value` lines are read -- the
    live SKILL.md corpus uses exactly that shape for `name`/`description`/`license`."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm: dict[str, str] = {}
    key = None
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            key = m.group(1).lower()
            fm[key] = m.group(2).strip().strip("'\"")
        elif key and line.startswith(("  ", "\t")):
            fm[key] = (fm[key] + " " + line.strip()).strip()
    return fm, text[end + 4 :]


# --------------------------------------------------------------------------- card


#: Injected-byte cap per capability. Imported by budget.py; defined here so the
#: indexer can enforce it at construction time rather than trusting a later caller.
CARD_BYTE_CAP = int(os.environ.get("ROUTING_CARD_BYTES") or 220)

#: UTF-8 width of the truncation marker, reserved out of the budget before cutting.
ELLIPSIS = "…"
ELLIPSIS_BYTES = len(ELLIPSIS.encode("utf-8"))


def make_card(invoke: str, purpose: str, tags: tuple[str, ...] = ()) -> tuple[str, int]:
    """Build the byte-capped injection card.

    Truncation is on a UTF-8 byte boundary and word-preferring, so a card never ends
    mid-codepoint (which would corrupt the injected context) and rarely mid-word.
    """
    tagpart = f" [{','.join(tags[:3])}]" if tags else ""
    head = f"{invoke} - " if invoke else ""
    body = norm(purpose)
    room = CARD_BYTE_CAP - len(head.encode()) - len(tagpart.encode())
    if room < 8:  # pragma: no cover - only reachable with an absurd invoke token
        head, room = "", CARD_BYTE_CAP - len(tagpart.encode())
    enc = body.encode("utf-8")
    if len(enc) > room:
        # ELLIPSIS_BYTES must be reserved BEFORE truncating. Measured defect: computing
        # `room` and then appending "…" (3 UTF-8 bytes) put the max card at 221 for a
        # 220 cap, which index.main()'s own over-cap gate caught. The cap is the
        # anti-flooding contract, so an off-by-three there is not cosmetic.
        cut = enc[: max(room - ELLIPSIS_BYTES, 1)]
        # back off to a valid codepoint boundary
        while cut and (cut[-1] & 0xC0) == 0x80:
            cut = cut[:-1]
        if cut and (cut[-1] & 0x80):
            cut = cut[:-1]
        txt = cut.decode("utf-8", "ignore")
        sp = txt.rfind(" ")
        if sp > room * 0.6:
            txt = txt[:sp]
        body = txt.rstrip(" ,;:-") + ELLIPSIS
    card = f"{head}{body}{tagpart}"
    return card, len(card.encode("utf-8"))


def _mk(
    cls: str,
    name: str,
    anchor: Path | str,
    purpose: str,
    routing_extra: str = "",
    *,
    invoke: str = "",
    tags: tuple[str, ...] = (),
    categories: tuple[str, ...] = (),
    family: str = "",
    classification: str = "",
    license: str = "",
) -> Capability:
    purpose = norm(purpose)
    full = norm(
        f"{name} {purpose} {routing_extra} {' '.join(tags)} {' '.join(categories)} {family}"
    )
    card, nbytes = make_card(invoke or name, purpose, tags)
    return Capability(
        id=f"{cls}:{name}",
        cls=cls,
        name=name,
        anchor=str(anchor),
        routing_text=full,
        card=card,
        card_bytes=nbytes,
        invoke=invoke or name,
        desc_source=purpose,
        tags=tags,
        categories=categories,
        family=family,
        triggers=mine_triggers(purpose),
        anti_triggers=mine_anti_triggers(purpose + " " + routing_extra),
        supersedes=mine_supersedes(purpose),
        classification=classification,
        license=license,
    )


# --------------------------------------------------------------------------- sources


#: Every `kind` in the blueprint corpus that is a routable workflow document.
#: MEASURED at HEAD over platform/workflows/*.json: 89 `workflow` + 4 `meta-workflow`
#: + 4 `subworkflow` = 97, which independently reproduces the pinned "97 materially
#: distinct blueprints". A `kind == "workflow"` filter (the first version of this
#: function) silently dropped 8 real blueprints -- including every meta-workflow -- and
#: was caught only because SOURCE_FLOORS made the shortfall a hard failure rather than
#: a plausible-looking count.
WORKFLOW_KINDS = frozenset({"workflow", "meta-workflow", "subworkflow"})

#: Blueprint `kind` -> routing `family`. Must stay key-compatible with
#: `descriptions.STRUCTURAL_ALIASES`, which is asserted by
#: `test_descriptions.py::test_every_kind_family_has_a_structural_alias`.
KIND_FAMILY = {
    "workflow": "blueprint",
    "meta-workflow": "blueprint-meta",
    "subworkflow": "blueprint-sub",
}

#: Blueprint subdirectories that also hold routable documents. `forged/` holds the
#: foundry's fused outputs (including verdict-namespaced REJECTED ones, which stay
#: indexed: the spec forbids pruning, and a rejection carries the rationale an agent
#: asking "why not X?" needs). `_shared/` holds composable subworkflow fragments.
WORKFLOW_SUBDIRS = ("_shared", "forged")


def workflows(root: Path | None) -> list[Capability]:
    """platform/workflows/**.json -- the blueprint corpus (97 top-level + nested)."""
    out: list[Capability] = []
    if not root or not root.is_dir():
        return out
    paths = list(sorted(root.glob("*.json")))
    for sub in WORKFLOW_SUBDIRS:
        paths += sorted((root / sub).glob("*.json"))
    seen: set[str] = set()
    for p in paths:
        # Status/validation sidecars are reports about blueprints, not blueprints.
        # They are excluded by SHAPE below (no `kind`), so the name filter here is
        # only a fast path -- a renamed sidecar still cannot slip through.
        if p.name.startswith("_") or "-STATUS" in p.name:
            continue
        d = _json(p)
        if not isinstance(d, dict) or "id" not in d:
            continue
        kind = str(d.get("kind") or "")
        if kind not in WORKFLOW_KINDS:
            continue
        wid = str(d["id"])
        if wid in seen:
            # The foundry writes a fused blueprint twice (`*.workflow.json` and
            # `*.TOURNAMENT-WINNER.workflow.json`) under ONE content-addressed id.
            # Deduping by id is what makes the record count match D4's measured
            # 102 distinct ids instead of over-counting the same capability.
            continue
        seen.add(wid)
        stage_txt = flatten(
            [
                f"{s.get('id', '')} {s.get('kind', '')} {s.get('description', '')}"
                for s in (d.get("stages") or [])
                if isinstance(s, dict)
            ],
            cap=40,
        )
        rel = p.relative_to(root).as_posix()
        if d.get("flagship"):
            family = "blueprint-flagship"
        elif kind != "workflow":
            # EXPLICIT map, not chained str.replace. The chained form
            # `kind.replace("-workflow","").replace("workflow","sub")` produced
            # `blueprint-subsub` for kind="subworkflow" (the first replace does not match,
            # then the second rewrites the "workflow" inside "subworkflow"). Caught by
            # test_all_three_workflow_kinds_are_indexed, and it would have silently
            # broken the STRUCTURAL_ALIASES lookup for every subworkflow.
            family = KIND_FAMILY[kind]
        elif p.parent.name in WORKFLOW_SUBDIRS:
            family = f"blueprint-{p.parent.name.lstrip('_')}"
        else:
            family = "blueprint"
        out.append(
            _mk(
                "workflow",
                wid,
                p,
                d.get("name") or d.get("description") or wid,
                routing_extra=f"{d.get('description', '')} {stage_txt}",
                invoke=f"platform/workflows/{rel}",
                tags=tuple(str(t) for t in (d.get("tags") or [])[:8]),
                categories=tuple(str(c) for c in (d.get("categories") or [])[:4]),
                family=family,
                # A verdict-namespaced id is the foundry's REJECTED marker (D4).
                # Carried so conflict resolution can demote it without deleting it.
                classification="REJECTED" if wid.startswith("rejected.") else "",
            )
        )
    return out


def _councilspec(cls: str, p: Path) -> Capability | None:
    d = _json(p)
    if not isinstance(d, dict) or "council_id" not in d:
        return None
    obj = d.get("objective") or {}
    meta = d.get("metadata") or {}
    purpose = norm(obj.get("statement") or meta.get("title") or d["council_id"])
    extra = norm(
        f"{obj.get('charter', '')} {obj.get('desired_output', '')} "
        f"{' '.join(str(s) for s in (obj.get('success_criteria') or [])[:4])} "
        f"{meta.get('title', '')} {meta.get('notes', '')[:1200]}"
    )
    seats = d.get("participants") or {}
    roles = seats.get("seats") if isinstance(seats, dict) else None
    if isinstance(roles, list):
        extra += " " + " ".join(
            norm(r.get("role") or r.get("id") or "")
            for r in roles
            if isinstance(r, dict)
        )
    return _mk(
        cls,
        str(d["council_id"]),
        p,
        purpose,
        routing_extra=extra,
        invoke=f"platform/council/{'protocols' if cls == 'protocol' else 'presets'}/{p.name}",
        tags=(str(obj.get("risk_tier") or "") or "council",),
        family=cls,
    )


def protocols(root: Path | None) -> list[Capability]:
    if not root or not root.is_dir():
        return []
    out = []
    for p in sorted(root.glob("*.json")):
        if p.name.startswith("_"):
            continue
        c = _councilspec("protocol", p)
        if c:
            out.append(c)
    return out


def presets(root: Path | None) -> list[Capability]:
    if not root or not root.is_dir():
        return []
    out = []
    for p in sorted(root.glob("*.json")):
        if p.name.startswith("_"):
            continue
        c = _councilspec("preset", p)
        if c:
            out.append(c)
    return out


def candidates(root: Path | None) -> list[Capability]:
    """platform/registry/workflow-candidates-*.json -- the 161 classified candidates.

    A REJECTED candidate is still indexed. The spec forbids pruning by usage, and a
    rejected candidate carries the *rationale* for its rejection, which is exactly the
    thing an agent asking "why not X?" needs to find.
    """
    if not root or not root.is_dir():
        return []
    out: list[Capability] = []
    seen: set[str] = set()
    for p in sorted(root.glob("workflow-candidates-*.json")):
        if ".COVERAGE." in p.name or ".METHOD." in p.name:
            continue
        d = _json(p)
        rows = d if isinstance(d, list) else (d or {}).get("candidates") or []
        for c in rows:
            if not isinstance(c, dict) or not c.get("id") or c["id"] in seen:
                continue
            seen.add(c["id"])
            out.append(
                _mk(
                    "candidate",
                    str(c["id"]),
                    p,
                    c.get("name") or str(c["id"]),
                    routing_extra=norm(
                        f"{flatten(c.get('task_fit'))} {flatten(c.get('classification_rationale'))} "
                        f"{flatten(c.get('stages'))} {flatten(c.get('roles'))} "
                        f"{flatten(c.get('tools'))}"
                    ),
                    invoke=str(c["id"]),
                    family=norm(c.get("family")),
                    classification=norm(c.get("classification")),
                    license=norm(c.get("license"))[:120],
                )
            )
    return out


def skills(roots: list[Path]) -> list[Capability]:
    """Live SKILL.md trees. Later roots do not overwrite earlier ones; the first
    anchor wins and the duplicate is dropped (`~/.agents/skills` is the vault
    superset of `~/.claude/skills`, so double-indexing would double the corpus)."""
    out: list[Capability] = []
    seen: set[str] = set()
    for root in roots or []:
        if not root or not Path(root).is_dir():
            continue
        for md in sorted(glob.glob(str(Path(root) / "*" / "SKILL.md"))):
            text = _read(md)
            fm, body = _frontmatter(text)
            name = norm(fm.get("name")) or Path(md).parent.name
            if name in seen:
                continue
            seen.add(name)
            desc = norm(fm.get("description"))
            heads = " ".join(re.findall(r"^#{1,3}\s+(.{3,90})$", body, re.M)[:14])
            out.append(
                _mk(
                    "skill",
                    name,
                    md,
                    desc or name,
                    routing_extra=f"{heads} {norm(body[:1500])}",
                    invoke=f"/{name}",
                    license=norm(fm.get("license"))[:120],
                )
            )
    return out


def plugins(installed_json: Path | None) -> list[Capability]:
    """Installed plugins, described from their OWN manifests.

    MEASURED DEFECT this closes. The first version synthesized "Installed plugin <name>
    from marketplace <market>." for all 98 plugins -- 11% of the corpus carrying zero
    routing signal. The consequence was not merely low recall for plugins, it was FALSE
    POSITIVES for everything else: `plugin:data` (from the key `data@claude-plugins-official`)
    is a 6-token document, so BM25 length normalization handed it a huge score for any
    query containing the word "data", and it won the query "spin up a rented GPU box and
    copy my data onto it" outright over `mcp:cloud-hub`.

    Every installed plugin ships a real manifest at
    `<installPath>/.claude-plugin/plugin.json` (or `<installPath>/plugin.json`) with
    `description`, `displayName` and `keywords`. Reading the manifest is strictly better
    than inventing a sentence: it is the author's own text, it costs one file read per
    plugin, and it removes the short-document artifact at the source rather than
    compensating for it downstream with a length hack.

    Fail-soft per plugin: a missing or malformed manifest falls back to the synthesized
    line, so a partially-installed plugin degrades instead of breaking discovery.
    """
    d = _json(installed_json) if installed_json else None
    if not isinstance(d, dict):
        return []
    out = []
    for key in sorted((d.get("plugins") or {})):
        name, _, market = str(key).partition("@")
        installs = d["plugins"][key] if isinstance(d["plugins"].get(key), list) else []
        manifest: dict[str, Any] = {}
        for inst in installs:
            root = Path(str((inst or {}).get("installPath") or ""))
            for rel in (Path(".claude-plugin") / "plugin.json", Path("plugin.json")):
                m = _json(root / rel)
                if isinstance(m, dict):
                    manifest = m
                    break
            if manifest:
                break
        desc = norm(manifest.get("description"))
        extra = norm(
            f"{manifest.get('displayName', '')} {flatten(manifest.get('keywords'), cap=20)} "
            f"{str(key).replace('-', ' ')}"
        )
        out.append(
            _mk(
                "plugin",
                name,
                installed_json,
                desc
                or f"Installed plugin {name} from marketplace {market or 'local'}.",
                routing_extra=extra,
                invoke=str(key),
                family=market or "local",
            )
        )
    return out


#: SUPPLEMENT for servers the shared map does not cover.
#:
#: MEASURED: the shared `hooks/semantic-router/mcp_hints.py` holds 37 entries but covers
#: only 5 of the 14 servers in the CURRENT `~/.mcp.json` -- it predates the multiplexer
#: consolidation (`cloud-hub`, `search-hub`, `social-hub`) and the browser rails. The 9
#: uncovered servers had no domain vocabulary at all, which is why the breadth probe
#: selected 0 of 14.
#:
#: Kept HERE rather than appended to the shared map on purpose: that file belongs to the
#: hook router, `harness-vcs-hygiene.md` makes the repo the source of truth for it, and a
#: routing unit reaching sideways into another unit's data file is how two copies start
#: drifting. The shared map stays PRIMARY (`_mcp_hints` prefers it); this only fills gaps.
MCP_HINTS_SUPPLEMENT = {
    "angr": "angr binary analysis: load a binary, control-flow graph CFG, call graph, "
    "decompile a function, basic blocks, imports exports strings, cross references xrefs, "
    "symbolic execution over a native executable.",
    "brightdata": "Bright Data web data: scrape a page as markdown, batch scrape, search "
    "engine queries, unblocked residential proxy fetching of public web content.",
    "cloud-hub": "Cloud infrastructure multiplexer: RunPod GPU pods and serverless "
    "endpoints, Azure resources, Google Cloud, Kaggle competitions datasets kernels, "
    "rclone remote file sync, Modal sandboxes and functions, Lightning AI studios, "
    "OVHcloud VPS and DNS, Databricks clusters jobs notebooks warehouses secrets.",
    "figma": "Figma design: read design context and variables from a file, screenshot a "
    "frame, generate a design into Figma, Code Connect component mapping, design tokens, "
    "FigJam diagrams, download assets.",
    "playwright": "Playwright browser automation: navigate, click, fill forms, type, "
    "hover, screenshot, accessibility snapshot, console messages, network requests, "
    "evaluate script, drive a web app end to end.",
    "playwright-cdp": "Playwright over Chrome DevTools Protocol: attach to an already "
    "running Chrome with a real logged-in profile, drive and inspect pages via CDP.",
    "playwright-extension": "Playwright via a browser extension: drive the user's own "
    "logged-in Chrome tabs, snapshot and interact without a separate browser launch.",
    "search-hub": "Web search and research multiplexer: Exa neural and keyword web "
    "search, code context search, Firecrawl scrape crawl map extract and change "
    "monitoring, Tavily search extract crawl research, SearXNG metasearch, deep research "
    "agents, paper and GitHub search.",
    "social-hub": "Social media accounts: Instagram saved collections feed and search, "
    "Facebook Messenger groups and pages, WhatsApp messages, TikTok public read-only "
    "trending creator and hashtag data.",
}


def _mcp_hints() -> dict[str, str]:
    """Load the estate's ALREADY-CURATED per-server capability prose.

    `hooks/semantic-router/mcp_hints.py` holds a maintained natural-language purpose plus
    representative tool-name keywords for each server ("decompile_function", "glide_dock",
    "tavily_search"). REUSED rather than re-authored -- re-deriving it here would create a
    second copy to drift out of sync, and this unit's brief is to build on what exists.

    MEASURED reason this matters: without it an mcp record's entire routing text was
    "MCP server <name> tool family" plus its argv, and the breadth probe reported
    **0 of 14** MCP servers selected across the whole 57-query set. A capability whose
    description contains no domain vocabulary is unreachable no matter how good the
    matcher is -- the clearest instance of the spec's "improve descriptions for routing".

    Fail-soft: a missing/unimportable hints module degrades to name-only records (the
    prior behaviour), never an exception.
    """
    out = dict(MCP_HINTS_SUPPLEMENT)
    path = REPO / "hooks" / "semantic-router" / "mcp_hints.py"
    if not path.is_file():  # pragma: no cover - the shared map is committed
        return out
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location("_routing_mcp_hints", path)
        if spec is None or spec.loader is None:  # pragma: no cover - defensive
            return out
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        hints = getattr(mod, "MCP_HINTS", None)
        if isinstance(hints, dict):
            # Shared map WINS on any key it defines -- it is the maintained source, and the
            # supplement exists only to cover servers it has not caught up with.
            out.update({str(k): str(v) for k, v in hints.items()})
        return out
    except Exception:  # pragma: no cover - any import failure degrades, never raises
        return out


def mcp(mcp_json: Path | None) -> list[Capability]:
    """MCP servers = tool FAMILIES. One record per server, not per tool: a server's
    tools share a domain, and per-tool records would dominate the corpus (the live
    fleet exposes hundreds of tools across 14 servers) without adding routing signal."""
    d = _json(mcp_json) if mcp_json else None
    servers = (d or {}).get("mcpServers") if isinstance(d, dict) else None
    if not isinstance(servers, dict):
        return []
    hints = _mcp_hints()
    out = []
    for name in sorted(servers):
        cfg = servers[name] if isinstance(servers[name], dict) else {}
        argv = " ".join(str(a) for a in (cfg.get("args") or [])[:8])
        hint = hints.get(str(name), "")
        out.append(
            _mk(
                "mcp",
                str(name),
                mcp_json,
                hint or f"MCP server {name} tool family.",
                routing_extra=f"{name.replace('-', ' ')} {cfg.get('command', '')} {argv}",
                invoke=f"mcp__{name}__*",
                family="mcp-server",
            )
        )
    return out


def _md_units(cls: str, root: Path | None, pattern: str) -> list[Capability]:
    if not root or not Path(root).is_dir():
        return []
    out = []
    for md in sorted(glob.glob(str(Path(root) / pattern), recursive=True)):
        fm, body = _frontmatter(_read(md))
        name = norm(fm.get("name")) or Path(md).stem
        desc = norm(fm.get("description")) or norm(body[:200])
        out.append(
            _mk(
                cls,
                name,
                md,
                desc or name,
                routing_extra=norm(body[:900]),
                invoke=f"/{name}" if cls == "command" else name,
            )
        )
    return out


def agents(root: Path | None) -> list[Capability]:
    return _md_units("agent", root, "*.md")


def commands(root: Path | None) -> list[Capability]:
    return _md_units("command", root, "**/*.md")


# --------------------------------------------------------------------------- discover

#: Class precedence for conflict resolution. Lower index wins a genuine tie.
#: Rationale: a live skill is directly invocable; a blueprint is a design to execute;
#: a registry candidate is only a pointer to something not yet adopted.
CLASS_PRECEDENCE = (
    "skill",
    "command",
    "workflow",
    "protocol",
    "preset",
    "mcp",
    "agent",
    "plugin",
    "candidate",
)


@dataclass
class Index:
    records: list[Capability]
    counts: dict[str, int]
    roots: Roots

    def __len__(self) -> int:
        return len(self.records)

    def by_id(self) -> dict[str, Capability]:
        return {r.id: r for r in self.records}

    def by_class(self, cls: str) -> list[Capability]:
        return [r for r in self.records if r.cls == cls]

    def verify_floors(self, floors: dict[str, int] | None = None) -> list[str]:
        """Return the list of floor VIOLATIONS. Empty list == every source populated.

        FAIL-CLOSED: a source below floor means the discovery walk broke, not that the
        inventory is empty. `[]` here is a positive assertion, never "nothing found".
        """
        floors = SOURCE_FLOORS if floors is None else floors
        return [
            f"{cls}: {self.counts.get(cls, 0)} < floor {n}"
            for cls, n in sorted(floors.items())
            if self.counts.get(cls, 0) < n
        ]

    def link_equivalents(self, min_similarity: float = 0.55) -> int:
        """Group MIRROR duplicates -- the same capability present in two trees.

        The live harness mirrors `~/.claude/commands/<x>.md` and `~/.claude/agents/<x>.md`
        into `~/.agents/skills/source-command-<x>/SKILL.md` and `source-agent-<x>/`. Both
        copies land in the index, and injecting BOTH is pure context waste: identical
        content, two cards, one capability.

        MEASURED before this was written, so the grouping rests on evidence rather than on
        the naming convention: all 23 detected pairs have token-Jaccard >= 0.842 between
        their declared descriptions and 20/23 are exactly 1.000. `min_similarity` is
        nevertheless enforced per pair -- if the mirror ever diverges into a genuinely
        different capability, it stops being grouped instead of being silently suppressed.

        DELIBERATELY NOT GROUPED: cross-class same-name records (18 measured, e.g.
        `mcp:figma` / `skill:figma` / `plugin:figma`). Those are a *server*, a *how-to*
        and a *plugin* -- related but not interchangeable, and a user may legitimately
        want more than one. Collapsing them would suppress real capability, which is the
        pruning the spec forbids.

        Returns the number of records assigned to a group.
        """
        from .descriptions import tokens as _tok

        by_cls_name = {(r.cls, r.name.lower()): r for r in self.records}
        linked = 0
        for r in self.records:
            m = _MIRROR_RX.match(r.name.lower())
            if not m:
                continue
            target = by_cls_name.get((m.group(1), m.group(2)))
            if target is None or target is r:
                continue
            a, b = set(_tok(r.desc_source)), set(_tok(target.desc_source))
            union = a | b
            if not union or len(a & b) / len(union) < min_similarity:
                continue
            key = f"{target.cls}:{target.name.lower()}"
            r.equiv_key = key
            target.equiv_key = key
            linked += 1
        return linked

    def equivalence_groups(self) -> dict[str, list[str]]:
        """key -> ids sharing it. Only non-trivial groups are returned."""
        groups: dict[str, list[str]] = {}
        for r in self.records:
            if r.equiv_key:
                groups.setdefault(r.equiv_key, []).append(r.id)
        return {k: sorted(v) for k, v in groups.items() if len(v) > 1}

    def resolve_tombstones(self) -> int:
        """Link `supersedes` prose to real ids and set `superseded_by` on the target.

        Returns the number of links made. Only exact-name matches within the SAME class
        are linked -- a fuzzy match here would silently retire a live capability.
        """
        idx = {r.name.lower(): r for r in self.records}
        links = 0
        for r in self.records:
            for target in r.supersedes:
                t = idx.get(target.strip().lower())
                if t is None or t is r or t.cls != r.cls:
                    continue
                # Prose direction: "<r> is renamed to <t>" => r is the tombstone.
                r.superseded_by = t.id
                links += 1
        return links


def discover(roots: Roots | None = None) -> Index:
    """Walk every source and return the normalized Index."""
    roots = roots or Roots.live()
    recs: list[Capability] = []
    recs += workflows(roots.workflows)
    recs += protocols(roots.protocols)
    recs += presets(roots.presets)
    recs += candidates(roots.registry)
    recs += skills(roots.skills)
    recs += plugins(roots.plugins_json)
    recs += mcp(roots.mcp_json)
    recs += agents(roots.agents)
    recs += commands(roots.commands)

    # Deterministic order: class precedence then id. Load-bearing -- every tie-break
    # downstream resolves by index position, so a nondeterministic walk would make
    # the router's output depend on filesystem iteration order.
    pos = {c: i for i, c in enumerate(CLASS_PRECEDENCE)}
    recs.sort(key=lambda r: (pos.get(r.cls, 99), r.id))

    counts: dict[str, int] = {}
    for r in recs:
        counts[r.cls] = counts.get(r.cls, 0) + 1
    idx = Index(records=recs, counts=counts, roots=roots)
    idx.resolve_tombstones()
    idx.link_equivalents()
    return idx


def main(argv: list[str] | None = None) -> int:
    """CLI gate. Enumerates real inputs, fails closed, emits a terminal marker."""
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    idx = discover()
    bad = idx.verify_floors()
    payload = {
        "total": len(idx),
        "counts": dict(sorted(idx.counts.items())),
        "floor_violations": bad,
        "card_bytes_total": sum(r.card_bytes for r in idx.records),
        "card_bytes_max": max((r.card_bytes for r in idx.records), default=0),
        "tombstones": sum(1 for r in idx.records if r.superseded_by),
        "with_anti_triggers": sum(1 for r in idx.records if r.anti_triggers),
        "with_triggers": sum(1 for r in idx.records if r.triggers),
        "equivalence_groups": len(idx.equivalence_groups()),
    }
    if "--json" in argv:
        print(json.dumps(payload, indent=2))
    else:
        for k, v in payload.items():
            print(f"{k:22}: {v}")
    if bad:
        print(f"FAILED:routing-index floor-violations={len(bad)}")
        return 1
    if payload["card_bytes_max"] > CARD_BYTE_CAP:
        print(f"FAILED:routing-index card-over-cap max={payload['card_bytes_max']}")
        return 1
    print(f"SUCCESS:routing-index units={len(idx)}")
    return 0
