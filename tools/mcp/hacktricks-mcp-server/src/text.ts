// Control/bidi character handling shared by input validation and citation-label
// normalization. The escape TEXT is assembled from plain ASCII so this source
// file never carries a literal control byte.

function hex4(n: number): string {
  return `\\u${n.toString(16).padStart(4, "0")}`;
}

// C0 (0x00-0x1F), DEL + C1 (0x7F-0x9F), and the bidi controls LRM/RLM,
// LRE..RLO/PDF (0x202A-0x202E) and LRI..PDI (0x2066-0x2069).
const STRIP_RANGES: ReadonlyArray<readonly [number, number]> = [
  [0x0000, 0x001f],
  [0x007f, 0x009f],
  [0x200e, 0x200f],
  [0x202a, 0x202e],
  [0x2066, 0x2069],
];

const CLASS_BODY = STRIP_RANGES.map(([a, b]) => `${hex4(a)}-${hex4(b)}`).join("");
const STRIP_GLOBAL = new RegExp(`[${CLASS_BODY}]`, "gu");
const STRIP_TEST = new RegExp(`[${CLASS_BODY}]`, "u");

export function stripControlAndBidi(value: string): string {
  return value.replace(STRIP_GLOBAL, "");
}

export function hasControlOrBidi(value: string): boolean {
  return STRIP_TEST.test(value);
}
