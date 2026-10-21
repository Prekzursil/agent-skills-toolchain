// ─── Response Helpers ───
export function text(msg) {
    return { content: [{ type: "text", text: msg }] };
}
export function json(data) {
    return text(JSON.stringify(data, null, 2));
}
//# sourceMappingURL=index.js.map