// Deterministic, fence-aware Markdown parsing: heading outline, revision-pinned
// heading-aware section extraction, and ordinary triple-backtick code blocks.
// Recognizes ATX headings and ordinary triple-backtick fences only (no tilde
// fences, no indented code), matching the documented upstream behavior.

export interface Heading {
  level: number;
  text: string;
  line: number;
}

export interface SectionHit {
  requestedHeading: string;
  returnedHeading: string;
  content: string;
  matchCount: number;
}

const FENCE = /^```/;

function splitLines(md: string): string[] {
  return md.split(/\r?\n/);
}

export function parseOutline(md: string): Heading[] {
  const lines = splitLines(md);
  const headings: Heading[] = [];
  let inFence = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i] as string;
    if (FENCE.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) {
      continue;
    }
    if (line.startsWith("#")) {
      let level = 0;
      while (line[level] === "#") {
        level++;
      }
      if (level <= 6 && line[level] === " ") {
        headings.push({ level, text: line.slice(level + 1).trim(), line: i + 1 });
      }
    }
  }
  return headings;
}

export function firstH1(md: string): string | null {
  const h1 = parseOutline(md).find((h) => h.level === 1);
  if (h1 === undefined) {
    return null;
  }
  return h1.text;
}

export function titleFor(md: string, fallback: string): string {
  const h1 = firstH1(md);
  if (h1 === null) {
    return fallback;
  }
  return h1;
}

// Case-insensitive PARTIAL heading match; returns the first matching heading
// through the next heading at the same or higher level (or EOF).
export function extractSection(md: string, section: string): SectionHit | null {
  const headings = parseOutline(md);
  const lines = splitLines(md);
  const needle = section.toLowerCase();
  const matches = headings.filter((h) => h.text.toLowerCase().includes(needle));
  const first = matches[0];
  if (first === undefined) {
    return null;
  }
  let endLine = lines.length;
  for (const h of headings) {
    if (h.line > first.line && h.level <= first.level) {
      endLine = h.line - 1;
      break;
    }
  }
  const content = lines.slice(first.line - 1, endLine).join("\n");
  return {
    requestedHeading: section,
    returnedHeading: first.text,
    content,
    matchCount: matches.length,
  };
}

// Ordinary triple-backtick fenced blocks (including their fence lines). An
// unterminated final fence is discarded. Returns at most `max` blocks.
export function extractCodeBlocks(md: string, max: number): string[] {
  const lines = splitLines(md);
  const blocks: string[] = [];
  let inFence = false;
  let current: string[] = [];
  for (const line of lines) {
    if (FENCE.test(line)) {
      if (inFence) {
        current.push(line);
        blocks.push(current.join("\n"));
        current = [];
        inFence = false;
      } else {
        inFence = true;
        current = [line];
      }
    } else if (inFence) {
      current.push(line);
    }
  }
  return blocks.slice(0, max);
}
