import { type TorStatus, type ScrapedPage } from "../utils/tor-fetch.js";
export type { TorStatus, ScrapedPage };
export interface TorExitNode {
    fingerprint: string;
    published: string;
    lastStatus: string;
    exitAddress: string;
    exitAddressTimestamp: string;
}
export interface AhmiaResult {
    title: string;
    url: string;
    description: string;
}
export declare function torStatus(host?: string, port?: number): Promise<TorStatus>;
export declare function torFetchOnionHtml(url: string, host?: string, port?: number): Promise<{
    html: string;
    statusCode: number;
}>;
export declare function torScrapeOnionPage(url: string, host?: string, port?: number): Promise<ScrapedPage>;
export declare function torSearchOnion(query: string, limit?: number): Promise<AhmiaResult[]>;
export declare function torExitNodes(limit?: number): Promise<string[]>;
export declare function torExitCheck(ip: string): Promise<{
    isTorExit: boolean;
    ip: string;
}>;
export declare function torExitDetails(limit?: number): Promise<TorExitNode[]>;
//# sourceMappingURL=index.d.ts.map