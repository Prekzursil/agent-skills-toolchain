// ORIGIN: tools/web/agentify-desktop/orchestrator/security.mjs
//
// SURVIVED THE RETIREMENT because path containment is architecture-independent: any tool that
// writes under an allowed root needs it, and nothing in it knew about a browser or an Electron
// shell. The retirement (agentify-desktop / promptbridge-talk-lane / codex-orchestrator /
// agent-lanes-*) removed every consumer; the predicate itself outlives them.
//
// It uses path.relative rather than a naive startsWith, so `C:\allowedother\x` is correctly
// rejected against root `C:\allowed`. That part is carried over verbatim.
//
// TWO DEFECTS FIXED HERE - the original shipped them and its own test suite never caught them
// because it never tried a second volume:
//   1. CROSS-VOLUME. On Windows path.relative('C:\\allowed\\root','D:\\x') returns the ABSOLUTE
//      'D:\\x', which neither starts with '..\\' nor equals '..', so the original returned true
//      for any path on another drive. Measured: shipped predicate returns true for
//      'D:\\anything\\at\\all'. Fixed by comparing path.parse().root first.
//   2. UNC. path.relative('C:\\a\\root','\\\\evil.example\\share\\x') likewise returns the
//      absolute UNC path -> original returned true. A UNC target coerces an outbound SMB/NTLM
//      authentication (hash leak / relay), so it is rejected outright on Windows semantics.
//
// pathImpl is injectable so Windows semantics can be exercised deterministically from a POSIX
// CI runner: pass `path.win32`. Default is the host platform's `path`.

import nodePath from 'node:path';

export function normalizeAbs(p, pathImpl = nodePath) {
  return pathImpl.resolve(String(p || '').trim());
}

/**
 * True when `p` uses Windows UNC form (\\server\share\...). Only meaningful under Windows
 * semantics - on POSIX a backslash is a legal filename character, so this always returns false
 * there rather than mangling legitimate names.
 */
export function isUncPath(p, pathImpl = nodePath) {
  if (pathImpl.sep !== '\\') return false;
  return /^[\\/]{2}/.test(String(p || ''));
}

function sameVolume(a, b, pathImpl) {
  const ra = pathImpl.parse(a).root;
  const rb = pathImpl.parse(b).root;
  // Windows paths are case-insensitive and `path.win32.parse('c:\\x').root` preserves the
  // lowercase drive letter, so a case-sensitive compare would falsely reject 'c:\\' vs 'C:\\'.
  if (pathImpl.sep === '\\') return ra.toUpperCase() === rb.toUpperCase();
  return ra === rb;
}

export function isPathWithin({ filePath, allowedRoots, pathImpl = nodePath }) {
  const raw = String(filePath || '').trim();
  if (!raw) return false;

  const fp = normalizeAbs(raw, pathImpl);
  if (isUncPath(fp, pathImpl)) return false; // DEFECT FIX 2

  const roots = Array.isArray(allowedRoots)
    ? allowedRoots.map((r) => normalizeAbs(r, pathImpl))
    : [];
  if (!roots.length) return false;

  for (const r of roots) {
    // A UNC allowed-root would re-open the hole fix 2 closes, so it never admits anything.
    if (isUncPath(r, pathImpl)) continue;
    if (!sameVolume(r, fp, pathImpl)) continue; // DEFECT FIX 1
    const rel = pathImpl.relative(r, fp);
    if (!rel || (!rel.startsWith('..' + pathImpl.sep) && rel !== '..')) return true;
  }
  return false;
}

export function assertWithin({ filePath, allowedRoots, pathImpl = nodePath }) {
  if (!isPathWithin({ filePath, allowedRoots, pathImpl })) {
    const err = new Error('path_not_allowed');
    err.data = {
      filePath: String(filePath || ''),
      allowedRoots: (allowedRoots || []).map(String)
    };
    throw err;
  }
}
