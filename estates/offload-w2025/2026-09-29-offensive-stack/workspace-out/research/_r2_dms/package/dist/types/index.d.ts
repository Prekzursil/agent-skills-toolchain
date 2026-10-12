import type { z } from "zod";
export interface ToolDef {
    name: string;
    description: string;
    schema: Record<string, z.ZodType>;
    execute: (args: Record<string, unknown>, ctx: ToolContext) => Promise<ToolResult>;
}
export interface ToolContext {
    config: {
        hibpApiKey?: string;
        intelxApiKey?: string;
        otxApiKey?: string;
        abuseipdbApiKey?: string;
        abusechAuthKey?: string;
        pulsediveApiKey?: string;
        hudsonrockApiKey?: string;
        vulnersApiKey?: string;
        hybridApiKey?: string;
        phishtankApiKey?: string;
        torSocksHost: string;
        torSocksPort: number;
    };
}
export interface ToolResult {
    [key: string]: unknown;
    content: {
        type: "text";
        text: string;
    }[];
}
export declare function text(msg: string): ToolResult;
export declare function json(data: unknown): ToolResult;
//# sourceMappingURL=index.d.ts.map