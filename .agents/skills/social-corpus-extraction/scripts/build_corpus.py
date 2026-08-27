#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_corpus.py — unify the per-source owner-only JSONL files into ONE corpus (R8 design).

Reads whatever per-source `.jsonl` files exist (Discord / Facebook / Messenger / WhatsApp),
normalises them to one Dolma-shaped record schema, merges consecutive messages into BURSTS,
strips text the owner did not write, grades every record into tiers A/B/C/D, deduplicates,
applies a privacy pass, and emits:

    corpus/corpus.jsonl     canonical, one record per burst, every record graded  (source of truth)
    corpus/corpus.md        human reading view, chronological, tier A by default
    corpus/MANIFEST.md      per-source counts, word counts, date ranges, DROP ACCOUNTING
    corpus/pseudonyms.map.json   salted mention->pseudonym map, LOCAL ONLY, never ship

Runs with ONLY SOME sources present (today only Discord exists). A missing/broken source
degrades to a per-source status line in the manifest; it never aborts the run.


PII DEFAULT: --pii-tier L0  (secrets-only redaction). WHY:
    R8 §9.1 argues the GDPR Art. 2(2)(c) + Recital 18 "purely personal or household activity"
    exemption very likely (80-90%) covers a private, local corpus of one's own correspondence,
    and R8 §9.4 argues the dominant failure mode here is symmetric OVER-redaction, which
    produces a legally tidy corpus with the personality removed. So the default redacts only
    the class where the utility/privacy trade-off has no interior optimum: secrets (API keys,
    tokens, JWTs, card PANs, IBANs, CNPs, private keys) — "zero style value and unbounded
    downside" (R8 §9.2). Everything else is opt-in and escalates with --pii-tier:
        L0 (default) secrets only                        -> canonical, this machine only
        L1           + third-party emails/phones/handles  -> local training only
        L2           + context[] dropped                  -> uploading to a provider
        L3           + owner's own identifiers            -> publication (reconsider entirely)
    L2/L3 REFUSE TO RUN without --unsafe-no-ner, because PERSON-name detection is NOT
    implemented here (it needs NER; Presidio ships no Romania pack — R8 §9.3) and a tier
    that silently fails to remove third-party names is worse than no tier at all.

