---
name: social-corpus-extraction
description: 'Use when building a personal writing/style corpus from a user''s OWN
  messages and posts across Discord, Facebook posts + comments, Facebook Messenger,
  and WhatsApp — isolating only the owner''s authored text, then folding every source
  into one deduplicated jsonl corpus. Handles the traps that silently break these
  extractions: the Meta DYI double-encoded-UTF-8 mojibake, the 4-way Facebook post-path
  drift, WhatsApp-DYI-has-no-message-bodies, and locale-dependent title strings. NOT
  for scraping other people''s content, NOT a live-API social client (see social-media-toolchain),
  NOT for one specific person''s hardcoded identity — every script takes the owner
  identity by argv/env.'
permalink: dqverify-repo-20261013/skills/social-corpus-extraction/skill
---

# social-corpus-extraction

Turn a user's own social-media history into a clean, deduplicated **writing corpus** (for style
analysis, fine-tuning, or personal archive). Five stdlib-only Python scripts under `scripts/`, each
mirroring the same three-output shape (`<owner>_all.txt`, `<owner>_substantial.txt`, `<owner>.jsonl`)
plus a unifier. **Classify structurally, never by language** — the owner's archive may be in any
locale, and every locale-dependent heuristic is a bug (see gotcha 4).

## The rails, and which actually carry the owner's WRITING

| Source | Rail | What you get |
|---|---|---|
| Discord | DiscordChatExporter JSON | full history — `isolate_discord.py` (reference impl) |
| Facebook posts + comments | Meta "Download Your Information" (JSON, All-time) | full history — `isolate_facebook.py` |
| Facebook Messenger | same DYI zip, `messages/inbox/` | full history — `isolate_messenger.py` |
| WhatsApp | **phone-side only** — per-chat "Export chat" `_chat.txt`, or the on-device DB | `isolate_whatsapp.py` |
| WhatsApp via Meta DYI | ❌ **NO message bodies** — account metadata only (gotcha 3) | — |
| a live MCP rail (`social-hub`) | partial recent window only (Baileys ~4-5 days) | supplements, never replaces the export |

Then `build_corpus.py` folds every per-source `.jsonl` into one deduplicated corpus with a MANIFEST
that accounts for every dropped record under a named reason.

## The four traps (each cost real debugging — do not rediscover)

1. **Meta DYI mojibake is double-encoded UTF-8, and the naive fix silently corrupts.**
   Meta emits `Ä`+U+0083 where `ă` belongs. `s.encode('latin-1').decode('utf-8')` is the correct
   *inverse* but NOT safe: on an already-clean string with Latin-1-range chars it raises (so a
   try/except returns it UNREPAIRED and silent); on a mixed string with any char > U+00FF it raises
   too. **Gate the repair on a detector** (a UTF-8-run regex) and run it **after `json.loads`** —
   Meta double-escapes ASCII metacharacters too (`"`→bare `"`), so raw-byte repair yields
   JSONDecodeError. NEVER apply it to client-written UTF-8 (Discord, WhatsApp `_chat.txt`) — it
   CREATES corruption. `build_corpus.py` applies repair only to facebook/messenger sources.

2. **The Facebook post path drifted ≥4×**: `posts/your_posts.json` → `posts/your_posts_1.json` →
   `your_facebook_activity/posts/your_posts__check_ins__photos_and_videos_1.json` →
   `your_activity_across_facebook/...`. A pipeline pinned to one path finds **zero** posts in a
   2024+ archive. `isolate_facebook.py` globs all known roots and exits non-zero (naming the file)
   on an unrecognised schema — never silently emits empty.

3. **WhatsApp DYI export contains NO message text** (WhatsApp Help Center, verbatim; E2EE means Meta
   has no plaintext). The owner's WhatsApp history is obtainable ONLY client-side: iPhone → device
   backup → `ChatStorage.sqlite`; Android → 64-digit-key backup → `crypt15` → `wa-crypt-tools`; or
   in-app per-chat "Export chat" `_chat.txt` (manual, most-recent-N). `isolate_whatsapp.py` reads
   the `_chat.txt` / DB-JSON, never the DYI zip.

4. **Classify structurally, not by locale keyword.** Meta's auto-generated `title`/notification
   strings are localized; an English regex silently misclassifies a non-English archive. Key on JSON
   structure + prose length. The min-length floor is the single most load-bearing,
   language-independent predicate (it removed 99.1% of posts-on-others'-timelines in the reference run).

## Usage

```
python scripts/isolate_facebook.py  --owner-name "Full Name" --owner-name "alt spelling"   # DYI zip/dir in ./Facebook
python scripts/isolate_messenger.py --root ./Facebook --me "Full Name"
python scripts/isolate_whatsapp.py  <path-to-_chat.txt-or-db.json> --owner-name "<display name>"
python scripts/build_corpus.py       # auto-discovers every per-source .jsonl, writes corpus/{corpus.jsonl,corpus.md,MANIFEST.md}
```
Every script is **stdlib-only, Windows/Unix, streams per-file** (never `json.load` a multi-GB export
whole). Owner identity is argv/env — no identity is hardcoded. Exit 4 from `isolate_facebook.py` =
an unrecognised schema; the corpus is INCOMPLETE — read the printed filename, extend the glob.

## Honest limits

Fixture-green does NOT prove real-archive-correct — the fixtures encode our assumptions about a Meta
export that had not yet arrived when these were written. Treat the first real run as an experiment:
read `MANIFEST.md`'s drop accounting, and do not treat exit-0 as proof of completeness — proof is the
owner reading `corpus.md` and recognising their own writing. See `references/method.md`.