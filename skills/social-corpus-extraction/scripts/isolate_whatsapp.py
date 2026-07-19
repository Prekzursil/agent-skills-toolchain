#!/usr/bin/env python3
r"""Isolate the owner's OWN WhatsApp messages into a long-form writing corpus.

Companion to isolate_discord.py (repo root). Emits the same three outputs, into Whatsapp/:
    owner_all.txt          every owner message, timestamped -- the complete record
    owner_substantial.txt  only messages >= MIN_CHARS -- the actual WRITING
    owner.jsonl            structured, for downstream tooling

===========================================================================================
READ FIRST -- A META DYI EXPORT DOES NOT CONTAIN WHATSAPP MESSAGE BODIES
===========================================================================================
Research unit R4 established this with three mechanically-independent signals and zero
contradicting ones (research/R4-whatsapp-dyi.md:10-96). WhatsApp's Help Center states it
verbatim: "Account information reports don't include your personal messages"
(https://faq.whatsapp.com/526463418847093/). E2EE means Meta never holds the plaintext
(https://faq.whatsapp.com/849367647393371/), so it cannot be in any server-side export.

This CORRECTS GROUNDING.md:37-39, which says "the same DYI flow is a viable rail" for
WhatsApp. It is not, for message text. Confidence: almost certain (90-99%).

Consequently the DYI rail here DEGRADES LOUDLY rather than pretending to work: it
inventories the archive (which does carry group names / contacts / settings, per
R4-whatsapp-dyi.md:113-124), actively probes it for message-body-shaped content so that
R4's finding stays falsifiable at runtime rather than baked in as dogma, and exits 2.
The corpus itself comes from the .txt rail below.

RAIL (a) DYI archive  -> inventory + probe + explain + exit 2. Zero corpus words.
RAIL (b) _chat.txt    -> the real rail. In-app "Export chat", per chat, from the phone.
                         Accepts a bare .txt, a directory of them, or the ZIPs WhatsApp
                         produces (member `_chat.txt`), in any mix. Auto-detected.

===========================================================================================
WHY THIS PARSER IS NOT A LINE-PER-MESSAGE READER
===========================================================================================
A `_chat.txt` line is `[date, time] Sender: text`, but four documented properties make the
naive reader silently destroy exactly the long-form messages this corpus exists for:

 1. MULTI-LINE MESSAGES HAVE NO TERMINATOR. Any line that fails the message-start regex is
    a CONTINUATION of the previous message and is appended, never dropped. The long
    messages are precisely the multi-line ones (R4-whatsapp-dyi.md:251-253).
 2. INVISIBLE BIDI MARKS. Lines may be prefixed with U+200E / U+200F, so a `^\[` match
    silently returns nothing and reads as "empty file" (R4-whatsapp-dyi.md:239-244).
    Locale builds also emit U+00A0 / U+202F / U+2011 (R5-whatsapp-alt-rails.md:286-287).
    NOTE: the cited prior art DELETES U+00A0, which joins adjacent words. We map
    space-like characters to U+0020 and delete only zero-width/bidi ones.
 3. LOCALE-DEPENDENT DATES WITH NO IN-FILE DECLARATION. dd/mm vs mm/dd, 12h vs 24h. We
    INFER per file from evidence (a component > 12 proves its own position) and fall back
    to DEFAULT_DAY_FIRST only when the file is genuinely ambiguous -- and say so
    (R4-whatsapp-dyi.md:245-249).
 4. SYSTEM LINES ARE AUTHOR-LESS AND LOCALIZED. Detection is STRUCTURAL first (no
    `Sender: ` group == system). The phrase list is advisory only, because R3 established
    that Meta's auto-generated strings are localized and an English-only filter matches
    nothing on a Romanian account (research/R3-original-vs-share.md, lead correction).

ENCODING -- THE KNOWN FIX IS THE BUG HERE. GROUNDING.md:48-52 prescribes
`s.encode('latin-1').decode('utf-8')`. That is scoped to Meta's SERVER-SIDE DYI emitter.
`_chat.txt` is written client-side as UTF-8 and never transits it, so applying the repair
would CREATE corruption (R4-whatsapp-dyi.md:302-310, very likely 80-90%). We therefore
DETECT and report, and never repair unless --repair-mojibake is passed explicitly. That is
the "detect, then repair" rule from R1/R2 rather than blind transformation.

OWNER ISOLATION -- THE HARD PART, AND WHY THIS SCRIPT REFUSES TO GUESS.
`_chat.txt` carries NO owner flag; the only sender identifier is a display-name STRING
(R4-whatsapp-dyi.md:262-274). Worse, that string is whatever the EXPORTING DEVICE had
saved -- so if the file came from the other party's phone, the owner's own lines carry
whatever THEY saved the owner as, which no constant can predict. Four strategies run in
order (see resolve_owner_label); if none is conclusive the file is SKIPPED with a report
of its candidate senders. For a corpus of "writing by me", admitting someone else's prose
is far worse than missing some of mine, so ambiguity fails loud instead of guessing.

MEMORY -- STATED HONESTLY, because the earlier claim here was false. This module does NOT
stream .txt files. `_read_lines` calls `fh.read()` and `parse_chat_file` then holds, for
ONE chat file at a time: the whole decoded text, its `splitlines()` list, a per-line
`heads` list, and a WaMessage per message INCLUDING other participants'. Peak is therefore
several times the size of the single largest chat export, not O(1). That is acceptable
here only because WhatsApp's in-app "Export chat" writes ONE FILE PER CHAT (tens of MB at
worst), and files are processed one at a time, so a large archive of many chats never
loads at once. It would NOT be acceptable for a single multi-GB file. GROUNDING.md:60-61
is satisfied by the per-chat bound, not by streaming -- and a multi-GB _chat.txt would
still OOM. UNVERIFIED what the owner's largest real export actually is; settled by running
this on the real archive and watching peak RSS.

A DYI zip is inventoried from its central directory and only probed member-by-member under
PROBE_BYTE_CAP, which IS bounded.

Run `python isolate_whatsapp.py --self-test` to exercise every trap above against
synthetic fixtures built from the cited format specs (they are TEST VECTORS derived from
R4-whatsapp-dyi.md:220-228 and R5-whatsapp-alt-rails.md:282-295, not real archive data).
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from collections import Counter

# =============================================================================
# CONFIGURATION -- the identity set is a constant so it can be edited in one place.
# =============================================================================

#: Every string that may denote the owner as a message SENDER. Matched after
#: normalisation (invisible-strip + NFC + cedilla-fold + casefold). Phone numbers are
#: compared digits-only on the last PHONE_MATCH_DIGITS digits, so "<OWNER_PHONE_INTL>",
#: "<OWNER_PHONE_INTL>" and "<OWNER_PHONE_LOCAL>" all match.
#: NOTE: this set is necessary but NOT sufficient -- see the module docstring on why the
#: owner's label in any given export is not predictable. It is strategy 2 of 4.
OWNER_IDENTITY: tuple[str, ...] = (
    "<OWNER_PHONE_INTL>",
    "<OWNER_PHONE_INTL>",
    "<OWNER_PHONE_LOCAL>",
    "Owner Name",
    "Owner",
    "owner",
    "<owner_ig_handle>",
)

#: Labels WhatsApp uses for the exporting user's own messages in some builds/locales.
#: UNVERIFIED that any of these appear in this owner's exports -- settled by exporting one
#: short chat and reading the label on a known-sent line (R4-whatsapp-dyi.md:269-274).
OWNER_SELF_LABELS: tuple[str, ...] = ("You", "Tu", "Eu")

PHONE_MATCH_DIGITS = 9  # compare the last 9 digits; survives +40 / 0040 / 0 prefixes
MIN_CHARS = 150  # parity with isolate_discord.py:16 -- keeps corpora comparable
BURST_GAP_SECONDS = 420  # R8: merge same-author uninterrupted runs under 7 minutes
DEFAULT_DAY_FIRST = True  # Romanian locale; used ONLY when a file is truly ambiguous
PROBE_BYTE_CAP = 2_000_000  # per-member read cap when probing a DYI archive
OUT_PREFIX = "owner"

HERE = os.path.dirname(os.path.abspath(__file__))
WHATSAPP_DIR = os.path.join(HERE, "Whatsapp")

# R8: grade, never delete. Tiers are prose-WORD counts, recorded per record in the JSONL.
WORD_TIERS = ((100, "A"), (25, "B"), (5, "C"), (0, "D"))

# =============================================================================
# TEXT HYGIENE
# =============================================================================

#: Deleted outright: zero-width and bidi-control characters. Invisible in every editor;
#: they break naive matching and corrupt word counts.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍‎‏‪‫‬‭‮⁦⁧⁨⁩﻿"))
#: Mapped, NOT deleted: these carry real spacing/hyphen semantics. Deleting U+00A0 (as the
#: cited prior art does) silently glues two words together.
_LOOKALIKE = {ord(" "): " ", ord(" "): " ", ord(" "): " ", ord(" "): " ", ord("‑"): "-"}

#: Romanian s/t-cedilla -> s/t-comma. Legacy CP1250 / Mac-Romanian emitted the cedilla
#: forms; the correct Romanian letters are the comma-below ones. VERIFIED BY EXECUTION
#: that NFC and NFKC do NOT merge them (they are distinct codepoints with distinct
#: canonical decompositions), so an explicit map is required -- R8's correction, which I
#: re-derived independently rather than taking on trust.
_CEDILLA_FOLD = {0x015F: "ș", 0x0163: "ț", 0x015E: "Ș", 0x0162: "Ț"}

#: Detector for Meta's UTF-8-bytes-read-as-Latin-1 mojibake. Ported from
#: research/R2-mojibake.md:339-349. The byte-range exclusions (no C0/C1, E0 needs A0-BF,
#: ED needs 80-9F, F0 needs 90-BF, F4 needs 80-8F, no F5-FF) are what stop it firing on
#: ordinary accented text. Used here for MEASUREMENT ONLY -- see module docstring.
_UTF8_RUN = re.compile(
    "(?:"
    "[Â-ß][-¿]"  # 2-byte -> U+0080..U+07FF
    "|à[ -¿][-¿]"  # 3-byte, E0 non-overlong
    "|[á-ìîï][-¿]{2}"  # 3-byte -> U+1000..U+FFFF
    "|í[-][-¿]"  # 3-byte, ED pre-surrogate
    "|ð[-¿][-¿]{2}"  # 4-byte, F0 non-overlong
    "|[ñ-ó][-¿]{3}"  # 4-byte -> astral plane
    "|ô[-][-¿]{2}"  # 4-byte, F4 <= U+10FFFF
    ")+"
)


def strip_invisible(s: str) -> str:
    """Delete zero-width/bidi marks; map NBSP-likes to a real space. Never raises."""
    if not s:
        return s
    return s.translate(_ZERO_WIDTH).translate(_LOOKALIKE)


def normalize_text(s: str, *, fold_cedilla: bool = True) -> str:
    """NFC + optional Romanian cedilla->comma fold.

    This is DECODING normalisation, not content editing: the owner typed the same letter
    either way and the input method decided which codepoint landed. We deliberately do NOT
    restore ABSENT diacritics -- diacritic-less Romanian is authentic authorial behaviour
    and inventing characters would both fabricate text and destroy a register signal (R8).
    """
    out = unicodedata.normalize("NFC", s)
    return out.translate(_CEDILLA_FOLD) if fold_cedilla else out


def looks_mojibaked(s: str) -> bool:
    """True iff s contains at least one Latin-1-over-UTF-8 run. MEASUREMENT ONLY.

    Cannot distinguish genuine text that merely looks like mojibake (R7); that is why it
    reports rather than gates.
    """
    return isinstance(s, str) and _UTF8_RUN.search(s) is not None


def repair_mojibake(s: str) -> str:
    """Per-run latin-1->utf-8 repair. Opt-in only (--repair-mojibake); never raises.

    Per-RUN, not whole-string: the bare one-liner aborts on the first correct character
    above U+00FF, so under try/except a mixed string returns silently unrepaired (R2).
    """
    if type(s) is not str or s.isascii():
        return s
    try:
        return _UTF8_RUN.sub(
            lambda m: m.group(0).encode("latin-1", "strict").decode("utf-8", "strict"),
            s,
        )
    except Exception:
        return s


def match_key(s: str) -> str:
    """Canonical form for comparing sender labels."""
    return normalize_text(strip_invisible(s or "")).strip().casefold()


def digits_only(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


# =============================================================================
# MESSAGE MODEL
# =============================================================================


@dataclasses.dataclass
class WaMessage:
    ts_raw: str  # timestamp exactly as written in the file
    when: dt.datetime | None  # parsed; None if the format defeated us (text is kept)
    author: str | None  # None == structural system line
    body: str
    chat: str
    is_system: bool = False
    had_attachment: bool = False
    interrupted: bool = True  # was the previous message in this chat by someone else?
    n_merged: int = 1

    @property
    def iso(self) -> str:
        return self.when.strftime("%Y-%m-%dT%H:%M:%S") if self.when else self.ts_raw


# =============================================================================
# LINE GRAMMAR
# =============================================================================

# Ported from whatsapp-chat-parser's sharedRegex (R4-whatsapp-dyi.md:220-228). Three
# date components are REQUIRED, which is what keeps ordinary prose ("12/25 was a good
# day") from being mistaken for a message start.
_LINE_START = re.compile(
    r"^[‎‏]*"
    r"\[?"
    r"(?P<date>\d{1,4}[-/.]\s?\d{1,4}[-/.]\s?\d{1,4})"
    r"[,.]?\s"
    r"\D*?"
    r"(?P<time>\d{1,2}[.:]\d{1,2}(?:[.:]\d{1,2})?)"
    r"\s?(?P<ampm>[ap]\.?\s?m\.?)?"
    r"\]?"
    r"(?:\s-|:)?"
    r"\s",
    re.IGNORECASE,
)

# Author split. Non-greedy to the FIRST ": ", so a colon later in the body is safe.
_AUTHOR_SPLIT = re.compile(r"^(?P<author>.+?):\s(?P<body>.*)$", re.DOTALL)

# Attachment placeholders, both dialects (R4-whatsapp-dyi.md:258-259).
#
# B2-ADV D5 -- THESE PATTERNS USED TO EAT ORDINARY PROSE. The previous forms were
#   <[^<>]*:\s*[^<>]+>              and   \b[\w-]+\.\w{2,5}\s*[(<][^)>]*[)>]
# The first swallowed any bracketed "<word: words>" -- including a bare URL written as
# <https://example.com/articol>. The second swallowed ANY dotted token followed by a
# parenthetical, which in Romanian chat prose means PRICES and TIMES:
#   "costa 3.50 (cu tot cu tva)"        -> "costa"          (proven by execution)
#   "am zis 12.30 (ora) ne vedem"       -> "am zis ne vedem"
#   "pe emag.ro (magazinul lor)"        -> "pe"
# Text vanished mid-sentence, silently, and had_attachment was set True on a message with
# no attachment. Both now require POSITIVE evidence of an attachment:
#   * a real media/document extension from a closed list, AND
#   * a parenthetical that actually contains an attachment marker word;
#   * the iOS "<attached: NAME.ext>" form additionally forbids "/" in the filename, which
#     is what keeps a URL in angle brackets from matching.
# A stray "(file attached)" surviving into the corpus costs one token; deleting a clause
# of the owner's own writing is unrecoverable, so the bias is deliberately asymmetric.
_MEDIA_EXT = (
    r"(?:jpe?g|png|gif|webp|heic|mp4|3gp|mov|mkv|webm|mp3|m4a|opus|ogg|aac|wav"
    r"|amr|pdf|docx?|xlsx?|pptx?|zip|rar|7z|txt|csv|vcf|apk)"
)
_ATTACH_MARK = (
    r"(?:attached|attachment|omitted|file|document|ata[sșş]at|omis|fi[sșş]ier)"
)

_ATTACH_PATTERNS = (
    # iOS: <attached: 00000031-PHOTO-....jpg>. No "/" in the name => URLs cannot match.
    re.compile(r"<\s*[^<>:/]{0,25}:\s*[^<>/]{1,160}\.\w{2,5}\s*>"),
    # Android: IMG-2025.jpg (file attached) -- known extension AND a marker word.
    re.compile(
        rf"\b[\w][\w -]{{0,80}}\.{_MEDIA_EXT}\s*[(<][^)>]{{0,30}}{_ATTACH_MARK}"
        rf"[^)>]{{0,20}}[)>]",
        re.IGNORECASE,
    ),
    re.compile(r"<[^<>]{0,40}omitted>", re.IGNORECASE),  # <Media omitted>
    re.compile(
        r"^\s*(?:image|video|audio|sticker|GIF|document|Contact card|"
        r"imagine|videoclip|autocolant)\s+omitted\s*$",
        re.IGNORECASE,
    ),
)

# Advisory only -- the STRUCTURAL rule (no "Sender: " group) is what actually carries the
# load. Present so localized system lines that DO contain a colon are still caught.
# Romanian variants included because an English-only list matches nothing on a Romanian
# account, which is exactly the failure R3 documented for Meta's localized `title`.
_SYSTEM_HINTS = (
    "end-to-end encrypted",
    "criptate integral",
    "criptate de la un capăt la altul",
    "this message was deleted",
    "you deleted this message",
    "acest mesaj a fost șters",
    "ai șters acest mesaj",
    "missed voice call",
    "missed video call",
    "apel vocal pierdut",
    "apel video pierdut",
    "changed the subject",
    "changed this group's icon",
    "changed their phone number",
    "a schimbat subiectul",
    "și-a schimbat numărul de telefon",
    "joined using this group's invite link",
    "s-a alăturat",
    "created group",
    "a creat grupul",
    "security code changed",
    "codul de securitate",
    "messages and calls are end-to-end",
    "waiting for this message",
)

#: B2-ADV D4 -- THIS LIST USED TO DELETE THE OWNER'S OWN WRITING, SILENTLY.
#: It previously contained the bare words "added", "left" and "a plecat", matched as
#: UNANCHORED, UNBOUNDED substrings against a body of ANY length. Proven by execution:
#:   "I left the meeting early yesterday because ..."  (205 chars) -> is_system True
#:   "Am adaugat si partea a doua, plus I added ..."   (168 chars) -> is_system True
#:   "leftover pizza" / "a padded cell" / "cand a plecat el" -> is_system True
#: main() then discards every is_system message, so a long, entirely genuine English or
#: Romanian message containing the word "left" or "added" never reached the corpus and
#: nothing in the output said so. Three defences now apply:
#:   1. the three ambiguous words are GONE -- WhatsApp's membership events ("X added Y",
#:      "X left") carry NO "Sender: " group, so the STRUCTURAL rule already catches them;
#:      the fixture at tests/fixtures/whatsapp/_chat.txt:10 is exactly that shape and is
#:      dropped structurally, not by any phrase;
#:   2. matching is word-bounded, so "leftover"/"padded" can no longer trip it;
#:   3. the list only applies to SHORT bodies -- every real WhatsApp system string is
#:      short, while this corpus exists for long ones (MIN_CHARS = 150).
#: Residual over-reach is now COUNTED and PRINTED per run (see main), because an advisory
#: heuristic that discards writing must be auditable rather than silent.
_SYSTEM_HINT_MAX_CHARS = 120

_SYSTEM_HINT_RE = re.compile(
    "|".join(r"\b" + re.escape(h) + r"\b" for h in _SYSTEM_HINTS), re.IGNORECASE
)


def _looks_system(body: str) -> bool:
    """Advisory phrase check for AUTHORED system lines. Structural detection leads."""
    s = body.strip()
    if len(s) > _SYSTEM_HINT_MAX_CHARS:
        return False
    return _SYSTEM_HINT_RE.search(s) is not None


def strip_attachments(body: str) -> tuple[str, bool]:
    """Remove attachment placeholder tokens, KEEPING any caption prose around them.

    A caption is authored writing; the placeholder is not. iOS emits the placeholder on
    its own line with the caption following as a continuation line, so after multi-line
    assembly both live in one body and only the token must go.
    """
    out, hit = body, False
    for pat in _ATTACH_PATTERNS:
        new = pat.sub(" ", out)
        if new != out:
            hit, out = True, new
    return re.sub(r"[ \t]{2,}", " ", out).strip(), hit


# =============================================================================
# TIMESTAMPS
# =============================================================================


def _split_date(date_str: str) -> list[int]:
    parts = re.split(r"[-/.]", date_str.replace(" ", ""))
    return [int(p) for p in parts if p.isdigit()]


def infer_date_order(date_strings: list[str]) -> tuple[str, str]:
    """Infer component order from evidence. Returns (order, human-readable evidence).

    order is one of 'ymd' | 'dmy' | 'mdy' | 'conflict' | 'ambiguous'. A first component
    > 12 PROVES day-first (no month exceeds 12) and vice-versa. When neither ever exceeds
    12 the file is genuinely undecidable and we say so rather than implying certainty.
    """
    iso = first_gt12 = second_gt12 = 0
    for dstr in date_strings:
        p = _split_date(dstr)
        if len(p) != 3:
            continue
        if p[0] > 31:
            iso += 1
            continue
        first_gt12 += p[0] > 12
        second_gt12 += p[1] > 12
    if iso and not (first_gt12 or second_gt12):
        return "ymd", f"{iso} 4-digit-year-first dates"
    if first_gt12 and second_gt12:
        return (
            "conflict",
            f"{first_gt12} dates prove day-first AND {second_gt12} prove month-first",
        )
    if first_gt12:
        return "dmy", f"{first_gt12} dates have component 1 > 12"
    if second_gt12:
        return "mdy", f"{second_gt12} dates have component 2 > 12"
    return "ambiguous", "no date component ever exceeds 12"


def build_datetime(
    date_str: str, time_str: str, ampm: str | None, order: str
) -> dt.datetime | None:
    """Assemble a datetime, or None. Returning None never discards the message text."""
    p = _split_date(date_str)
    t = [int(x) for x in re.split(r"[.:]", time_str) if x.isdigit()]
    if len(p) != 3 or len(t) < 2:
        return None
    if p[0] > 31 or order == "ymd":
        year, month, day = p
    elif order == "mdy":
        month, day, year = p
    else:  # dmy, plus 'ambiguous'/'conflict' fallback
        day, month, year = p
    if year < 100:  # WhatsApp launched 2009, so 2000+yy is safe
        year += 2000
    hour, minute = t[0], t[1]
    second = t[2] if len(t) > 2 else 0
    if ampm:
        marker = ampm.replace(".", "").replace(" ", "").lower()
        hour = hour % 12 + (12 if marker.startswith("p") else 0)
    try:
        return dt.datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


# =============================================================================
# PARSING
# =============================================================================


def _read_lines(path: str) -> tuple[str, list[str], int]:
    """Yield (chat_name, lines, replacement_char_count) for a .txt or an export ZIP.

    Decode errors are REPLACED but COUNTED, so a bad decode surfaces as a number instead
    of silently mangling the corpus.
    """
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            members = [n for n in zf.namelist() if n.lower().endswith(".txt")]
            if not members:
                return "", [], 0
            member = next(
                (m for m in members if m.lower().endswith("_chat.txt")), members[0]
            )
            raw = zf.read(member).decode("utf-8-sig", errors="replace")
        chat = os.path.splitext(os.path.basename(path))[0]
    else:
        with io.open(path, encoding="utf-8-sig", errors="replace") as fh:
            raw = fh.read()
        chat = os.path.splitext(os.path.basename(path))[0]
    return chat, raw.splitlines(), raw.count("�")


def parse_chat_file(path: str) -> tuple[list[WaMessage], dict]:
    """Parse one export into messages, preserving multi-line bodies. Two passes.

    Pass 1 collects every date token so the order can be inferred from the WHOLE file
    before any timestamp is committed; pass 2 assembles messages.
    """
    chat, lines, bad_chars = _read_lines(path)
    heads: list[tuple[re.Match, str]] = []
    for line in lines:
        clean = strip_invisible(line)
        m = _LINE_START.match(clean)
        heads.append((m, clean[m.end() :] if m else clean))

    order, evidence = infer_date_order([m.group("date") for m, _ in heads if m])

    msgs: list[WaMessage] = []
    preamble = 0
    for m, rest in heads:
        if m is None:  # continuation -- append, never drop
            if msgs:
                msgs[-1].body += "\n" + rest
            elif rest.strip():
                # B2-ADV D6: a non-blank line BEFORE the first message start has no message
                # to attach to and was silently discarded ("never drop" held for every line
                # but the first). Real exports open with the encryption notice so this is
                # rare, but a silent drop is exactly what this module refuses to do
                # elsewhere, so it is now counted and surfaced by main().
                preamble += 1
            continue
        split = _AUTHOR_SPLIT.match(rest)
        author, body = (
            (split.group("author").strip(), split.group("body"))
            if split
            else (None, rest)
        )
        msgs.append(
            WaMessage(
                ts_raw=f"{m.group('date')} {m.group('time')}{' ' + m.group('ampm') if m.group('ampm') else ''}",
                when=build_datetime(
                    m.group("date"), m.group("time"), m.group("ampm"), order
                ),
                author=author,
                body=body,
                chat=chat,
                is_system=author is None or _looks_system(body),
            )
        )

    for msg in msgs:  # attachments, post-assembly
        msg.body, msg.had_attachment = strip_attachments(msg.body)

    stats = {
        "chat": chat,
        "path": path,
        "lines": len(lines),
        "messages": len(msgs),
        "date_order": order,
        "date_evidence": evidence,
        "bad_chars": bad_chars,
        "preamble_lines": preamble,
        "mojibake_hits": sum(looks_mojibaked(x.body) for x in msgs),
    }
    return msgs, stats


# =============================================================================
# OWNER RESOLUTION -- four strategies, in order; refuses rather than guesses
# =============================================================================


def resolve_owner_label(
    msgs: list[WaMessage], chat: str, override: str | None
) -> tuple[str | None, str]:
    """Return (owner_label, provenance). owner_label None == unresolved, skip the file."""
    senders = Counter(m.author for m in msgs if m.author and not m.is_system)
    if not senders:
        return None, "no non-system senders found"

    if override:  # 1. explicit
        for name in senders:
            if match_key(name) == match_key(override):
                return name, f"--owner-name override matched {name!r}"
        return None, f"--owner-name {override!r} matches none of {sorted(senders)}"

    ident = {match_key(x) for x in OWNER_IDENTITY} | {
        match_key(x) for x in OWNER_SELF_LABELS
    }
    phones = {
        digits_only(x)[-PHONE_MATCH_DIGITS:] for x in OWNER_IDENTITY if digits_only(x)
    }
    for name in senders:  # 2. identity set
        key, tail = match_key(name), digits_only(name)[-PHONE_MATCH_DIGITS:]
        if key in ident or (len(tail) == PHONE_MATCH_DIGITS and tail in phones):
            return name, f"matched OWNER_IDENTITY via {name!r}"

    # 3. structural inference for a 1:1 chat. WhatsApp names the export after the OTHER
    # party ("WhatsApp Chat with Maria"), so in a two-sender file the owner is whichever
    # sender the filename does NOT name -- true regardless of what label the exporting
    # device used, which is what makes it robust to "whatever the other party saved me as".
    if len(senders) == 2:
        hint = match_key(
            re.sub(r"(?i)^whatsapp\s*chat\s*(with|-|–|—)?\s*", "", chat)
        ).strip()
        if hint:
            others = [
                n for n in senders if match_key(n) in hint or hint in match_key(n)
            ]
            if len(others) == 1:
                owner = next(n for n in senders if n != others[0])
                return owner, (
                    f"1:1 structural inference -- filename names {others[0]!r}, "
                    f"so the other sender {owner!r} is the owner"
                )

    return None, (
        "ambiguous -- candidate senders: "
        + ", ".join(f"{n!r} ({c} msgs)" for n, c in senders.most_common())
    )


# =============================================================================
# BURST MERGE (R8) -- optional, default ON for WhatsApp
# =============================================================================


def mark_interruptions(msgs: list[WaMessage], owner_label: str) -> None:
    """Flag each owner message with whether the preceding chat message was someone else's.

    Must run BEFORE the owner filter: after filtering, another party's interjection is
    invisible and bursts would be merged across it, which R8's rule forbids.
    """
    prev_was_owner = False
    for m in msgs:
        m.interrupted = not prev_was_owner
        prev_was_owner = m.author == owner_label and not m.is_system


def merge_bursts(msgs: list[WaMessage], gap_seconds: int) -> list[WaMessage]:
    """Merge same-chat, uninterrupted owner runs inside `gap_seconds`.

    R8: WhatsApp is burst-heavy, so a 400-word argument typed as eight messages scores
    ZERO records under a per-message character threshold. The burst, not the message, is
    the authorial unit.

    B2-E2E D2: `msgs` is sorted globally across ALL chats, so the previous record in `out`
    is often from a different chat. Comparing against `out[-1]` therefore lost a legitimate
    same-chat merge whenever any other chat's message sorted between the two -- i.e. it
    degraded toward a no-op exactly on real multi-chat exports. Track the last emitted
    record PER CHAT instead. (Verified: chat A alone merged 2->1; A plus an interleaving
    chat B merged 3->3 before this change, 3->2 after.)
    """
    out: list[WaMessage] = []
    tail: dict[str, WaMessage] = {}  # last emitted record, keyed by chat
    for m in msgs:
        prev = tail.get(m.chat)
        if (
            prev
            and not m.interrupted
            and prev.when
            and m.when
            and 0 <= (m.when - prev.when).total_seconds() <= gap_seconds
        ):
            prev.body = f"{prev.body}\n{m.body}"
            prev.n_merged += 1
            prev.had_attachment |= m.had_attachment
        else:
            fresh = dataclasses.replace(m)
            out.append(fresh)
            tail[m.chat] = fresh
    return out


# =============================================================================
# CORPUS SHAPING
# =============================================================================

_URL = re.compile(r"https?://\S+|www\.\S+")


def prose_words(body: str) -> int:
    """Word count after stripping URLs and quote lines -- R8's 'prose words' metric."""
    text = _URL.sub(" ", body)
    text = "\n".join(ln for ln in text.split("\n") if not ln.lstrip().startswith(">"))
    return len(text.split())


