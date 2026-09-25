---
name: visual-regression-guard
description: Use when modifying React/UI components in repositories with Chromatic or Applitools visual testing gates, or when a visual regression test fails in CI
---

# Visual regression guard

## Overview

**Every component change needs a story. Every story needs a snapshot.** This skill ensures UI component modifications include Storybook coverage and avoid patterns that cause visual regression failures in Chromatic and Applitools.

## When to use

- Modifying any React component in a repo with `.storybook/` directory
- Adding new UI components that will be rendered in the browser
- A Chromatic or Applitools check has failed on a PR
- Changing CSS, Tailwind classes, or styled-components

## Pre-change checklist

Before modifying ANY component:

1. **Check for existing story** — look in `*.stories.tsx` / `*.stories.jsx` next to the component
2. **If no story exists** — create one BEFORE making changes (establishes baseline)
3. **Identify visual states** — list all variants: default, hover, active, disabled, loading, error, empty, responsive breakpoints
4. **Check for animation** — animated components need `disableAnimation` prop or Chromatic `delay` parameter

## Story requirements

Every component MUST have stories covering:

```typescript
// ComponentName.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { ComponentName } from './ComponentName';

const meta: Meta<typeof ComponentName> = {
  component: ComponentName,
  title: 'Components/ComponentName',
  // Chromatic: capture at multiple viewports
  parameters: {
    chromatic: {
      viewports: [375, 768, 1280],
    },
  },
};
export default meta;

type Story = StoryObj<typeof ComponentName>;

// Required: default state
export const Default: Story = {
  args: { /* default props */ },
};

// Required: every user-facing variant
export const Loading: Story = {
  args: { isLoading: true },
};

export const Error: Story = {
  args: { error: 'Something went wrong' },
};

export const Empty: Story = {
  args: { items: [] },
};

// Required if component is interactive
export const Disabled: Story = {
  args: { disabled: true },
};
```

## Patterns that cause failures

### Non-deterministic renders

```tsx
// ❌ Fails — different timestamp every snapshot
<span>{new Date().toLocaleDateString()}</span>

// ✅ Use a fixed date in stories
export const Default: Story = {
  decorators: [
    (Story) => {
      vi.useFakeTimers({ now: new Date('2024-01-15') });
      return <Story />;
    },
  ],
};

// ❌ Fails — random avatar colors
const color = `hsl(${Math.random() * 360}, 70%, 50%)`;

// ✅ Derive from deterministic input
const color = `hsl(${hashString(user.name) % 360}, 70%, 50%)`;
```

### Animation and transitions

```tsx
// ❌ Fails — screenshot captures mid-animation
<motion.div animate={{ opacity: 1 }} transition={{ duration: 0.3 }}>

// ✅ Disable in Chromatic
const isChromatic = process.env.CHROMATIC === 'true';
<motion.div
  animate={{ opacity: 1 }}
  transition={{ duration: isChromatic ? 0 : 0.3 }}
>

// Or use Chromatic delay parameter in story
export const Animated: Story = {
  parameters: {
    chromatic: { delay: 500 }, // wait for animation to complete
  },
};
```

### Responsive layout shifts

```tsx
// ❌ Fails at certain viewports — text wraps unpredictably
<div style={{ width: '100%' }}>Long title that might wrap</div>

// ✅ Test at all relevant breakpoints
parameters: {
  chromatic: {
    viewports: [375, 768, 1024, 1280],
  },
},
```

### External resources

```tsx
// ❌ Fails — external image might be unavailable or change
<img src="https://example.com/photo.jpg" />

// ✅ Use local assets or mock in stories
export const WithImage: Story = {
  args: {
    imageUrl: '/storybook-assets/placeholder.png',
  },
};
```

## When a visual test fails

1. **Open the Chromatic/Applitools diff view** — compare baseline vs new
2. **Determine if change is intentional:**
   - YES: Accept the new baseline in Chromatic UI / Applitools dashboard
   - NO: Identify the cause using patterns above
3. **Common false positives:**
   - Font rendering differences (anti-aliasing varies by OS) — use `diffThreshold` parameter
   - Sub-pixel rendering — set `chromatic: { diffThreshold: 0.2 }` for affected stories
   - Dynamic content (dates, random IDs) — mock them deterministically

## Applitools-specific

```typescript
// applitools.config.js
module.exports = {
  testConcurrency: 5,
  matchLevel: 'Strict', // or 'Layout' for responsive tests
  browser: [
    { width: 1280, height: 720, name: 'chrome' },
    { width: 375, height: 812, name: 'chrome' }, // mobile
  ],
};
```

When modifying shared layouts or design tokens, use `matchLevel: 'Layout'` to allow minor pixel shifts while catching structural regressions.

## Integration with other skills

- **gate-zero-enforcer** — visual tests are part of the CI gate; failures block merge
- **test-driven-development** — write the story BEFORE changing the component (visual TDD)
- **skill-router** — only loads this skill when `.storybook/` or Chromatic/Applitools config detected