MEMORY: holds all normalised records in RAM. Measured: 104,842 Discord records ~= 30 MB
resident. Reading is streamed line-by-line, so a large file is never json.load()ed whole
(GROUNDING trap #4). --max-records guards against an unexpectedly huge input.

Stdlib only. Python 3.9+. Windows-safe.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import secrets
import sys
import unicodedata
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone

# Windows consoles default to cp1252 and will crash on Romanian diacritics / emoji.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VERSION = "1.0.0"
ROOT = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# CONSTANTS — every one of these is a corpus-defining decision. R8 §7 requires
# them to be recorded in the datasheet; write_manifest() prints them verbatim.
# ---------------------------------------------------------------------------

# R8 §2: merge same-author messages into a burst when the gap is <= this.
# 420 s = Discord's own ~7 min same-author grouping window.
# MEASURED on the real control (104,842 owner messages, single DM channel):
#   gap<=60s 82.5% | gap<=420s 91.1% | gap<=900s 92.9% of consecutive pairs; median gap 14 s.
#   97.3% of messages land in a burst of >=2 at 420 s. R8's own falsification bar was
#   "<10% => §2 is wrong"; it is not wrong. Burst-merge is the dominant fact about this corpus.
BURST_GAP_SECONDS = 420

# R8 §3.3 tiers, on PROSE words (code fences, URLs, mention tokens and quotes removed first).
TIER_A_MIN_WORDS = 100  # "essay" — MTLD stabilises around 100 tokens
TIER_B_MIN_WORDS = (
    25  # "substantial" — ~= the legacy 150-char cut, so A+B is comparable to it
)
TIER_C_MIN_WORDS = 5  # "conversational"; below this is tier D "fragment"

# R8 §4.2: near-dup via MinHash/LSH over word-5-gram shingles, confirmed by exact Jaccard.
NEAR_DUP_JACCARD = 0.80
SHINGLE_SIZE = 5
MINHASH_PERMS = 128
MINHASH_BANDS = 16  # 16 bands x 8 rows -> LSH knee ~0.71, then exact-Jaccard confirm
MINHASH_MIN_WORDS = (
    50  # below this, word-5-grams are too few -> fall back to char-5-grams
)

# R8 §4.3: same normalised text sent >= this many times across >=2 venues == template/pasta.
SELF_PASTA_MIN_REPEATS = 3

MAX_CONTEXT_CHARS = (
    600  # cap on any carried context[] turn (R8 §9.1: capped and droppable)
)

# The mojibake defect is a property of META'S SERVER-SIDE DYI EMITTER, not of text in
# general, so the repair is scoped to the sources that actually have it. R4 and R5 both
# warn explicitly that applying it to WhatsApp's client-written UTF-8 would CREATE
# corruption rather than fix it; the same holds for DiscordChatExporter's clean UTF-8.
# MEASURED: running it unscoped over the Discord control corrupted 1 record (see
# _plausible_repair). Override with --mojibake-sources.
MOJIBAKE_SOURCES = {"facebook", "messenger"}

# Owner identity (GROUNDING "THE OWNER"). Exempt from redaction below L3 (R8 §9.4:
# he is the data subject AND the label).
OWNER_IDENTIFIERS = {
    "owner",
    "owner name",
    "<owner_ig_handle>",
    "<OWNER_DISCORD_ID>",
    "<OWNER_PHONE_INTL>",
    "<OWNER_PHONE_LOCAL>",
}

# ---------------------------------------------------------------------------
# DROP REASONS — the anti-silent-filter taxonomy. Every discarded record is
# counted under exactly one of these, and conservation is asserted per stage.
# NOTE length is NOT here: R8 proposal #3 (almost certain, 90-99%) says GRADE,
# never delete. A short record becomes tier D; it is still emitted.
# ---------------------------------------------------------------------------
DROP_REASONS = OrderedDict(
    [
        ("unparseable_json_line", "line was not valid JSON"),
        ("no_text_field", "record had no recognisable text field"),
        (
            "empty_after_clean",
            "text was empty once quotes/forwards/markup were removed",
        ),
        ("not_owner_authored", "record carried an explicit is_owner/from_me = false"),
        ("forward_only", "a forward/reshare carrying no commentary of the owner's own"),
        ("exact_duplicate", "identical to an earlier record after normalisation"),
        (
            "near_duplicate",
            "MinHash/Jaccard >= %.2f against an earlier record" % NEAR_DUP_JACCARD,
        ),
        (
            "cross_author_copypasta",
            "text also appears from a non-owner author in the reference corpus",
        ),
        (
            "below_min_tier",
            "tier below --drop-below-tier (OFF by default; grade, don't delete)",
        ),
    ]
)

# ---------------------------------------------------------------------------
# 1. TEXT REPAIR — mojibake, then Unicode normalisation
# ---------------------------------------------------------------------------

# A UTF-8 multi-byte sequence that has been decoded as Latin-1 leaves a lead byte in
# C2-F4 followed by continuation bytes in 80-BF, which land in these Unicode ranges.
_MOJIBAKE_RUN = re.compile("[Â-ô][-¿]{1,3}")


def looks_mojibaked(s):
    """True if s contains a run shaped like UTF-8 bytes mis-decoded as Latin-1.

    DETECT-THEN-REPAIR is the whole point (GROUNDING:50-51 asks for a fix that leaves an
    already-correct string unchanged and never raises). A blind
    s.encode('latin-1').decode('utf-8') silently CORRUPTS already-correct Latin-1-range
    text and raises on anything above U+00FF, so it cannot be used unguarded (R2, R7).
    """
    return bool(_MOJIBAKE_RUN.search(s))


def _plausible_repair(repaired):
    """Reject a 'repair' that introduces a script this author does not write.

    MEASURED FALSE POSITIVE, real control data, Discord/owner.jsonl line 13201: the
    owner typed a row of Alt-code symbols `«»¥×¥×'‘¾½¼€¤³²¡`. The pair `×¥` (U+00D7 U+00A5)
    is shaped exactly like the UTF-8 bytes D7 A5, so an unguarded repair rewrote it to the
    Hebrew letter `ץ` — silent corruption of genuine text, the exact hazard R7 flagged as
    undecidable in general. It is not undecidable in PRACTICE: a Romanian/English author's
    mojibake always repairs into Latin, punctuation or emoji, never into Hebrew or CJK.
    """
    for ch in repaired:
        o = ord(ch)
        if (
            o < 0x0250  # ASCII, Latin-1, Latin Extended-A/B
            or 0x0300 <= o <= 0x036F  # combining marks
            or 0x2000 <= o <= 0x206F  # general punctuation
            or 0x20A0 <= o <= 0x20CF  # currency
            or 0x2190 <= o <= 0x2BFF  # arrows, math, symbols, dingbats
            or 0x1F000 <= o <= 0x1FAFF  # emoji / pictographs
            or o in (0x200D, 0xFE0F)
        ):  # ZWJ, VS16 (emoji sequences)
            continue
        return False
    return True


def _repair_once(s):
    """Repair each mojibake-shaped RUN independently, leaving everything else byte-identical.

    Per-run (rather than whole-string) is required: on a MIXED string the whole-string
    latin-1 encode aborts on the first genuinely-correct character above U+00FF, so a
    defensive try/except returns the string UNREPAIRED with no error at all — the silent
    failure R2 measured ('bunÄ\\x83 ✓' stays corrupt).
    """

    def sub(m):
        try:
            out = m.group(0).encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return m.group(0)
        return out if _plausible_repair(out) else m.group(0)

    return _MOJIBAKE_RUN.sub(sub, s)


def fix_mojibake(s, max_passes=3):
    """Idempotent, never raises. Fixpoint loop: Meta emits DOUBLE-encoded text too (R7)."""
    if not s:
        return s
    for _ in range(max_passes):
        if not looks_mojibaked(s):
            break
        repaired = _repair_once(s)
        if repaired == s:
            break
        s = repaired
    return s


# R8 §0.1B: s-cedilla/t-cedilla are DISTINCT codepoints from s-comma/t-comma and Unicode
# normalisation will NOT merge them. Measured in the real control: 1 cedilla vs 85 comma
# forms, so the impact here is negligible — but the map costs nothing and is correct.
_CEDILLA_TO_COMMA = {0x15F: 0x219, 0x163: 0x21B, 0x15E: 0x218, 0x162: 0x21A}


def normalise_text(s):
    """NFC, then cedilla->comma. Deliberately does NOT restore missing diacritics.

    R8 §0.1C: diacritic-less Romanian is authentic authorial behaviour and a register
    signal. Measured: 307 diacritics in 2,601,899 letters (0.012%) in the control — the
    owner types Romanian almost entirely without them. Restoring would fabricate text.
    """
    return unicodedata.normalize("NFC", s).translate(_CEDILLA_TO_COMMA)


# ---------------------------------------------------------------------------
# 2. EXTRACTION — pull non-prose out of text, leave a typed placeholder (R8 §6)
# ---------------------------------------------------------------------------

RE_CODE_FENCE = re.compile(r"```(\w*)\n?(.*?)```", re.S)
RE_URL = re.compile(r"https?://[^\s<>\"')\]]+")
RE_MENTION_USER = re.compile(r"<@!?(\d+)>")
RE_MENTION_ROLE = re.compile(r"<@&(\d+)>")
RE_MENTION_CHAN = re.compile(r"<#(\d+)>")
RE_CUSTOM_EMOJI = re.compile(r"<(a?):(\w+):(\d+)>")
RE_DISCORD_TS = re.compile(r"<t:(\d+)(?::[tTdDfFR])?>")
RE_QUOTE_LINE = re.compile(r"^\s*>{1,3}\s?(.*)$")
RE_ATTRIB = re.compile(
    r"^\s*(On .{4,60}\bwrote:|.{1,40} (a scris|said|wrote):)\s*$", re.I
)

# A pasted chat transcript: "3:24 AM - Owner™: text" / "[12:04] Someone: text".
# MEASURED in the control: whole conversations pasted back into chat, carrying BOTH the
# owner's lines and other people's. Without this, a paste of someone else's dialogue reads
# as the owner's own long-form prose. High precision by construction — the speaker prefix is
# an explicit structural marker, not a register guess.
RE_TRANSCRIPT = re.compile(
    r"^\s*(?:\[\s*)?(\d{1,2}:\d{2}(?::\d{2})?)\s*(AM|PM)?\s*\]?\s*[-–—:]\s*([^:]{1,40}?):\s(.*)$",
    re.I,
)
TRANSCRIPT_MIN_LINES = 3
MEDIA_EXT = {
    ".jpg": "IMG",
    ".jpeg": "IMG",
    ".png": "IMG",
    ".gif": "IMG",
    ".webp": "IMG",
    ".mp4": "VID",
    ".mov": "VID",
    ".webm": "VID",
    ".mp3": "AUDIO",
    ".ogg": "AUDIO",
    ".wav": "AUDIO",
    ".opus": "AUDIO",
}


def strip_quotes(text):
    """Remove quoted spans -> (text, quotes).

    R8 §5: whitelist what he wrote; route every removed span to extracted.quotes[] with its
    detector name so the decision is auditable and reversible.

    A pasted transcript is handled as a block: only when >= TRANSCRIPT_MIN_LINES lines carry
    a speaker prefix is it treated as a transcript at all (one stray "12:30 - note:" line is
    not). Within such a block the OWNER's own lines are KEPT (prefix stripped) and everyone
    else's are routed to quotes[] — dropping the whole block would discard his half of a
    conversation he chose to preserve.
    """
    lines = text.split("\n")
    tmatches = [RE_TRANSCRIPT.match(x) for x in lines]
    is_transcript = sum(1 for m in tmatches if m) >= TRANSCRIPT_MIN_LINES

    kept, quotes = [], []
    for line, tm in zip(lines, tmatches):
        qm = RE_QUOTE_LINE.match(line)
        if qm:
            quotes.append({"detector": "markdown_blockquote", "text": qm.group(1)})
        elif RE_ATTRIB.match(line):
            quotes.append({"detector": "email_attribution", "text": line.strip()})
        elif is_transcript and tm:
            speaker, said = tm.group(3).strip(), tm.group(4)
            if _is_owner_token(speaker):
                kept.append(said)
            else:
                quotes.append(
                    {"detector": "pasted_transcript", "speaker": speaker, "text": said}
                )
        else:
            kept.append(line)
    return "\n".join(kept), quotes


def extract_elements(text):
    """Replace non-prose elements with typed placeholders; return (text, extracted)."""
    ex = {"code_blocks": [], "links": [], "quotes": [], "mentions": [], "media": []}

    def _code(m):
        lang, body = m.group(1) or "txt", m.group(2)
        ex["code_blocks"].append({"lang": lang, "text": body})
        return " [CODE:%s:%dL] " % (lang, body.count("\n") + 1)

    def _url(m):
        raw = m.group(0)
        base = raw.split("?", 1)[0]  # R8 §6: query string stripped (tracking + tokens)
        host = base.split("/")[2] if "://" in base else base
        host = host[4:] if host.startswith("www.") else host
        ext = os.path.splitext(base)[1].lower()
        ex["links"].append({"domain": host, "url_nq": base})
        if ext in MEDIA_EXT:
            ex["media"].append({"kind": MEDIA_EXT[ext], "domain": host})
            return " [%s] " % MEDIA_EXT[ext]
        return " [URL:%s] " % host

    def _mention(kind, fmt):
        def f(m):
            ex["mentions"].append({"kind": kind, "id": m.group(1)})
            return fmt % m.group(1)

        return f

    def _ts(m):
        try:
            return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
        except (ValueError, OverflowError, OSError):
            return "[DATE]"

    text = RE_CODE_FENCE.sub(_code, text)
    text = RE_URL.sub(_url, text)
    text = RE_CUSTOM_EMOJI.sub(
        lambda m: ":%s:" % m.group(2), text
    )  # name is style, id is noise
    text = RE_DISCORD_TS.sub(_ts, text)
    text = RE_MENTION_USER.sub(_mention("user", "[@%s]"), text)
    text = RE_MENTION_ROLE.sub(_mention("role", "[@&%s]"), text)
    text = RE_MENTION_CHAN.sub(_mention("channel", "[#%s]"), text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip(), ex


def prose_words(text):
    """Word count on prose only — placeholders and non-alphanumeric tokens do not count.

    R8 §3.2: measuring before extraction rewards exactly the records with the least style
    in them (a pasted stack trace is long in characters and zero in authorial voice).
    """
    stripped = re.sub(r"\[(CODE|URL|IMG|VID|AUDIO|DATE|@|#)[^\]]*\]", " ", text)
    return sum(1 for w in stripped.split() if any(c.isalnum() for c in w))


def count_emoji(text):
    return sum(
        1 for c in text if 0x1F300 <= ord(c) <= 0x1FAFF or 0x2600 <= ord(c) <= 0x27BF
    )


def diacritics_profile(text):
    comma = sum(text.count(c) for c in "șțȘȚ")
    cedilla = sum(text.count(c) for c in "şţŞŢ")
    other = sum(text.count(c) for c in "ăâîĂÂÎ")
    letters = sum(1 for c in text if c.isalpha()) or 1
    form = "absent"
    if comma and cedilla:
        form = "mixed"
    elif comma:
        form = "comma"
    elif cedilla:
        form = "cedilla"
    elif other:
        form = "comma"  # ă/â/î carry no cedilla/comma ambiguity
    return round((comma + cedilla + other) / letters, 5), form


def mtld(text, factor=0.72):
    """Measure of Textual Lexical Diversity, bidirectional (McCarthy & Jarvis)."""
    words = [w.lower() for w in re.findall(r"\w+", text, re.UNICODE)]
    if len(words) < 10:
        return None

    def run(seq):
        factors, types, n = 0.0, set(), 0
        for w in seq:
            types.add(w)
            n += 1
            if len(types) / n <= factor:
                factors += 1
                types, n = set(), 0
        if n:
            factors += (1 - len(types) / n) / (1 - factor)
        return len(seq) / factors if factors else len(seq)

    return round((run(words) + run(words[::-1])) / 2, 1)


# ---------------------------------------------------------------------------
# 3. PRIVACY — secrets always; everything else opt-in by tier (R8 §9)
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("aws_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}")),
    (
        "jwt",
        re.compile(
            r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"
        ),
    ),
    (
        "discord_token",
        re.compile(
            r"\b[MNO][A-Za-z0-9_\-]{23,}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}"
        ),
    ),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer", re.compile(r"\b[Bb]earer\s+[A-Za-z0-9._\-]{20,}")),
    (
        "url_secret",
        re.compile(
            r"[?&](?:token|api_key|apikey|password|passwd|secret|auth)=[^\s&]+", re.I
        ),
    ),
    ("ro_iban", re.compile(r"\bRO\d{2}[A-Z]{4}[A-Z0-9]{16}\b")),
]
RE_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
RE_CNP = re.compile(r"\b[1-8]\d{12}\b")
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]{2,}\b")
RE_PHONE_RO = re.compile(r"(?:\+?4?0)\s?7\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b")
_CNP_KEY = "279146358279"


