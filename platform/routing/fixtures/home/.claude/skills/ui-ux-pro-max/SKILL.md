---
name: ui-ux-pro-max
description: Use when designing UI/UX for web or mobile apps and needing opinionated style, color palette, font pairing, or chart-type recommendations from a searchable database of 67 styles, 96 palettes, 57 font pairings, and 99 UX guidelines across 13 stacks ; do NOT use for code implementation or pixel-perfect Figma work ; returns ranked design recommendations.
---
# ui-ux-pro-max

Comprehensive design guide for web and mobile applications. Contains 67 styles, 96 color palettes, 57 font pairings, 99 UX guidelines, and 25 chart types across 13 technology stacks. Searchable database with priority-based recommendations.

## Prerequisites

Check if Python is installed:

```bash
python3 --version || python --version
```

If Python is not installed, install it based on user's OS:

**macOS:**
```bash
brew install python3
```

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install python3
```

**Windows:**
```powershell
winget install Python.Python.3.12
```

---

## How to Use This Skill

When user requests UI/UX work (design, build, create, implement, review, fix, improve), follow this workflow:

### Step 1: Analyze User Requirements

Extract key information from user request:
- **Product type**: SaaS, e-commerce, portfolio, dashboard, landing page, etc.
- **Style keywords**: minimal, playful, professional, elegant, dark mode, etc.
- **Industry**: healthcare, fintech, gaming, education, etc.
- **Stack**: React, Vue, Next.js, or default to `html-tailwind`

### Step 2: Generate Design System (REQUIRED)

**Always start with `--design-system`** to get comprehensive recommendations with reasoning:

```bash
python3 skills/ui-ux-pro-max/scripts/search.py "<product_type> <industry> <keywords>" --design-system [-p "Project Name"]
```

This command:
1. Searches 5 domains in parallel (product, style, color, landing, typography)
2. Applies reasoning rules from `ui-reasoning.csv` to select best matches

### Step 2b: Persist Design System (Master + Overrides Pattern)
### Step 3: Supplement with Detailed Searches (as needed)
### Step 4: Stack Guidelines (Default: html-tailwind)
### Search Reference
### Available Domains
### Available Stacks
### Example Workflow
### Step 1: Analyze Requirements
### Step 2: Generate Design System (REQUIRED)
