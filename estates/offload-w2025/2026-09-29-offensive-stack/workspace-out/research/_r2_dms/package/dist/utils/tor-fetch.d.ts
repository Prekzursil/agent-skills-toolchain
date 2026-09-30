export interface TorStatus {
    socksAvailable: boolean;
    socksHost: string;
    socksPort: number;
}
export interface ScrapedPage {
    url: string;
    statusCode: number;
    title: string;
    links: {
        href: string;
        text: string;
    }[];
    bodyText: string;
    fetchTimeMs: number;
}
export declare function checkTorStatus(host?: string, port?: number): Promise<TorStatus>;
export declare function fetchOnion(url: string, host?: string, port?: number): Promise<{
    html: string;
    statusCode: number;
}>;
export declare function scrapeOnion(url: string, host?: string, port?: number): Promise<ScrapedPage>;
//# sourceMappingURL=tor-fetch.d.ts.map