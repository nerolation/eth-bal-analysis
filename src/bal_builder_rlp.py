import os
import rlp
import sys
import json
import argparse
import requests
from pathlib import Path
from collections import defaultdict
from typing import Dict
from eth_utils import to_canonical_address

project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import BALBuilder, BlockAccessList, get_account_stats, parse_hex_or_zero
from helpers import *
from helpers import fetch_block_info, fetch_block_receipts
from bal_builder import (
    extract_balance_touches_from_block,
    extract_balances,
    parse_pre_and_post_balances,
    get_balance_delta,
    identify_gas_related_addresses,
    process_balance_changes,
    extract_non_empty_code,
    decode_hex_code,
    process_code_changes,
    extract_reads_from_block,
    _is_non_write_read,
    process_storage_changes,
    _get_nonce,
    process_nonce_changes,
    collect_touched_addresses,
    sort_block_access_list,
    get_component_sizes,
    count_accounts_and_slots,
    process_system_contract_changes
)

rpc_file = os.path.join(project_root, "rpc.txt")
with open(rpc_file, "r") as file:
    RPC_URL = file.read().strip()

IGNORE_STORAGE_LOCATIONS = False

def encode_bal_to_rlp(bal: BlockAccessList) -> bytes:
    """Convert SSZ BlockAccessList to RLP format."""
    
    accounts_data = []
    
    for account in bal.account_changes:
        address_bytes = bytes(account.address)
        
        storage_writes_data = []
        for storage_access in account.storage_writes:
            slot_bytes = bytes(storage_access.slot)
            changes_data = []
            for change in storage_access.changes:
                changes_data.append([change.tx_index, bytes(change.new_value)])
            storage_writes_data.append([slot_bytes, changes_data])
        
        storage_reads_data = []
        for slot in account.storage_reads:
            storage_reads_data.append(bytes(slot))
        
        balance_changes_data = []
        for change in account.balance_changes:
            balance_int = int.from_bytes(bytes(change.post_balance), 'big')
            balance_changes_data.append([change.tx_index, balance_int])
        
        nonce_changes_data = []
        for change in account.nonce_changes:
            nonce_changes_data.append([change.tx_index, change.new_nonce])
        
        code_changes_data = []
        for change in account.code_changes:
            code_changes_data.append([change.tx_index, bytes(change.new_code)])
        
        account_data = [
            address_bytes,
            storage_writes_data,
            storage_reads_data,
            balance_changes_data,
            nonce_changes_data,
            code_changes_data
        ]
        
        accounts_data.append(account_data)
    
    return rlp.encode(accounts_data)

def get_rlp_compressed_size(data: bytes) -> float:
    """Get compressed size of RLP data in KB."""
    return get_compressed_size(data)

def get_rlp_component_sizes(bal: BlockAccessList) -> Dict[str, float]:
    
    storage_writes_size = 0
    storage_reads_size = 0
    balance_changes_size = 0
    nonce_changes_size = 0
    code_changes_size = 0
    
    for account in bal.account_changes:
        if account.storage_writes:
            writes_data = []
            for storage_access in account.storage_writes:
                slot_bytes = bytes(storage_access.slot)
                changes_data = []
                for change in storage_access.changes:
                    changes_data.append([change.tx_index, bytes(change.new_value)])
                writes_data.append([slot_bytes, changes_data])
            storage_writes_size += len(rlp.encode(writes_data))
        
        if account.storage_reads:
            reads_data = [bytes(slot) for slot in account.storage_reads]
            storage_reads_size += len(rlp.encode(reads_data))
        
        if account.balance_changes:
            balance_data = []
            for change in account.balance_changes:
                balance_int = int.from_bytes(bytes(change.post_balance), 'big')
                balance_data.append([change.tx_index, balance_int])
            balance_changes_size += len(rlp.encode(balance_data))
        
        if account.nonce_changes:
            nonce_data = [[change.tx_index, change.new_nonce] for change in account.nonce_changes]
            nonce_changes_size += len(rlp.encode(nonce_data))
        
        if account.code_changes:
            code_data = [[change.tx_index, bytes(change.new_code)] for change in account.code_changes]
            code_changes_size += len(rlp.encode(code_data))
    
    storage_writes_kb = get_compressed_size(rlp.encode(storage_writes_size)) if storage_writes_size else 0
    storage_reads_kb = get_compressed_size(rlp.encode(storage_reads_size)) if storage_reads_size else 0
    balance_kb = get_compressed_size(rlp.encode(balance_changes_size)) if balance_changes_size else 0
    nonce_kb = get_compressed_size(rlp.encode(nonce_changes_size)) if nonce_changes_size else 0
    code_kb = get_compressed_size(rlp.encode(code_changes_size)) if code_changes_size else 0
    
    total_storage_size = storage_writes_kb + storage_reads_kb
    total_size = total_storage_size + balance_kb + code_kb + nonce_kb
    
    return {
        'storage_writes_kb': storage_writes_kb,
        'storage_reads_kb': storage_reads_kb,
        'storage_total_kb': total_storage_size,
        'balance_diffs_kb': balance_kb,
        'nonce_diffs_kb': nonce_kb,
        'code_diffs_kb': code_kb,
        'total_kb': total_size,
    }