def _luhn_ok(digits):
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


def _cnp_ok(s):
    """Romanian CNP check digit. R8 §9.3: Presidio ships NO Romania pack, so this is ours."""
    if len(s) != 13:
        return False
    total = sum(int(s[i]) * int(_CNP_KEY[i]) for i in range(12))
    c = total % 11
    return int(s[12]) == (1 if c == 10 else c)


def _is_owner_token(tok):
    t = re.sub(r"[\s.\-]", "", tok).lower()
    return any(re.sub(r"[\s.\-]", "", o).lower() in t for o in OWNER_IDENTIFIERS)


def redact(text, tier):
    """Apply the privacy tier. Returns (text, redactions[]). Secrets go at EVERY tier."""
    reds = []

    def note(kind, span, repl):
        reds.append({"type": kind, "span": span, "replacement": repl})
        return repl

    for name, pat in SECRET_PATTERNS:
        text = pat.sub(
            lambda m, n=name: note(n, len(m.group(0)), "[SECRET:%s]" % n), text
        )
    text = RE_CARD.sub(
        lambda m: (
            note("card_pan", len(m.group(0)), "[SECRET:card_pan]")
            if _luhn_ok(re.sub(r"[ -]", "", m.group(0)))
            else m.group(0)
        ),
        text,
    )
    text = RE_CNP.sub(
        lambda m: (
            note("ro_cnp", len(m.group(0)), "[SECRET:ro_cnp]")
            if _cnp_ok(m.group(0))
            else m.group(0)
        ),
        text,
    )

    if tier in ("L1", "L2", "L3"):
        text = RE_EMAIL.sub(
            lambda m: (
                m.group(0)
                if _is_owner_token(m.group(0))
                else note("email", len(m.group(0)), "[EMAIL]")
            ),
            text,
        )
        text = RE_PHONE_RO.sub(
            lambda m: (
                m.group(0)
                if _is_owner_token(m.group(0))
                else note("phone", len(m.group(0)), "[PHONE]")
            ),
            text,
        )

    if tier == "L3":
        for ident in sorted(OWNER_IDENTIFIERS, key=len, reverse=True):
            if len(ident) > 4:
                text = re.sub(
                    re.escape(ident),
                    lambda m: note("owner_identifier", len(m.group(0)), "[OWNER]"),
                    text,
                    flags=re.I,
                )
    return text, reds


class PseudonymMap:
    """Salted, stable mention->pseudonym map. LOCAL ONLY — never ship (R8 §9.4)."""

    def __init__(self, path):
        self.path, self.map = path, {}
        self.salt = secrets.token_hex(16)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    blob = json.load(f)
                self.salt, self.map = blob.get("salt", self.salt), blob.get("map", {})
            except (OSError, ValueError, json.JSONDecodeError):
                pass

    def get(self, raw_id):
        if raw_id not in self.map:
            h = hashlib.sha256((self.salt + raw_id).encode()).hexdigest()
            self.map[raw_id] = "P%02d" % (int(h[:8], 16) % 100)
        return self.map[raw_id]

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "salt": self.salt,
                    "map": self.map,
                    "WARNING": "LOCAL ONLY — shipping this file re-links the corpus.",
                },
                f,
                ensure_ascii=False,
                indent=1,
            )


# ---------------------------------------------------------------------------
# 4. SOURCE DISCOVERY + TOLERANT READING
# ---------------------------------------------------------------------------

# The sibling isolators (B1/B2/B3) are authored concurrently with this unit, so their exact
# field names are NOT yet fixed. The only schema guaranteed today is the Discord reference's
# {ts, len, content} (isolate_discord.py:39). Reading by ALIAS rather than by a pinned name
# is therefore deliberate: an unexpected-but-reasonable field name degrades to a manifest
# line, not to a silent zero-record run.
FIELD_ALIASES = {
    "text": ["content", "text", "message", "body", "msg", "post"],
    "ts": [
        "ts",
        "timestamp",
        "created",
        "created_at",
        "date",
        "datetime",
        "time",
        "sent_at",
    ],
    "venue": [
        "venue",
        "channel",
        "channel_id",
        "thread",
        "thread_id",
        "conversation",
        "chat",
        "container",
        "container_id",
        "group",
    ],
    "kind": ["kind", "type", "message_type", "post_type"],
    "owner": ["is_owner", "from_me", "owner_authored", "by_owner"],
    "fwd": ["is_forward", "contains_forward", "forwarded", "is_share", "is_reshare"],
    "reply": ["reply_to_id", "reply_to", "in_reply_to", "referenced_message_id"],
    "brk": ["interrupted_before", "burst_break"],
    # An upstream burst count means the source ALREADY merged. Two sibling emitters do:
    # isolate_messenger.py:519 emits `msgs_in_burst`, isolate_whatsapp.py:803 emits
    # `n_messages`. See PRE_BURSTED handling in burst_merge() for why this matters.
    "nmsg": ["msgs_in_burst", "n_messages", "n_merged", "n_msgs"],
    # A source may carry the UTC offset ALONGSIDE a naive `ts` rather than inside it.
    # isolate_discord.py:63 does exactly that (`tz_offset`), keeping `ts` byte-identical
    # so pinned line numbers and .txt outputs do not move. Without reading this the
    # offset would arrive and be silently discarded here -- and it is load-bearing: the
    # real control export carries BOTH +02:00 and +03:00 (Romania observes DST), so a
    # naive merge mis-orders the corpus by up to 3 h against UTC-rendering sources.
    "tzoff": ["tz_offset", "utc_offset", "tz", "timezone", "offset"],
}

_TZ_RE = re.compile(r"^([+-])(\d{2}):?(\d{2})$")


