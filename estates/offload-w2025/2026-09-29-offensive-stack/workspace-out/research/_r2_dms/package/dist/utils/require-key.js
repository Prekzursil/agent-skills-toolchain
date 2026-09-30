// Shared helper for API key validation
export function requireApiKey(key, provider, envVar) {
    if (!key) {
        throw new Error(`${provider} API key required. Set ${envVar} environment variable to enable ${provider} tools.`);
    }
    return key;
}
//# sourceMappingURL=require-key.js.map