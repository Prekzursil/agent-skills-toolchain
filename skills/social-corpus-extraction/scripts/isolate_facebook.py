#!/usr/bin/env python3
"""Isolate the owner's OWN writing from a Facebook "Download Your Information" (DYI) export.

Counterpart to isolate_discord.py. Covers POSTS + COMMENTS + GROUP POSTS/COMMENTS.

Emits, into <outdir> (default: <script dir>/Facebook/):
  andrei_visalon_all.txt          every owner-authored record, chronological -- the complete record
  andrei_visalon_substantial.txt  only records >= MIN_PROSE_WORDS prose words -- the actual WRITING
  andrei_visalon.jsonl            structured, one record per line, with full per-record metadata

Usage:
    python isolate_facebook.py <archive.zip | archive-dir>            # both accepted
    python isolate_facebook.py <path> --outdir Facebook --min-words 25
    python isolate_facebook.py <path> --tier-a-only                   # >= 100 prose words
    python isolate_facebook.py <path> --no-groups                     # exclude group posts/comments

DESIGN NOTES (provenance in research/R1,R2,R3,R8; conflicts resolved in build/B1-isolate-facebook.md)

  * NEVER hardcode the posts path. Meta renamed both the file and its parent directory at least
    three times; a pipeline pinned to posts/your_posts_1.json finds ZERO posts in a 2024+ archive
    (R1 s2, C4). We match by filename pattern anywhere in the tree instead.
  * NEVER classify by the `title` string. `title` is auto-generated notification text AND it is
    LOCALIZED to the account's language -- a real German archive emits "hat einen Beitrag geteilt."
    (R3 s0.1). An English regex matches nothing on this owner's Romanian profile. Classification is
    STRUCTURAL; `title` is recorded and flagged for review, never used as grounds for a drop.
  * NEVER index data[0]. 27% of data[] members are literally {} (R3 s2.3). Scan the array.
  * Mojibake repair happens AFTER json.loads, never on the raw file (R2 s5). See fix_mojibake().
  * A zero-record run MUST say why. See Diagnostics.report() and the non-zero exit codes below.

Exit codes:
    0  records emitted
    2  zero records emitted (the reason is printed)
    3  no candidate files found in the archive (the archive layout is printed)
    4  finished, but one or more files had an unrecognised schema -- output is INCOMPLETE

Stdlib only. Python 3.8+. Runs on Windows.
"""

import argparse
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 1. OWNER / CORPUS CONSTANTS
# ---------------------------------------------------------------------------

OWNER_NAME = "Owner Name"
OUT_PREFIX = "andrei_visalon"

# B0-ADV: the owner has been on Facebook for many years and a display name is
# MUTABLE. author_is_other() drops any comment whose author does not casefold-equal
# an entry here, so a single hardcoded spelling silently discards every comment
# from any era in which the name differed. VERIFIED by execution: "Owner Name"
# and "owner name" pass, while "Owner Name (the same name typed with
# proper Romanian diacritics -- entirely plausible for this owner) is dropped as
# foreign. Populated from --owner-name at startup; the report prints an author
# census so a mismatch is diagnosable instead of invisible.
OWNER_NAMES = {OWNER_NAME}

# Every distinct author name that caused a not-owner drop, with its count. This is
# the diagnostic that turns "412 comments vanished" into "412 comments were signed
# 'Owner Name'" -- i.e. into an actionable --owner-name re-run.
FOREIGN_AUTHOR_CENSUS = Counter()

# --- the length threshold ---------------------------------------------------
# R8 s3.1 + s3.3: threshold on PROSE WORDS, not characters. A character floor is
# a broken proxy for information content (a pasted URL or stack trace is long in
# characters and zero in authorial style) and it is language-biased in a mixed
# RO/EN corpus, because the floor is easier to clear in whichever language has
# longer words. Words are language-portable and are the unit every corpus
# -linguistics / LLM-data source actually uses. Model tokens are rejected as the
# metric because Romanian tokenizer fertility spans 1.5-3.0x, so a token
# threshold would make the corpus definition tokenizer-dependent (R8 s3.1).
#
# Tier boundaries (R8:185-190), counted on PROSE words -- i.e. after stripping
# URLs, @[mention] markup, code spans and quoted lines (R8 s3.2):
#     A  essay          >= 100   lexical-diversity indices (MTLD et al.) stop
#                                being length-dependent around 100 tokens; this
#                                is the owner's own "long posts, not short thank
#                                you or so" line.
#     B  substantial     25-99   ~25 words is the equivalent of the Discord
#                                MIN_CHARS = 150 cut, so the Facebook and
#                                Discord corpora stay directly comparable.
#     C  conversational   5-24   real writing, too short to carry style alone.
#     D  fragment          < 5   "ok", "da", reactions.
#
# GRADE, NEVER DELETE (R8:182, and R8's correction to GROUNDING:28). Every
# owner-authored record reaches the .jsonl carrying its tier; the threshold
# selects the *substantial* view only. This deliberately supersedes R3 STEP 5,
# which dropped sub-threshold posts outright -- keeping them costs nothing and
# makes raising the bar a filter over the emitted data instead of a re-run.
MIN_PROSE_WORDS = 25
TIER_A_WORDS = 100
TIER_C_WORDS = 5

# Per-file guard. R1:408-412 measured real post shards in the low hundreds of KB
# (197 KB for 506 posts), so json.load PER SHARD is safe even when the archive as
# a whole is multi-GB -- we never load the archive, only one member at a time.
# Above this we warn that the file needs a streaming parser (ijson) instead.
LARGE_FILE_WARN_BYTES = 200 * 1024 * 1024

# ---------------------------------------------------------------------------
# 2. FILE DISCOVERY -- pattern matching, never hardcoded paths (R1 C4)
# ---------------------------------------------------------------------------

# Checked FIRST. These files exist in the posts folder but are not the owner's
# timeline authorship, and simply not reading them is the whole of R3 case (e)
# -- auto-generated life events, profile/cover changes and check-ins live here,
# not in the posts file (R3 s4(e), P4).
EXCLUDE_RE = re.compile(
    r"other_people.?s_posts_to_your_timeline"
    r"|profile_update_history"
    r"|check-?ins"
    r"|places_you_have_been_tagged_in"
    r"|your_uncategorized_photos"  # photos sent as messages / on others' profiles (R1:126)
    r"|your_videos"  # video descriptions; not timeline authorship
    r"|/album/|/media/|/photos/"
    r"|no-data\.txt",
    re.IGNORECASE,
)

