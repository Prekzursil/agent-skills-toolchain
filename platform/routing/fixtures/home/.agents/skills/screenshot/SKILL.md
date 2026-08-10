---
name: "screenshot"
description: "Use when the user explicitly asks for a desktop or system screenshot (full screen, specific app or window, or a pixel region), or when tool-specific capture capabilities are unavailable and an OS-level capture is needed."
---


# Screenshot Capture

Follow these save-location rules every time:

1) If the user specifies a path, save there.
2) If the user asks for a screenshot without a path, save to the OS default screenshot location.
3) If Codex needs a screenshot for its own inspection, save to the temp directory.

## Tool priority

- Prefer tool-specific screenshot capabilities when available (for example: a Figma MCP/skill for Figma files, or Playwright/agent-browser tools for browsers and Electron apps).
- Use this skill when explicitly asked, for whole-system desktop captures, or when a tool-specific capture cannot get what you need.
- Otherwise, treat this skill as the default for desktop apps without a better-integrated capture tool.

## macOS permission preflight (reduce repeated prompts)

On macOS, run the preflight helper once before window/app capture. It checks
Screen Recording permission, explains why it is needed, and requests it in one
place.

The helpers route Swift's module cache to `$TMPDIR/codex-swift-module-cache`
to avoid extra sandbox module-cache prompts.

```bash
bash <path-to-skill>/scripts/ensure_macos_permissions.sh
```

To avoid multiple sandbox approval prompts, combine preflight + capture in one
command when possible:

```bash
bash <path-to-skill>/scripts/ensure_macos_permissions.sh && \
python3 <path-to-skill>/scripts/take_screenshot.py --app "Codex"
```

For Codex inspection runs, keep the output in temp:

```bash
bash <path-to-skill>/scripts/ensure_macos_permissions.sh && \

### macOS and Linux (Python helper)
### Workflow examples
### Multi-display behavior
### Linux prerequisites and selection logic
### Windows (PowerShell helper)
### Direct OS commands (fallbacks)
### macOS
### Linux
### Error handling
