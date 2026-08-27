#!/usr/bin/env python3
"""Isolate the owner's OWN writing out of a Facebook/Messenger "Download Your
Information" (DYI) JSON export.

    python isolate_messenger.py --root Facebook --me "Owner Name"

The Messenger schema is NOT the posts schema. A thread is a DIRECTORY holding
one or more shards::

    <archive>/your_facebook_activity/messages/inbox/<thread_slug>/message_1.json
                                              .../message_2.json   ...

and each shard is::

    {"participants":[{"name":...}], "messages":[...], "title":...,
     "is_still_participant":..., "thread_type":..., "thread_path":...}

Message objects are SPARSE -- absent fields are omitted, not null -- so every
read goes through .get(). Attested message-level keys (see COMPANION NOTE):
    sender_name  timestamp_ms  content  type  photos  videos  audio_files
    files  gifs  sticker  share  reactions  call_duration  missed  is_unsent
    ip  is_geoblocked_for_viewer

Outputs (mirroring isolate_discord.py, plus a per-thread summary):
    messenger_all.txt          every owner text message, timestamped
    messenger_substantial.txt  bursts >= MIN_CHARS of prose -- THE CORPUS
    messenger.jsonl            structured records for downstream tooling
    messenger_threads.md       per-thread summary: which conversations paid off

Stdlib only. Python 3.8+. Windows-safe.

MEMORY MODEL (GROUNDING trap #4): one shard is json.load()ed at a time, so the
PARSE side is O(largest shard) and --max-file-mb guards a pathological one.
But the RETENTION side is O(the owner's whole corpus): main() accumulates every
burst record -- not just the substantial ones -- in `all_records` so that
--chrono can sort globally. MEASURED (B3-ADV): 100,000 owner messages / 36.8 MB
of shards -> 124 MB peak, 10x the messages for 9.6x the peak, while the largest
shard stayed 0.18 MB. So peak ~ 3.4x the owner-authored bytes, INDEPENDENT of
shard size. At the Discord control's scale (104,842 owner messages) that is
~130 MB -- fine -- but a caller who needs a hard bound should drop --chrono and
stream each thread's records straight to disk in the main() loop.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone

# --------------------------------------------------------------------------
# 0.  Console safety (Windows cp1252 consoles raise on Romanian/emoji)
# --------------------------------------------------------------------------
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# --------------------------------------------------------------------------
# 1.  Mojibake repair  (GROUNDING trap #1 -- the highest-impact correctness bug)
# --------------------------------------------------------------------------
# Meta escapes each UTF-8 *byte* as its own \u00XX, so 'ă' (C4 83) lands as the
# two code points U+00C4 U+0083. The inverse is .encode('latin-1').decode('utf-8')
# -- but applied blindly to a whole string it either raises (any char > U+00FF)
# or, worse, silently corrupts genuine Latin-1 text. So: match only runs whose
# code points, read as bytes, form WELL-FORMED UTF-8 (Unicode 16.0 Table 3-7),
# and decode each run in isolation. A clean file is then byte-identical output.
#
#   C0/C1 absent     -> no overlong 2-byte forms
#   E0 needs A0..BF  -> no overlong 3-byte forms
#   ED needs 80..9F  -> can never emit a surrogate D800..DFFF
#   F0 needs 90..BF  -> no overlong 4-byte forms
#   F4 needs 80..8F  -> can never exceed U+10FFFF
#   F5..FF absent    -> not valid UTF-8 lead bytes
_UTF8_RUN = re.compile(
    "(?:"
    "[\xc2-\xdf][\x80-\xbf]"  # 2-byte -> U+0080..U+07FF
    "|\xe0[\xa0-\xbf][\x80-\xbf]"  # 3-byte, E0 non-overlong
    "|[\xe1-\xec\xee\xef][\x80-\xbf]{2}"  # 3-byte -> U+1000..U+FFFF
    "|\xed[\x80-\x9f][\x80-\xbf]"  # 3-byte, ED pre-surrogate
    "|\xf0[\x90-\xbf][\x80-\xbf]{2}"  # 4-byte, F0 non-overlong
    "|[\xf1-\xf3][\x80-\xbf]{3}"  # 4-byte -> astral plane
    "|\xf4[\x80-\x8f][\x80-\xbf]{2}"  # 4-byte, F4 <= U+10FFFF
    ")+"
)


def _decode_run(match: "re.Match") -> str:
    try:
        return match.group(0).encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):  # unreachable by construction
        return match.group(0)


# A run whose continuation code points are ALL printable Latin-1 (U+00A0..BF)
# is the AMBIGUOUS shape: it is equally consistent with real mojibake and with
# already-correct text that merely happens to put an accented letter next to
# punctuation. Genuine Meta mojibake of Romanian leans on C1 controls
# (ă -> C4 83, ș -> C8 99, ț -> C8 9B), which land OUTSIDE this class -- so
# counting these separately tells the operator how much of the repair is
# guesswork. See B3-ADV-2 F9: 'Am citit «café\xa0» ieri.' -> 'Am citit «caf頻 ieri.'
_AMBIGUOUS_RUN = re.compile("[\xc2-\xf4][\xa0-\xbf]{1,3}")


def ord_above_ff(s) -> bool:
    """True iff s holds a code point above U+00FF.

    This is the MECHANICAL proof that a string was never mangled. Meta's defect
    maps every UTF-8 byte to its own code point, so a mangled string lands
    entirely inside U+0000..U+00FF and CANNOT contain 'ă' (U+0103), 'ș'
    (U+0219), an em dash or an emoji. If the archive is full of these, the
    repair has nothing to do and `--mojibake-passes 0` is the correct setting.
    """
    return isinstance(s, str) and not s.isascii() and any(ord(c) > 0xFF for c in s)


def ambiguous_runs(s) -> int:
    """Count repairable runs whose continuations are all printable Latin-1."""
    if not isinstance(s, str) or s.isascii():
        return 0
    return sum(1 for m in _UTF8_RUN.finditer(s) if _AMBIGUOUS_RUN.fullmatch(m.group(0)))


def fix_mojibake(s, passes: int = 1):
    """Repair Meta's UTF-8-bytes-as-Latin-1 mojibake.

    Contract: NEVER raises; non-str passes through untouched; idempotent;
    pure ASCII is a strict no-op; repairs MIXED strings per-run so one
    already-correct character no longer blocks repair of the rest (which is
    exactly what the bare one-liner does, silently).

    `passes <= 0` DISABLES the repair entirely. That escape hatch is not
    decoration: the repair provably corrupts some already-correct text
    (B3-ADV-2 F9), so an operator who determines the archive was never
    mangled MUST be able to turn it off. It previously could not be --
    `max(1, passes)` silently promoted 0 to 1.
    """
    if type(s) is not str:
        return s
    if passes <= 0:
        return s
    if s.isascii():  # fast path -- an ASCII string cannot contain a run
        return s
    try:
        for _ in range(passes):
            out = _UTF8_RUN.sub(_decode_run, s)
            if out == s:
                break
            s = out
        return s
    except Exception:  # belt-and-braces: the contract is "never raises"
        return s


def looks_mojibaked(s) -> bool:
    """True iff s still contains at least one repairable run. Used to MEASURE
    the archive (and to detect DOUBLE encoding), never to gate the repair."""
    return isinstance(s, str) and _UTF8_RUN.search(s) is not None


# Legacy s-cedilla / t-cedilla -> the correct Romanian comma-below forms.
# NFC does NOT unify these: they are distinct code points with distinct
# canonical decompositions. Opt-in (--map-cedilla) because it edits what the
# owner actually typed; the summary always reports how many there are.
_CEDILLA_MAP = {0x015F: "ș", 0x015E: "Ș", 0x0163: "ț", 0x0162: "Ț"}
_CEDILLA_RE = re.compile("[ŞşŢţ]")


def normalize_text(s: str, map_cedilla: bool = False) -> str:
    """NFC-compose (safe, canonical, idempotent). Optionally fold legacy cedillas."""
    s = unicodedata.normalize("NFC", s)
    if map_cedilla:
        s = s.translate(_CEDILLA_MAP)
    return s


# --------------------------------------------------------------------------
# 2.  Constants
# --------------------------------------------------------------------------
DEFAULT_OWNER_NAMES = ["Owner Name"]
MIN_CHARS = 150  # the "long posts, not short thank-you" bar, same as Discord
BURST_GAP_SECONDS = 420  # merge same-author uninterrupted runs (chat is bursty)
MAX_FILE_MB = 512

# message_1.json ... message_N.json -- the DYI shard pattern. The `_N` suffix is
# OPTIONAL: the pre-2018 vintage emitted a single unnumbered `message.json`, the
# same migration this archive family already shows for posts
# (tests/fixtures/_variants/e1_2018_archive/posts/your_posts.json vs the numbered
# your_posts_1.json). Unnumbered sorts first, as index 0. (B3-ADV P2)
RE_SHARD = re.compile(r"^message(?:_(\d+))?\.json$", re.IGNORECASE)
# The flat E2EE layout ("<Name>_<N>.json") shards the SAME way, so its shards
# must be grouped by stem, not treated as one thread each. (B3-ADV-2 F10)
RE_FLAT_SHARD = re.compile(r"^(?P<stem>.+)_(?P<idx>\d+)\.json$", re.IGNORECASE)
# Auto-generated / system message types. `type` is OPTIONAL: some exports omit
# it entirely, so it may only ever DROP a message, never qualify one.
SYSTEM_TYPES = {"subscribe", "unsubscribe", "call", "plan", "planupdate"}
# DYI thread sections. Used only to LABEL a thread -- discovery is a recursive
# walk, so an unknown/renamed section is still picked up.
KNOWN_SECTIONS = {
    "inbox",
    "archived_threads",
    "filtered_threads",
    "message_requests",
    "e2ee_cutover",
    "encrypted",
}
# DYI messages-root metadata files that are not threads.
NON_THREAD_JSON = {
    "autofill_information.json",
    "chat_invites_received.json",
    "community_chats_settings.json",
    "encrypted_messaging_backup_settings.json",
    "information_about_your_devices.json",
    "messaging_settings.json",
    "messenger_active_status_platform_settings.json",
    "messenger_active_status_settings.json",
    "messenger_ui_settings.json",
    "secret_conversations.json",
    "support_messages.json",
    "your_chat_settings_on_web.json",
    "your_end-to-end_encryption_enabled_messenger_device.json",
    "your_messenger_app_install_information.json",
    "your_responsiveness_in_messaging_threads.json",
}

RE_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
RE_WS = re.compile(r"\s+")

DROP_REASONS = [
    "unsent",
    "call",
    "system",
    "sticker",
    "photo",
    "video",
    "gif",
    "audio",
    "file",
    "share_only",
    "empty",
]


# --------------------------------------------------------------------------
# 3.  Helpers
# --------------------------------------------------------------------------
def norm_name(s) -> str:
    """Fold a display name for comparison: NFC, casefold, collapse whitespace."""
    if not isinstance(s, str):
        return ""
    return RE_WS.sub(" ", unicodedata.normalize("NFC", s)).strip().casefold()


def prose_of(text: str) -> str:
    """Text with URLs removed and whitespace collapsed -- what we MEASURE.
    (The emitted text is always the original; this only sizes it.)"""
    return RE_WS.sub(" ", RE_URL.sub(" ", text)).strip()


def as_number(v):
    """int/float/numeric-string -> float; anything else (incl. bool, NaN,
    +-inf, non-numeric text) -> None.

    Two defects close here (B3-ADV-2):
      F11  a STRING `"1500000000000"` was rejected outright, so a serializer
           vintage that quotes its numbers drops EVERY message.
      F12  `int(float('nan'))` raises ValueError. `json.load` accepts a bare
           `NaN` literal, so one such token ABORTED the whole multi-thousand
           -file run with an uncaught traceback. The finite range check below
           is false for NaN and both infinities.
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v if -1e18 < v < 1e18 else None
    if isinstance(v, str):
        try:
            f = float(v.strip())
        except (TypeError, ValueError):
            return None
        return f if -1e18 < f < 1e18 else None
    return None