# Checked before POST_FILE_RE, because your_posts_and_comments_in_groups.json
# would otherwise be swallowed by the generic your_posts* pattern.
GROUP_FILE_RE = re.compile(
    r"your_posts_and_comments_in_groups\w*\.json$"
    r"|your_comments_in_groups\w*\.json$"
    r"|your_group_(?:posts|comments)\w*\.json$"
    r"|/groups?/[^/]*\.json$",
    re.IGNORECASE,
)

# Covers all three eras in one pattern (R1 s2):
#   E1  posts/your_posts.json
#   E2  posts/your_posts_1.json
#   E3  your_facebook_activity/posts/your_posts__check_ins__photos_and_videos_1.json
#   E3' your_activity_across_facebook/posts/your_posts__check_ins__photos_and_videos_1.json
POST_FILE_RE = re.compile(r"your_posts\w*\.json$", re.IGNORECASE)

COMMENT_FILE_RE = re.compile(
    r"your_comments\w*\.json$"
    r"|(?:^|/)comments(?:_v?\d+)?\.json$",
    re.IGNORECASE,
)

# Recognised top-level wrapper keys. A DYI file is either a bare array (E2/E3) or
# a single-key object (E1 and the group/comment files). Anything else is an
# unrecognised schema and is reported loudly rather than silently skipped.
KNOWN_WRAPPERS = (
    "status_updates",  # E1 posts
    "posts",
    "group_posts",  # your_posts_and_comments_in_groups.json
    "group_comments",
    "comments_v2",  # comments file; the _v2 suffix is Meta's own versioning (R1:132)
    "comments",
    "your_comments",
)

# ---------------------------------------------------------------------------
# 3. MOJIBAKE REPAIR  (GROUNDING trap #1; implementation from R2 s7)
# ---------------------------------------------------------------------------
# Meta's DYI serializer takes the UTF-8 BYTES of each string and emits each byte
# as its own \u00XX JSON escape. A conforming parser therefore hands back one
# character per byte, all in U+0000..U+00FF -- UTF-8 round-tripped through
# Latin-1. Romanian "ă" (U+0103, UTF-8 C4 83) arrives as 'Ä\x83'.
#
# Two things GROUNDING:48-52 gets wrong, both verified by execution:
#
#  (1) The prescribed per-string s.encode('latin-1').decode('utf-8') is the right
#      inverse but is NOT complete, and it fails SILENTLY. On a MIXED string --
#      mojibake plus even one genuinely-correct character above U+00FF -- the
#      encode raises on that character, so under a defensive try/except the whole
#      string is returned UNREPAIRED with no error and no log line. One pasted
#      checkmark or em-dash in a long post defeats repair of that entire post.
#      Fix: segment into UTF-8-shaped runs and decode per run (below), which also
#      makes idempotence structural rather than exception-dependent.
#
#  (2) The tempting alternative -- regex-substituting \u00XX in the RAW FILE
#      before json.loads -- CORRUPTS the document. Meta also escapes ASCII
#      metacharacters, so " (a quote) becomes a bare " inside a JSON string.
#      Verified here: it raises JSONDecodeError. Repair AFTER parsing, always.
#
# The character classes below encode the Unicode 16.0 Table 3-7 well-formedness
# constraints, which is what stops us "repairing" ordinary accented text:
#     C0/C1 absent     -> no overlong 2-byte forms
#     E0 needs A0..BF  -> no overlong 3-byte forms
#     ED needs 80..9F  -> can never produce a surrogate D800..DFFF
#     F0 needs 90..BF  -> no overlong 4-byte forms
#     F4 needs 80..8F  -> can never exceed U+10FFFF
#     F5..FF absent    -> not valid UTF-8 lead bytes
# Written with explicit \uXXXX escapes rather than literal glyphs: the ranges
# include C1 control characters, which are invisible and do not survive copying.
_UTF8_RUN = re.compile(
    "(?:"
    "[\u00c2-\u00df][\u0080-\u00bf]"  # 2-byte  -> U+0080..U+07FF
    "|\u00e0[\u00a0-\u00bf][\u0080-\u00bf]"  # 3-byte, E0 non-overlong
    "|[\u00e1-\u00ec\u00ee\u00ef][\u0080-\u00bf]{2}"  # 3-byte  -> U+1000..U+FFFF
    "|\u00ed[\u0080-\u009f][\u0080-\u00bf]"  # 3-byte, ED pre-surrogate
    "|\u00f0[\u0090-\u00bf][\u0080-\u00bf]{2}"  # 4-byte, F0 non-overlong
    "|[\u00f1-\u00f3][\u0080-\u00bf]{3}"  # 4-byte  -> astral plane
    "|\u00f4[\u0080-\u008f][\u0080-\u00bf]{2}"  # 4-byte, F4 <= U+10FFFF
    ")+"
)

# Romanian legacy cedilla forms vs the correct comma-below forms. These are
# DISTINCT code points with distinct canonical decompositions, so NFC/NFKC will
# NOT merge them -- "și" and "şi" stay different tokens forever (R2 s9, R8 C1).
# Normalising is a LOSSY EDITORIAL choice, unlike fix_mojibake which is a
# lossless inverse, so it is opt-in (--normalize-cedilla) and the occurrence
# count is always reported so the decision is visible rather than silent.
CEDILLA_TO_COMMA = {0x015F: "ș", 0x015E: "Ș", 0x0163: "ț", 0x0162: "Ț"}
_CEDILLA_CHARS = "şŞţŢ"


def _decode_run(match):
    try:
        return match.group(0).encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):  # unreachable by construction
        return match.group(0)


def fix_mojibake(s):
    """Repair Meta's UTF-8-bytes-as-Latin-1 mojibake.

    Contract: never raises; non-str passes through; idempotent; pure ASCII is a
    strict no-op; handles 1-4 byte UTF-8 so emoji/astral/ZWJ/flags survive; and
    repairs MIXED strings per run, which the bare one-liner silently does not.
    """
    if type(s) is not str:
        return s
    if s.isascii():  # fast path: an ASCII string cannot contain a run
        return s
    try:
        return _UTF8_RUN.sub(_decode_run, s)
    except Exception:  # belt and braces: the contract is "never raises"
        return s