def tier_of(words: int) -> str:
    return next(t for floor, t in WORD_TIERS if words >= floor)


# =============================================================================
# RAIL (a) -- DYI ARCHIVE: degrade loudly, but stay falsifiable
# =============================================================================

_DYI_BODY_KEYS = ("content", "message", "text", "body", "caption")


def _probe_member_for_bodies(data: bytes) -> int:
    """Count message-body-shaped keys in a JSON member. Keeps R4's finding testable."""
    try:
        obj = json.loads(data.decode("utf-8", errors="replace"))
    except Exception:
        return 0
    hits, stack = 0, [obj]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            hits += sum(
                1
                for k, v in node.items()
                if k.lower() in _DYI_BODY_KEYS and isinstance(v, str) and v.strip()
            )
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return hits


def _collect_members(
    src, label: str = "", depth: int = 0
) -> list[tuple[str, int, bytes | None]]:
    """Return [(label, size, json_bytes|None)] for a zip / directory / file.

    DESCENDS INTO NESTED ZIPS. A DYI download is routinely a folder containing a zip (or a
    zip of zips), and a shallow walk would list the archive itself as a single "member" --
    which makes the body-probe below read zero because it never opened anything. That is a
    broken detector reporting an absence, so the descent is load-bearing, not a nicety.
    """
    out: list[tuple[str, int, bytes | None]] = []
    if depth > 3:
        return out
    if isinstance(src, str) and os.path.isdir(src):
        for p in sorted(glob.glob(os.path.join(src, "**", "*"), recursive=True)):
            if os.path.isfile(p):
                out.extend(_collect_members(p, os.path.relpath(p, src), depth + 1))
        return out

    name = label or (os.path.basename(src) if isinstance(src, str) else "archive")
    if hasattr(src, "seek"):
        src.seek(0)
    if zipfile.is_zipfile(src):
        if hasattr(src, "seek"):
            src.seek(0)
        with zipfile.ZipFile(src) as zf:
            for info in zf.infolist():
                if info.filename.endswith("/"):
                    continue
                sub = f"{name}::{info.filename}"
                low = info.filename.lower()
                if low.endswith(".zip"):
                    out.extend(
                        _collect_members(
                            io.BytesIO(zf.read(info.filename)), sub, depth + 1
                        )
                    )
                elif low.endswith(".json") and info.file_size <= PROBE_BYTE_CAP:
                    out.append((sub, info.file_size, zf.read(info.filename)))
                else:
                    out.append((sub, info.file_size, None))
        return out

    if isinstance(src, str):
        size = os.path.getsize(src)
        data = None
        if src.lower().endswith(".json") and size <= PROBE_BYTE_CAP:
            with open(src, "rb") as fh:
                data = fh.read()
        out.append((name, size, data))
    return out