def parse_offset(raw):
    """'+02:00' | '+0200' | 'Z' -> a timezone, else None. Never raises."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s in ("Z", "z", "UTC", "utc"):
        return timezone.utc
    m = _TZ_RE.match(s)
    if not m:
        return None
    sign, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
    if hh > 23 or mm > 59:
        return None
    delta = timedelta(hours=hh, minutes=mm)
    return timezone(-delta if sign == "-" else delta)


SOURCE_BY_DIR = {
    "discord": "discord",
    "facebook": "facebook",
    "messenger": "messenger",
    "whatsapp": "whatsapp",
    "wa": "whatsapp",
    "fb": "facebook",
}


def pick(rec, key):
    for alias in FIELD_ALIASES[key]:
        if alias in rec and rec[alias] not in (None, ""):
            return rec[alias]
    return None


def infer_source(path):
    parent = os.path.basename(os.path.dirname(os.path.abspath(path))).lower()
    if parent in SOURCE_BY_DIR:
        return SOURCE_BY_DIR[parent]
    stem = os.path.basename(path).lower()
    for key, val in SOURCE_BY_DIR.items():
        if key in stem or key in parent:
            return val
    return parent or "unknown"


# Auto-discovery must never sweep in test scaffolding. A sibling unit's E2E run wrote
# e2e/out_b1/andrei_visalon.jsonl, which auto-discovery picked up as a source named
# "out_b1" and merged into the real corpus — synthetic fixture text silently contaminating
# the owner's writing. Excluded by directory, not by filename, because the filename was
# indistinguishable from a genuine output.
EXCLUDED_DIR_PARTS = {
    "e2e",
    "tests",
    "test",
    "fixtures",
    "fixture",
    "__pycache__",
    ".git",
    "node_modules",
    "sample",
    "samples",
    "scratch",
    "tmp",
}


def discover_sources(root, out_dir, explicit):
    """Find per-source .jsonl files. Explicit --source name=path always wins."""
    found = []
    for spec in explicit:
        name, _, path = spec.partition("=")
        found.append((name or infer_source(path), os.path.abspath(path)))
    if found:
        return found
    out_abs = os.path.abspath(out_dir)
    for path in sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)):
        ap = os.path.abspath(path)
        base = os.path.basename(ap).lower()
        rel_parts = {p.lower() for p in os.path.relpath(ap, root).split(os.sep)[:-1]}
        if (
            ap.startswith(out_abs)
            or base == "corpus.jsonl"
            or "_others" in base
            or base.endswith(".others.jsonl")
            or rel_parts & EXCLUDED_DIR_PARTS
        ):
            continue
        found.append((infer_source(ap), ap))
    return found


def parse_ts(raw):
    """-> (datetime|None, is_aware, literal). NEVER invents a timezone.

    The Discord reference truncates the offset (isolate_discord.py:36 slices [:19]), so its
    timestamps arrive NAIVE. R8 §7.2 wants an offset; the information is simply gone from
    the .jsonl and cannot be recovered here. We record `tz: naive` and count it in the
    manifest rather than fabricating UTC.
    """
    if raw is None:
        return None, False, ""
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc), True, str(raw)
        except (ValueError, OverflowError, OSError):
            return None, False, str(raw)
    s = str(raw).strip().replace("Z", "+00:00")
    for cand in (s, s[:19], s[:10]):
        try:
            dt = datetime.fromisoformat(cand)
            return dt, dt.tzinfo is not None, str(raw)
        except ValueError:
            continue
    return None, False, str(raw)


def sort_key(rec):
    """Orderable epoch. Naive timestamps are ordered AS IF UTC — ordering only, never stored."""
    dt = rec["_dt"]
    if dt is None:
        return float("inf")
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).timestamp()


def read_source(path, source, ledger, pseudo, max_records, fix_moji=True, refs=None):
    """Stream one .jsonl -> normalised message dicts. Never json.load()s the file whole.

    Returns (messages, fields_seen, consumed) where `consumed` counts only non-blank lines
    that reached a keep/drop decision — so `consumed == kept + dropped` holds exactly and
    the conservation check cannot be fooled by blank lines or by --max-records truncation.
    """
    out, fields_seen, consumed = [], Counter(), 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            if max_records and len(out) >= max_records:
                break
            consumed += 1
            try:
                rec = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                ledger.drop(source, "unparseable_json_line", 0)
                continue
            if not isinstance(rec, dict):
                ledger.drop(source, "unparseable_json_line", 0)
                continue
            fields_seen.update(rec.keys())
            msg = normalise_record(
                rec, source, path, lineno, ledger, pseudo, fix_moji, refs
            )
            if msg:
                out.append(msg)
    return out, fields_seen, consumed


def normalise_record(
    rec, source, path, lineno, ledger, pseudo, fix_moji=True, refs=None
):
    """One raw source record -> one normalised message, or None (counted in the ledger).

    Cross-author copypasta is checked HERE, per message, deliberately BEFORE burst-merge.
    Checking it after the merge is wrong and was observed to be wrong: burst-merge welded a
    pasted vendor announcement onto the owner's genuine surrounding messages, producing one
    355-word "tier A" record that was half his writing and half someone else's. Post-merge
    the only available choices are to keep the contamination or discard his real words.
    """
    raw_text = pick(rec, "text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        ledger.drop(source, "no_text_field", 0)
        return None

    owner = pick(rec, "owner")
    if owner is False or (
        isinstance(owner, str) and owner.lower() in ("false", "no", "0")
    ):
        ledger.drop(source, "not_owner_authored", len(raw_text.split()))
        return None

    repaired = fix_mojibake(raw_text) if fix_moji else raw_text
    text = normalise_text(repaired)
    moji = repaired != raw_text
    text, quotes = strip_quotes(text)
    text, ex = extract_elements(text)
    ex["quotes"] = quotes

    is_fwd = bool(pick(rec, "fwd"))
    if not text.strip():
        ledger.drop(
            source,
            "forward_only" if is_fwd else "empty_after_clean",
            len(raw_text.split()),
        )
        return None

    if refs and dedup_key(text) in refs:
        ledger.drop(source, "cross_author_copypasta", prose_words(text))
        return None

    for m in ex["mentions"]:
        m["pseudo"] = pseudo.get(m["id"])
        m["id"] = "sha256:" + hashlib.sha256(m["id"].encode()).hexdigest()[:16]
    for m in ex["mentions"]:
        text = text.replace("[@%s]" % m["id"], "[@%s]" % m["pseudo"])

    dt, aware, literal = parse_ts(pick(rec, "ts"))
    # Reattach an offset carried in a SIBLING field (isolate_discord.py:63 `tz_offset`).
    # Only ever ATTACHES to a naive stamp -- it never overrides an offset already inside
    # `ts`, and it never invents one when the field is absent (R8 §7 wants the offset;
    # fabricating UTC would be worse than recording `naive`).
    if dt is not None and not aware:
        tz = parse_offset(pick(rec, "tzoff"))
        if tz is not None:
            dt, aware = dt.replace(tzinfo=tz), True
            literal = "%s%s" % (literal, tz.tzname(None).replace("UTC", "") or "+00:00")
    venue = pick(rec, "venue") or os.path.splitext(os.path.basename(path))[0]

    # PRE-BURSTED SOURCES. If the emitter already merged, its record is burst-FINAL and
    # must not be merged again here. This is not a tidiness point, it is a correctness
    # one: isolate_messenger.py:387-391 flushes a burst when ANOTHER SPEAKER talks, but
    # emits no marker saying so. Re-merging blind at 420 s would weld two of its records
    # back across exactly the interruption it split, silently undoing an
    # interruption-AWARE decision with an interruption-BLIND one. Discord (the only
    # source live today) carries no such field, so nothing changes for it.
    raw_n = pick(rec, "nmsg")
    try:
        n_src = max(1, int(raw_n)) if raw_n is not None else 1
    except (TypeError, ValueError):
        n_src = 1
    return {
        "_dt": dt,
        "_aware": aware,
        "_ts_literal": literal,
        "_source": source,
        "_venue": str(venue),
        "_text": text,
        "_ex": ex,
        "_fwd": is_fwd,
        "_mojibake": moji,
        "_brk": bool(pick(rec, "brk")),
        "_reply": pick(rec, "reply"),
        "_kind": pick(rec, "kind"),
        "_nsrc": n_src,
        "_pre": raw_n is not None,
        "_id": "%s:%s:%d" % (source, os.path.basename(path), lineno),
    }


# ---------------------------------------------------------------------------
# 5. BURST MERGE (R8 §2)
# ---------------------------------------------------------------------------


def burst_merge(messages, gap_seconds, interruption_blind):
    """Merge consecutive same-source same-venue owner messages within gap_seconds."""
    if not messages:
        return []
    messages = sorted(messages, key=lambda r: (r["_source"], r["_venue"], sort_key(r)))
    bursts, cur = [], [messages[0]]
    for prev, msg in zip(messages, messages[1:]):
        same = prev["_source"] == msg["_source"] and prev["_venue"] == msg["_venue"]
        gap = sort_key(msg) - sort_key(prev)
        # A record from a pre-bursted source is burst-final on EITHER side of the pair.
        already_final = msg["_pre"] or prev["_pre"]
        contiguous = (
            same and 0 <= gap <= gap_seconds and not msg["_brk"] and not already_final
        )
        if contiguous:
            cur.append(msg)
        else:
            bursts.append(_fuse(cur, interruption_blind))
            cur = [msg]
    bursts.append(_fuse(cur, interruption_blind))
    return bursts


def _fuse(group, interruption_blind):
    """Collapse a run of messages into one burst record."""
    head = group[0]
    ex = {k: [] for k in ("code_blocks", "links", "quotes", "mentions", "media")}
    for m in group:
        for k in ex:
            ex[k].extend(m["_ex"][k])
    span = max(0.0, sort_key(group[-1]) - sort_key(head)) if head["_dt"] else 0.0
    return {
        "_dt": head["_dt"],
        "_aware": head["_aware"],
        "_ts_literal": head["_ts_literal"],
        "_source": head["_source"],
        "_venue": head["_venue"],
        "_text": "\n".join(m["_text"] for m in group),
        "_ex": ex,
        "_msg_ids": [m["_id"] for m in group],
        "_n": len(group),
        # _n  = source LINES fused here -> the unit the conservation check balances in.
        # _nsrc = ORIGINAL messages those lines stand for, which differs only for a
        # pre-bursted source. Kept separate on purpose: mixing them would make
        # sum(n_messages) exceed the line count and break the conservation invariant.
        "_nsrc": sum(m["_nsrc"] for m in group),
        "_pre": any(m["_pre"] for m in group),
        "_span": None if span == float("inf") else round(span),
        "_fwd": any(m["_fwd"] for m in group),
        "_mojibake": any(m["_mojibake"] for m in group),
        "_reply": head["_reply"],
        "_kind": head["_kind"],
        # A pre-bursted record's boundaries were drawn upstream WITH sight of the other
        # party's turns, so it is not blind. Only bursts this tool drew are blind.
        "_blind": interruption_blind and not any(m["_pre"] for m in group),
    }


# ---------------------------------------------------------------------------
# 6. DEDUP (R8 §4)
# ---------------------------------------------------------------------------


def dedup_key(text):
    """Normalised form for exact dedup: NFC -> cedilla -> casefold -> collapse -> strip punct."""
    t = normalise_text(text).casefold()
    return re.sub(r"\s+", " ", t).strip(" .,!?;:…")


def shingles(text):
    words = re.findall(r"\w+", dedup_key(text), re.UNICODE)
    if len(words) >= MINHASH_MIN_WORDS:
        return {
            " ".join(words[i : i + SHINGLE_SIZE])
            for i in range(len(words) - SHINGLE_SIZE + 1)
        }, "word5"
    flat = "".join(words)
    return {
        flat[i : i + SHINGLE_SIZE] for i in range(max(0, len(flat) - SHINGLE_SIZE + 1))
    }, "char5"


def minhash(shs):
    """Deterministic MinHash — fixed seeds, so two runs always agree."""
    sig = []
    for i in range(MINHASH_PERMS):
        best = None
        for sh in shs:
            h = int(
                hashlib.blake2b(
                    ("%d\x00%s" % (i, sh)).encode(), digest_size=8
                ).hexdigest(),
                16,
            )
            if best is None or h < best:
                best = h
        sig.append(best if best is not None else 0)
    return sig


def jaccard(a, b):
    return len(a & b) / len(a | b) if (a or b) else 0.0


def dedup(bursts, ledger, enable_near):
    """Exact dedup, then MinHash/LSH near-dup confirmed by exact Jaccard. Returns kept list."""
    seen, kept = {}, []
    for b in bursts:
        k = dedup_key(b["_text"])
        if k in seen:
            seen[k]["_dup_count"] += 1
            ledger.drop(
                b["_source"], "exact_duplicate", prose_words(b["_text"]), b["_n"]
            )
            continue
        b["_dup_count"], b["_exact_hash"] = (
            1,
            hashlib.sha256(k.encode()).hexdigest()[:32],
        )
        b["_near_cluster"] = None
        seen[k] = b
        kept.append(b)
    if not enable_near or len(kept) < 2:
        return kept

    rows = MINHASH_PERMS // MINHASH_BANDS
    buckets, sigs, shs = defaultdict(list), {}, {}
    survivors = []
    for b in kept:
        s, mode = shingles(b["_text"])
        if not s:
            survivors.append(b)
            continue
        shs[id(b)], sigs[id(b)] = s, minhash(s)
        hit = None
        for band in range(MINHASH_BANDS):
            key = (band, mode, tuple(sigs[id(b)][band * rows : (band + 1) * rows]))
            for cand in buckets[key]:
                if jaccard(shs[id(cand)], s) >= NEAR_DUP_JACCARD:
                    hit = cand
                    break
            if hit:
                break
        if hit:
            hit["_dup_count"] += 1
            ledger.drop(
                b["_source"], "near_duplicate", prose_words(b["_text"]), b["_n"]
            )
            continue
        for band in range(MINHASH_BANDS):
            buckets[
                (band, mode, tuple(sigs[id(b)][band * rows : (band + 1) * rows]))
            ].append(b)
        b["_near_cluster"] = b["_exact_hash"][:12]
        survivors.append(b)
    return survivors


def load_reference_corpus(paths):
    """Non-owner text used as the cross-author copypasta detector (R8 §4.3).

    Returns None when unavailable, so the manifest can say DETECTOR UNAVAILABLE rather than
    the far more dangerous '0 found'. The per-source .jsonl files are owner-only by
    construction (isolate_discord.py:28), so this needs an explicit --others-jsonl.
    """
    if not paths:
        return None
    keys = set()
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    continue
                txt = pick(rec, "text") if isinstance(rec, dict) else None
                if isinstance(txt, str) and txt.strip():
                    keys.add(dedup_key(txt))
    return keys


# ---------------------------------------------------------------------------
# 7. GRADING + RECORD ASSEMBLY
# ---------------------------------------------------------------------------


def tier_of(words):
    if words >= TIER_A_MIN_WORDS:
        return "A"
    if words >= TIER_B_MIN_WORDS:
        return "B"
    if words >= TIER_C_MIN_WORDS:
        return "C"
    return "D"


def build_record(b, idx, pii_tier, keep_context):
    """Assemble one Dolma-shaped canonical record (R8 §8.1)."""
    text, reds = redact(b["_text"], pii_tier)
    words = prose_words(text)
    tier = tier_of(words)
    ratio, form = diacritics_profile(text)
    created = b["_dt"].isoformat() if b["_dt"] else (b["_ts_literal"] or None)
    return {
        "id": "%s:%s:b%06d"
        % (b["_source"], hashlib.sha256(b["_venue"].encode()).hexdigest()[:8], idx),
        "text": text,
        "source": b["_source"],
        "created": created,
        "added": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "version": VERSION,
        "metadata": {
            "author": {"is_owner": True},
            "unit": {
                "kind": "burst" if max(b["_n"], b["_nsrc"]) > 1 else "message",
                "n_messages": b["_n"],  # source lines fused HERE (accounting unit)
                "n_source_messages": b["_nsrc"],  # original messages they stand for
                "merged_upstream": b["_pre"],
                "span_s": b["_span"],
                "msg_ids": b["_msg_ids"],
                "burst_interruption_blind": b["_blind"],
            },
            "venue": {
                "platform": b["_source"],
                "kind": b["_kind"] or "unknown",
                "container_id_hash": "sha256:"
                + hashlib.sha256(b["_venue"].encode()).hexdigest()[:16],
            },
            "thread": {"reply_to_id": b["_reply"]},
            "time": {
                "tz": "aware" if b["_aware"] else "naive",
                "literal": b["_ts_literal"],
            },
            "lang": {
                "diacritics_ratio": ratio,
                "diacritics_form": form,
                "lid": "not-run",
            },
            "stats": {
                "chars": len(text),
                "words_prose": words,
                "mtld": mtld(text),
                "emoji_count": count_emoji(text),
                "caps_ratio": round(
                    sum(1 for c in text if c.isupper())
                    / max(1, sum(1 for c in text if c.isalpha())),
                    4,
                ),
            },
            "extracted": b["_ex"] if keep_context else {k: [] for k in b["_ex"]},
            "context": [],
            "provenance": {
                "owner_authored": True,
                "contains_forward": b["_fwd"],
                "quote_chars_removed": sum(len(q["text"]) for q in b["_ex"]["quotes"]),
                "mojibake_repaired": b["_mojibake"],
            },
            "dedup": {
                "exact_hash": b["_exact_hash"],
                "minhash_cluster": b["_near_cluster"],
                "dup_count": b["_dup_count"],
            },
            "privacy": {
                "tier": pii_tier,
                "redactions": reds,
                "person_ner": "not-implemented",
            },
            "quality": {"tier": tier},
        },
    }


# ---------------------------------------------------------------------------
# 8. DROP LEDGER — named reasons + conservation invariant
# ---------------------------------------------------------------------------


class DropLedger:
    """Every discarded record is counted under a named reason. A silent filter is how a
    corpus quietly loses half its material, so the counts are asserted, not just printed."""

    def __init__(self):
        self.counts = defaultdict(Counter)  # records dropped
        self.words = defaultdict(Counter)  # prose words lost
        self.msgs = defaultdict(Counter)  # UNDERLYING MESSAGES lost
        self.violations = []

    def drop(self, source, reason, words=0, msgs=1):
        """msgs is the number of ORIGINAL messages the dropped record stands for.

        A dropped burst removes n_messages messages, not one. Conflating the two is exactly
        the accounting error the conservation check exists to catch — and did catch.
        """
        assert reason in DROP_REASONS, "undeclared drop reason: %s" % reason
        self.counts[source][reason] += 1
        self.words[source][reason] += words
        self.msgs[source][reason] += msgs

    def total(self, source=None):
        if source:
            return sum(self.counts[source].values())
        return sum(sum(c.values()) for c in self.counts.values())

    def total_msgs(self):
        return sum(sum(c.values()) for c in self.msgs.values())

    def check(self, label, expect_in, out_n):
        """Assert in == out + dropped, IN MESSAGE UNITS; record any violation loudly."""
        dropped = self.total_msgs()
        if expect_in != out_n + dropped:
            self.violations.append(
                "%s: in=%d out=%d dropped=%d  (unaccounted %+d)"
                % (label, expect_in, out_n, dropped, expect_in - out_n - dropped)
            )
        return not self.violations


# ---------------------------------------------------------------------------
# 9. OUTPUT WRITERS
# ---------------------------------------------------------------------------


def render_readable(text):
    text = re.sub(r"\[URL:([^\]]+)\]", lambda m: "[link: %s]" % m.group(1), text)
    return re.sub(
        r"\[CODE:(\w+):(\d+)L\]",
        lambda m: "[%s code, %s lines]" % (m.group(1), m.group(2)),
        text,
    )


def write_corpus_md(path, records, tiers):
    """Chronological reading view grouped year -> month (R8 §8.4)."""
    sel = [r for r in records if r["metadata"]["quality"]["tier"] in tiers]
    sel.sort(key=lambda r: r["created"] or "")
    lines = [
        "# my_writing — reading view",
        "",
        "Tier(s) %s · %d records · %d prose words · generated %s"
        % (
            "+".join(sorted(tiers)),
            len(sel),
            sum(r["metadata"]["stats"]["words_prose"] for r in sel),
            datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        ),
        "",
        "*Generated from corpus.jsonl — do not hand-edit.*",
        "",
    ]
    cur_ym = None
    for r in sel:
        created = r["created"] or "unknown"
        ym = created[:7]
        if ym != cur_ym:
            cur_ym = ym
            lines += ["", "## %s" % ym, ""]
        md = r["metadata"]
        lines += [
            "**%s** · %s · %s · tier %s · %d words"
            % (
                created[:16].replace("T", " "),
                md["venue"]["platform"],
                md["venue"]["kind"],
                md["quality"]["tier"],
                md["stats"]["words_prose"],
            ),
            "",
        ]
        lines += [render_readable(r["text"]), "", "---", ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return len(sel)


def _fmt_range(records):
    ds = sorted(r["created"][:10] for r in records if r["created"])
    return "%s .. %s" % (ds[0], ds[-1]) if ds else "n/a"


def write_manifest(path, records, ledger, per_source, args, refs_available, read_total):
    """The datasheet (R8 §7): counts, words, date ranges, and WHAT WAS DROPPED AND WHY."""
    by_src = defaultdict(list)
    for r in records:
        by_src[r["source"]].append(r)
    L = [
        "# MANIFEST — my_writing corpus",
        "",
        "Generated %s · build_corpus.py v%s"
        % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), VERSION),
        "",
    ]

    L += [
        "## 1. Sources",
        "",
        "| source | file | status | lines | read | emitted | prose words | date range "
        "| mojibake repair |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for src, info in sorted(per_source.items()):
        recs = by_src.get(src, [])
        L.append(
            "| %s | `%s` | %s | %s | %d | %d | %s | %s | %s |"
            % (
                src,
                info.get("file", "-"),
                info["status"],
                info.get("lines", "-"),
                info.get("read", 0),
                len(recs),
                "{:,}".format(sum(r["metadata"]["stats"]["words_prose"] for r in recs)),
                _fmt_range(recs),
                info.get("mojibake_repair", "-"),
            )
        )
    L += [
        "",
        "**Absent sources are absent, not empty.** A source with status MISSING produced",
        "no file at all; that is a pending export, not a measurement that it holds nothing.",
        "",
    ]

    L += [
        "## 2. Drop accounting",
        "",
        "Every discarded record is counted under exactly one named reason. Length is NOT a",
        "drop reason: R8 proposal #3 grades rather than deletes, so a short record becomes",
        "tier D and is still emitted.",
        "",
        "| reason | records | prose words | meaning |",
        "|---|---|---|---|",
    ]
    for reason, meaning in DROP_REASONS.items():
        n = sum(c[reason] for c in ledger.counts.values())
        w = sum(c[reason] for c in ledger.words.values())
        if n or reason in ("exact_duplicate", "near_duplicate"):
            L.append(
                "| `%s` | %s | %s | %s |"
                % (reason, "{:,}".format(n), "{:,}".format(w), meaning)
            )
    L += ["", "Total dropped: **%s** records." % "{:,}".format(ledger.total()), ""]

    emitted_msgs = sum(r["metadata"]["unit"]["n_messages"] for r in records)
    L += [
        "### Conservation check",
        "",
        "Checked in MESSAGE units, not record units: burst-merge collapses many messages",
        "into one record, so `%s emitted records` stand for `%s original messages`."
        % ("{:,}".format(len(records)), "{:,}".format(emitted_msgs)),
        "",
    ]
    if ledger.violations:
        L += (
            ["**FAILED — messages are unaccounted for:**", ""]
            + ["- `%s`" % v for v in ledger.violations]
            + [""]
        )
    else:
        L += [
            "PASS — every non-blank line read is either emitted inside some burst or",
            "counted under a named drop reason:",
            "",
            "```",
            "%s read = %s emitted + %s dropped"
            % (
                "{:,}".format(read_total),
                "{:,}".format(emitted_msgs),
                "{:,}".format(ledger.total_msgs()),
            ),
            "```",
            "",
        ]

    tiers = Counter(r["metadata"]["quality"]["tier"] for r in records)
    tw = defaultdict(int)
    for r in records:
        tw[r["metadata"]["quality"]["tier"]] += r["metadata"]["stats"]["words_prose"]
    L += [
        "## 3. Tier distribution (graded, not deleted)",
        "",
        "| tier | definition | records | prose words |",
        "|---|---|---|---|",
    ]
    for t, d in (
        ("A", ">= %d prose words" % TIER_A_MIN_WORDS),
        ("B", "%d-%d" % (TIER_B_MIN_WORDS, TIER_A_MIN_WORDS - 1)),
        ("C", "%d-%d" % (TIER_C_MIN_WORDS, TIER_B_MIN_WORDS - 1)),
        ("D", "< %d (fragment)" % TIER_C_MIN_WORDS),
    ):
        L.append(
            "| %s | %s | %s | %s |"
            % (t, d, "{:,}".format(tiers.get(t, 0)), "{:,}".format(tw.get(t, 0)))
        )

    bursts = [r for r in records if r["metadata"]["unit"]["kind"] == "burst"]
    upstream = [r for r in records if r["metadata"]["unit"]["merged_upstream"]]
    naive = sum(1 for r in records if r["metadata"]["time"]["tz"] == "naive")
    moji = sum(1 for r in records if r["metadata"]["provenance"]["mojibake_repaired"])
    L += [
        "",
        "## 4. Pipeline facts",
        "",
        "- Burst merge: **%d/%d** emitted records are multi-message bursts (gap <= %ds)."
        % (len(bursts), len(records), args.burst_gap),
        "- Interruption-blind: **%s** (%s/%s records). The per-source files are owner-only,"
        % (
            "yes"
            if any(r["metadata"]["unit"]["burst_interruption_blind"] for r in records)
            else "no",
            "{:,}".format(
                sum(
                    1
                    for r in records
                    if r["metadata"]["unit"]["burst_interruption_blind"]
                )
            ),
            "{:,}".format(len(records)),
        ),
        "  so a burst this tool drew cannot see whether the other party spoke in the",
        "  middle unless the source emits an `interrupted_before` flag. Those merged",
        "  spans are an UPPER bound.",
        "- Merged upstream (burst-final on arrival, NOT re-merged here): **%s/%s**."
        % ("{:,}".format(len(upstream)), "{:,}".format(len(records))),
        "  A source that already merged did so with sight of the other party's turns",
        "  (isolate_messenger.py:387-391 flushes on another speaker), so re-merging it",
        "  blind here would weld across an interruption it deliberately split.",
        "- Timestamps without an offset: **%s/%s**.%s"
        % (
            "{:,}".format(naive),
            "{:,}".format(len(records)),
            ""
            if not naive
            else " Not repaired and not invented — the offset\n  is absent from the input."
            " A source may carry it in a sibling `tz_offset` field\n  (isolate_discord.py:63);"
            " where that field is present it IS reattached.",
        ),
        "- Mojibake repaired in **%s** records (detector-gated, so a clean string is"
        % ("{:,}".format(moji)),
        "  byte-identical through the pipeline).",
        "- Cross-author copypasta detector: **%s**."
        % (
            "available"
            if refs_available
            else "UNAVAILABLE (no --others-jsonl reference corpus) — this is not a finding of zero"
        ),
        "- PERSON-name NER: **not implemented** (needs Presidio + a Romania pack that does",
        "  not exist — R8 §9.3). No tier of this tool can claim third-party names are gone.",
        "",
    ]

    L += [
        "## 5. Constants (this corpus's definition)",
        "",
        "| constant | value |",
        "|---|---|",
    ]
    for k, v in (
        ("BURST_GAP_SECONDS", args.burst_gap),
        ("TIER_A_MIN_WORDS", TIER_A_MIN_WORDS),
        ("TIER_B_MIN_WORDS", TIER_B_MIN_WORDS),
        ("TIER_C_MIN_WORDS", TIER_C_MIN_WORDS),
        ("NEAR_DUP_JACCARD", NEAR_DUP_JACCARD),
        ("SHINGLE_SIZE", SHINGLE_SIZE),
        ("MINHASH_PERMS", MINHASH_PERMS),
        ("pii_tier", args.pii_tier),
        ("reading_tiers", args.reading_tier),
        ("near_dup_enabled", not args.no_near_dup),
    ):
        L.append("| `%s` | `%s` |" % (k, v))
    L += [
        "",
        "*Change any of these and it is a different corpus. That is why they are here.*",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


# ---------------------------------------------------------------------------
# 10. MAIN
# ---------------------------------------------------------------------------


def self_test():
    """Regression guard for the subtle invariants. Returns 0 on pass, 1 on failure.

    The pre-bursted case is the one a future edit is most likely to undo silently, so it
    is asserted in BOTH directions: with the upstream marker the records must stay apart,
    and WITHOUT it the same records must weld. A one-directional test would still pass if
    burst-merging broke entirely.
    """
    import tempfile

    fails, ran = [], []

    def check(name, ok, detail=""):
        ran.append(name)
        print(
            "    [%s] %s%s"
            % ("PASS" if ok else "FAIL", name, "  -- " + detail if detail else "")
        )
        if not ok:
            fails.append(name)

    print(
        "\n  SELF-TEST -- synthetic vectors; the real acceptance run is the Discord control.\n"
    )
    ledger = DropLedger()
    pseudo = PseudonymMap(
        os.path.join(tempfile.gettempdir(), "_bc_selftest_pseudo.json")
    )

    def mk(**kw):
        return normalise_record(
            kw, "messenger", "x.jsonl", 1, ledger, pseudo, False, None
        )

    # 1+2. Pre-bursted records 200 s apart (INSIDE the 420 s gap) must NOT re-merge,
    #      because isolate_messenger.py:387-391 already split them on another speaker.
    a = mk(
        ts="2024-03-11T21:00:00+02:00",
        thread="M",
        msgs_in_burst=4,
        content="alfa " * 40,
    )
    b = mk(
        ts="2024-03-11T21:03:20+02:00",
        thread="M",
        msgs_in_burst=3,
        content="beta " * 40,
    )
    kept = burst_merge([a, b], BURST_GAP_SECONDS, True)
    check("pre-bursted records are NOT re-merged", len(kept) == 2, "got %d" % len(kept))
    check(
        "upstream message count preserved",
        sum(k["_nsrc"] for k in kept) == 7,
        "got %s" % sum(k["_nsrc"] for k in kept),
    )
    check(
        "upstream burst is not labelled interruption-blind",
        not any(k["_blind"] for k in kept),
    )

    # 3. NEGATIVE CONTROL: identical timing, no marker -> must weld. Proves 1 is live.
    c = mk(ts="2024-03-11T21:00:00+02:00", thread="M", content="alfa " * 40)
    d = mk(ts="2024-03-11T21:03:20+02:00", thread="M", content="beta " * 40)
    welded = burst_merge([c, d], BURST_GAP_SECONDS, True)
    check(
        "negative control: unmarked records DO merge",
        len(welded) == 1,
        ""
        if len(welded) == 1
        else "got %d -- the hazard did not reproduce, so check 1 proves nothing"
        % len(welded),
    )

    # 4. Mojibake repair is detector-gated: correct text must pass through byte-identical.
    clean = "bună ziua, ce faci? ✓ 👍 mulțumesc"
    check(
        "clean text is byte-identical through the repair", fix_mojibake(clean) == clean
    )
    check(
        "mojibake IS repaired",
        fix_mojibake("bunÄ\x83 ziua") == "bună ziua",
        repr(fix_mojibake("bunÄ\x83 ziua")),
    )

    # 5. Cedilla->comma (R8 §0.1 B): NFC alone will not do this.
    check("s-cedilla folds to s-comma", normalise_text("şi ţara") == "și țara")

    # 6. Secrets redact at L0; a valid RO CNP is caught and a random 13-digit number is not.
    _, red = redact("cheia sk-" + "a" * 32 + " gata", "L0")
    check("L0 redacts secrets", [r["type"] for r in red] == ["openai_key"], str(red))
    _, red = redact("cnp 1960229123452 gata", "L0")
    check("valid RO CNP redacted", [r["type"] for r in red] == ["ro_cnp"], str(red))
    _, red = redact("am 1234567890123 puncte", "L0")
    check("invalid 13-digit number NOT redacted", red == [], str(red))
    _, red = redact("scrie la ana@example.com", "L0")
    check(
        "L0 does NOT redact third-party email (over-redaction guard)",
        red == [],
        str(red),
    )

    # 7. Tier boundaries (R8 §3.3).
    check(
        "tier boundaries",
        [tier_of(n) for n in (100, 99, 25, 24, 5, 4)] == ["A", "B", "B", "C", "C", "D"],
    )

    # 8. Sibling-carried UTC offset (isolate_discord.py:63) must be REATTACHED, not dropped.
    #    The control export mixes +02:00 and +03:00 (Romania DST), so this decides ordering.
    r2 = mk(ts="2024-07-01T12:00:00", tz_offset="+03:00", content="cuvinte " * 30)
    r3 = mk(ts="2024-01-01T12:00:00", tz_offset="+02:00", content="altele " * 30)
    check(
        "naive ts + sibling tz_offset -> aware",
        bool(r2 and r2["_aware"] and r3["_aware"]),
    )
    check(
        "DST offsets are distinct, not normalised away",
        bool(r2) and bool(r3) and r2["_dt"].utcoffset() != r3["_dt"].utcoffset(),
        "%s vs %s"
        % (
            r2["_dt"].utcoffset() if r2 else None,
            r3["_dt"].utcoffset() if r3 else None,
        ),
    )
    r4 = mk(ts="2024-07-01T12:00:00", content="fara offset " * 20)
    check("absent offset stays naive (never fabricated)", bool(r4) and not r4["_aware"])
    r5 = mk(ts="2024-07-01T12:00:00+05:00", tz_offset="+03:00", content="deja " * 30)
    check(
        "offset inside ts is NOT overridden by the sibling field",
        bool(r5) and r5["_dt"].utcoffset() == timedelta(hours=5),
        str(r5["_dt"].utcoffset()) if r5 else "none",
    )
    check(
        "malformed offset degrades to naive, never raises",
        (parse_offset("garbage"), parse_offset("+99:99"), parse_offset(None))
        == (None, None, None),
    )

    # 8. End-to-end: a source with only SOME files present must not abort.
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "Discord"))
        with open(
            os.path.join(td, "Discord", "owner.jsonl"), "w", encoding="utf-8"
        ) as f:
            f.write(
                json.dumps({"ts": "2024-01-01T10:00:00", "content": "cuvinte " * 40})
                + "\n"
            )
            f.write("{ not json\n")
        rc = main(["--root", td, "--out", os.path.join(td, "out")])
        ok = rc == 0 and os.path.exists(os.path.join(td, "out", "corpus.jsonl"))
        check("degrades to one present source, counts the bad line", ok, "rc=%s" % rc)

    print(
        "\n  %s -- %d/%d checks passed\n"
        % (
            "SUCCESS:build_corpus-self-test"
            if not fails
            else "FAILED:build_corpus-self-test " + "; ".join(fails),
            len(ran) - len(fails),
            len(ran),
        )
    )
    return 1 if fails else 0


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="Unify per-source owner-only JSONL into one corpus (R8 design)."
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="run the built-in regression checks and exit",
    )
    p.add_argument("--root", default=ROOT, help="tree to scan for per-source .jsonl")
    p.add_argument(
        "--out", default=os.path.join(ROOT, "corpus"), help="output directory"
    )
    p.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="explicit source file; repeatable. Overrides auto-discovery.",
    )
    p.add_argument(
        "--others-jsonl",
        action="append",
        default=[],
        metavar="PATH",
        help="NON-owner messages, used as the cross-author copypasta detector.",
    )
    p.add_argument(
        "--burst-gap",
        type=int,
        default=BURST_GAP_SECONDS,
        help="burst merge gap in seconds (0 disables merging)",
    )
    p.add_argument(
        "--reading-tier", default="A", help="tiers in corpus.md, e.g. A or AB"
    )
    p.add_argument(
        "--drop-below-tier",
        default=None,
        choices=[None, "A", "B", "C"],
        help="HARD-delete below this tier. Off by default: grade, don't delete.",
    )
    p.add_argument(
        "--pii-tier",
        default="L0",
        choices=["L0", "L1", "L2", "L3"],
        help="L0 secrets only (default) | L1 +third-party | L2 +drop context | L3 +owner",
    )
    p.add_argument(
        "--unsafe-no-ner",
        action="store_true",
        help="acknowledge that PERSON-name detection is NOT implemented (L2/L3)",
    )
    p.add_argument(
        "--mojibake-sources",
        default=",".join(sorted(MOJIBAKE_SOURCES)),
        help="sources to run the Meta latin-1 mojibake repair on ('all'/'none' "
        "accepted). Default: the Meta DYI emitters only — running it on "
        "Discord/WhatsApp text CREATES corruption (R4, R5, and measured).",
    )
    p.add_argument(
        "--no-near-dup", action="store_true", help="skip the MinHash near-dup pass"
    )
    p.add_argument(
        "--max-records", type=int, default=0, help="per-source cap (0 = no cap)"
    )
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    if args.pii_tier in ("L2", "L3") and not args.unsafe_no_ner:
        print(
            "REFUSING: --pii-tier %s implies third-party names are removed, but PERSON-name\n"
            "detection is NOT implemented here (R8 §9.3: Presidio ships no Romania pack).\n"
            "Re-run with --unsafe-no-ner if you accept that names remain in the text."
            % args.pii_tier,
            file=sys.stderr,
        )
        return 2

    spec = args.mojibake_sources.strip().lower()
    if spec == "all":
        moji_sources = None  # None == every source
    elif spec in ("none", ""):
        moji_sources = set()
    else:
        moji_sources = {s.strip() for s in spec.split(",") if s.strip()}

    os.makedirs(args.out, exist_ok=True)
    ledger = DropLedger()
    pseudo = PseudonymMap(os.path.join(args.out, "pseudonyms.map.json"))

    sources = discover_sources(args.root, args.out, args.source)
    if not sources:
        print(
            "No per-source .jsonl found under %s.\n"
            "Nothing to unify yet — run the isolators first, or pass --source NAME=PATH."
            % args.root,
            file=sys.stderr,
        )
        return 1

    refs = load_reference_corpus(
        args.others_jsonl
    )  # BEFORE ingest — see normalise_record
    messages, per_source, read_total = [], {}, 0
    for source, path in sources:
        info = {"file": os.path.relpath(path, args.root), "status": "OK"}
        if not os.path.exists(path):
            info["status"] = "MISSING"
            per_source[source] = info
            continue
        fix_moji = moji_sources is None or source in moji_sources
        info["mojibake_repair"] = (
            "on" if fix_moji else "off (source not a Meta DYI emitter)"
        )
        try:
            msgs, fields, lines = read_source(
                path, source, ledger, pseudo, args.max_records, fix_moji, refs
            )
        except (OSError, UnicodeError) as exc:  # degrade per-source, never abort
            info.update(status="ERROR: %s" % type(exc).__name__, lines=0, read=0)
            per_source[source] = info
            print("  [%s] ERROR %s" % (source, exc), file=sys.stderr)
            continue
        info.update(
            lines=lines,
            read=len(msgs),
            status="OK" if msgs else "EMPTY (0 usable records — see drop accounting)",
        )
        if not msgs:
            info["fields"] = ",".join(sorted(fields)) or "none"
        per_source[source] = info
        read_total += lines
        messages.extend(msgs)
        print(
            "  [%s] %s -> %d messages from %d lines"
            % (source, info["file"], len(msgs), lines)
        )

    if not messages:
        print(
            "Read %d lines but produced 0 usable records. Drop reasons: %s"
            % (read_total, dict(sum(ledger.counts.values(), Counter()))),
            file=sys.stderr,
        )

    bursts = (
        burst_merge(messages, args.burst_gap, interruption_blind=True)
        if args.burst_gap > 0
        else burst_merge(messages, -1, True)
    )
    print(
        "  burst-merge: %d messages -> %d bursts (gap %ds)"
        % (len(messages), len(bursts), args.burst_gap)
    )

    bursts = dedup(bursts, ledger, enable_near=not args.no_near_dup)

    keep_context = args.pii_tier not in ("L2", "L3")
    records = [
        build_record(b, i, args.pii_tier, keep_context) for i, b in enumerate(bursts)
    ]

    if args.drop_below_tier:
        order = {"A": 3, "B": 2, "C": 1, "D": 0}
        floor, kept = order[args.drop_below_tier], []
        for r in records:
            if order[r["metadata"]["quality"]["tier"]] < floor:
                ledger.drop(
                    r["source"],
                    "below_min_tier",
                    r["metadata"]["stats"]["words_prose"],
                    r["metadata"]["unit"]["n_messages"],
                )
            else:
                kept.append(r)
        records = kept

    # Conservation is asserted in MESSAGE units, not record units: burst-merge collapses
    # many messages into one record, so a dropped burst removes n_messages messages. The
    # invariant is "every non-blank line read is either emitted inside some burst, or
    # counted under a named drop reason".
    emitted_msgs = sum(r["metadata"]["unit"]["n_messages"] for r in records)
    ledger.check("messages", read_total, emitted_msgs)

    corpus_path = os.path.join(args.out, "corpus.jsonl")
    with open(corpus_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_md = write_corpus_md(
        os.path.join(args.out, "corpus.md"), records, set(args.reading_tier.upper())
    )
    write_manifest(
        os.path.join(args.out, "MANIFEST.md"),
        records,
        ledger,
        per_source,
        args,
        refs is not None,
        read_total,
    )
    pseudo.save()

    words = sum(r["metadata"]["stats"]["words_prose"] for r in records)
    tiers = Counter(r["metadata"]["quality"]["tier"] for r in records)
    print(
        "\ncorpus: %s records, %s prose words  (A=%d B=%d C=%d D=%d)"
        % (
            "{:,}".format(len(records)),
            "{:,}".format(words),
            tiers["A"],
            tiers["B"],
            tiers["C"],
            tiers["D"],
        )
    )
    print(
        "dropped: %s records under %d named reasons"
        % (
            "{:,}".format(ledger.total()),
            len([r for r in DROP_REASONS if sum(c[r] for c in ledger.counts.values())]),
        )
    )
    print(
        "  -> %s\n  -> %s (%d records)\n  -> %s"
        % (
            corpus_path,
            os.path.join(args.out, "corpus.md"),
            n_md,
            os.path.join(args.out, "MANIFEST.md"),
        )
    )
    if ledger.violations:
        print(
            "\nCONSERVATION FAILED: %s" % "; ".join(ledger.violations), file=sys.stderr
        )
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