def looks_mojibaked(s):
    """True iff s contains at least one repairable run. Used to MEASURE the
    archive's hit-rate (R2's settling experiment), never to gate the repair."""
    return isinstance(s, str) and _UTF8_RUN.search(s) is not None


class TextCleaner:
    """fix_mojibake -> NFC -> optional cedilla fold, with counters.

    NFC matters because Meta's double-encoding has been documented emitting
    DECOMPOSED text (a combining acute, U+0301) -- so a repaired string may still
    be NFD (R3 s0.2). Counting how often NFC actually changes something is that
    finding's settling experiment, run automatically on every invocation.
    """

    def __init__(self, normalize_cedilla=False):
        self.normalize_cedilla = normalize_cedilla
        self.seen = 0
        self.repaired = 0
        self.nfc_changed = 0
        self.cedilla_chars = 0

    def clean(self, s):
        """Return (cleaned_text, was_repaired).

        The flag is propagated to every record so repairs stay AUDITABLE. That matters
        because a false positive is possible in principle: any string that is both
        Latin-1-encodable and valid UTF-8 will be "repaired" whether or not it was
        ever mojibaked, and no implementation (this one, ftfy, or any other) can
        tell the difference. MEASURED on the 104,842-message real Discord control
        -- correctly-encoded owner text, so every hit is a false positive by
        construction -- the rate is 2/104,842 = 0.0019%, and BOTH hits were
        keyboard alt-code symbol runs ("«»¥×¥×’‘¾½¼€¤³²¡"), not Romanian prose.
        Grep the corpus for mojibake_repaired to review them:
            jq 'select(.mojibake_repaired)' andrei_visalon.jsonl
        """
        if not isinstance(s, str) or not s:
            return s, False
        self.seen += 1
        fixed = fix_mojibake(s)
        repaired = fixed != s
        if repaired:
            self.repaired += 1
        normalized = unicodedata.normalize("NFC", fixed)
        if normalized != fixed:
            self.nfc_changed += 1
        self.cedilla_chars += sum(normalized.count(c) for c in _CEDILLA_CHARS)
        if self.normalize_cedilla:
            normalized = normalized.translate(CEDILLA_TO_COMMA)
        return normalized, repaired

    def __call__(self, s):
        return self.clean(s)[0]


# ---------------------------------------------------------------------------
# 4. ARCHIVE ACCESS -- directory or .zip, uniformly, never loaded whole
# ---------------------------------------------------------------------------


class SchemaError(Exception):
    """An input file did not match any DYI shape we recognise."""


class Archive:
    """Read-only view over one DYI export (a directory or a .zip).

    Members are addressed by POSIX-style relative path in both cases so the
    discovery regexes do not have to care which form the owner unzipped into.
    """

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.is_zip = zipfile.is_zipfile(self.path) and not os.path.isdir(self.path)
        self._zf = zipfile.ZipFile(self.path) if self.is_zip else None

    @property
    def label(self):
        return "%s (%s)" % (self.path, "zip" if self.is_zip else "dir")

    def members(self):
        if self.is_zip:
            return [i.filename for i in self._zf.infolist() if not i.is_dir()]
        out = []
        for root, _dirs, files in os.walk(self.path):
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, self.path).replace(os.sep, "/")
                out.append(rel)
        return out

    def size(self, name):
        if self.is_zip:
            return self._zf.getinfo(name).file_size
        return os.path.getsize(os.path.join(self.path, name.replace("/", os.sep)))

    def read_bytes(self, name):
        if self.is_zip:
            with self._zf.open(name) as fh:
                return fh.read()
        with open(os.path.join(self.path, name.replace("/", os.sep)), "rb") as fh:
            return fh.read()

    def close(self):
        if self._zf is not None:
            self._zf.close()


def open_archives(path):
    """Return every archive rooted at `path`.

    A DYI export can be delivered as several .zip parts, so a directory that
    contains .zip files is treated as the directory PLUS each zip inside it.
    """
    if not os.path.exists(path):
        raise SystemExit("ERROR: path does not exist: %s" % path)
    archives = [Archive(path)]
    if os.path.isdir(path):
        for name in sorted(os.listdir(path)):
            full = os.path.join(path, name)
            if os.path.isfile(full) and zipfile.is_zipfile(full):
                archives.append(Archive(full))
    return archives


# ---------------------------------------------------------------------------
# 5. SCHEMA NORMALISATION -- absorb the E1/E2/E3 breaks, fail loudly otherwise
# ---------------------------------------------------------------------------


def unwrap(obj, source):
    """Return (records, wrapper_key, novel).

    E1 posts are {"status_updates": [...]}; E2/E3 posts are a bare array; group
    and comment files are single-key objects. A dict with exactly one list-valued
    key that we do not know is accepted but reported as NOVEL, so schema drift
    surfaces as a printed warning instead of a silent zero.
    """
    if isinstance(obj, list):
        return obj, None, False
    if isinstance(obj, dict):
        for key in KNOWN_WRAPPERS:
            value = obj.get(key)
            if isinstance(value, list):
                return value, key, False
            # R3:337-338 -- your_posts_and_comments_in_groups.json DOUBLE-nests:
            # {"group_posts": {"activity_log_data_points": [...]}}. The wrapper key
            # is recognised but its value is a dict, so the list-only test above
            # misses it, the file raises SchemaError, and every group record is
            # lost. flatten_if_nested() below was written for this shape but is
            # unreachable, because unwrap() raises before it can run. Descend
            # exactly one level, and only when that level is unambiguous.
            if isinstance(value, dict):
                inner = [k for k, v in value.items() if isinstance(v, list)]
                if len(inner) == 1:
                    return value[inner[0]], "%s.%s" % (key, inner[0]), False
        list_keys = [k for k, v in obj.items() if isinstance(v, list)]
        if len(list_keys) == 1:
            return obj[list_keys[0]], list_keys[0], True
        raise SchemaError(
            "%s: object with no recognised wrapper. Top-level keys: %s. "
            "List-valued keys: %s. Expected one of %s, or a bare array."
            % (source, sorted(obj.keys())[:20], list_keys, list(KNOWN_WRAPPERS))
        )
    raise SchemaError(
        "%s: top level is %s, expected list or object." % (source, type(obj).__name__)
    )


