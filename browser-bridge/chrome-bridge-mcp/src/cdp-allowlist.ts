/**
 * Estate CDP allowlist (MUST-FIX 2).
 *
 * The hub and the extension both enforce this. Anything not listed is refused.
 * Cookie/credential methods are named in COOKIE_DENY so the error is explicit
 * even if someone later adds a broad Network.* glob by mistake.
 */

export const CDP_ALLOWLIST = new Set<string>([
  "Page.enable",
  "Page.disable",
  "Page.navigate",
  "Page.reload",
  "Page.getNavigationHistory",
  "Page.navigateToHistoryEntry",
  "Page.captureScreenshot",
  "Page.getLayoutMetrics",
  "Page.getFrameTree",
  "Page.createIsolatedWorld",
  "Page.handleJavaScriptDialog",
  "Runtime.enable",
  "Runtime.disable",
  "Runtime.evaluate",
  "Runtime.callFunctionOn",
  "Runtime.releaseObject",
  "DOM.enable",
  "DOM.disable",
  "DOM.getFrameOwner",
  "DOM.resolveNode",
  "DOM.setFileInputFiles",
  "Log.enable",
  "Log.disable",
  "Input.dispatchMouseEvent",
  "Input.dispatchKeyEvent",
  "Input.insertText",
]);

export const CDP_COOKIE_DENY = new Set<string>([
  "Network.getAllCookies",
  "Network.getCookies",
  "Network.setCookie",
  "Network.setCookies",
  "Network.deleteCookies",
  "Network.enable",
  "Network.getResponseBody",
  "Storage.getCookies",
  "Storage.getAllCookies",
  "Storage.setCookies",
  "Storage.clearCookies",
  "DOMStorage.getDOMStorageItems",
  "DOMStorage.setDOMStorageItem",
  "DOMStorage.removeDOMStorageItem",
  "IndexedDB.requestData",
  "IndexedDB.requestDatabase",
  "CacheStorage.requestCachedResponse",
  "CacheStorage.requestEntries",
]);

/**
 * Static credential-read filter for Runtime.evaluate / callFunctionOn.
 *
 * Residual: obfuscated JS (string concat, unicode, Function constructor) can
 * still read document.cookie in page context. Full isolation is not feasible
 * while Runtime.evaluate remains required for snapshot/click. Documented in
 * the hardening receipt.
 */
const CREDENTIAL_PATTERN =
  /document\s*\.\s*cookie|\[["']cookie["']\]|cookieStore|localStorage|sessionStorage|indexedDB|navigator\s*\.\s*credentials|getAllCookies|getCookies|DOMStorage/i;

export function assertSafePageScript(src: string): void {
  if (CREDENTIAL_PATTERN.test(String(src ?? ""))) {
    throw new Error("page script refused: cookie/credential/storage access is blocked");
  }
}

export function assertCdpAllowed(method: unknown, params?: Record<string, unknown> | null): void {
  const name = String(method ?? "");
  if (!name) throw new Error("CDP method is required");
  if (CDP_COOKIE_DENY.has(name) || /\.(getAllCookies|getCookies|setCookie|setCookies|clearCookies|deleteCookies)$/i.test(name)) {
    throw new Error(`CDP method ${name} is denied (cookie/credential exfil)`);
  }
  if (!CDP_ALLOWLIST.has(name)) {
    throw new Error(`CDP method ${name} is not on the estate allowlist`);
  }
  if (name === "Runtime.evaluate") {
    assertSafePageScript(String(params?.expression ?? ""));
  }
  if (name === "Runtime.callFunctionOn") {
    assertSafePageScript(String(params?.functionDeclaration ?? ""));
  }
}