def handle_dyi(path: str) -> int:
    """Inventory a DYI archive, probe it for bodies, explain, exit 2.

    Members are DISCOVERED BY WALKING, never hardcoded: no primary source names them and
    the two-file AccountInfo.{html,json} layout is only likely (55-80%)
    (R4-whatsapp-dyi.md:113-124).
    """
    print("\n  RAIL (a): this looks like a Meta DYI / WhatsApp account-info archive.")
    print(
        "  A DYI export contains NO message bodies -- WhatsApp Help Center, verbatim:"
    )
    print('    "Account information reports don\'t include your personal messages"')
    print("    https://faq.whatsapp.com/526463418847093/")
    print(
        "  E2EE means Meta never holds the plaintext, so no server-side export can carry"
    )
    print(
        "  it (https://faq.whatsapp.com/849367647393371/). This is a structural limit,"
    )
    print("  not a configuration mistake, and it CORRECTS GROUNDING.md:37-39.\n")

    members = _collect_members(path)
    body_hits = sum(_probe_member_for_bodies(data) for _, _, data in members if data)
    probed = sum(1 for _, _, data in members if data)

    print(f"  Archive inventory ({len(members)} members):")
    for lbl, size, _ in members[:40]:
        print(f"    {lbl} ({size:,} B)")
    if len(members) > 40:
        print(f"    ... and {len(members) - 40} more")

    print(
        f"\n  Body-shaped-field probe: {body_hits} hit(s) across {probed} JSON member(s)."
    )
    if not probed:
        print(
            "  !! NO JSON MEMBER WAS READ, so this probe proves NOTHING about message"
        )
        print(
            "     bodies. Do not read it as confirmation -- inspect the members by hand."
        )
    elif body_hits:
        print(
            "  !! NON-ZERO. That CONTRADICTS R4's finding and would mean Meta changed the"
        )
        print(
            "     payload. Do not dismiss it -- inspect the members above by hand before"
        )
        print("     trusting either conclusion.")
    else:
        print(
            "  Zero, as R4 predicts. Detector positive control: run --self-test, which"
        )
        print(
            "  proves this same probe DOES find bodies in a known-present fixture -- so"
        )
        print("  this zero is a real absence, not a broken detector.")

    print("\n  What to do instead (R4 §4): export chats from the PHONE --")
    print("    open a chat -> More options -> More -> Export chat -> Without media")
    print("  Drop the resulting .txt/.zip files into:")
    print(f"    {WHATSAPP_DIR}")
    print("  then re-run this script. It auto-detects them.")
    print(
        "\n  This archive still has value for group names / contacts / settings, just not"
    )
    print("  for the writing corpus. Zero corpus words come from here.")
    return 2


