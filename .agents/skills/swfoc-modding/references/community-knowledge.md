# Community Knowledge and Caveats

Use this file for practical patterns when official docs are silent. Validate critical claims against current build behavior.

## Tiered Trust
- Higher trust: long-lived Revora technical threads and active maintainers' guides.
- Medium trust: Steam guides with clear update history and reproducible steps.
- Lower trust: old tutorials (still useful for concepts, often outdated tooling links).

## High-Value Community References

### Steam beginner modding guide (2022, updated 2023)
Source: https://steamcommunity.com/sharedfiles/filedetails/?id=2812662575

Useful takeaways:
- clean starter folder structure
- emphasis on no-space mod names (for launch robustness)
- practical tool list and starter flow
- reminder to keep submods lightweight and permission-aware

### Revora XML coding tutorial
Source: https://forums.revora.net/topic/109328-eaw-coding-tutorial-coding-in-xml-for-dummies/

Useful for:
- object/XML entry mental model
- beginner-safe step-by-step edits
- common naming/registration mistakes

### Revora map editor guides
Sources:
- https://forums.revora.net/topic/60390-eaw-map-editor-tutorial/
- https://forums.revora.net/topic/45288-guide-to-map-making-and-map-editor-tips/

Useful for:
- map editor onboarding
- map composition pitfalls and practical editor workflow

### ModDB long-form beginner tutorial (2010)
Source: https://www.moddb.com/games/star-wars-empire-at-war/tutorials/beginners-tutorial-for-modding-empire-at-war-forces-of-corruption

Still useful for:
- conceptual end-to-end flow (extract -> structure -> model/hardpoint -> XML registration)
- understanding how older community workflows were structured

Caveat:
- old tooling links, old assumptions, and outdated launcher context.

### Fandom modding hub and AI guide
Sources:
- https://focumentation.fandom.com/wiki/Empire_at_War_Modding_Hub_Wiki
- https://focumentation.fandom.com/wiki/AI_Guide

Useful for:
- topic index and cross-links for AI framework concepts
- community-maintained conceptual docs

Caveat:
- variable depth/quality by page and editor recency.

## Practical Community Patterns Worth Preserving
- Keep a minimal reproducible mod skeleton for each test branch.
- Split XML and Lua changes into small commits to simplify fault isolation.
- Treat AI behavior changes as data + script + load-order problems, not just script logic.
- For submods, document parent dependency and expected install path exactly.
