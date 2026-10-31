---
title: method
type: note
permalink: dqverify-repo-20261013/skills/social-corpus-extraction/references/method
---

# Method — corpus design + drop-reason taxonomy

## Output shape (every isolator mirrors this)

- `<owner>_all.txt` — every owner message/post, `[<ts19>] <content>`, chronological. The complete record.
- `<owner>_substantial.txt` — only records over the length floor (the "long posts, not short
  thank-you" bar). Per-medium: Discord/FB posts ~150 chars; WhatsApp chat ~80 (a lower bar, because
  chat messages are short by nature). This is the *writing* view.
- `<owner>.jsonl` — `{ts, len, content}` (+ `chat`/`source` where relevant) for downstream tooling.

## Isolating "the owner" per source

- **Discord**: `author.id` == owner id (most reliable) OR `author.name` == owner handle.
- **Facebook posts**: keep records whose authored body is in `data[].post` / `media.description` /
  group `comment.comment` / `life_event.title`; drop where the comment author != owner.
- **Messenger**: `sender_name` == owner (pass BOTH the ASCII and correct-diacritic spelling via
  `--me`, or a legitimately-authored message signed with the exact-diacritic name is dropped as a
  foreign author — a real defect caught in review).
- **WhatsApp**: `is_from_me == true` (DB/MCP rail) or phone-number match on the last 9 digits
  (`_chat.txt` rail has no owner field — display-name matching is brittle; the DB rail is preferred).
  The script REFUSES rather than guesses when it cannot identify the owner.

## build_corpus.py drop-reason taxonomy (each dropped record counted under exactly one reason)

| Reason | Removes | Why |
|---|---|---|
| not-owner-author | comments/messages signed by someone else | isolate "me" |
| no-body | pure reshares, pure attachments, empty `{}` data | not the owner's prose |
| below-min-words | genuine but under the length floor | the "not short" bar — graded, still emitted at a low tier, NOT deleted |
| reshare-empty-url | a reshare with `external_context.url == ""` AND body below floor | cross-lingual reshare marker; gated below `--min-words` so a real commentary-on-a-share is KEPT |
| dedupe | exact duplicate | sharded exports overlap |

**Do NOT filter by the `title` field** — it is auto-generated, localized, and mojibake corrupts it;
a title regex is wrong in both directions (a large fraction of "shared a link" posts carry the
owner's own commentary; the owner's longest posts often have no title at all).

## PII / privacy

This corpus is private conversations. `build_corpus.py` supports an opt-in redaction pass; decide
per use what to redact (phone numbers, addresses, third-party names) before any corpus leaves the
owner's machine. The corpus DATA never belongs in a git repo — only this tooling does.