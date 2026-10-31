---
name: clone-website
description: Use when the user wants to clone, replicate, reverse-engineer, or create
  a pixel-perfect copy of a website or web app as a single self-contained HTML prototype
  — extracts design tokens, assets, computed CSS, interaction patterns, and content
  via Playwright, then rebuilds one dependency-free HTML file.
permalink: dqverify-repo-20261013/skills/clone-website/skill
---

<!-- Source: cherry-picked from https://github.com/coco-research/coco (skills/clone-website) on 27.08.2026 per grill decision G-11/11B; itself adapted from https://github.com/JCodesMore/ai-website-cloner-template. Adapted to house format; coco brain-DB integration removed. -->

# Clone Website — Single-File HTML Prototype Builder

Reverse-engineer one or more target URLs into a pixel-perfect single-file HTML prototype:

- **One HTML file** with `<style>` + markup + `<script>` sections
- **Zero external dependencies** — all CSS inline, all JS inline, all assets base64-encoded or SVG inline
- **Real data injection** — actual data from the project's files where available, not lorem ipsum
- **Project design system** when available — use tokens from a `design-system.json` colocated with the project

## Pre-Flight

1. **Playwright is required.** Verify: `npx playwright --version`. If missing, install (`npm i -D playwright`) or use the resident Playwright MCP.
2. Validate each target URL is accessible.
3. Create an output directory for captured assets (e.g. `{project}/Screenshots-clone/`).
4. Determine clone mode:
   - **Full clone** (default): pixel-perfect reproduction of the entire page
   - **Design extraction only**: capture design tokens, screenshots, and component specs without building
   - **Selective clone** (e.g. "header,table,sidebar"): clone only named sections

## Phase 1: Reconnaissance (Playwright)

### 1.1 Screenshots

```javascript
import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(URL);
await page.screenshot({ path: 'full-desktop.png', fullPage: true });
await page.screenshot({ path: 'viewport-desktop.png' });
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({ path: 'viewport-mobile.png', fullPage: true });
```

### 1.2 Design Token Extraction

Run in `page.evaluate()`:

```javascript
const tokens = await page.evaluate(() => {
  const colorMap = new Map();
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    ['color','backgroundColor','borderColor','borderTopColor','borderBottomColor'].forEach(p => {
      const v = cs[p];
      if (v && v !== 'rgba(0, 0, 0, 0)' && v !== 'transparent') colorMap.set(v, (colorMap.get(v)||0)+1);
    });
  });
  const fontMap = new Map();
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    const key = `${cs.fontFamily}|${cs.fontSize}|${cs.fontWeight}|${cs.lineHeight}`;
    fontMap.set(key, (fontMap.get(key)||0)+1);
  });
  const spacingSet = new Set(), shadowSet = new Set(), radiusSet = new Set();
  document.querySelectorAll('*').forEach(el => {
    const cs = getComputedStyle(el);
    ['padding','margin','gap'].forEach(p => { const v = cs[p]; if (v && v !== '0px') spacingSet.add(v); });
    if (cs.boxShadow && cs.boxShadow !== 'none') shadowSet.add(cs.boxShadow);
    if (cs.borderRadius && cs.borderRadius !== '0px') radiusSet.add(cs.borderRadius);
  });
  return {
    colors: [...colorMap.entries()].sort((a,b) => b[1]-a[1]).slice(0,30),
    typography: [...fontMap.entries()].sort((a,b) => b[1]-a[1]).slice(0,20),
    spacing: [...spacingSet].sort(),
    shadows: [...shadowSet],
    radii: [...radiusSet].sort()
  };
});
```

### 1.3 Component CSS Extraction (Deep)

For each major component/section, extract exact computed styles recursively (depth ≤ 4), keeping only meaningful values:

```javascript
const componentCSS = await page.evaluate((selector) => {
  const el = document.querySelector(selector);
  if (!el) return null;
  const props = [
    'fontSize','fontWeight','fontFamily','lineHeight','letterSpacing','color',
    'textTransform','textDecoration','backgroundColor','background',
    'padding','paddingTop','paddingRight','paddingBottom','paddingLeft',
    'margin','marginTop','marginRight','marginBottom','marginLeft',
    'width','height','maxWidth','minWidth','display','flexDirection',
    'justifyContent','alignItems','gap','gridTemplateColumns',
    'borderRadius','border','boxShadow','overflow','position',
    'top','right','bottom','left','zIndex','opacity','transform','transition'
  ];
  function extract(element, depth) {
    if (depth > 4) return null;
    const cs = getComputedStyle(element);
    const styles = {};
    props.forEach(p => {
      const v = cs[p];
      if (v && v !== 'none' && v !== 'normal' && v !== 'auto' && v !== '0px' && v !== 'rgba(0, 0, 0, 0)')
        styles[p] = v;
    });
    return {
      tag: element.tagName.toLowerCase(),
      classes: element.className?.toString().split(' ').slice(0,5).join(' '),
      text: element.childNodes.length === 1 && element.childNodes[0].nodeType === 3
        ? element.textContent.trim().slice(0,200) : null,
      styles,
      children: [...element.children].slice(0,20).map(c => extract(c, depth+1)).filter(Boolean)
    };
  }
  return extract(el, 0);
}, selector);
```

### 1.4 Interaction Sweep

- **Scroll sweep:** step `window.scrollTo` in ~300px increments; watch for sticky headers and scroll-triggered animations.
- **Hover sweep:** hover `button, a, [role="tab"], .nav-item, .card` (cap ~30 elements).
- **Click sweep:** click tabs/dropdowns (`[role="tab"], .tab-item, .nav-tab`) and observe state changes.

### 1.5 Asset Extraction

- Extract all inline `<svg>` elements as code (with parent class and dimensions).
- Collect all `<img>` URLs with alt text and natural dimensions for download/base64 embedding.

## Phase 2: Foundation Build

Convert extracted tokens into CSS custom properties (`--color-bg`, `--color-text`, `--color-accent`, `--font-family`, `--shadow-sm`, ...), mapped to semantic names.

## Phase 3: Section Building

For each major section of the page:

1. Write a spec with exact CSS values + screenshot + content
2. Build the section's HTML + CSS + JS (dispatch parallel builder subagents only if the environment allows it — on RAM-constrained boxes build sequentially)
3. **Complexity budget:** if a section spec exceeds ~150 lines, split it

## Phase 4: Assembly

1. Deduplicate CSS — combine all section styles, remove duplicates
2. Order HTML — sections in visual order (top to bottom)
3. Combine JS — all event handlers and render functions in one `<script>` block
4. Base64-encode any images that couldn't be replaced with CSS/SVG
5. Verify: open in browser, compare against original screenshots

## Phase 5: Quality Check

Use Playwright to open the built HTML file, re-screenshot at the same viewpoints as Phase 1, compare side-by-side, test all interactions (clicks, hovers, tabs), and report visual differences.

## Project-Specific Mode

When a `design-system.json` exists in the project: load its tokens as CSS custom properties in the output, and inject any real data the project references (Excel, JSON).