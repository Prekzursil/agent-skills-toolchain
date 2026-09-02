"""Deterministic extraction of raw claim records from the harness-restore corpus.

Every parser here is a pure function over file text. No LLM judgement, no heuristics that
depend on wording semantics: a record is recognised by its STRUCTURAL marker (heading shape,
table shape, bold-field marker) and its fields are sliced by regex.

Record classes and their structural markers (all verified against the real corpus):

  option_universe   07-OPTION-UNIVERSE.md        ``#### `A-01` Title``
  option_lane       07-OPTIONS-{AB,CD,EFG,HIJK,LM}.md
                                                 ``### A-01 - Title`` / ``### H-01 . Title``
  probe_finding     07-OPTIONS-*.md              ``### P1 - ...`` (measured ground truth)
  council_card      11-COUNCIL-OPTION-CARDS.md   ``#### CF-01 `slug` ``
  protocol          12-COUNCIL-PROTOCOLS...md    ``#### P01 `slug` ``
  preset            12-COUNCIL-PROTOCOLS...md    ``#### C-M01 `slug` ``
  blueprint         09-WORKFLOW-BLUEPRINT...md   ``### `BP-RES-01` v1.0.0 - Title``
  archaeology       08-WORKFLOW-ARCHAEOLOGY...md ``### `wf-saved-x` - file``
  mechanism_card    13-ARCHITECTURE-CANDIDATES   ``**MECH-01 - Title.** ...``
  arch_candidate    13-ARCHITECTURE-CANDIDATES   ``### A1 - NAME``
  invariant         14-NO-REGRESSION-CONTRACT.md ``## INV-4a - ...``
  decision          17-DECISION-LOG.md           ``| **D-O-01** | date | text | evidence |``
  unknown           18-OPEN-UNKNOWNS...md        ``### U-01 - ...``
  grill             16-GRILL-QUEUE*.md           ``### G-01 - ...``
  verify_doc        ADV*VERIFY*.md / verify-*.md one record per file (H1 + VERDICT)
  lane_finding      lane-*.md / 31-LANE-*.md     ``### 1.3 Title - VERDICT`` / ``### FIX-1 - ...``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------------------
# raw record
# --------------------------------------------------------------------------------------


@dataclass
class RawRecord:
    raw_id: str
    local_id: str
    record_class: str
    source_file: str
    source_line: int
    title: str = ""
    problem_text: str = ""
    mechanism_text: str = ""
    distinct_from: list[str] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    verdict: str = ""
    confidence_raw: str = ""
    severity_raw: str = ""
    evidence_anchors: list[str] = field(default_factory=list)
    probe_text: str = ""
    body: str = ""

    def as_dict(self) -> dict:
        return {
            "raw_id": self.raw_id,
            "local_id": self.local_id,
            "record_class": self.record_class,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "title": self.title,
            "problem_text": self.problem_text,
            "mechanism_text": self.mechanism_text,
            "distinct_from": self.distinct_from,
            "deps": self.deps,
            "verdict": self.verdict,
            "confidence_raw": self.confidence_raw,
            "severity_raw": self.severity_raw,
            "evidence_anchors": self.evidence_anchors,
            "probe_text": self.probe_text,
        }


# --------------------------------------------------------------------------------------
# tolerant field slicing
# --------------------------------------------------------------------------------------

# A bold field marker in ANY of the five dialects the corpus uses:
#   - **mechanism:** x        (07-OPTIONS-AB / EFG / 07-OPTION-UNIVERSE)
#   **Mechanism.** x          (07-OPTIONS-CD, paragraph form)
#   **Mechanism** x           (07-OPTIONS-HIJK, inline form)
#   - **Mechanism.** x        (07-OPTIONS-LM)
_BOLD_FIELD = re.compile(r"\*\*([^*]{1,60}?)\*\*[.:]?\s*")

_MECHANISM_KEYS = ("mechanism",)
_PROBLEM_KEYS = ("problem", "problem it claims to solve", "problem.")
_DISTINCT_KEYS = (
    "not a duplicate",
    "not a duplicate of",
    "why it is not a duplicate",
    "distinct because",
    "distinct",
    "distinct-because",
)
_DEPS_KEYS = ("deps", "deps / compatible / conflicts", "class/deps", "dependencies")
_CONF_KEYS = ("confidence", "conf", "conf.")
_PROOF_KEYS = (
    "proof",
    "proof before adoption",
    "proof-before-adoption",
    "settling experiment",
)

_ID_TOKEN = re.compile(
    r"\b((?:[A-Z]{1,4}-\d{1,3}[a-z]?)|(?:MECH-\d{1,3})|(?:[A-Z]\d{1,2}))\b"
)


def _norm_key(k: str) -> str:
    return re.sub(r"[^a-z /-]", "", k.strip().lower()).strip()


def slice_bold_fields(block: str) -> dict[str, str]:
    """Split a record body into {normalised bold-field key: value}.

    A field's value runs from the end of its marker to the start of the next bold marker
    that looks like a field key (i.e. a marker followed by ``:`` / ``.`` / whitespace and
    which is not an inline emphasis of running prose).  We accept the next bold marker
    unconditionally: over-truncating a value is safe here because the mechanism sentence
    always leads its field, while under-truncating would let a neighbouring field's tokens
    leak into the mechanism signature.
    """
    out: dict[str, str] = {}
    marks = list(_BOLD_FIELD.finditer(block))
    for i, m in enumerate(marks):
        key = _norm_key(m.group(1))
        if not key:
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(block)
        val = block[m.end() : end].strip()
        # strip a leading list bullet / separator residue
        val = re.sub(r"^[-*·|:.\s]+", "", val).strip()
        if key not in out and val:
            out[key] = val
    return out


def _pick(fields: dict[str, str], keys: tuple[str, ...]) -> str:
    for k in keys:
        if k in fields:
            return fields[k]
    # prefix match (handles "mechanism / how" style compound keys)
    for fk, fv in fields.items():
        for k in keys:
            if fk.startswith(k):
                return fv
    return ""


def ids_in(text: str) -> list[str]:
    seen: list[str] = []
    for m in _ID_TOKEN.finditer(text or ""):
        t = m.group(1)
        if t not in seen:
            seen.append(t)
    return seen


# --------------------------------------------------------------------------------------
# generic heading-block splitter
# --------------------------------------------------------------------------------------


def _blocks_by_heading(
    text: str, heading_re: re.Pattern[str], min_level: int = 3
) -> list[tuple[int, re.Match[str], str]]:
    """Return (1-indexed line, match, block-text) for every heading matching heading_re.

    A block ends at the next heading of the same or shallower level.
    """
    lines = text.splitlines()
    hits: list[tuple[int, re.Match[str], int]] = []
    for i, ln in enumerate(lines):
        m = heading_re.match(ln)
        if m:
            level = len(ln) - len(ln.lstrip("#"))
            hits.append((i, m, level))
    out = []
    for j, (i, m, level) in enumerate(hits):
        end = len(lines)
        for k in range(i + 1, len(lines)):
            ln = lines[k]
            if ln.startswith("#"):
                lvl = len(ln) - len(ln.lstrip("#"))
                if lvl <= level and lvl >= min_level - 1:
                    end = k
                    break
        out.append((i + 1, m, "\n".join(lines[i + 1 : end])))
    return out


# --------------------------------------------------------------------------------------
# per-class parsers
# --------------------------------------------------------------------------------------

_RE_UNIVERSE = re.compile(r"^#### +`([A-Z]{1,3}-\d{1,3})` +(.+?)\s*$")
_RE_LANE_OPT = re.compile(r"^### +`?([A-Z]{1,3}-\d{1,3})`? *[-—·:] *(.+?)\s*$")
_RE_PROBE = re.compile(r"^### +(P\d{1,2}) *[-—·:] *(.+?)\s*$")
_RE_CF = re.compile(r"^#### +(CF-\d{1,3}) +`([^`]+)`")
_RE_PROTO = re.compile(r"^#### +(P\d{2}) +`([^`]+)`")
_RE_PRESET = re.compile(r"^#### +(C-[A-Z]\d{2}) +`([^`]+)`")
_RE_BP = re.compile(r"^### +`(BP-[A-Z]+-\d{1,3})` +v[\d.]+ *[-—] *(.+?)\s*$")
_RE_ARCH_WF = re.compile(r"^### +`(wf-[a-z0-9-]+)` *[-—] *(.+?)\s*$")
_RE_ARCH_CAND = re.compile(r"^### +(A\d{1,2}) *[-—] *(.+?)\s*$")
_RE_MECHCARD = re.compile(r"^\*\*(MECH-\d{1,3}) *[-—] *(.+?)\*\* *(.*)$")
_RE_INV = re.compile(r"^## +(INV-[0-9]+[a-z]?(?:\.[A-Z])?) *[-—] *(.+?)\s*$")
_RE_UNKNOWN = re.compile(r"^### +(U-\d{1,3}) *[-—] *(.+?)\s*$")
_RE_GRILL = re.compile(r"^### +(G-\d{1,3}) *[-—] *(.+?)\s*$")
_RE_DECISION_ROW = re.compile(r"^\| *\*\*(D-[A-Z]-\d{1,3})\*\* *\|(.*)$")
# Lane reports label findings in FIVE shapes, all present in the real corpus.  The separator
# after the label is OPTIONAL; requiring it extracted 8 findings where ~100 are present, and
# requiring level>=3 missed every ``## FINDING X`` / ``## F1`` doc entirely.
_RE_LANE_FINDING_PATTERNS = (
    # ## FINDING P (the real regression) - text     /  ## FINDING A (critical) - text
    re.compile(r"^#{2,4} +FINDING +([A-Z0-9]{1,3})\b *(.+?)\s*$"),
    # ## F1 - CONFIRMED ROOT CAUSE of ...
    re.compile(r"^#{2,4} +(F\d{1,2}) *[-—.:·] *(.+?)\s*$"),
    # ### 1.3 Title   /  ### 1a. Title
    re.compile(r"^#{3,4} +(\d+\.\d+(?:\.\d+)?|\d+[a-z])\.? *[-—.:·]? *(.+?)\s*$"),
    # ### FIX-4 - Title  /  ### R-2: Title
    re.compile(r"^#{2,4} +(FIX-\d+|[A-Z]{1,3}-\d+) *[-—.:·]? *(.+?)\s*$"),
    # ## 1. Live MODULE_ORDER (11) vs main (13)
    re.compile(r"^## +(\d{1,2})\. +(.+?)\s*$"),
)

# A numbered lane section whose title matches one of these is bookkeeping, not a finding.
# Excluded from the claim set (kept in the raw dump as record_class='lane_section').
_RE_LANE_NONFINDING = re.compile(
    r"^\s*(?:coverage|what (?:this|i) (?:lane )?did not|what i did not|order of application|"
    r"appendix|method(?:ology)?|measurement caveats|reading key|scope|index|"
    r"patches\b|dead code on disk|wiring map|second-signal table|verdict in one line)",
    re.IGNORECASE,
)
_RE_VERDICT = re.compile(
    r"\*\*?VERDICT:?\*{0,2} *:?\*{0,2} *([A-Z][A-Z-]{2,30})", re.IGNORECASE
)
_RE_VERDICT_INLINE = re.compile(
    r"\b(CONFIRMED|REFUTED|PARTIAL|PARTIALLY[ -]CONFIRMED|NOT-CHECKED|NOT CHECKED|"
    r"BLOCKED|UNVERIFIED|CONFIRMED-BY-JOIN|SUPERSEDED)\b"
)
_RE_CONF_BAND = re.compile(
    r"\b(almost[- ]certain|likely|roughly[- ]even|even|unlikely|remote)\b"
    r"(?: *\(?(\d{2}) *[-–] *(\d{2}))?",
    re.IGNORECASE,
)
_RE_SEV = re.compile(
    r"\b(?:sev|severity)[ =:]*\**(critical|high|medium|med|low|info)\b", re.IGNORECASE
)
_RE_ANCHOR = re.compile(
    r"`([^`\n]*?(?:\.py|\.json|\.md|\.mjs|\.js|\.ps1|\.sh|\.yaml|\.yml|\.toml)(?::\d+(?:-\d+)?)?)`"
)


def _common_fields(rec: RawRecord, block: str) -> None:
    f = slice_bold_fields(block)
    rec.mechanism_text = _pick(f, _MECHANISM_KEYS)
    rec.problem_text = _pick(f, _PROBLEM_KEYS)
    rec.deps = ids_in(_pick(f, _DEPS_KEYS))
    rec.distinct_from = ids_in(_pick(f, _DISTINCT_KEYS))
    rec.confidence_raw = _pick(f, _CONF_KEYS)
    rec.probe_text = _pick(f, _PROOF_KEYS)
    rec.evidence_anchors = sorted(set(_RE_ANCHOR.findall(block)))[:12]
    m = _RE_SEV.search(block)
    if m:
        rec.severity_raw = m.group(1).lower()
    rec.body = block


def _mk(
    local_id: str,
    cls: str,
    src: Path,
    line: int,
    title: str,
    block: str,
    stem_prefix: bool = True,
) -> RawRecord:
    stem = src.name
    raw_id = f"{stem}#{local_id}" if stem_prefix else local_id
    rec = RawRecord(
        raw_id=raw_id,
        local_id=local_id,
        record_class=cls,
        source_file=stem,
        source_line=line,
        title=title.strip(),
    )
    _common_fields(rec, block)
    return rec


def parse_heading_class(
    path: Path,
    text: str,
    pattern: re.Pattern[str],
    cls: str,
    id_group: int = 1,
    title_group: int = 2,
) -> list[RawRecord]:
    out = []
    for line, m, block in _blocks_by_heading(text, pattern):
        title = (
            m.group(title_group) if m.lastindex and m.lastindex >= title_group else ""
        )
        out.append(_mk(m.group(id_group), cls, path, line, title, block))
    return out


def parse_mechanism_cards(path: Path, text: str) -> list[RawRecord]:
    """13-ARCHITECTURE-CANDIDATES §4: paragraph cards `**MECH-01 - Title.** body`."""
    out = []
    lines = text.splitlines()
    starts = [(i, m) for i, ln in enumerate(lines) if (m := _RE_MECHCARD.match(ln))]
    for j, (i, m) in enumerate(starts):
        end = starts[j + 1][0] if j + 1 < len(starts) else len(lines)
        # stop at a heading too
        for k in range(i + 1, end):
            if lines[k].startswith("#"):
                end = k
                break
        block = "\n".join([m.group(3)] + lines[i + 1 : end])
        rec = _mk(m.group(1), "mechanism_card", path, i + 1, m.group(2), block)
        # these cards are ` · `-separated, not bold-field-separated: mechanism is the
        # segment after the problem statement.  Recover it positionally.
        if not rec.mechanism_text:
            segs = [s.strip() for s in block.split("·")]
            # drop route/size tokens, then problem is next, mechanism the one after
            body_segs = [
                s
                for s in segs
                if s
                and not re.fullmatch(
                    r"(ADAPT|BUILD-(SMALL|MEDIUM|LARGE)|REPAIR|BUILD-NEW)", s
                )
            ]
            if len(body_segs) >= 2:
                rec.problem_text = rec.problem_text or body_segs[0]
                rec.mechanism_text = body_segs[1]
        if not rec.distinct_from:
            dm = re.search(r"\*distinct[^:]*:\*? *([^·]+)", block)
            if dm:
                rec.distinct_from = ids_in(dm.group(1))
        out.append(rec)
    return out


def parse_decision_rows(path: Path, text: str) -> list[RawRecord]:
    out = []
    for i, ln in enumerate(text.splitlines()):
        m = _RE_DECISION_ROW.match(ln)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        title = cells[1] if len(cells) > 1 else (cells[0] if cells else "")
        rec = _mk(m.group(1), "decision", path, i + 1, title[:300], ln)
        rec.mechanism_text = title
        rec.verdict = "DECIDED"
        rec.evidence_anchors = sorted(set(_RE_ANCHOR.findall(ln)))[:12]
        out.append(rec)
    return out


def parse_verify_doc(path: Path, text: str) -> list[RawRecord]:
    """One adversarial-verification document == one claim record with a verdict."""
    lines = text.splitlines()
    h1 = ""
    for ln in lines[:12]:
        if ln.startswith("# "):
            h1 = ln[2:].strip()
            break
    if not h1:
        h1 = path.stem
    head = "\n".join(lines[:80])
    verdict = ""
    m = _RE_VERDICT.search(head)
    if m:
        verdict = m.group(1).upper()
    if not verdict:
        m2 = _RE_VERDICT_INLINE.search(head)
        if m2:
            verdict = m2.group(1).upper().replace(" ", "-")
    rec = RawRecord(
        raw_id=f"{path.name}#doc",
        local_id=path.stem,
        record_class="verify_doc",
        source_file=path.name,
        source_line=1,
        title=h1,
        verdict=verdict or "UNSTATED",
    )
    # the target-finding line names the artifact under test == the mechanism locus
    tf = re.search(r"\*\*Target finding:?\*\*(.{0,400})", text, re.S)
    rec.mechanism_text = (tf.group(1) if tf else h1).strip()
    rec.problem_text = h1
    rec.evidence_anchors = sorted(set(_RE_ANCHOR.findall(head)))[:12]
    sm = _RE_SEV.search(head)
    if sm:
        rec.severity_raw = sm.group(1).lower()
    cm = _RE_CONF_BAND.search(head)
    if cm:
        rec.confidence_raw = cm.group(0)
    rec.body = head
    return [rec]


def parse_lane_findings(path: Path, text: str) -> list[RawRecord]:
    """Extract every labelled finding section from a lane report.

    Patterns are tried in declared order and the FIRST match wins per heading line, so a
    heading is never emitted twice.  De-duplicated on (local_id, source_line).
    """
    out: list[RawRecord] = []
    seen: set[tuple[str, int]] = set()
    for pattern in _RE_LANE_FINDING_PATTERNS:
        for line, m, block in _blocks_by_heading(text, pattern, min_level=2):
            key = (m.group(1), line)
            if any(k[1] == line for k in seen):
                continue
            seen.add(key)
            title = (m.group(2) or "").strip(" -—.:·")
            cls = "lane_section" if _RE_LANE_NONFINDING.match(title) else "lane_finding"
            rec = _mk(m.group(1), cls, path, line, title, block)
            head = title + "\n" + block[:1500]
            vm = _RE_VERDICT_INLINE.search(head)
            if vm:
                rec.verdict = vm.group(1).upper().replace(" ", "-")
            if not rec.mechanism_text:
                rec.mechanism_text = title
            out.append(rec)
    return sorted(out, key=lambda r: r.source_line)


# --------------------------------------------------------------------------------------
# corpus driver
# --------------------------------------------------------------------------------------

_VERIFY_NAME = re.compile(
    r"(?:^|[-_])(?:adv|adversarial)|verify|VERIFY|ADVERSARIAL", re.IGNORECASE
)


def _is_verify_doc(name: str) -> bool:
    n = name.lower()
    if not n.endswith(".md"):
        return False
    if n.startswith(
        ("00-", "07-", "08-", "09-", "11-", "12-", "13-", "16-", "17-", "18-")
    ):
        return False
    return ("verify" in n) or ("adversarial" in n) or n.startswith(("adv", "_adv"))


def extract_corpus(root: Path) -> list[RawRecord]:
    records: list[RawRecord] = []

    def rd(p: Path) -> str:
        return p.read_text(encoding="utf-8", errors="replace")

    # 1. option universe (post-consolidation canonical option set)
    p = root / "07-OPTION-UNIVERSE.md"
    if p.exists():
        records += parse_heading_class(p, rd(p), _RE_UNIVERSE, "option_universe")

    # 2. the five pre-consolidation lane option docs + their measured probe findings
    for name in (
        "07-OPTIONS-AB.md",
        "07-OPTIONS-CD.md",
        "07-OPTIONS-EFG.md",
        "07-OPTIONS-HIJK.md",
        "07-OPTIONS-LM.md",
    ):
        p = root / name
        if not p.exists():
            continue
        t = rd(p)
        records += parse_heading_class(p, t, _RE_LANE_OPT, "option_lane")
        records += parse_heading_class(p, t, _RE_PROBE, "probe_finding")

    # 3. council option cards / protocols / presets
    p = root / "11-COUNCIL-OPTION-CARDS.md"
    if p.exists():
        records += parse_heading_class(p, rd(p), _RE_CF, "council_card")
    p = root / "12-COUNCIL-PROTOCOLS-AND-PRESETS.md"
    if p.exists():
        t = rd(p)
        records += parse_heading_class(p, t, _RE_PROTO, "protocol")
        records += parse_heading_class(p, t, _RE_PRESET, "preset")

    # 4. blueprints
    p = root / "09-WORKFLOW-BLUEPRINT-LIBRARY.md"
    if p.exists():
        records += parse_heading_class(p, rd(p), _RE_BP, "blueprint")

    # 5. archaeology catalog
    p = root / "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"
    if p.exists():
        records += parse_heading_class(p, rd(p), _RE_ARCH_WF, "archaeology")

    # 6. architecture candidates + mechanism cards
    p = root / "13-ARCHITECTURE-CANDIDATES.md"
    if p.exists():
        t = rd(p)
        records += parse_heading_class(p, t, _RE_ARCH_CAND, "arch_candidate")
        records += parse_mechanism_cards(p, t)

    # 7. no-regression invariants
    p = root / "14-NO-REGRESSION-CONTRACT.md"
    if p.exists():
        records += parse_heading_class(p, rd(p), _RE_INV, "invariant")

    # 8. decision log rows
    p = root / "17-DECISION-LOG.md"
    if p.exists():
        records += parse_decision_rows(p, rd(p))

    # 9. open unknowns + settling probes
    p = root / "18-OPEN-UNKNOWNS-AND-PROBES.md"
    if p.exists():
        records += parse_heading_class(p, rd(p), _RE_UNKNOWN, "unknown")

    # 10. grill queue (owner decisions still open)
    for name in ("16-GRILL-QUEUE.md", "16-GRILL-QUEUE-PHASE2.md"):
        p = root / name
        if p.exists():
            records += parse_heading_class(p, rd(p), _RE_GRILL, "grill")

    # 11. lane reports (findings + fixes)
    for p in sorted(root.glob("*.md")):
        n = p.name
        if n.startswith("lane-") or n.startswith("31-LANE-"):
            records += parse_lane_findings(p, rd(p))

    # 12. adversarial verification documents (one record per document)
    for p in sorted(root.glob("*.md")):
        if _is_verify_doc(p.name):
            records += parse_verify_doc(p, rd(p))

    return records