def flatten_if_nested(records, source, diag):
    """Bounded one-level flatten for the double-nested group files (R1:130).

    Only fires when NO record looks like a post/comment (no timestamp, no data)
    and every record is a single-key object wrapping a list. Reported when used.
    """
    if not records or any(
        isinstance(r, dict) and ("timestamp" in r or "data" in r) for r in records
    ):
        return records
    flat = []
    for record in records:
        if not isinstance(record, dict):
            return records
        inner = [v for v in record.values() if isinstance(v, list)]
        if len(inner) != 1:
            return records
        flat.extend(inner[0])
    diag.notes.append(
        "flattened one nesting level in %s (%d -> %d records)"
        % (source, len(records), len(flat))
    )
    return flat


# ---------------------------------------------------------------------------
# 6. FIELD EXTRACTION -- scan, never index (R3 s2.3)
# ---------------------------------------------------------------------------

_MENTION_ONLY = re.compile(r"^(?:@\[[^\]]*\]\s*)+$")
_URL_ONLY = re.compile(r"^\s*(?:(?:https?://|www\.)\S+\s*)+$", re.IGNORECASE)

_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE = re.compile(r"`[^`]*`")
_URL_ANY = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_FB_MENTION = re.compile(r"@\[[^\]]*\]")
_QUOTE_LINE = re.compile(r"^\s*>.*$", re.MULTILINE)
_WORD = re.compile(r"[^\W\d_]+(?:['’‘-][^\W\d_]+)*")


def prose_words(text):
    """Word count over PROSE only -- code spans, URLs, @[mention] markup and
    quoted lines removed first (R8 s3.2). Counting them would reward exactly the
    records with the least of the owner's style in them."""
    stripped = _CODE_FENCE.sub(" ", text)
    stripped = _INLINE_CODE.sub(" ", stripped)
    stripped = _QUOTE_LINE.sub(" ", stripped)
    stripped = _URL_ANY.sub(" ", stripped)
    stripped = _FB_MENTION.sub(" ", stripped)
    return len(_WORD.findall(stripped))


def tier_of(n_prose_words):
    if n_prose_words >= TIER_A_WORDS:
        return "A"
    if n_prose_words >= MIN_PROSE_WORDS:
        return "B"
    if n_prose_words >= TIER_C_WORDS:
        return "C"
    return "D"


def author_is_other(container):
    """True when an explicit author field names someone OTHER than the owner.

    comments.json and the group-comment union carry data[].comment.author, and a
    LONG, well-formed comment by another person is structurally indistinguishable
    from the owner's own -- only this field separates them (EXPECTED.json
    fb-comment-003 pins exactly that). The field is mojibaked the same way the
    body is, so it MUST be repaired before comparison (R7:104, and
    EXPECTED.json:rules.owner_isolation).

    Absence is NOT foreign: your_posts*.json has no per-record author because the
    file itself scopes authorship to the owner. Only an explicit, non-matching
    name is grounds for a drop.
    """
    author = container.get("author")
    if not isinstance(author, str) or not author.strip():
        return False
    repaired = unicodedata.normalize("NFC", fix_mojibake(author)).strip()
    foreign = repaired.casefold() not in {n.casefold() for n in OWNER_NAMES}
    if foreign:
        FOREIGN_AUTHOR_CENSUS[repaired] += 1
    return foreign


def comment_body(node):
    """Return (text_or_None, foreign_author) for one data[] node's comment field.

    Split out of extract_bodies purely to keep that function under the project's
    lizard -C 15 ceiling; adding the owner-isolation check inline pushed it to 16.
    data[].comment is a dict in comments.json and the group union, but a bare
    string in some shards, so both shapes are handled. Only the dict shape can
    carry an author, so only it can report foreign.
    """
    comment = node.get("comment")
    if isinstance(comment, dict):
        if author_is_other(comment):
            return None, True
        inner = comment.get("comment")
        return (inner if isinstance(inner, str) and inner.strip() else None), False
    if isinstance(comment, str) and comment.strip():
        return comment, False
    return None, False


def extract_bodies(record, diag):
    """Yield (node_kind, text) for every authored-prose node in data[].

    SCANS the array: data[0]["post"] is wrong, because 27% of data[] members are
    literally {} and a real record can read
        [{"post": "..."}, {"update_timestamp": ...}, {}, {}]   (R3 s2.3)
    Authored fields, in R1 s4 rank order: data[].post (primary) and
    data[].comment.comment (group posts + comments). data[].text is an
    undocumented stringified fallback -- taken, but flagged so it is auditable.
    """
    data = record.get("data")
    if isinstance(data, dict):  # mock-only shape; one line of defence (R3 s2.4)
        data = [data]
    found = []
    fallback = []
    foreign_author = False
    for node in data or []:
        if not isinstance(node, dict):
            continue
        post = node.get("post")
        if isinstance(post, str) and post.strip():
            found.append(("post", post))
        body, foreign = comment_body(node)
        if foreign:
            foreign_author = True
            continue
        if body:
            found.append(("comment", body))
        text = node.get("text")
        if isinstance(text, str) and text.strip():
            fallback.append(("text", text))
    # B0-ADV: the `text` fallback used to be gated on `not found`, which is
    # ORDER-DEPENDENT. data == [{"text": ...}, {"post": ...}] appended the
    # undocumented fallback FIRST, and build_record takes bodies[0] -- so the real
    # authored post was silently discarded whenever a text node preceded it.
    # `text` is a fallback by RANK (R1 s4), not by position: it is now consulted
    # only after the whole array has been scanned for authored post/comment nodes.
    if not found and fallback:
        found = fallback[:1]
        diag.data_text_fallback += 1
    return found, foreign_author


def scan_attachments(record, diag):
    """Return (external_contexts, has_media). Unknown union keys are counted and
    reported, never asserted on -- the published schema is already incomplete
    against real data (R3 s2.4)."""
    attachments = record.get("attachments")
    if isinstance(attachments, dict):  # mock-only shape (R3 s2.4)
        attachments = [attachments]
    contexts, has_media = [], False
    for wrapper in attachments or []:
        if not isinstance(wrapper, dict):
            continue
        nodes = wrapper.get("data")
        if isinstance(nodes, dict):
            nodes = [nodes]
        for node in nodes or []:
            if not isinstance(node, dict):
                continue
            for key, value in node.items():
                if key == "external_context" and isinstance(value, dict):
                    contexts.append(value)
                elif key == "media":
                    has_media = True
                elif key not in (
                    "place",
                    "event",
                    "for_sale_item",
                    "life_event",
                    "text",
                    "name",
                ):
                    diag.unknown_attachment_keys[key] += 1
    return contexts, has_media


