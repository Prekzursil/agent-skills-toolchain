// Trusted provenance adapter: canonical URLs, immutable permalinks, and citation
// label normalization. URLs are CONSTRUCTED here, never copied from page metadata.

import { CITATION_LABEL_MAX_CHARS } from "./limits.js";
import { stripControlAndBidi } from "./text.js";

export type Book = "main" | "cloud";

export const CORPUS_REPOSITORY_MAIN =
  "https://github.com/HackTricks-wiki/hacktricks";
export const CORPUS_REPOSITORY_CLOUD =
  "https://github.com/HackTricks-wiki/hacktricks-cloud";
export const PINNED_CORPUS_COMMIT = "346301958c8bf94120ba0aaaaf9cd963997bdac3";
export const CANONICAL_HOST_MAIN = "hacktricks.wiki";
export const CANONICAL_HOST_CLOUD = "cloud.hacktricks.wiki";

// Normalize a git origin URL for comparison against the official repository:
// strip a trailing ".git" and a trailing slash and lowercase the whole thing.
export function normalizeOrigin(url: string): string {
  let out = url.trim();
  if (out.endsWith(".git")) {
    out = out.slice(0, -4);
  }
  if (out.endsWith("/")) {
    out = out.slice(0, -1);
  }
  return out.toLowerCase();
}

export function repositoryFor(book: Book): string {
  return book === "cloud" ? CORPUS_REPOSITORY_CLOUD : CORPUS_REPOSITORY_MAIN;
}

export function canonicalHostFor(book: Book): string {
  return book === "cloud" ? CANONICAL_HOST_CLOUD : CANONICAL_HOST_MAIN;
}

// Map a validated src-rooted relative markdown path to its published canonical URL.
// - src/README.md        -> https://<host>/en/index.html
// - src/<rel>/README.md  -> https://<host>/en/<rel>/index.html
// - src/<rel>.md         -> https://<host>/en/<rel>.html
export function canonicalUrl(book: Book, srcPath: string): string {
  const host = canonicalHostFor(book);
  // srcPath is guaranteed to start with "src/" and end with ".md" by validation.
  const rel = srcPath.slice("src/".length, -".md".length);
  const segments = rel.split("/");
  const last = segments[segments.length - 1];
  const dirSegments = segments.slice(0, -1);
  const suffix = last === "README" ? "index.html" : `${last}.html`;
  const encoded = dirSegments.map((s) => encodeURIComponent(s));
  const pathPart = encoded.length > 0 ? `${encoded.join("/")}/` : "";
  return `https://${host}/en/${pathPart}${suffix}`;
}

export function immutablePermalink(
  book: Book,
  fullSha: string,
  srcPath: string,
): string {
  const repo = repositoryFor(book);
  const encoded = srcPath
    .split("/")
    .map((s) => encodeURIComponent(s))
    .join("/");
  return `${repo}/blob/${fullSha}/${encoded}`;
}

const MARKDOWN_DELIMITERS = /[\\`*_[\]()<>#]/g;

// Normalize an untrusted page title/heading into a safe, bounded citation label.
export function normalizeLabel(raw: string): string {
  let s = raw.normalize("NFC");
  s = stripControlAndBidi(s);
  s = s.replace(MARKDOWN_DELIMITERS, (ch) => `\\${ch}`);
  s = s.replace(/\s+/g, " ").trim();
  if (s.length > CITATION_LABEL_MAX_CHARS) {
    s = s.slice(0, CITATION_LABEL_MAX_CHARS);
  }
  return s;
}
