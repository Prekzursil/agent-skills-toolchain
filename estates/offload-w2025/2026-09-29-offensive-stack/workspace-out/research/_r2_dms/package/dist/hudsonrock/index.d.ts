export interface StealerEntry {
    date_compromised: string;
    url: string;
    computer_name: string;
    operating_system: string;
    malware_path: string;
    antiviruses: string;
    ip: string;
    top_logins: {
        url: string;
        login: string;
    }[];
    top_passwords: string[];
    [key: string]: unknown;
}
export interface StealerDomainResponse {
    stealers: StealerEntry[];
    total: number;
    [key: string]: unknown;
}
export interface StealerEmailResponse {
    stealers: StealerEntry[];
    total: number;
    [key: string]: unknown;
}
export interface StealerIpResponse {
    stealers: StealerEntry[];
    total: number;
    [key: string]: unknown;
}
export declare function stealerDomain(domain: string, apiKey: string): Promise<StealerDomainResponse>;
export declare function stealerEmail(email: string, apiKey: string): Promise<StealerEmailResponse>;
export declare function stealerIp(ip: string, apiKey: string): Promise<StealerIpResponse>;
//# sourceMappingURL=index.d.ts.map