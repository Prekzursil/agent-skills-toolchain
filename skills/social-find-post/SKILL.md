---
name: social-find-post
description: Use when the user wants to find, recall, or locate a specific social-media
  post, reel, or saved/bookmarked item across Instagram (saved collections, feed,
  search) or Facebook (feed/profile). Pairs with the social-media-toolchain MCPs.
permalink: dqverify-repo-20261013/skills/social-find-post/skill
---

# Find a Social Post

## Overview

Locate a specific post the user is trying to recall, across their connected accounts. The fastest path depends on **where the item lives** — figure that out first; it often collapses the search. See [[social-media-toolchain]] for the servers, tools, and limits.

## Step 1 — Clarify target + location (before any tool call)

Ask (briefly) what the post is and where they saw it:
- A **public** post / someone's profile → no account access needed; just navigate the public web.
- In **their Instagram** (Saved, their posts, liked, a DM) → use `insta-mcp`.
- In **their Facebook** (feed, their posts, saved) → drive `facebook.com` in their logged-in browser.

## Step 2 — Instagram (`insta-mcp`)

- **Saved collections:** `get_saved_posts`.
- **Their own / a user's recent posts:** `get_recent_posts`.
- **By keyword / hashtag / account:** `search_instagram`.
- **Liked history:** `get_liked_posts`.
- **In a DM:** `get_inbox` → `get_direct_messages` (or use [[social-dm-search]]).

If the IG MCP tools aren't loaded yet (registered but Claude Code not restarted), run the capability directly via a one-shot Node script against the saved session in `~/source/repos/insta-mcp` (the `InstagramClient` exposes the same methods).

## Step 3 — Facebook feed / posts / saved (browser)

There is **no FB API path** for feed/saved and **no FB app** on the user's BlueStacks. Drive their **logged-in `facebook.com`** session (Claude-in-Chrome / Playwright):
- Navigate to their profile / Saved (`facebook.com/saved`) / a target profile.
- Scroll + screenshot; read the content visually to locate the post.
- Confirm the find with a screenshot/link.

## Step 4 — Present

Return the post (link + a 1-line description, or a screenshot). If searching was inconclusive, say what was searched and what's left to try — never imply full coverage that wasn't done.

## Guardrails

- Read-only by default. Do not like/comment/share/save without explicit confirmation.
- If a platform throws a checkpoint/challenge, stop and surface it (ban-risk).