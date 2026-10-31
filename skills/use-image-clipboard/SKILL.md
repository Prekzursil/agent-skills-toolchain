---
name: use-image-clipboard
description: Use when needing to read an image from the Windows clipboard and save
  it to a temporary PNG file on disk, returning its path for downstream use in scripts
  or pipelines. Required workaround for Antigravity CLI, which does not support direct
  image paste (Alt+V) the way Claude Code and Codex CLI do.
permalink: dqverify-repo-20261013/skills/use-image-clipboard/skill
---

# Use Image from Clipboard

## Overview

**Antigravity CLI does not support direct image paste** (the Alt+V shortcut available in Claude Code and Codex CLI). This skill is the workaround: it reads an image from the Windows clipboard via `.NET System.Windows.Forms` and saves it as a PNG to a temp path, emitting the file path so Antigravity can pick it up with its image-viewing tool.

## When to Use

Use this skill when:
- You want to share a screenshot or clipboard image with Antigravity and it cannot accept it via direct paste
- You need to materialise clipboard image data as a file path for further analysis or upload
- Running any PowerShell workflow that needs clipboard image access on Windows

**Not for:** macOS/Linux, non-image clipboard content (text, files), or Claude Code/Codex sessions where Alt+V paste works natively.

## The Problem This Solves

| CLI | Native image paste | This skill needed? |
|---|---|---|
| Claude Code | ✅ Alt+V | No |
| Codex CLI | ✅ Alt+V | No |
| **Antigravity CLI** | ❌ Not supported | **Yes** |

## Workflow

1. Take a screenshot or copy any image to the clipboard (Print Screen, Snipping Tool, Win+Shift+S, etc.)
2. Run the script below in PowerShell — it outputs a file path
3. Pass that path to Antigravity using its `view_file` tool on the returned path

## Script

```powershell
Add-Type -AssemblyName System.Windows.Forms
if ([System.Windows.Forms.Clipboard]::ContainsImage()) {
    $img = [System.Windows.Forms.Clipboard]::GetImage()
    $tempPath = [System.IO.Path]::Combine($env:TEMP, "cli_screenshot.png")
    $img.Save($tempPath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output $tempPath
} else {
    Write-Error "No image in clipboard."
}
```

Alternatively, run it inline from a one-liner:

```powershell
powershell -Command "Add-Type -AssemblyName System.Windows.Forms; if ([System.Windows.Forms.Clipboard]::ContainsImage()) { $img = [System.Windows.Forms.Clipboard]::GetImage(); $p = [System.IO.Path]::Combine($env:TEMP, 'cli_screenshot.png'); $img.Save($p, [System.Drawing.Imaging.ImageFormat]::Png); Write-Output $p } else { Write-Error 'No image in clipboard.' }"
```

## Quick Reference

| Detail | Value |
|---|---|
| Output | Absolute path to saved PNG (stdout) |
| Error path | `Write-Error` if clipboard has no image |
| Output filename | `cli_screenshot.png` (fixed; overwritten each call) |
| Requires | Windows, PowerShell 5.1+, .NET Framework (built-in on all modern Windows) |
| Assembly loaded | `System.Windows.Forms` |
| Typical save location | `C:\Users\<you>\AppData\Local\Temp\cli_screenshot.png` |

## Common Mistakes

| Mistake | Fix |
|---|---|
| Running on macOS/Linux | Use platform-specific clipboard tools; this is Windows-only |
| Running when no image is in clipboard | `ContainsImage()` guards against crashes — copy an image first |
| Expecting unique filenames per call | The path is always `cli_screenshot.png`; rename/copy after if you need multiple |
| Piping the error output | `Write-Error` writes to PowerShell's error stream, not stdout; check `$?` or wrap in `try/catch` |
| Trying Alt+V in Antigravity | Not supported — use this script instead |

## Integration Example

After running the script and getting back a path like `C:\Users\you\AppData\Local\Temp\cli_screenshot.png`, tell Antigravity:

> "Please view the image at `C:\Users\you\AppData\Local\Temp\cli_screenshot.png`"

Antigravity will use its `view_file` tool to load and analyse the image.