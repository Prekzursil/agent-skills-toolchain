---
name: frontend-a11y
description: >
  Accessibility patterns for React and Next.js — semantic HTML, ARIA attributes,
  form labeling, keyboard navigation, focus management, and screen reader support.
  Use when building any interactive UI component or form.
origin: community
---

# Frontend Accessibility Patterns

Practical accessibility patterns for React and Next.js. Covers the issues most commonly flagged in code review: missing form labels, incorrect ARIA usage, non-semantic interactive elements, and broken keyboard navigation.

## When to Activate

- Building or reviewing form components (`<input>`, `<select>`, `<textarea>`)
- Creating interactive elements (modals, dropdowns, tooltips, tabs)
- Using `<div>` or `<span>` with `onClick`
- Adding `aria-*` attributes to any element
- Implementing keyboard navigation or focus management
- Receiving accessibility feedback from code review tools (CodeRabbit, ESLint a11y)
- Building components that must support screen readers

## Form Accessibility

Missing `htmlFor` / `id` pairing and disconnected error messages are the most common issues flagged in code review.

### Label Connection

```tsx
// BAD: label has no connection to input — screen readers cannot associate them
<label>Email</label>
<input type="email" />

// GOOD: htmlFor matches input id
<label htmlFor="email">Email</label>
<input id="email" type="email" />
```

### Required Fields

```tsx
// BAD: visual-only asterisk conveys nothing to screen readers
<label htmlFor="email">Email *</label>
<input id="email" type="email" />

// GOOD: required enables native browser validation; aria-required signals it to screen readers
<label htmlFor="email">
  Email <span aria-hidden="true">*</span>
</label>
<input id="email" type="email" required aria-required="true" />

### Error Messages
### Complete Accessible Form
### Semantic HTML
### ARIA Attributes
### aria-label vs aria-labelledby
### aria-describedby
### aria-live for Dynamic Content
### aria-expanded and aria-controls
### Keyboard Navigation