def main():
    global IGNORE_STORAGE_LOCATIONS
    
    parser = argparse.ArgumentParser(description='Build RLP-encoded Block Access Lists (BALs) from Ethereum blocks')
    parser.add_argument('--no-reads', action='store_true', 
                        help='Ignore storage read locations (only include writes)')
    parser.add_argument('--block', type=int, help='Process a single block number')
    args = parser.parse_args()
    
    IGNORE_STORAGE_LOCATIONS = args.no_reads
    
    print(f"Running RLP BAL builder with IGNORE_STORAGE_LOCATIONS = {IGNORE_STORAGE_LOCATIONS}")
    
    if args.block:
        blocks_to_process = [args.block]
    else:
        blocks_to_process = range(22886914 - 500, 22886914, 100)[:5]
    
    totals = defaultdict(list)
    block_totals = []
    data = []

    for block_number in blocks_to_process:
        print(f"\nProcessing block {block_number}...")
        trace_result = fetch_block_trace(block_number, RPC_URL)
        
        block_reads = None
        if not IGNORE_STORAGE_LOCATIONS:
            print(f"  Fetching reads for block {block_number}...")
            block_reads = extract_reads_from_block(block_number, RPC_URL)

        print(f"  Fetching balance touches for block {block_number}...")
        balance_touches = extract_balance_touches_from_block(block_number, RPC_URL)
        
        print(f"  Fetching transaction receipts for block {block_number}...")
        receipts = fetch_block_receipts(block_number, RPC_URL)
        reverted_tx_indices = set()
        for i, receipt in enumerate(receipts):
            if receipt and receipt.get("status") == "0x0":
                reverted_tx_indices.add(i)
        if reverted_tx_indices:
            print(f"    Found {len(reverted_tx_indices)} reverted transactions: {sorted(reverted_tx_indices)}")
            
        print(f"  Fetching block info...")
        block_info = fetch_block_info(block_number, RPC_URL)

        builder = BALBuilder()
        
        touched_addresses = collect_touched_addresses(trace_result)
        
        process_storage_changes(trace_result, block_reads, IGNORE_STORAGE_LOCATIONS, builder, reverted_tx_indices)
        process_balance_changes(trace_result, builder, touched_addresses, balance_touches, reverted_tx_indices, block_info, receipts, IGNORE_STORAGE_LOCATIONS)
        process_code_changes(trace_result, builder, reverted_tx_indices)
        process_nonce_changes(trace_result, builder, reverted_tx_indices)
        
        # Process system contract changes with tx_index = len(transactions)
        tx_count = len(block_info.get('transactions', []))
        process_system_contract_changes(block_info, builder, tx_count)
        
        if not IGNORE_STORAGE_LOCATIONS:
            for addr in touched_addresses:
                canonical = to_canonical_address(addr)
                builder.add_touched_account(canonical)
        
        block_obj = builder.build(ignore_reads=IGNORE_STORAGE_LOCATIONS)
        block_obj_sorted = sort_block_access_list(block_obj)
        
        full_block_encoded = encode_bal_to_rlp(block_obj_sorted)

        bal_raw_dir = os.path.join(project_root, "bal_raw", "rlp")
        os.makedirs(bal_raw_dir, exist_ok=True)
        
        reads_suffix = "without_reads" if IGNORE_STORAGE_LOCATIONS else "with_reads"
        filename = f"{block_number}_{reads_suffix}.rlp"
        filepath = os.path.join(bal_raw_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(full_block_encoded)

        raw_size = len(full_block_encoded)
        compressed_size = get_rlp_compressed_size(full_block_encoded)
        
        print(f"  Raw size: {raw_size:,} bytes")
        print(f"  Compressed size: {compressed_size:.2f} KB")
        print(f"  Saved to: {filepath}")

        bal_stats = get_account_stats(block_obj_sorted)

        data.append({
            "block_number": block_number,
            "raw_size": raw_size,
            "compressed_size_kb": compressed_size,
            "bal_stats": bal_stats,
        })

        block_totals.append(compressed_size)

    if len(blocks_to_process) > 1:
        print("\nSummary:")
        print(f"Blocks processed: {len(data)}")
        
        overall_avg = sum(block_totals) / len(block_totals) if block_totals else 0
        print(f"Average compressed size per block: {overall_avg:.2f} KB")
        
        if data:
            avg_accounts = sum(d["bal_stats"]["total_accounts"] for d in data) / len(data)
            avg_storage_writes = sum(d["bal_stats"]["total_storage_writes"] for d in data) / len(data)
            avg_storage_reads = sum(d["bal_stats"]["total_storage_reads"] for d in data) / len(data)
            
            print(f"\nEfficiency stats:")
            print(f"Average accounts per block: {avg_accounts:.1f}")
            print(f"Average storage writes per block: {avg_storage_writes:.1f}")
            print(f"Average storage reads per block: {avg_storage_reads:.1f}")

if __name__ == "__main__":
    main()