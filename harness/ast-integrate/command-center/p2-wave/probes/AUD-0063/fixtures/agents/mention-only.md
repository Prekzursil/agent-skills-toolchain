---
name: mention-only-lookup
description: Control fixture whose body mentions sonnet
model: opus
tools: Read, Grep
---

This agent looks up docs. It talks about sonnet in prose so a body grep
would mis-assign it. The frontmatter model field is opus, not sonnet.
Do not classify this file as sonnet.