# ---------------------------------------------------------------------------
# 7. TITLE PATTERNS -- ADVISORY ONLY, never grounds for a drop (R3 s0.1, s5)
# ---------------------------------------------------------------------------
# Enumerated from real archives (R3 s7). English and German only: the Romanian
# row is deliberately EMPTY because no Romanian DYI archive could be found to
# read the strings off, and inventing them would be worse than omitting them.
# UNVERIFIED -- the Romanian equivalents of these templates are unknown; the
# experiment that settles it is the "title catalogue" this script prints on every
# run (see Diagnostics.report), which is exactly R3's recommended
# Counter(p.get('title')).most_common(40) probe. Paste its output into
# research/R3-original-vs-share.md s7 to close that gap.
# Because these are advisory, a Romanian archive costs only the review flag, not
# a misclassification: R3 measured that the LENGTH filter alone removes 99.1% of
# posts made on other people's timelines, with no language dependence at all.
WALL_POST_TITLE_RE = re.compile(
    r"wrote on .*(?:timeline|profile)"
    r"|hat etwas in .*Chronik geschrieben",
    re.IGNORECASE,
)
RESHARE_TITLE_RE = re.compile(
    r"shared a (?:post|photo|memory|product)"
    r"|hat (?:einen Beitrag|ein Foto) geteilt"
    r"|likes a link"
    r"|created the group"
    r"|was with "
    r"|is feeling ",
    re.IGNORECASE,
)


def title_flag(title):
    if not title:
        return None
    if WALL_POST_TITLE_RE.search(title):
        return "wall-post?"
    if RESHARE_TITLE_RE.search(title):
        return "reshare?"
    return None


# ---------------------------------------------------------------------------
# 8. DIAGNOSTICS -- a zero-record run must state WHY
# ---------------------------------------------------------------------------


