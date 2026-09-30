export interface OnionLookupResponse {
    address: string;
    first_seen: string;
    last_seen: string;
    last_check: string;
    status: string;
    tags: string[];
    pgp: string[];
    certificates: string[];
    ports: number[];
    base_url: string;
    title: string;
    bitcoin_addresses: string[];
    [key: string]: unknown;
}
export declare function onionLookup(address: string): Promise<OnionLookupResponse>;
//# sourceMappingURL=index.d.ts.map