def looks_like_dyi(path: str) -> bool:
    """True for an account-info archive. Positive signal required, never assumed."""
    markers = (
        "accountinfo",
        "account_info",
        "personal_information",
        "your_information",
        "connections",
        "preferences",
    )
    try:
        if zipfile.is_zipfile(path):
            names = [n.lower() for n in zipfile.ZipFile(path).namelist()]
            if any(n.endswith("_chat.txt") for n in names):
                return False  # an in-app export ZIP, not DYI
            return any(mk in n for n in names for mk in markers)
        if os.path.isdir(path):
            names = [p.lower() for p in os.listdir(path)]
            return any(mk in n for n in names for mk in markers)
    except Exception:
        return False
    return False


# =============================================================================
# INPUT DISCOVERY
# =============================================================================


def collect_inputs(roots: list[str]) -> tuple[list[str], list[str]]:
    """Return (chat_txt_like_paths, dyi_paths)."""
    chats, dyis = [], []
    for root in roots:
        if os.path.isfile(root):
            candidates = [root]
        elif os.path.isdir(root):
            if looks_like_dyi(root):
                dyis.append(root)
                continue
            candidates = sorted(
                p
                for ext in ("txt", "zip")
                for p in glob.glob(os.path.join(root, "**", f"*.{ext}"), recursive=True)
            )
        else:
            continue
        for p in candidates:
            if os.path.basename(p).startswith(OUT_PREFIX):
                continue  # never re-ingest our own output
            (dyis if looks_like_dyi(p) else chats).append(p)
    return chats, dyis


