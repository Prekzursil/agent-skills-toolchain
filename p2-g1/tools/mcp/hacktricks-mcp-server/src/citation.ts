// Offline, revision-pinned citation receipt builders. Titles/headings are
// normalized to safe bounded labels; URLs are constructed by the provenance
// adapter, never copied from page metadata.

import { titleFor } from "./markdown.js";
import {
  type Book,
  canonicalUrl,
  immutablePermalink,
  normalizeLabel,
  repositoryFor,
} from "./provenance.js";
import { byteLength } from "./util.js";

export interface SearchHit {
  book: Book;
  title: string;
  path: string;
  heading: string;
  line: number;
  snippet: string;
  canonical_url: string;
  repository: string;
  revision: string;
  source_blob: string | null;
}

export function buildSearchHit(args: {
  book: Book;
  path: string;
  title: string;
  heading: string;
  line: number;
  snippet: string;
  revision: string;
  sourceBlob: string | null;
}): SearchHit {
  return {
    book: args.book,
    title: normalizeLabel(args.title),
    path: args.path,
    heading: normalizeLabel(args.heading),
    line: args.line,
    snippet: args.snippet,
    canonical_url: canonicalUrl(args.book, args.path),
    repository: repositoryFor(args.book),
    revision: args.revision,
    source_blob: args.sourceBlob,
  };
}

export interface PageReceipt {
  book: Book;
  title: string;
  path: string;
  requested_heading: string | null;
  returned_heading: string | null;
  canonical_url: string;
  immutable_url: string;
  repository: string;
  revision: string;
  source_blob: string | null;
  corpus_committed_at: string;
  retrieved_at: string;
  content_bytes: number;
  truncated: boolean;
  content: string;
}

export function buildPageReceipt(args: {
  book: Book;
  path: string;
  content: string;
  requestedHeading: string | null;
  returnedHeading: string | null;
  revision: string;
  sourceBlob: string | null;
  corpusCommittedAt: string;
  retrievedAt: string;
  truncated: boolean;
}): PageReceipt {
  return {
    book: args.book,
    title: normalizeLabel(titleFor(args.content, args.path)),
    path: args.path,
    requested_heading:
      args.requestedHeading === null ? null : normalizeLabel(args.requestedHeading),
    returned_heading:
      args.returnedHeading === null ? null : normalizeLabel(args.returnedHeading),
    canonical_url: canonicalUrl(args.book, args.path),
    immutable_url: immutablePermalink(args.book, args.revision, args.path),
    repository: repositoryFor(args.book),
    revision: args.revision,
    source_blob: args.sourceBlob,
    corpus_committed_at: args.corpusCommittedAt,
    retrieved_at: args.retrievedAt,
    content_bytes: byteLength(args.content),
    truncated: args.truncated,
    content: args.content,
  };
}
