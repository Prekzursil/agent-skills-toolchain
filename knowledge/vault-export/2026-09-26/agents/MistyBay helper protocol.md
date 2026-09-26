---
title: MistyBay helper protocol
type: note
permalink: main/agents/misty-bay-helper-protocol
---

# MistyBay helper protocol

Goose is wired as a helper peer on project `estate`.

- Agent: **MistyBay**
- Program/model: goose
- Contact policy: **open** (accept inbound mail without handshake)
- Role: execute help requests with developer tools and reply with results
- Out of scope: git writes, control-plane ownership, file-reservation ownership

## How other agents request help
1. Address agent-mail to `MistyBay` on project `estate`.
2. Put a concrete task in the subject/body (paths, expected output, constraints).
3. Wait for a reply with results, not a broadcast.
4. Keep git commits and control-plane actions on the requesting agent.

## How MistyBay responds
1. Fetch inbox as MistyBay.
2. Acknowledge the request.
3. Execute with local developer tools.
4. Reply on the same thread with findings/results.
5. Do not take git writes or control-plane ownership.

## Current session
- Registration: active
- Inbox at last poll: empty
- Live registered peers at last poll: none (historical names FoggyGrove, OliveCompass, BlackRaven, estate-lens-1 are not currently registered)