# =============================================================================
# OUTPUT -- the same three files as isolate_discord.py:43-53
# =============================================================================


def emit(records: list[dict], outdir: str, min_chars: int) -> dict:
    os.makedirs(outdir, exist_ok=True)
    paths = {
        k: os.path.join(outdir, f"{OUT_PREFIX}{sfx}")
        for k, sfx in (
            ("all", "_all.txt"),
            ("sub", "_substantial.txt"),
            ("jsonl", ".jsonl"),
        )
    }
    lines = [f"[{r['ts']}] {r['content']}" for r in records]
    subst = [f"[{r['ts']}] {r['content']}" for r in records if r["len"] >= min_chars]

    with open(paths["all"], "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    with open(paths["sub"], "w", encoding="utf-8") as f:
        f.write("\n\n".join(subst))
    with open(paths["jsonl"], "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return paths


def build_records(
    msgs: list[WaMessage], *, normalize: bool, repair: bool
) -> tuple[list[dict], int]:
    records, folded = [], 0
    for m in msgs:
        body = m.body.strip()
        if repair:
            body = repair_mojibake(body)
        if normalize:
            new = normalize_text(body)
            folded += sum(1 for a, b in zip(body, new) if a != b)
            body = new
        if not body:
            continue  # attachment-only / empty: not writing
        words = prose_words(body)
        records.append(
            {
                "ts": m.iso,
                "len": len(body),
                "content": body,
                "words": words,
                "tier": tier_of(words),
                "chat": m.chat,
                "n_messages": m.n_merged,
                "had_attachment": m.had_attachment,
                "ts_raw": m.ts_raw,
            }
        )
    return records, folded


# =============================================================================
# SELF-TEST -- synthetic fixtures built from the CITED format specs
# =============================================================================

_FIXTURE_1TO1 = (
    "‎[15/01/2025, 10:32:00] Messages and calls are end-to-end encrypted.\n"
    "[15/01/2025, 10:32:05] Maria Ionescu: salut\n"
    "[15/01/2025, 10:33:00] Andrei ❤: Bună Maria, m-am tot gândit la ce ai zis ieri\n"
    "si cred ca ai dreptate in mare parte, dar sunt cateva lucruri care nu se leaga.\n"
    "In primul rand, argumentul cu timpul nu tine cont de faptul ca noi am inceput\n"
    "proiectul mult mai devreme decat au facut-o ei.\n"
    "[15/01/2025, 10:33:30] Andrei ❤: Si inca ceva important pe care voiam sa il adaug\n"
    "aici, pentru ca mi se pare esential pentru discutia noastra de maine dimineata.\n"
    "[15/01/2025, 10:40:00] Maria Ionescu: ok\n"
    "[15/01/2025, 10:41:00] Andrei ❤: ‎<attached: 00000042-PHOTO-2025-01-15.jpg>\n"
    "uite poza despre care vorbeam, e din vara trecuta cand am fost la munte impreuna\n"
    "cu toata gasca si a fost probabil cea mai buna vacanta din ultimii cinci ani.\n"
    "[15/01/2025, 10:42:00] Andrei ❤: <Media omitted>\n"
    "[15/01/2025, 10:43:00] Andrei ❤: This message was deleted\n"
)

_FIXTURE_ANDROID_AMPM = (
    "25/12/2024, 9:05 PM - Owner Name: mesaj scurt\n"
    "25/12/2024, 9:06 PM - Owner Name: al doilea\n"
)

_FIXTURE_GROUP = (
    "[03/02/2025, 08:00:00] Ana: buna\n"
    "[03/02/2025, 08:01:00] Bogdan: salut\n"
    "[03/02/2025, 08:02:00] Cristina: hey\n"
)


def _write(path: str, text: str) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def self_test() -> int:
    """Exercise every documented trap. Returns 0 on pass, 1 on failure."""
    import tempfile

    fails: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(
            f"    [{'PASS' if ok else 'FAIL'}] {name}{'  -- ' + detail if detail else ''}"
        )
        if not ok:
            fails.append(name)

    print(
        "\n  SELF-TEST -- fixtures are TEST VECTORS derived from the cited format specs"
    )
    print(
        "  (R4-whatsapp-dyi.md:220-228, R5-whatsapp-alt-rails.md:282-295), not real data.\n"
    )

    with tempfile.TemporaryDirectory() as td:
        p1 = _write(
            os.path.join(td, "WhatsApp Chat with Maria Ionescu.txt"), _FIXTURE_1TO1
        )
        msgs, stats = parse_chat_file(p1)

        check(
            "bidi-prefixed first line parses (U+200E)",
            stats["messages"] == 8,
            f"got {stats['messages']} messages",
        )
        check(
            "date order inferred as dmy from evidence",
            stats["date_order"] == "dmy",
            stats["date_evidence"],
        )

        long_msg = next((m for m in msgs if "m-am tot" in m.body), None)
        check(
            "multi-line body assembled, not shredded",
            long_msg is not None and long_msg.body.count("\n") == 3,
            f"newlines={long_msg.body.count(chr(10)) if long_msg else 'n/a'}",
        )

        cap = next((m for m in msgs if "uite poza" in m.body), None)
        check(
            "attachment token stripped, caption kept",
            cap is not None and "attached:" not in cap.body and cap.had_attachment,
        )
        media = next((m for m in msgs if m.ts_raw.startswith("15/01/2025 10:42")), None)
        check(
            "<Media omitted> reduces to empty body",
            media is not None and not media.body.strip(),
        )

        enc = msgs[0]
        check(
            "author-less encryption notice flagged system",
            enc.is_system and enc.author is None,
        )
        deleted = next((m for m in msgs if "deleted" in m.body.lower()), None)
        check(
            "'This message was deleted' flagged system",
            deleted is not None and deleted.is_system,
        )

        owner, prov = resolve_owner_label(
            msgs, "WhatsApp Chat with Maria Ionescu", None
        )
        check(
            "owner found by 1:1 structural inference despite unknown label",
            owner == "Andrei ❤",
            prov,
        )

        mark_interruptions(msgs, owner)
        mine = [m for m in msgs if m.author == owner and not m.is_system]
        merged = merge_bursts(mine, BURST_GAP_SECONDS)
        check(
            "burst merge joins the 10:33:00 + 10:33:30 run",
            any(m.n_merged == 2 for m in merged),
            f"{len(mine)} owner msgs -> {len(merged)} bursts",
        )
        check(
            "burst merge does NOT cross Maria's 10:40 interjection",
            all(m.n_merged <= 2 for m in merged),
        )

        p2 = _write(os.path.join(td, "WhatsApp Chat with X.txt"), _FIXTURE_ANDROID_AMPM)
        m2, s2 = parse_chat_file(p2)
        check(
            "Android dash + 12h + narrow-NBSP parses",
            len(m2) == 2 and m2[0].when is not None,
            f"when={m2[0].when}",
        )
        check("PM converted to 21:00", m2[0].when and m2[0].when.hour == 21)
        o2, _ = resolve_owner_label(m2, "WhatsApp Chat with X", None)
        check("owner found via OWNER_IDENTITY name", o2 == "Owner Name")

        p3 = _write(os.path.join(td, "Grup proiect.txt"), _FIXTURE_GROUP)
        m3, _ = parse_chat_file(p3)
        o3, prov3 = resolve_owner_label(m3, "Grup proiect", None)
        check("ambiguous group REFUSES rather than guessing", o3 is None, prov3)

        # ISO + month-first evidence
        m4, s4 = parse_chat_file(
            _write(os.path.join(td, "iso.txt"), "[2025-01-15, 10:32:00 AM] A: hi\n")
        )
        check(
            "ISO yyyy-mm-dd detected",
            s4["date_order"] == "ymd" and m4[0].when.year == 2025,
        )
        _, s5 = parse_chat_file(
            _write(os.path.join(td, "us.txt"), "[01/25/2025, 10:32:00] A: hi\n")
        )
        check(
            "month-first proven when component 2 > 12",
            s5["date_order"] == "mdy",
            s5["date_evidence"],
        )

        # Encoding: detector positive control BEFORE trusting any zero
        check(
            "mojibake detector positive control fires on known-mojibaked input",
            looks_mojibaked("bunÄ ziua"),
        )
        check(
            "detector reports ZERO on clean UTF-8 Romanian",
            not looks_mojibaked("bună ziua, ce mai faci? și țara"),
        )
        check(
            "clean Romanian survives a --repair-mojibake pass unchanged",
            repair_mojibake("bună și ț ❤️") == "bună și ț ❤️",
        )

        # Diacritics
        check(
            "cedilla folds to comma (NFC alone does not)",
            normalize_text("şi ţara") == "și țara"
            and unicodedata.normalize("NFC", "ş") != "ș",
        )
        check(
            "missing diacritics are NOT fabricated",
            normalize_text("si tara") == "si tara",
        )

        # NBSP handling: mapped to a space, not deleted (deleting would glue words)
        check(
            "NBSP becomes a space, not a deletion",
            strip_invisible("două cuvinte") == "două cuvinte",
        )

        # DYI probe -- positive control, then the real-shaped negative
        zp = os.path.join(td, "AccountInfo.zip")
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr(
                "account_info.json", json.dumps({"groups": ["a"], "sent_count": 12})
            )
        with zipfile.ZipFile(zp) as zf:
            neg = _probe_member_for_bodies(zf.read("account_info.json"))
        pos = _probe_member_for_bodies(
            json.dumps({"messages": [{"content": "hello there"}]}).encode()
        )
        check(
            "DYI body-probe positive control finds a known body",
            pos == 1,
            f"hits={pos}",
        )
        check(
            "DYI body-probe reports zero on an account-info shape",
            neg == 0,
            f"hits={neg}",
        )
        check("DYI archive detected as DYI, not as a chat export", looks_like_dyi(zp))

        # REGRESSION: a directory holding a zip must be descended into, not listed as one
        # opaque member -- otherwise the body-probe reads zero without opening anything,
        # i.e. a broken detector reporting a false absence.
        nest = os.path.join(td, "dyi_dir")
        os.makedirs(nest, exist_ok=True)
        with zipfile.ZipFile(os.path.join(nest, "AccountInfo.zip"), "w") as zf:
            zf.writestr("AccountInfo.json", json.dumps({"groups": ["a"]}))
            zf.writestr("AccountInfo.html", "<html></html>")
        mem = _collect_members(nest)
        check(
            "DYI walk descends into a zip inside a directory",
            len(mem) == 2 and any(m[2] is not None for m in mem),
            f"{len(mem)} members, {sum(1 for m in mem if m[2] is not None)} readable JSON",
        )
        deep = os.path.join(td, "outer.zip")  # zip-of-zip, the DYI norm
        with zipfile.ZipFile(deep, "w") as zf:
            zf.write(os.path.join(nest, "AccountInfo.zip"), "AccountInfo.zip")
        check(
            "DYI walk descends into a nested zip-of-zip",
            any(m[2] is not None for m in _collect_members(deep)),
        )

        # Never re-ingest our own outputs
        _write(os.path.join(td, f"{OUT_PREFIX}_all.txt"), "[x] y\n")
        chats, _ = collect_inputs([td])
        check(
            "own output files excluded from inputs",
            not any(os.path.basename(c).startswith(OUT_PREFIX) for c in chats),
            f"{len(chats)} inputs",
        )

    print(f"\n  {'ALL PASS' if not fails else 'FAILURES: ' + ', '.join(fails)}")
    return 1 if fails else 0


# =============================================================================
# MAIN
# =============================================================================


def _force_utf8_console() -> None:
    """Make stdout/stderr able to carry Romanian. MUST run before the first print().

    On Windows, Python encodes console output with the ANSI code page (cp1252 here) unless
    PYTHONIOENCODING/PYTHONUTF8 says otherwise. cp1252 cannot represent `ș` U+0219 or
    `Ș` U+0218, so a single print of a chat name -- and WhatsApp names every export after
    the contact, "WhatsApp Chat with Ștefan Mureșan" -- raised UnicodeEncodeError at the
    summary line and killed the run BEFORE emit() wrote anything. Verified by execution:
    identical input exits 0 under PYTHONIOENCODING=utf-8 and dies at line ~958 without it.
    Romanian diacritics are load-bearing for this corpus (GROUNDING.md:24), so the console
    must not be allowed to decide whether the script runs.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:
            try:  # last resort: never crash on output
                stream.reconfigure(errors="replace")  # type: ignore[union-attr]
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    ap = argparse.ArgumentParser(
        description="Isolate the owner's own WhatsApp messages into a writing corpus."
    )
    ap.add_argument(
        "inputs",
        nargs="*",
        default=None,
        help=f"chat .txt/.zip files or directories (default: {WHATSAPP_DIR})",
    )
    ap.add_argument("--outdir", default=WHATSAPP_DIR)
    ap.add_argument(
        "--owner-name",
        default=None,
        help="exact sender label for the owner; overrides all inference",
    )
    ap.add_argument("--min-chars", type=int, default=MIN_CHARS)
    # B2-E2E D3: the shared oracle's chosen_default for `threshold-chars-vs-words` is
    # "R3 -- char length >= 150 on the repaired NFC text", i.e. the PER-MESSAGE unit that
    # isolate_discord.py:16,40 actually ran. R8's burst unit is the documented ALTERNATE.
    # Shipping the alternate as the default made a single-file run glue a 5-char filler
    # onto a 356-char piece of writing and promote a pinned MIN_CHARS drop into the corpus.
    # Default is now the oracle's choice; the burst unit is opt-in.
    ap.add_argument(
        "--burst-merge",
        action="store_true",
        help="threshold per BURST instead of per message (R8 alternate); "
        f"merges same-author runs under {BURST_GAP_SECONDS}s. Default is "
        "the R3 per-message unit. NOTE: this deliberately DIVERGES from "
        "tests/fixtures/EXPECTED.json, whose records are per-message -- a "
        "sub-threshold message merged into a long one is promoted into the "
        "corpus. Recovers genuine multi-message writing; costs exactness.",
    )
    ap.add_argument(
        "--no-burst-merge",
        action="store_true",
        help="explicit form of the default (per-message, Discord-identical); "
        "always wins over --burst-merge",
    )
    ap.add_argument(
        "--no-normalize",
        action="store_true",
        help="skip NFC + Romanian cedilla->comma fold",
    )
    ap.add_argument(
        "--repair-mojibake",
        action="store_true",
        help="OPT-IN. Only if the reported mojibake hit-rate is non-trivial; on "
        "clean client-side UTF-8 this transform CORRUPTS text (R4 §6).",
    )
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    min_chars = args.min_chars
    roots = args.inputs or [WHATSAPP_DIR]
    chats, dyis = collect_inputs(roots)

    if not chats and not dyis:
        print(f"  No input found under: {', '.join(roots)}")
        print("  Expected in-app 'Export chat' .txt or .zip files. See --help.")
        return 1
    if not chats and dyis:
        return handle_dyi(dyis[0])
    for d in dyis:
        print(
            f"  NOTE: ignoring DYI archive {d!r} -- it carries no message bodies (R4)."
        )

    kept: list[WaMessage] = []
    hint_dropped: list[WaMessage] = []
    skipped: list[tuple[str, str]] = []
    total_seen = mojibake_hits = bad_chars = 0

    for path in chats:
        msgs, stats = parse_chat_file(path)
        if not msgs:
            skipped.append((path, "no parseable messages"))
            continue
        owner, prov = resolve_owner_label(msgs, stats["chat"], args.owner_name)
        print(
            f"  {stats['chat']}: {stats['messages']} msgs, dates={stats['date_order']} "
            f"({stats['date_evidence']})"
        )
        if stats["date_order"] in ("ambiguous", "conflict"):
            print(
                f"    ! date order undecidable -- assuming "
                f"{'day' if DEFAULT_DAY_FIRST else 'month'}-first. Text is unaffected; "
                f"only timestamps and burst grouping could be wrong."
            )
        if owner is None:
            print(f"    ! SKIPPED, owner unresolved: {prov}")
            print("      re-run with --owner-name '<label>' to include this chat")
            skipped.append((path, prov))
            continue
        print(f"    owner = {owner!r} ({prov})")
        # B2-ADV D9: strategy 3 (1:1 structural inference) assumes the file was exported
        # from the OWNER'S OWN phone, so WhatsApp named it after the OTHER party and the
        # owner is "the sender the filename does not name". If instead the file came from the
        # OTHER participant's phone, the filename names the OWNER, and this rule silently
        # picks the OTHER party -- harvesting THEIR prose as the owner's writing, the exact
        # poisoning this module claims to refuse (docstring: "admitting someone else's prose
        # is far worse than missing some of mine"). The pick cannot be verified from a
        # _chat.txt alone, so it is surfaced LOUDLY instead of trusted silently.
        if "structural inference" in prov:
            print(
                "    ! owner chosen by an UNVERIFIED heuristic, not an identity match. It"
            )
            print(
                "      is correct ONLY if this export came from the OWNER'S phone. If it"
            )
            print(
                f"      came from {sorted({m.author for m in msgs if m.author and not m.is_system} - {owner})!r}'s"
            )
            print(
                f"      phone, {owner!r} is the WRONG person and their text will poison the"
            )
            print("      corpus. Confirm with --owner-name '<label>' if unsure.")
        if stats["preamble_lines"]:
            print(
                f"    ! {stats['preamble_lines']} line(s) before the first message start "
                f"could not be attached to any message and were not ingested"
            )
        total_seen += stats["messages"]
        mojibake_hits += stats["mojibake_hits"]
        bad_chars += stats["bad_chars"]
        mark_interruptions(msgs, owner)
        # An owner-AUTHORED message flagged system came from the ADVISORY phrase list, not
        # the structural rule (structural system lines have author None). That list is a
        # heuristic that DISCARDS the owner's writing, so every one of its decisions is
        # surfaced for inspection instead of being applied silently (B2-ADV D4).
        by_hint = [m for m in msgs if m.author == owner and m.is_system]
        if by_hint:
            hint_dropped.extend(by_hint)
            print(
                f"    ! {len(by_hint)} owner message(s) dropped by the advisory system-phrase "
                f"list -- verify these are really WhatsApp system lines:"
            )
            for m in by_hint[:3]:
                print(f"        [{m.iso}] {m.body.strip()[:70]!r}")
        kept.extend(m for m in msgs if m.author == owner and not m.is_system)

    if not kept:
        print(
            "\n  No owner messages isolated. Nothing written (existing outputs untouched)."
        )
        return 3

    kept.sort(key=lambda m: (m.when or dt.datetime.max, m.chat))
    seen, deduped = set(), []
    for m in kept:  # (chat, ts, body) dedup -- no message IDs
        # B2-ADV D8: the key MUST include the chat. Without it, the owner sending the SAME
        # text at the SAME wall-clock time in two DIFFERENT conversations (e.g. the same
        # greeting copy-pasted to two people in one minute) collapsed to one record and a
        # genuinely distinct message was silently dropped -- proven by execution (2 chats,
        # identical owner body+ts_raw -> 1 record). This also matches the chat-scoped keep
        # lookup that e2e/assert_b2_independent.py already relies on. A true cross-device
        # duplicate (iOS+Android of ONE message) is NOT collapsed here anyway, because the
        # two dialects write ts_raw at different precision (seconds vs minute).
        key = (m.chat, m.ts_raw, hashlib.sha1(m.body.encode("utf-8")).hexdigest())
        if key not in seen:
            seen.add(key)
            deduped.append(m)
    dropped_dupes = len(kept) - len(deduped)

    flat, _ = build_records(
        deduped, normalize=not args.no_normalize, repair=args.repair_mojibake
    )
    flat_subst = [r for r in flat if r["len"] >= min_chars]
    unmerged_subst, unmerged_words = (
        len(flat_subst),
        sum(r["words"] for r in flat_subst),
    )

    burst_on = (
        args.burst_merge and not args.no_burst_merge
    )  # explicit --no- always wins
    final = merge_bursts(deduped, BURST_GAP_SECONDS) if burst_on else deduped
    records, folded = build_records(
        final, normalize=not args.no_normalize, repair=args.repair_mojibake
    )

    # B2-ADV D7: build_records drops every body that is empty after attachment stripping,
    # so a chat whose owner side is all media yields ZERO records -- and emit() would then
    # TRUNCATE an existing, good corpus to three empty files. The `if not kept` guard above
    # does not cover this: kept is non-empty, records is not. Refuse instead.
    if not records:
        print(
            f"\n  {len(deduped)} owner message(s) found, but every one reduced to empty text "
            f"(attachment-only / whitespace)."
        )
        print(
            "  Nothing written -- existing outputs in the output directory are untouched."
        )
        return 3

    paths = emit(records, args.outdir, min_chars)

    subst = [r for r in records if r["len"] >= min_chars]
    words = sum(r["words"] for r in subst)
    print(
        f"\n  chats parsed:            {len(chats) - len(skipped)} "
        f"({len(skipped)} skipped)"
    )
    print(f"  messages scanned:        {total_seen}")
    print(
        f"  owner messages:          {len(deduped)}"
        f"{f' ({dropped_dupes} duplicates dropped)' if dropped_dupes else ''}"
    )
    if burst_on:
        print(
            f"  after burst merge:       {len(final)} bursts (gap <= {BURST_GAP_SECONDS}s)"
        )
    print(f"  with text content:       {len(records)}")
    print(
        f"  substantial (>={min_chars}):    {len(subst)}  (~{words:,} words of writing)"
    )
    if burst_on:
        # Report WORDS, not just records. Record count understates the effect: merging two
        # sub-threshold fragments into one substantial record leaves the count flat while
        # recovering writing a per-message threshold would have discarded outright.
        print(
            f"    burst merge effect:    {unmerged_subst} -> {len(subst)} records, "
            f"{unmerged_words:,} -> {words:,} words ({words - unmerged_words:+,} recovered); "
            f"re-run without --burst-merge to compare"
        )
    print(
        f"  mojibake detector hits:  {mojibake_hits}"
        f"{'  (expected 0 on client-side UTF-8 -- R4 §6)' if not mojibake_hits else '  ! INVESTIGATE'}"
    )
    print(f"  cedilla/NFC chars folded:{folded}")
    if bad_chars:
        print(
            f"  ! {bad_chars} undecodable byte(s) replaced -- check the source encoding"
        )
    for k in ("all", "sub", "jsonl"):
        print(f"  -> {paths[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
