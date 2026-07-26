// Named, documented operational limits for the hardened HackTricks MCP server.
// These are exported so tests can assert exact boundaries (spec: "Adopt and export
// these named, documented limits; add exact boundary tests").

export const MAX_QUERY_CHARS = 512;
export const MAX_PATH_CHARS = 1024;
export const MAX_SECTION_CHARS = 512;
export const DEFAULT_SEARCH_RESULTS = 20;
export const MAX_SEARCH_RESULTS = 50;
export const SEARCH_TIMEOUT_MS = 15000;
export const RG_MAX_BUFFER_BYTES = 2097152;
export const MAX_FILE_BYTES = 524288;
export const MAX_SECTION_BYTES = 131072;
export const MAX_OUTLINE_BYTES = 65536;
export const MAX_CHEATSHEET_BYTES = 131072;
export const MAX_QUICK_LOOKUP_BYTES = 196608;
export const MAX_CATEGORY_TREE_NODES = 2000;
export const MAX_CATEGORY_DEPTH = 3;
export const MAX_TOOL_RESPONSE_BYTES = 524288;
export const CITATION_LABEL_MAX_CHARS = 160;
export const MAX_REMOTE_RETRIES = 2;
export const MAX_UNCACHED_RAG_CALLS_PER_FINDING = 1;
export const STALE_SOURCE_DAYS = 30;

// Number of code fences quick lookup may return (spec: "no more than five").
export const MAX_QUICK_LOOKUP_BLOCKS = 5;
// Sampled match cap per file used when invoking ripgrep (spec: --max-count 3).
export const RG_MAX_COUNT = 3;
// Bounded byte cap for the text `content` projection retained for client compat.
export const MAX_TEXT_PROJECTION_BYTES = 4096;
// Bounded caps for the online citation verifier.
export const VERIFY_MAX_RESPONSE_BYTES = 262144;
export const VERIFY_MAX_REDIRECT_HOPS = 5;