class Diagnostics:
    def __init__(self):
        self.members_scanned = 0
        self.excluded_files = []
        self.candidate_files = []  # (path, kind)
        self.parsed_ok = 0
        self.parse_errors = []  # (path, message)
        self.schema_errors = []  # (path, message)
        self.records_seen = 0
        self.wrappers_seen = Counter()
        self.novel_wrappers = Counter()
        self.malformed_records = 0
        self.data_text_fallback = 0
        self.extra_bodies_dropped = 0  # B0-ADV: build_record keeps bodies[0]
        # only. A record whose data[] holds MORE
        # THAN ONE authored node loses the rest
        # SILENTLY -- it is neither emitted nor
        # counted under any drop reason, so the
        # conservation arithmetic in the report
        # still balances while prose goes
        # missing. Counted here so the loss is
        # at least visible; whether to emit the
        # extras as separate records is an owner
        # decision (it changes record identity).
        self.unknown_attachment_keys = Counter()
        self.drops = Counter()
        self.duplicates = 0  # authored, but identical to an earlier
        # record of the same kind -- reported
        # apart from self.drops because a
        # duplicate IS the owner's writing and
        # counting it under "not authored"
        # hides owner-isolation regressions
        # inside a benign-looking total.
        self.kinds = Counter()
        self.tiers = Counter()
        self.titles = Counter()
        self.title_flags = Counter()
        self.reshare_overrides = 0  # B1-ADV: substantial bodies KEPT despite
        # the n=5 external_context.url=="" marker.
        self.json_basenames = []  # for the "nothing matched" diagnosis
        self.top_level_entries = []
        self.notes = []

    # -- the "why did I get nothing" logic ---------------------------------
    def zero_reason(self, kept):
        if kept:
            return None
        if not self.candidate_files:
            return (
                "NO CANDIDATE FILES MATCHED.\n"
                "  Looked for, anywhere in the tree (case-insensitive):\n"
                "    posts    : your_posts*.json\n"
                "    groups   : your_posts_and_comments_in_groups*.json, "
                "your_comments_in_groups*.json, groups/*.json\n"
                "    comments : your_comments*.json, comments.json, comments_v2.json\n"
                "  This is the top silent-failure mode of the Facebook rail: Meta has\n"
                "  renamed both the posts file and its parent directory at least three\n"
                "  times. If the archive genuinely holds posts under a NEW name, add it\n"
                "  to POST_FILE_RE -- do not assume the archive is empty.\n"
                "  Archive top level: %s\n"
                "  .json files found: %s"
                % (
                    self.top_level_entries[:25] or "(empty)",
                    self.json_basenames[:40] or "(none)",
                )
            )
        if self.records_seen == 0:
            detail = "; ".join(
                "%s: %s" % (p, m)
                for p, m in (self.schema_errors + self.parse_errors)[:5]
            )
            return (
                "CANDIDATE FILES WERE FOUND BUT YIELDED ZERO RECORDS.\n"
                "  %d file(s) matched, %d parsed. Schema/parse problems: %s"
                % (
                    len(self.candidate_files),
                    self.parsed_ok,
                    detail or "(none reported)",
                )
            )
        return (
            "RECORDS WERE PARSED BUT EVERY ONE WAS DROPPED.\n"
            "  %d records seen. Drop reasons: %s\n"
            "  If 'no-body' dominates, the archive's authored text is not in\n"
            "  data[].post / data[].comment.comment -- inspect one record by hand.\n"
            "  If 'reshare-empty-url' dominates, re-run with "
            "--keep-empty-url-shares: that marker is only measured at n=5."
            % (self.records_seen, dict(self.drops) or "(none)")
        )

    def report(self, out, kept, substantial, words, cleaner, args):
        w = out.write
        w("\n" + "=" * 72 + "\n")
        w("FACEBOOK ISOLATION REPORT  --  owner: %s\n" % OWNER_NAME)
        w("=" * 72 + "\n")
        self._report_discovery(w)
        self._report_parse(w)
        self._report_encoding(w, cleaner, args)
        self._report_filtering(w)
        self._report_kept(w, kept, substantial, words, args)
        self._report_titles(w)
        for note in self.notes:
            w("\n  note: %s\n" % note)

    def _report_discovery(self, w):
        w("\n[discovery]\n")
        w("  members scanned         : %d\n" % self.members_scanned)
        w("  candidate files         : %d\n" % len(self.candidate_files))
        for kind, count in sorted(Counter(k for _, k in self.candidate_files).items()):
            w("      %-20s: %d\n" % (kind, count))
        for path, kind in self.candidate_files[:25]:
            w("      [%s] %s\n" % (kind, path))
        if len(self.candidate_files) > 25:
            w("      ... and %d more\n" % (len(self.candidate_files) - 25))
        w("  excluded by rule        : %d\n" % len(self.excluded_files))

    def _report_parse(self, w):
        w("\n[parse]\n")
        w("  files parsed OK         : %d\n" % self.parsed_ok)
        w("  records seen            : %d\n" % self.records_seen)
        w(
            "  wrapper keys seen       : %s\n"
            % (dict(self.wrappers_seen) or "(bare arrays)")
        )
        if self.novel_wrappers:
            w(
                "  NOVEL wrapper keys      : %s  <- schema drift; verify these\n"
                % dict(self.novel_wrappers)
            )
        if self.malformed_records:
            w(
                "  malformed records       : %d  (no timestamp and no data)\n"
                % self.malformed_records
            )
        if self.data_text_fallback:
            w(
                "  data[].text fallback    : %d  (undocumented field; audit these)\n"
                % self.data_text_fallback
            )
        if FOREIGN_AUTHOR_CENSUS:
            w(
                "  not-owner author census : %s\n"
                "                            <- if one of these is YOU under an older or\n"
                "                               diacritic spelling, re-run with\n"
                "                               --owner-name '<that spelling>'.\n"
                % dict(FOREIGN_AUTHOR_CENSUS.most_common(10))
            )
        if self.extra_bodies_dropped:
            w(
                "  EXTRA authored bodies   : %d  <- records held >1 authored node; only\n"
                "                                the first was emitted. This prose is NOT\n"
                "                                in the corpus and NOT in any drop reason.\n"
                % self.extra_bodies_dropped
            )
        if self.unknown_attachment_keys:
            w("  unknown attachment keys : %s\n" % dict(self.unknown_attachment_keys))
        for path, message in self.parse_errors:
            w("  PARSE ERROR  %s: %s\n" % (path, message))
        for path, message in self.schema_errors:
            w("  SCHEMA ERROR %s: %s\n" % (path, message))

    def _report_encoding(self, w, cleaner, args):
        w("\n[encoding]  -- GROUNDING trap #1\n")
        w("  strings examined        : %d\n" % cleaner.seen)
        w(
            "  mojibake repaired       : %d (%.1f%%)\n"
            % (cleaner.repaired, 100.0 * cleaner.repaired / max(1, cleaner.seen))
        )
        w("  NFC changed             : %d\n" % cleaner.nfc_changed)
        w(
            "  legacy cedilla chars    : %d %s\n"
            % (
                cleaner.cedilla_chars,
                "(folded to comma-below)"
                if args.normalize_cedilla
                else "(left as-is; --normalize-cedilla to fold)",
            )
        )
        if cleaner.repaired == 0 and cleaner.seen:
            w(
                "  NOTE: zero repairs. Either Meta fixed the defect, or the text is\n"
                "        ASCII-only. Confirm by eye on one Romanian post before\n"
                "        concluding the archive is clean.\n"
            )

    def _report_filtering(self, w):
        w("\n[filtering]\n")
        w("  dropped (not authored)  : %d\n" % sum(self.drops.values()))
        for reason, count in self.drops.most_common():
            w("      %-20s: %d\n" % (reason, count))
        w(
            "  collapsed as duplicate  : %d  (authored; same kind + same text)\n"
            % self.duplicates
        )
        if self.reshare_overrides:
            w(
                "  reshare marker overridden: %d  (substantial body kept despite "
                "external_context.url=='')\n" % self.reshare_overrides
            )
        w("  title review flags      : %s\n" % (dict(self.title_flags) or "(none)"))

    def _report_kept(self, w, kept, substantial, words, args):
        w("\n[kept]  -- graded, nothing deleted for length\n")
        w("  owner-authored records  : %d\n" % kept)
        for kind, count in self.kinds.most_common():
            w("      %-20s: %d\n" % (kind, count))
        w(
            "  tiers (prose words)     : A>=%d  B>=%d  C>=%d  D<%d\n"
            % (TIER_A_WORDS, MIN_PROSE_WORDS, TIER_C_WORDS, TIER_C_WORDS)
        )
        for tier in ("A", "B", "C", "D"):
            w("      tier %s              : %d\n" % (tier, self.tiers.get(tier, 0)))
        w(
            "  substantial (>=%d words) : %d  (~%s words of writing)\n"
            % (args.min_words, substantial, format(words, ","))
        )

    def _report_titles(self, w):
        # R3's recommended settling experiment for the localisation gap, run
        # automatically: 40 lines of output closes the Romanian title question.
        w("\n[title catalogue]  -- top 40 raw `title` values, AFTER mojibake repair.\n")
        w("  Titles are auto-generated AND localized; this script never classifies\n")
        w("  on them. Paste this into research/R3 s7 to close the Romanian gap.\n")
        if self.titles:
            for title, count in self.titles.most_common(40):
                w("      %5d  %s\n" % (count, title[:110]))
        else:
            w("      (no title field present on any record)\n")


# ---------------------------------------------------------------------------
# 9. THE PIPELINE
# ---------------------------------------------------------------------------


def classify_file(path):
    """Return the record kind for a member path, or None to skip it."""
    if EXCLUDE_RE.search(path):
        return None
    if GROUP_FILE_RE.search(path):
        return "group"
    if POST_FILE_RE.search(path):
        return "post"
    if COMMENT_FILE_RE.search(path):
        return "comment"
    return None


def discover(archives, diag, include_groups):
    """Walk every archive and collect the files worth parsing."""
    found = []
    for archive in archives:
        for name in sorted(archive.members()):
            diag.members_scanned += 1
            if name.lower().endswith(".json"):
                diag.json_basenames.append(name)
            if "/" not in name.strip("/"):
                diag.top_level_entries.append(name)
            elif name.count("/") == 1:
                diag.top_level_entries.append(name.split("/")[0] + "/")
            if EXCLUDE_RE.search(name):
                if name.lower().endswith(".json"):
                    diag.excluded_files.append(name)
                continue
            kind = classify_file(name)
            if kind is None:
                continue
            if kind == "group" and not include_groups:
                diag.excluded_files.append(name)
                continue
            found.append((archive, name, kind))
            diag.candidate_files.append((name, kind))
    diag.top_level_entries = sorted(set(diag.top_level_entries))
    return found


