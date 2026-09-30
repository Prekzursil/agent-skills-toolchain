export interface BtcTransaction {
    hash: string;
    ver: number;
    vin_sz: number;
    vout_sz: number;
    size: number;
    weight: number;
    fee: number;
    lock_time: number;
    block_height: number;
    block_index: number;
    time: number;
    result: number;
    balance: number;
    inputs: {
        prev_out: {
            addr: string;
            value: number;
            spent: boolean;
            script: string;
        };
        script: string;
        sequence: number;
    }[];
    out: {
        addr: string;
        value: number;
        spent: boolean;
        script: string;
    }[];
    [key: string]: unknown;
}
export interface BtcAddressResponse {
    hash160: string;
    address: string;
    n_tx: number;
    n_unredeemed: number;
    total_received: number;
    total_sent: number;
    final_balance: number;
    txs: BtcTransaction[];
}
export interface BtcBalanceResponse {
    [address: string]: {
        final_balance: number;
        n_tx: number;
        total_received: number;
    };
}
export interface BtcTxResponse {
    hash: string;
    ver: number;
    vin_sz: number;
    vout_sz: number;
    size: number;
    weight: number;
    fee: number;
    lock_time: number;
    block_height: number;
    block_index: number;
    time: number;
    inputs: {
        prev_out: {
            addr: string;
            value: number;
            spent: boolean;
            script: string;
        };
        script: string;
        sequence: number;
    }[];
    out: {
        addr: string;
        value: number;
        spent: boolean;
        script: string;
        n: number;
    }[];
    [key: string]: unknown;
}
export interface ChainAbuseReport {
    id: string;
    address: string;
    chain: string;
    description: string;
    category: string;
    createdAt: string;
    scamType: string;
    [key: string]: unknown;
}
export interface ChainAbuseResponse {
    reports: ChainAbuseReport[];
    count: number;
}
export declare function btcAddress(address: string): Promise<BtcAddressResponse>;
export declare function btcBalance(address: string): Promise<BtcBalanceResponse>;
export declare function btcTx(txhash: string): Promise<BtcTxResponse>;
export declare function btcAbuseCheck(address: string): Promise<ChainAbuseResponse>;
//# sourceMappingURL=index.d.ts.map