def iso_utc(ts_ms) -> str:
    try:
        return datetime.fromtimestamp(int(ts_ms) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
    except Exception:
        return "0000-00-00T00:00:00"


def tier_of(words: int) -> str:
    """Grade, never delete (R8). A=essay, B=paragraph, C=note, D=fragment."""
    if words >= 100:
        return "A"
    if words >= 25:
        return "B"
    if words >= 5:
        return "C"
    return "D"


# --------------------------------------------------------------------------
# 4.  Discovery -- recursive, layout-agnostic
# --------------------------------------------------------------------------
# The DYI root has been renamed at least three times
# ("messages/" -> "your_activity_across_facebook/messages/" ->
#  "your_facebook_activity/messages/"), so NOTHING is hardcoded: we walk the
# tree and take every message_<N>.json we find. --include-flat additionally
# accepts the E2EE "<Name>_<N>.json" flat layout, which carries the same
# {participants, messages} shape.
def discover_threads(root: str, include_flat: bool = False):
    """Yield (thread_key, section, [shard_path, ...]) with shards in NUMERIC
    order. Sorting matters: a plain glob puts message_10 before message_2."""
    by_dir = {}
    by_flat = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for name in sorted(filenames):
            if not name.lower().endswith(".json"):
                continue
            m = RE_SHARD.match(name)
            if m:
                idx = int(m.group(1)) if m.group(1) else 0
                by_dir.setdefault(dirpath, []).append(
                    (idx, os.path.join(dirpath, name))
                )
            elif (
                include_flat
                and name not in NON_THREAD_JSON
                and under_messages(dirpath, root)
            ):
                # The flat E2EE layout shards exactly like the nested one:
                # `Stefan Muresan_1.json`, `Stefan Muresan_2.json` are ONE
                # conversation. Keying on the full filename made each shard its
                # own "thread", which double-counts the thread table and -- worse
                # -- prevents burst merging across the shard boundary, so an
                # argument split across two files is destroyed. Group on the
                # stem with the `_N` suffix removed. (B3-ADV-2 F10)
                fm = RE_FLAT_SHARD.match(name)
                stem = fm.group("stem") if fm else name[:-5]
                idx = int(fm.group("idx")) if fm else 0
                by_flat.setdefault((dirpath, stem), []).append(
                    (idx, os.path.join(dirpath, name))
                )

    nested = {p for lst in by_dir.values() for _, p in lst}
    for dirpath in sorted(by_dir):
        shards = [p for _, p in sorted(by_dir[dirpath])]
        yield (os.path.relpath(dirpath, root), section_of(dirpath, root), shards)
    for dirpath, stem in sorted(by_flat):
        shards = [p for _, p in sorted(by_flat[(dirpath, stem)]) if p not in nested]
        if not shards:
            continue
        key = os.path.relpath(os.path.join(dirpath, stem), root)
        yield (key, section_of(dirpath, root) or "flat", shards)


def under_messages(path: str, root: str) -> bool:
    """True iff `path` sits inside the messages subtree.

    Scope guard for --include-flat. Without it the flat branch accepts EVERY
    .json anywhere in the archive -- posts, ads, security logs, topics -- and
    json.load()s each one looking for a `messages` list it will never find
    (B3-ADV P7: 4 non-message files admitted as "threads" from a 5-file
    archive). Harmless downstream, but it is unbounded I/O on a multi-GB export
    and it pollutes --census.
    """
    parts = os.path.relpath(path, root).replace("\\", "/").lower().split("/")
    if parts == ["."]:
        # The caller pointed --root straight AT a messages directory. This
        # clause used to return True unconditionally, which re-opened the very
        # hole F5 closed: with --root <archive root>, EVERY loose .json at the
        # archive root was admitted as a "thread" -- including the E2E oracle
        # `EXPECTED.json`, a declared must_not_read file. Admit the root itself
        # only when it IS a messages/section directory. A genuine thread
        # directory needs no exemption: its shards match RE_SHARD and never
        # reach this branch at all. (B3-ADV-2 F16)
        base = os.path.basename(os.path.abspath(root)).lower()
        return base == "messages" or base in KNOWN_SECTIONS
    return "messages" in parts or any(p in KNOWN_SECTIONS for p in parts)


def section_of(path: str, root: str) -> str:
    parts = os.path.relpath(path, root).replace("\\", "/").split("/")
    for part in parts:
        if part.lower() in KNOWN_SECTIONS:
            return part.lower()
    return ""


def load_shard(path: str, max_bytes: int, warn):
    """json.load ONE shard. Returns None (and warns) on oversize/corrupt --
    a bad shard must never abort a multi-thousand-file run."""
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        warn(f"stat failed {path}: {exc}")
        return None
    if size > max_bytes:
        warn(f"SKIPPED oversize shard ({size / 1e6:.0f} MB > limit): {path}")
        return None
    try:
        # utf-8-sig, not utf-8: a BOM makes json.load raise "Unexpected UTF-8
        # BOM", the shard is dropped with only a buried warning, and a whole
        # thread silently vanishes. utf-8-sig reads BOM-less files identically.
        # (B3-ADV P10)
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        warn(f"unreadable/corrupt shard {path}: {exc}")
        return None
    return data if isinstance(data, dict) else None


# --------------------------------------------------------------------------
# 5.  Message classification -- STRUCTURAL, never by localized strings
# --------------------------------------------------------------------------
# The auto-generated text Meta puts in system messages is LOCALIZED, so an
# English keyword filter matches nothing on a Romanian account. Every rule
# below keys off a structural field instead. The MIN_CHARS bar then does the
# language-independent heavy lifting on whatever slips through.
def classify(msg: dict, content: str):
    """Return (keep, drop_reason). `content` is already mojibake-repaired."""
    if msg.get("is_unsent"):
        return False, "unsent"
    # A call row carries no prose. Presence of the key must NOT by itself
    # discard writing: `"missed": false` and `"call_duration": 0` are falsy but
    # `is not None`, so an export vintage that stamps either onto ordinary
    # messages would have binned the entire corpus as "call" with a
    # plausible-looking summary. Require the row to actually be textless.
    # (B3-ADV P1 -- reproduced: 2/2 long Romanian messages dropped.)
    if (
        msg.get("call_duration") is not None or msg.get("missed") is not None
    ) and not content.strip():
        return False, "call"
    mtype = msg.get("type")
    if isinstance(mtype, str) and mtype.strip().lower() in SYSTEM_TYPES:
        return False, "system"

    if content.strip():
        # A share WITH the owner's own commentary is his writing -- keep it.
        # A bare link drop has no prose left once the URL is stripped.
        if msg.get("share") and not prose_of(content):
            return False, "share_only"
        return True, ""

    # No text: attribute the drop to whatever attachment it actually was.
    for key, reason in (
        ("sticker", "sticker"),
        ("photos", "photo"),
        ("videos", "video"),
        ("gifs", "gif"),
        ("audio_files", "audio"),
        ("files", "file"),
        ("share", "share_only"),
    ):
        if msg.get(key):
            return False, reason
    return False, "empty"


# --------------------------------------------------------------------------
# 6.  Burst merging (R8) -- the unit of writing in chat is the BURST
# --------------------------------------------------------------------------
# A 400-word argument typed as eight messages scores ZERO records at a 150-char
# per-message bar. Merge consecutive owner messages in the same thread that are
# uninterrupted by anyone else and separated by < gap seconds, THEN threshold.
# --burst-gap 0 disables this and reproduces the Discord control exactly.
def merge_bursts(timeline, gap_seconds: int):
    """timeline: [(ts_ms, is_owner, text_or_None), ...] sorted by ts_ms.
    Yields (ts_start_ms, ts_end_ms, n_msgs, text)."""
    gap_ms = max(0, gap_seconds) * 1000
    cur = []
    for ts_ms, is_owner, text in timeline:
        if not is_owner:
            if cur:
                yield _flush(cur)
                cur = []
            continue
        if cur and (gap_ms == 0 or ts_ms - cur[-1][0] > gap_ms):
            yield _flush(cur)
            cur = []
        cur.append((ts_ms, text))
    if cur:
        yield _flush(cur)


def _flush(cur):
    return (cur[0][0], cur[-1][0], len(cur), "\n".join(t for _, t in cur))


# --------------------------------------------------------------------------
# 7.  The pass over one thread
# --------------------------------------------------------------------------
class ThreadStats:
    __slots__ = (
        "key",
        "section",
        "title",
        "thread_type",
        "n_participants",
        "total",
        "owner_total",
        "owner_text",
        "bursts",
        "substantial",
        "words",
        "first_ms",
        "last_ms",
        "drops",
        "mojibake_hits",
        "residual_hits",
        "cedilla",
        "repair_samples",
        "no_ts",
        "dupes",
        "above_ff",
        "ambiguous",
    )

    def __init__(self, key: str, section: str):
        self.key, self.section = key, section
        self.title, self.thread_type, self.n_participants = "", "", 0
        self.total = self.owner_total = self.owner_text = self.no_ts = 0
        self.bursts = self.substantial = self.words = 0
        self.dupes = self.above_ff = self.ambiguous = 0
        self.first_ms = self.last_ms = None
        self.drops = {r: 0 for r in DROP_REASONS}
        self.mojibake_hits = self.residual_hits = self.cedilla = 0
        # Bounded before/after evidence so every repair is auditable. The
        # repair CANNOT distinguish real mojibake from text that merely looks
        # like it (a message of AltGr symbol soup can decode as valid UTF-8);
        # measured on the Discord control that is 2 in 104,842 messages and
        # 0 in 1,045 long-form ones, but it must be visible, not silent.
        self.repair_samples = []


def process_thread(key, section, shards, cfg, warn):
    """Read every shard of one thread; return (ThreadStats, [burst records])."""
    st = ThreadStats(key, section)
    timeline = []
    seen_rows = set()  # (ts_ms, content) of owner rows already taken -- F15

    for path in shards:
        data = load_shard(path, cfg.max_bytes, warn)
        if data is None:
            continue
        if not st.title:
            st.title = fix_mojibake(data.get("title") or "", cfg.passes) or key
            st.thread_type = data.get("thread_type") or ""
            st.n_participants = len(data.get("participants") or [])
        messages = data.get("messages")
        if not isinstance(messages, list):
            continue

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            st.total += 1
            # as_number() also absorbs a quoted "1500000000000" and rejects
            # NaN/inf, which used to crash int() outright. (B3-ADV-2 F11/F12)
            ts_num = as_number(msg.get("timestamp_ms"))
            if ts_num is None:
                # Pre-2018 vintages carried `timestamp` in SECONDS. Accept it,
                # but only at an unambiguous magnitude (< 1e11 would be the year
                # 1973 if read as ms, so it cannot be a real ms value here).
                # Anything else is COUNTED, not silently discarded: without
                # no_ts a whole-archive field rename reads as a clean run with
                # an empty corpus. (B3-ADV P4)
                alt = as_number(msg.get("timestamp"))
                if alt is not None and 0 < alt < 1e11:
                    ts_num = alt * 1000
                else:
                    st.no_ts += 1
                    continue
            ts_ms = int(ts_num)

            sender_raw = msg.get("sender_name") or ""
            if not isinstance(sender_raw, str):
                sender_raw = ""
            if norm_name(fix_mojibake(sender_raw, cfg.passes)) not in cfg.owner_keys:
                # Only another PERSON SPEAKING is a conversational turn that may
                # break the owner's burst. Two rows that are NOT that were being
                # counted as interruptions, splitting an argument in half so the
                # merged record never reached the bar (191 chars vs 150 in both
                # probes): an auto-generated membership/call row from another
                # participant (B3-ADV-2 F13), and an unattributed row with no
                # sender_name at all, as seen in E2EE-cutover dumps (F14).
                mtype = msg.get("type")
                if sender_raw.strip() and not (
                    isinstance(mtype, str) and mtype.strip().lower() in SYSTEM_TYPES
                ):
                    timeline.append((ts_ms, False, None))
                continue

            raw = msg.get("content") or ""
            if not isinstance(raw, str):
                raw = ""
            # DYI shards can overlap at their boundary, and a duplicated row is
            # concatenated verbatim into the burst -- the same paragraph twice in
            # the corpus. Identical (timestamp_ms, content) is the same message by
            # any reading; two DISTINCT messages cannot share a millisecond AND a
            # body. Only text-bearing rows are deduped, so attachment drop
            # accounting is untouched. (B3-ADV-2 F15; shard overlap itself is
            # UNVERIFIED against a real export -- settled by checking whether any
            # (timestamp_ms, content) pair repeats across two shards of one thread.)
            if raw:
                if (ts_ms, raw) in seen_rows:
                    st.dupes += 1
                    continue
                seen_rows.add((ts_ms, raw))

            st.owner_total += 1
            if ord_above_ff(raw):
                st.above_ff += 1
            st.ambiguous += ambiguous_runs(raw)
            if looks_mojibaked(raw):
                st.mojibake_hits += 1
            content = fix_mojibake(raw, cfg.passes)
            if content != raw and len(st.repair_samples) < 3:
                st.repair_samples.append((raw[:110], content[:110]))
            if looks_mojibaked(content):  # survived the repair => DOUBLE-encoded
                st.residual_hits += 1
            content = normalize_text(content, cfg.map_cedilla)
            if _CEDILLA_RE.search(content):
                st.cedilla += 1

            keep, reason = classify(msg, content)
            if not keep:
                st.drops[reason] = st.drops.get(reason, 0) + 1
                # NOT appended to the timeline. The owner's own photo/sticker/
                # call is not another speaker, so it must not BREAK his burst --
                # only someone else's message may. Measured cost of the old
                # behaviour: a 193-char argument typed either side of one photo
                # scored 2 sub-threshold bursts and 0 substantial records.
                # (B3-ADV P3)
                continue

            st.owner_text += 1
            st.first_ms = ts_ms if st.first_ms is None else min(st.first_ms, ts_ms)
            st.last_ms = ts_ms if st.last_ms is None else max(st.last_ms, ts_ms)
            timeline.append((ts_ms, True, content.strip()))

    timeline.sort(key=lambda t: t[0])
    records = []
    for ts0, ts1, n, text in merge_bursts(timeline, cfg.burst_gap):
        prose = prose_of(text)
        words = len(prose.split())
        st.bursts += 1
        rec = {
            "ts": iso_utc(ts0),
            "ts_ms": ts0,
            "ts_end_ms": ts1,
            "thread": st.title or key,
            "thread_key": key,
            "section": section,
            "thread_type": st.thread_type,
            "participants": st.n_participants,
            "msgs_in_burst": n,
            "len": len(text),
            "prose_len": len(prose),
            "words": words,
            "tier": tier_of(words),
            "substantial": len(prose) >= cfg.min_chars,
            "content": text,
        }
        if rec["substantial"]:
            st.substantial += 1
            st.words += words
        records.append(rec)
    return st, records


# --------------------------------------------------------------------------
# 8.  Sender census -- prove the detector before trusting an absence
# --------------------------------------------------------------------------
# There is no numeric owner id in the Messenger export (unlike Discord's
# OWNER_ID): isolation rests entirely on a display-name string, which can drift
# over a decade. The census counts, per sender, both messages AND the number of
# DISTINCT THREADS they appear in. That thread-count is a mechanically
# independent identifier: the account owner is the one participant present in
# (nearly) every thread. Run this FIRST on a real archive.
def run_census(threads, cfg, warn, limit: int = 30) -> int:
    msgs, in_threads = {}, {}
    n_threads = 0
    for key, section, shards in threads:
        n_threads += 1
        seen = set()
        for path in shards:
            data = load_shard(path, cfg.max_bytes, warn)
            if data is None:
                continue
            for msg in data.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                name = fix_mojibake(msg.get("sender_name") or "", cfg.passes).strip()
                if not name:
                    continue
                msgs[name] = msgs.get(name, 0) + 1
                seen.add(name)
        for name in seen:
            in_threads[name] = in_threads.get(name, 0) + 1

    print(f"\n  SENDER CENSUS over {n_threads} threads\n")
    print(f"  {'threads':>8} {'msgs':>10}  sender_name")
    print(f"  {'-' * 8} {'-' * 10}  {'-' * 40}")
    for name in sorted(in_threads, key=lambda n: (-in_threads[n], -msgs[n]))[:limit]:
        print(f"  {in_threads[name]:>8} {msgs[name]:>10}  {name!r}")
    print(
        "\n  The owner is the sender present in (nearly) ALL threads.\n"
        "  Pass every historical spelling with repeated --me flags.\n"
    )
    return 0


# --------------------------------------------------------------------------
# 9.  Output
# --------------------------------------------------------------------------
def write_outputs(out_dir, all_records, stats, cfg, warnings):
    os.makedirs(out_dir, exist_ok=True)
    p_all = os.path.join(out_dir, "messenger_all.txt")
    p_sub = os.path.join(out_dir, "messenger_substantial.txt")
    p_jsonl = os.path.join(out_dir, "messenger.jsonl")
    p_threads = os.path.join(out_dir, "messenger_threads.md")

    ordered = (
        sorted(all_records, key=lambda r: r["ts_ms"]) if cfg.chrono else all_records
    )

    with (
        open(p_all, "w", encoding="utf-8", newline="\n") as fa,
        open(p_jsonl, "w", encoding="utf-8", newline="\n") as fj,
        open(p_sub, "w", encoding="utf-8", newline="\n") as fs,
    ):
        for rec in ordered:
            fa.write(f"[{rec['ts']}] ({rec['thread']}) {rec['content']}\n")
            fj.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if rec["substantial"]:
                fs.write(f"[{rec['ts']}] ({rec['thread']})\n{rec['content']}\n\n")

    write_thread_summary(p_threads, stats, cfg, warnings)
    return p_all, p_sub, p_jsonl, p_threads


def write_thread_summary(path, stats, cfg, warnings):
    ranked = sorted(stats, key=lambda s: (-s.words, -s.substantial, s.key))
    tot = {
        k: sum(getattr(s, k) for s in stats)
        for k in (
            "total",
            "owner_total",
            "owner_text",
            "bursts",
            "substantial",
            "words",
            "mojibake_hits",
            "residual_hits",
            "cedilla",
            "no_ts",
            "dupes",
            "above_ff",
            "ambiguous",
        )
    }
    drops = {r: sum(s.drops.get(r, 0) for s in stats) for r in DROP_REASONS}

    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# Messenger — per-thread contribution to the corpus\n\n")
        fh.write(
            f"Owner names matched: {', '.join(repr(n) for n in cfg.owner_names)}  \n"
            f"MIN_CHARS = {cfg.min_chars} (measured on URL-stripped prose)  \n"
            f"burst gap = {cfg.burst_gap}s "
            f"({'per-message, Discord-equivalent' if cfg.burst_gap == 0 else 'same-author runs merged'})  \n"
            f"mojibake passes = {cfg.passes}; NFC = always; cedilla folding = {cfg.map_cedilla}\n\n"
        )
        fh.write("## Totals\n\n")
        fh.write(f"- threads scanned: **{len(stats)}**\n")
        fh.write(f"- messages seen (all senders): **{tot['total']:,}**\n")
        fh.write(f"- owner messages: **{tot['owner_total']:,}**\n")
        fh.write(f"- owner messages with usable text: **{tot['owner_text']:,}**\n")
        fh.write(f"- bursts after merging: **{tot['bursts']:,}**\n")
        fh.write(
            f"- **substantial (>= {cfg.min_chars} chars of prose): "
            f"{tot['substantial']:,}  (~{tot['words']:,} words)**\n"
        )
        if tot["no_ts"]:
            fh.write(
                f"- **messages skipped for an unreadable timestamp: {tot['no_ts']:,}** "
                f"(neither `timestamp_ms` nor a seconds-scale `timestamp`; a large "
                f"number here means a schema drift, not a sparse archive)\n"
            )
        fh.write("\n### Owner messages dropped, by reason\n\n")
        for reason in DROP_REASONS:
            if drops[reason]:
                fh.write(f"- {reason}: {drops[reason]:,}\n")
        if tot["dupes"]:
            fh.write(
                f"- duplicate owner rows collapsed (same `timestamp_ms` AND same "
                f"`content`, i.e. overlapping shards): **{tot['dupes']:,}**\n"
            )
        fh.write("\n### Mojibake diagnostics\n\n")
        fh.write(
            f"- owner messages already holding a code point above U+00FF "
            f"(`ă ș ț — 😀`): **{tot['above_ff']:,}**\n"
        )
        if tot["above_ff"] and not tot["mojibake_hits"]:
            fh.write(
                "  - Meta's defect maps every UTF-8 byte to its own code point, so a\n"
                "    mangled string CANNOT hold one of these. This archive was never\n"
                "    mangled: re-run with **`--mojibake-passes 0`** to switch the repair\n"
                "    off entirely and remove all risk of the F9 false-positive below.\n"
            )
        fh.write(
            f"- owner messages containing a repairable run: **{tot['mojibake_hits']:,}**\n"
        )
        fh.write(
            f"- of those, runs of the AMBIGUOUS shape (all continuations printable\n"
            f"  Latin-1) — equally consistent with correct text: **{tot['ambiguous']:,}**\n"
        )
        if tot["ambiguous"]:
            fh.write(
                "  - These are the repairs that can be WRONG. Real mojibaked Romanian\n"
                "    leans on C1 controls (`ă`->`C4 83`, `ș`->`C8 99`), which are not of\n"
                "    this shape. Measured false positive: `Am citit «café\\xa0» ieri.` ->\n"
                "    `Am citit «caf頻 ieri.` — correct French/Romanian typography with a\n"
                "    no-break space, destroyed. Eyeball the sample repairs below.\n"
            )
        fh.write(
            f"- still repairable AFTER the repair (=> double-encoded): "
            f"**{tot['residual_hits']:,}**\n"
        )
        if tot["residual_hits"]:
            fh.write(
                "  - `--mojibake-passes 2` fixes those, but it is applied GLOBALLY and a\n"
                "    second pass is NOT a no-op on text the first pass already got right:\n"
                "    B3-ADV P6 decoded `Ã© Ä¤ Î» Â« Å¾` -> `é Ĥ λ « ž` -> further. Only\n"
                "    raise it if the sample repairs below still look broken.\n"
            )
        fh.write(
            f"- messages containing legacy cedilla ş/ţ: **{tot['cedilla']:,}**\n\n"
        )
        samples = [s for st in stats for s in st.repair_samples][:10]
        if samples:
            fh.write(
                "Sample repairs (eyeball these — the repair cannot tell real\n"
                "mojibake from text that merely looks like it):\n\n"
            )
            for before, after in samples:
                fh.write(f"- `{before}`\n  -> `{after}`\n")
            fh.write("\n")
        if warnings:
            fh.write(f"### Warnings ({len(warnings)})\n\n")
            for w in warnings[:50]:
                fh.write(f"- {w}\n")
            if len(warnings) > 50:
                fh.write(f"- ... and {len(warnings) - 50} more\n")
            fh.write("\n")

        fh.write("## Threads (ranked by words contributed)\n\n")
        fh.write(
            "| words | subst | bursts | owner txt | owner msgs | all msgs | ppl | type | section | thread | span |\n"
        )
        fh.write("|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|\n")
        for s in ranked:
            if not s.owner_total:
                continue
            span = (
                f"{iso_utc(s.first_ms)[:10]} .. {iso_utc(s.last_ms)[:10]}"
                if s.first_ms
                else "-"
            )
            title = (s.title or s.key).replace("|", "\\|")[:60]
            fh.write(
                f"| {s.words:,} | {s.substantial:,} | {s.bursts:,} | {s.owner_text:,} "
                f"| {s.owner_total:,} | {s.total:,} | {s.n_participants} "
                f"| {s.thread_type} | {s.section} | {title} | {span} |\n"
            )


# --------------------------------------------------------------------------
# 10.  CLI
# --------------------------------------------------------------------------
class Config:
    pass


def build_config(args) -> Config:
    cfg = Config()
    cfg.owner_names = args.me or list(DEFAULT_OWNER_NAMES)
    cfg.owner_keys = {norm_name(n) for n in cfg.owner_names}
    cfg.min_chars = args.min_chars
    cfg.burst_gap = args.burst_gap
    cfg.passes = args.mojibake_passes
    cfg.map_cedilla = args.map_cedilla
    cfg.chrono = args.chrono
    cfg.max_bytes = int(args.max_file_mb * 1_000_000)
    return cfg


def parse_args(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(
        description="Isolate the owner's writing from a Facebook/Messenger DYI JSON export.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument(
        "--root",
        default=os.path.join(here, "Facebook"),
        help="unzipped DYI archive root (walked recursively)",
    )
    ap.add_argument("--out", default=None, help="output directory (default: --root)")
    ap.add_argument(
        "--me",
        action="append",
        metavar="NAME",
        help="owner sender_name; repeat for historical spellings "
        f"(default: {DEFAULT_OWNER_NAMES[0]!r})",
    )
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS)
    ap.add_argument(
        "--burst-gap",
        type=int,
        default=BURST_GAP_SECONDS,
        help="merge same-author uninterrupted runs closer than this; 0 = off",
    )
    ap.add_argument(
        "--mojibake-passes",
        type=int,
        default=1,
        help="repair passes; 0 DISABLES the repair (use when the summary "
        "reports messages already above U+00FF); raise to 2 only if "
        "the summary reports residual hits",
    )
    ap.add_argument(
        "--map-cedilla",
        action="store_true",
        help="fold legacy s/t-cedilla to the correct comma-below forms",
    )
    ap.add_argument(
        "--chrono",
        action="store_true",
        help="order every output globally by time (default: grouped by thread)",
    )
    ap.add_argument(
        "--include-flat",
        action="store_true",
        help="also accept the E2EE flat '<Name>_<N>.json' thread layout",
    )
    ap.add_argument("--max-file-mb", type=float, default=MAX_FILE_MB)
    ap.add_argument(
        "--limit-threads", type=int, default=0, help="stop after N threads (smoke run)"
    )
    ap.add_argument(
        "--census",
        action="store_true",
        help="report every sender_name with message and THREAD counts, then exit",
    )
    ap.add_argument(
        "--selftest", action="store_true", help="run built-in fixture tests, then exit"
    )
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.selftest:
        return selftest()

    cfg = build_config(args)
    root = os.path.abspath(args.root)
    out_dir = os.path.abspath(args.out or args.root)

    if not os.path.isdir(root):
        print(
            f"FAILED: archive root does not exist: {root}\n"
            f"  Unzip the DYI export there, or pass --root.",
            file=sys.stderr,
        )
        return 2

    warnings = []
    warn = warnings.append

    threads = list(discover_threads(root, args.include_flat))
    if not threads:
        print(
            f"FAILED: no message_<N>.json found anywhere under {root}\n"
            f"  Two things to check: (1) is the zip actually extracted? "
            f"(2) did the export include Messages?",
            file=sys.stderr,
        )
        return 2
    if args.limit_threads:
        threads = threads[: args.limit_threads]

    if args.census:
        return run_census(threads, cfg, warn)

    print(f"  scanning {len(threads)} threads under {root}")
    stats, all_records = [], []
    for i, (key, section, shards) in enumerate(threads, 1):
        st, recs = process_thread(key, section, shards, cfg, warn)
        stats.append(st)
        all_records.extend(recs)
        if i % 250 == 0:
            print(
                f"  ... {i}/{len(threads)} threads, {len(all_records):,} bursts so far"
            )

    owner_total = sum(s.owner_total for s in stats)
    if owner_total == 0:
        print(
            "\nFAILED: matched 0 messages for "
            f"{', '.join(repr(n) for n in cfg.owner_names)}.\n"
            "  This is almost always a display-name mismatch, NOT an empty archive.\n"
            "  Run:  python isolate_messenger.py --root <root> --census\n"
            "  then re-run with --me for each spelling it shows.",
            file=sys.stderr,
        )
        return 3

    matched_threads = sum(1 for s in stats if s.owner_total)
    if matched_threads < len(threads) * 0.5:
        warn(
            f"owner matched in only {matched_threads}/{len(threads)} threads — "
            f"likely an unlisted historical display name. Run --census."
        )

    paths = write_outputs(out_dir, all_records, stats, cfg, warnings)
    subs = [r for r in all_records if r["substantial"]]
    residual = sum(s.residual_hits for s in stats)

    print(f"\n  threads with owner messages: {matched_threads}/{len(threads)}")
    print(f"  owner messages total:        {owner_total:,}")
    print(f"  with usable text:            {sum(s.owner_text for s in stats):,}")
    print(f"  bursts (gap={cfg.burst_gap}s):        {len(all_records):,}")
    print(
        f"  substantial (>={cfg.min_chars} chars):  {len(subs):,}  "
        f"(~{sum(r['words'] for r in subs):,} words of writing)"
    )
    hits = sum(s.mojibake_hits for s in stats)
    above = sum(s.above_ff for s in stats)
    ambig = sum(s.ambiguous for s in stats)
    dupes = sum(s.dupes for s in stats)
    print(f"  mojibake repaired in:        {hits:,} messages")
    if above and not hits:
        print(
            f"  NOTE: {above:,} messages already hold characters above U+00FF, which a\n"
            f"        mangled string cannot -- this archive was never mangled. Re-run\n"
            f"        with --mojibake-passes 0 to switch the repair off entirely."
        )
    elif ambig:
        print(
            f"  !! {ambig:,} of those repairs are AMBIGUOUS (see the summary): the run\n"
            f"     shape is equally consistent with already-correct text. Eyeball the\n"
            f"     sample repairs before trusting them."
        )
    if dupes:
        print(f"  duplicate rows collapsed:    {dupes:,} (overlapping shards)")
    no_ts = sum(s.no_ts for s in stats)
    if no_ts:
        print(f"  !! {no_ts:,} messages had no usable timestamp and were skipped")
    if not subs:
        print(
            "  !! ZERO substantial records. The owner WAS matched, so this is not a\n"
            "     name mismatch -- check --min-chars and the drop table in the summary\n"
            "     before treating an empty corpus as a finished run."
        )
    if residual:
        print(
            f"  !! {residual:,} messages STILL mojibaked after 1 pass -> consider "
            f"--mojibake-passes 2 (destructive to already-correct text; see summary)"
        )
    if warnings:
        print(f"  warnings: {len(warnings)} (see the thread summary)")
    for p in paths:
        print(f"  -> {p}")
    return 0


# --------------------------------------------------------------------------
# 11.  Self-test -- runs the whole pipeline against synthetic fixtures
# --------------------------------------------------------------------------
def _mojibake(s: str) -> str:
    """Reproduce Meta's defect: emit each UTF-8 byte as its own code point."""
    return s.encode("utf-8").decode("latin-1")


def selftest() -> int:
    import shutil
    import tempfile

    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r} want {want!r}")

    # -- 1. mojibake repair -------------------------------------------------
    for src in [
        "bună",
        "când",
        "întâi",
        "și",
        "țară",
        "ăâîșț ĂÂÎȘȚ",
        "şţ",
        "Într-o zi, mă gândeam la știință și artă.",
        "❤️",
        "😀",
        "🤣🎉",
        "👨‍👩‍👧‍👦",
        "👍🏿",
        "🇷🇴",
        "don’t",
        "bună ziua 😀",
    ]:
        check(f"repair {src!r}", fix_mojibake(_mojibake(src)), src)
    # mixed: mojibake NEXT TO an already-correct char -- the case the bare
    # one-liner silently fails (it raises, so try/except returns it unrepaired)
    check("mixed", fix_mojibake(_mojibake("bună") + " ✓"), "bună ✓")
    for clean in [
        "Trebuie sa fac asta.",
        "",
        "bună ziua",
        "😀",
        "știință",
        "café",
        "naïve",
        "Grüße",
    ]:
        check(f"noop {clean!r}", fix_mojibake(clean), clean)
        check(f"idempotent {clean!r}", fix_mojibake(fix_mojibake(clean)), clean)
    check("non-str int", fix_mojibake(12345), 12345)
    check("non-str None", fix_mojibake(None), None)
    check("detector positive", looks_mojibaked(_mojibake("bună")), True)
    check("detector negative", looks_mojibaked("bună"), False)

    # -- 2. helpers ---------------------------------------------------------
    check("prose strips url", prose_of("see https://x.com/a?b=1 ok"), "see ok")
    check("prose url only", prose_of("https://x.com/a"), "")
    check("norm_name", norm_name(" Andrei   Visalon "), "owner name")
    check("tier A", tier_of(100), "A")
    check("tier D", tier_of(4), "D")
    check("cedilla map", normalize_text("şţ", True), "șț")
    check("cedilla kept", normalize_text("şţ", False), "şţ")

    # -- 3. end-to-end over a fixture archive -------------------------------
    tmp = tempfile.mkdtemp(prefix="msgr_selftest_")
    try:
        me, other = "Owner Name", "Someone Else"
        long_ro = (
            "Mă gândeam mult la ce ai spus și cred că nu sunt de acord "
            "cu premisa, pentru că întreaga concluzie depinde de o "
            "presupunere pe care nimeni nu a verificat-o vreodată. "
        )
        thread = os.path.join(tmp, "your_facebook_activity", "messages", "inbox", "t_1")
        os.makedirs(thread)

        # shard 2 = OLDER; shard 10 exists purely to prove numeric ordering
        write_json(
            os.path.join(thread, "message_2.json"),
            {
                "participants": [{"name": _mojibake(me)}, {"name": other}],
                "title": _mojibake("Conversație lungă"),
                "thread_type": "Regular",
                "messages": [
                    msg(me, 1_000_000, content=_mojibake(long_ro * 2)),  # KEEP
                    msg(other, 1_001_000, content=_mojibake(long_ro * 2)),  # not owner
                    msg(me, 1_002_000, content="ok"),  # short
                    msg(me, 1_003_000, call_duration=42),  # call
                    msg(me, 1_004_000, missed=True),  # call
                    msg(me, 1_005_000, content="regret", is_unsent=True),  # unsent
                    msg(me, 1_006_000, photos=[{"uri": "p.jpg"}]),  # photo
                    msg(me, 1_007_000, sticker={"uri": "s.png"}),  # sticker
                    msg(me, 1_008_000, gifs=[{"uri": "g.gif"}]),  # gif
                    msg(me, 1_009_000, videos=[{"uri": "v.mp4"}]),  # video
                    msg(me, 1_010_000, audio_files=[{"uri": "a.mp3"}]),  # audio
                    msg(me, 1_011_000, files=[{"uri": "f.pdf"}]),  # file
                    msg(
                        me,
                        1_012_000,
                        content="https://a.example/x",
                        share={"link": "https://a.example/x"},
                    ),  # share_only
                    msg(
                        me,
                        1_013_000,
                        content=_mojibake(long_ro) + " https://a.example/x",
                        share={"link": "https://a.example/x"},
                    ),  # KEEP (commentary)
                    msg(me, 1_014_000, content="joined", type="Subscribe"),  # system
                    msg(me, 1_015_000, content=""),  # empty
                    "not-a-dict",  # hostile
                    msg(me, None, content="no timestamp"),  # hostile
                ],
            },
        )
        # shard 1 = NEWER, and holds a BURST: 3 short messages that only clear
        # MIN_CHARS once merged. Reactions appear in both attested shapes.
        write_json(
            os.path.join(thread, "message_1.json"),
            {
                "participants": [{"name": me}, {"name": other}],
                "title": _mojibake("Conversație lungă"),
                "thread_type": "Regular",
                "messages": [
                    msg(
                        me,
                        2_000_000,
                        content=_mojibake(
                            "Deci uite care e ideea, "
                            "și am tot vrut să scriu asta de mult timp: "
                        ),
                        reactions=[{"reaction": "ð", "actor": other}],
                    ),
                    msg(
                        me,
                        2_000_060,
                        content=_mojibake(
                            "problema nu e că nu avem "
                            "date, ci că nimeni nu se uită la ele cu atenție. "
                        ),
                    ),
                    msg(
                        me,
                        2_000_120,
                        content=_mojibake(
                            "Și asta se vede peste tot, "
                            "în absolut fiecare discuție pe care am avut-o."
                        ),
                    ),
                    msg(other, 2_000_200, content="hmm"),
                    msg(me, 9_000_000, content="fragment după pauză"),
                ],
            },
        )
        write_json(
            os.path.join(thread, "message_10.json"),
            {"participants": [{"name": me}], "title": "x", "messages": []},
        )
        # a group thread in a different section, to prove sections are walked
        grp = os.path.join(
            tmp, "your_facebook_activity", "messages", "archived_threads", "g_1"
        )
        os.makedirs(grp)
        write_json(
            os.path.join(grp, "message_1.json"),
            {
                "participants": [{"name": me}, {"name": other}, {"name": "Third"}],
                "title": "Grup",
                "thread_type": "RegularGroup",
                "messages": [msg(me, 3_000_000, content=long_ro * 2)],  # already clean
            },
        )
        # a metadata file that must NOT be read as a thread
        write_json(
            os.path.join(
                tmp, "your_facebook_activity", "messages", "autofill_information.json"
            ),
            {"a": 1},
        )

        found = list(discover_threads(tmp))
        check("threads discovered", len(found), 2)
        shard_names = [os.path.basename(p) for p in found[1][2]]
        check(
            "shard numeric order",
            shard_names,
            ["message_1.json", "message_2.json", "message_10.json"],
        )
        check("section labelled", found[0][1], "archived_threads")

        args = parse_args(["--root", tmp, "--out", tmp])
        cfg = build_config(args)
        st, recs = process_thread(*found[1], cfg, lambda m: None)

        check("title demojibaked", st.title, "Conversație lungă")
        # 15 owner rows in shard 2 (the 16th has no timestamp_ms and is skipped
        # before it is counted) + 4 in shard 1.
        check("owner messages", st.owner_total, 19)
        check("owner text kept", st.owner_text, 7)
        check("dropped call", st.drops["call"], 2)
        check("dropped unsent", st.drops["unsent"], 1)
        check("dropped photo", st.drops["photo"], 1)
        check("dropped sticker", st.drops["sticker"], 1)
        check("dropped gif", st.drops["gif"], 1)
        check("dropped video", st.drops["video"], 1)
        check("dropped audio", st.drops["audio"], 1)
        check("dropped file", st.drops["file"], 1)
        check("dropped share_only", st.drops["share_only"], 1)
        check("dropped system", st.drops["system"], 1)
        check("dropped empty", st.drops["empty"], 1)
        # 5 owner messages carry mojibaked content; "fragment după pauză" is
        # written clean, and must NOT be counted (or touched).
        check("mojibake counted", st.mojibake_hits, 5)
        check("no double-encoding", st.residual_hits, 0)

        subs = [r for r in recs if r["substantial"]]
        # the 3-message burst must survive as ONE substantial record
        burst = [r for r in subs if r["msgs_in_burst"] == 3]
        check("burst merged into 1 record", len(burst), 1)
        check(
            "burst text is Romanian",
            "știe" in burst[0]["content"] or "Și" in burst[0]["content"],
            True,
        )
        check("substantial count", len(subs), 3)
        check(
            "chronological ts",
            [r["ts_ms"] for r in recs],
            sorted(r["ts_ms"] for r in recs),
        )

        # --burst-gap 0 == the Discord control: no merge, so the 3-part
        # argument (~211 chars merged, ~70 each apart) is DESTROYED. This is
        # the measured cost of the per-message unit: 3 substantial -> 2.
        cfg0 = build_config(parse_args(["--root", tmp, "--burst-gap", "0"]))
        _, recs0 = process_thread(*found[1], cfg0, lambda m: None)
        check("no merge at gap 0", max(r["msgs_in_burst"] for r in recs0), 1)
        check("burst lost at gap 0", len([r for r in recs0 if r["substantial"]]), 2)

        rc = main(["--root", tmp, "--out", tmp])
        check("main rc", rc, 0)
        for name in (
            "messenger_all.txt",
            "messenger_substantial.txt",
            "messenger.jsonl",
            "messenger_threads.md",
        ):
            check(f"wrote {name}", os.path.getsize(os.path.join(tmp, name)) > 0, True)
        with open(os.path.join(tmp, "messenger.jsonl"), encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh]
        check("jsonl rows", len(rows), len(recs) + 1)  # +1 group thread
        check("jsonl is clean utf-8", any("ă" in r["content"] for r in rows), True)

        # a wrong --me must FAIL LOUDLY, never emit a silent empty corpus
        check(
            "wrong name fails", main(["--root", tmp, "--out", tmp, "--me", "Nobody"]), 3
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if fails:
        print(f"FAILED: {len(fails)} self-test assertion(s)")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("SUCCESS: all self-tests passed")
    return 0


def msg(sender, ts_ms, **kw):
    """Build a fixture message. Absent fields are OMITTED, as Meta does."""
    out = {"sender_name": sender}
    if ts_ms is not None:
        out["timestamp_ms"] = ts_ms
    out.update(kw)
    return out


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
