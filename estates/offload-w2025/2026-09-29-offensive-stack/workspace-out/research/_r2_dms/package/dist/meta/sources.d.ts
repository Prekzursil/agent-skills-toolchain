import type { ToolContext } from "../types/index.js";
export interface DataSource {
    name: string;
    url: string;
    authRequired: boolean;
    envVar: string | null;
    tools: string[];
    configured: boolean;
}
export declare function listSources(config: ToolContext["config"]): DataSource[];
//# sourceMappingURL=sources.d.ts.map