def load_records(archive, name, kind, diag):
    """Parse one member into a list of raw records. Never loads the archive."""
    try:
        size = archive.size(name)
    except (KeyError, OSError):
        size = 0
    if size > LARGE_FILE_WARN_BYTES:
        diag.notes.append(
            "%s is %.0f MB -- parsed whole. If memory is tight, switch this file "
            "to a streaming parser (ijson)." % (name, size / 1e6)
        )
    try:
        raw = archive.read_bytes(name)
        # utf-8-sig strips a BOM if present; json.loads on raw bytes would choke.
        obj = json.loads(raw.decode("utf-8-sig", errors="replace"))
    except (ValueError, OSError) as exc:
        diag.parse_errors.append((name, "%s: %s" % (type(exc).__name__, exc)))
        return []
    try:
        records, wrapper, novel = unwrap(obj, name)
    except SchemaError as exc:
        diag.schema_errors.append((name, str(exc)))
        return []
    diag.parsed_ok += 1
    if wrapper:
        diag.wrappers_seen[wrapper] += 1
        if novel:
            diag.novel_wrappers[wrapper] += 1
    records = flatten_if_nested(records, name, diag)
    return [(r, kind) for r in records if isinstance(r, dict)]


def to_iso(value):
    """Meta emits Unix SECONDS (R1:151). Guard against a milliseconds variant."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return None, None
    if seconds > 10_000_000_000:  # milliseconds
        seconds //= 1000
    if seconds <= 0:
        return None, None
    try:
        stamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None, seconds
    return stamp.strftime("%Y-%m-%d %H:%M:%S"), seconds


def drop_reason(body, contexts, args):
    """Return why this body is not the owner's prose, or None to keep it.

    Bodies that are only markup are not writing: a real reshare in the measured
    corpus had body == "@[100001208381643:2048:Dennis Leps]" (R3 s4(b)), and
    bare-URL bodies were observed in a real Spanish archive (R3 s4(d)).

    The empty-string external_context.url is a LANGUAGE-INDEPENDENT reshare
    marker -- 5/5 correct across two languages in the measured corpus.
    UNVERIFIED at scale (n=5): the experiment is to count these on the real
    archive and eyeball 20 of them. The per-run count is printed under
    [filtering], and --keep-empty-url-shares disables it if it misfires.

    B1-ADV: that marker is NEVER allowed to delete a SUBSTANTIAL body. Sharing
    someone else's post with your own long take is ordinary Facebook behaviour,
    the share target is a Facebook-internal object so external_context.url is ""
    -- and the commentary on top is exactly the owner's writing this corpus
    exists to collect. VERIFIED by execution before the guard: a 300-prose-word
    body plus external_context {"url": ""} returned "reshare-empty-url" and the
    record was deleted, visible only as a counter. An n=5 heuristic must not
    outrank the length signal R3 measured at 99.1% precision, so the marker now
    applies only BELOW the substantial floor; at or above it the record is kept
    and counted under reshare_marker_overridden so the decision stays auditable.
    """
    if _MENTION_ONLY.match(body):
        return "mention-only"
    if _URL_ONLY.match(body):
        return "url-only"
    if args.keep_empty_url_shares:
        return None
    if any(isinstance(c, dict) and c.get("url") == "" for c in contexts):
        if prose_words(body) >= args.min_words:
            return "keep:reshare-marker-overridden"
        return "reshare-empty-url"
    return None


def record_kind(file_kind, node_kind):
    """Label a record by the file it came from and the data[] node that held it."""
    if file_kind == "group":
        return "group_comment" if node_kind == "comment" else "group_post"
    if node_kind == "comment":
        return "comment"
    return "comment" if file_kind == "comment" else "post"


def build_record(raw, file_kind, source, clean, diag, args):
    """Apply the R3 predicates. Returns a dict to keep, or None (drop counted)."""
    if "timestamp" not in raw and "data" not in raw:
        diag.malformed_records += 1
        diag.drops["malformed"] += 1
        return None

    title = clean(raw.get("title") or "")
    if title:
        diag.titles[title] += 1

    bodies, foreign_author = extract_bodies(raw, diag)
    if len(bodies) > 1:
        diag.extra_bodies_dropped += len(bodies) - 1
    if not bodies:
        # "not-owner" is reported separately from "no-body": a record dropped
        # because someone else wrote it is a very different archive fact from a
        # record that carried no prose at all, and conflating them would hide
        # owner-isolation failures inside a benign-looking counter.
        diag.drops["not-owner" if foreign_author else "no-body"] += 1
        return None
    node_kind, raw_body = bodies[0]
    body, mojibake_repaired = clean.clean(raw_body)
    body = body.strip()
    if not body:
        diag.drops["no-body"] += 1
        return None

    contexts, has_media = scan_attachments(raw, diag)
    reason = drop_reason(body, contexts, args)
    if reason and reason.startswith("keep:"):
        # B1-ADV: a substantial body that tripped the n=5 reshare marker. It is
        # KEPT (the length signal outranks the marker) but the override is
        # counted so the decision is visible in the report, never silent.
        diag.reshare_overrides += 1
        reason = None
    if reason:
        diag.drops[reason] += 1
        return None

    # A link share WITH the owner's own commentary is his writing and is KEPT --
    # 46% of link-shares carried commentary in the measured corpus (R3 s3.1). A
    # bare reshare has no body and has already been dropped above as "no-body".
    # external_context.name is the LINK's headline, never the owner's words, so
    # it is deliberately not concatenated into the corpus (R1 s4 row 8).
    flag = title_flag(title)
    if flag:
        diag.title_flags[flag] += 1
    iso, unix = to_iso(raw.get("timestamp"))
    n_prose = prose_words(body)

    return {
        "ts": iso,
        "ts_unix": unix,
        "platform": "facebook",
        "kind": record_kind(file_kind, node_kind),
        "source": source,
        "chars": len(body),
        "words": len(body.split()),
        "prose_words": n_prose,
        "tier": tier_of(n_prose),
        "title": title or None,
        "title_flag": flag,
        "has_external_link": bool(contexts),
        "has_media": has_media,
        "mojibake_repaired": mojibake_repaired,
        "content": body,
    }


def dedupe(records, diag):
    """De-duplicate by BODY TEXT, not timestamp: Facebook 'Memories' re-shares
    republish older content under a new timestamp (R1:416). Earliest wins.

    Keyed on (kind, text), NOT on text alone. The Memories case R1:416 actually
    documents is a timeline post republishing a timeline post, so keying within
    a kind still collapses it. Text alone additionally collapses a CROSS-POST --
    the same essay published to the owner's timeline and to a group, which is
    ordinary behaviour and two genuinely distinct authorship events in two
    different venues. EXPECTED.json pins that pair (fb-post-017 and
    fb-grouppost-001 share one sha256 across two files, 22 days apart) and
    expects both; text-only keying silently discarded the group one.
    """
    records.sort(key=lambda r: (r["ts_unix"] is None, r["ts_unix"] or 0))
    seen, out = set(), []
    for record in records:
        key = (record["kind"], " ".join(record["content"].split()).casefold())
        if key in seen:
            diag.duplicates += 1
            continue
        seen.add(key)
        out.append(record)
    return out


# ---------------------------------------------------------------------------
# 10. OUTPUT
# ---------------------------------------------------------------------------

SEP = "-" * 72


def format_entry(record):
    head = "[%s] (%s | %s)" % (
        record["ts"] or "no-timestamp",
        record["kind"],
        os.path.basename(record["source"]),
    )
    return "%s\n%s\n%s" % (head, record["content"], SEP)


def write_outputs(records, outdir, min_words):
    """Three outputs, mirroring the Discord run. Bodies are long-form and
    multi-line, so entries carry an explicit header + rule rather than the
    one-line-per-message layout isolate_discord.py used."""
    os.makedirs(outdir, exist_ok=True)
    paths = {
        "all": os.path.join(outdir, "%s_all.txt" % OUT_PREFIX),
        "substantial": os.path.join(outdir, "%s_substantial.txt" % OUT_PREFIX),
        "jsonl": os.path.join(outdir, "%s.jsonl" % OUT_PREFIX),
    }
    substantial = [r for r in records if r["prose_words"] >= min_words]

    with open(paths["all"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(format_entry(r) for r in records))
        fh.write("\n")
    with open(paths["substantial"], "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(format_entry(r) for r in substantial))
        fh.write("\n")
    with open(paths["jsonl"], "w", encoding="utf-8", newline="\n") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return paths, substantial


# ---------------------------------------------------------------------------
# 11. CLI
# ---------------------------------------------------------------------------


def parse_args(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Isolate %s's own Facebook posts, comments and group posts "
        "from a DYI export (directory or .zip)." % OWNER_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "archive",
        nargs="?",
        default=os.path.join(here, "Facebook"),
        help="DYI archive root: an unzipped directory, a .zip, or a directory "
        "containing the .zip parts. Default: ./Facebook",
    )
    parser.add_argument(
        "-o", "--outdir", default=None, help="output directory (default: ./Facebook)"
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=MIN_PROSE_WORDS,
        help="prose-word floor for the _substantial view "
        "(default: %d = tier B)" % MIN_PROSE_WORDS,
    )
    parser.add_argument(
        "--tier-a-only",
        action="store_true",
        help="shorthand for --min-words %d (essay tier)" % TIER_A_WORDS,
    )
    parser.add_argument(
        "--no-groups",
        dest="include_groups",
        action="store_false",
        help="exclude group posts and group comments "
        "(default: include; they averaged 523 chars in the "
        "measured corpus and are the owner's own writing)",
    )
    parser.add_argument(
        "--keep-empty-url-shares",
        action="store_true",
        help="disable the external_context.url == '' reshare "
        "marker (only measured at n=5)",
    )
    parser.add_argument(
        "--owner-name",
        action="append",
        default=[],
        metavar="NAME",
        help="additional spelling of the owner's Facebook display "
        "name to treat as the owner (repeatable). A display "
        "name is mutable across years; without this, comments "
        "signed with an older or diacritic spelling are dropped "
        "as not-owner. See the author census in the report.",
    )
    parser.add_argument(
        "--normalize-cedilla",
        action="store_true",
        help="fold legacy s/t-cedilla to the correct comma-below "
        "forms; LOSSY and off by default",
    )
    args = parser.parse_args(argv)
    OWNER_NAMES.update(n.strip() for n in args.owner_name if n and n.strip())
    if args.tier_a_only:
        args.min_words = TIER_A_WORDS
    if args.outdir is None:
        args.outdir = os.path.join(here, "Facebook")
    return args


def force_utf8_console():
    """A Romanian title catalogue printed to a cp1252 Windows console raises
    UnicodeEncodeError and kills the run at the last step. Reconfigure first."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    force_utf8_console()
    args = parse_args(argv)
    diag = Diagnostics()
    clean = TextCleaner(normalize_cedilla=args.normalize_cedilla)

    archives = open_archives(args.archive)
    print("archive(s):")
    for archive in archives:
        print("  %s" % archive.label)

    try:
        targets = discover(archives, diag, args.include_groups)
        records = []
        for archive, name, kind in targets:
            for raw, file_kind in load_records(archive, name, kind, diag):
                diag.records_seen += 1
                built = build_record(raw, file_kind, name, clean, diag, args)
                if built is not None:
                    records.append(built)
        records = dedupe(records, diag)
    finally:
        for archive in archives:
            archive.close()

    for record in records:
        diag.kinds[record["kind"]] += 1
        diag.tiers[record["tier"]] += 1

    paths, substantial = write_outputs(records, args.outdir, args.min_words)
    words = sum(r["words"] for r in substantial)

    buffer = io.StringIO()
    diag.report(buffer, len(records), len(substantial), words, clean, args)
    sys.stdout.write(buffer.getvalue())

    reason = diag.zero_reason(len(records))
    if reason:
        sys.stdout.write("\n" + "!" * 72 + "\n")
        sys.stdout.write("ZERO RECORDS EMITTED -- %s\n" % reason)
        sys.stdout.write("!" * 72 + "\n")
    else:
        sys.stdout.write(
            "\n  -> %s\n  -> %s\n  -> %s\n"
            % (paths["all"], paths["substantial"], paths["jsonl"])
        )

    if reason:
        return 3 if not diag.candidate_files else 2
    if diag.schema_errors:
        sys.stdout.write(
            "\nWARNING: %d file(s) had an unrecognised schema (listed above). The\n"
            "output is INCOMPLETE -- do not treat this corpus as the full archive.\n"
            % len(diag.schema_errors)
        )
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
