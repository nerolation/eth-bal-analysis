#!/usr/bin/env python3
"""
Collect BAL sizes for all formats (SSZ/RLP, Standard/Columnar, with/without reads).
Efficient parsing script that generates and measures BALs in all formats.
"""

import os
import sys
import json
import time
import gzip
import argparse
import rlp
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

# Add project root to Python path
project_root = str(Path(__file__).parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

# Import SSZ formats
import ssz
from BALs import BlockAccessList as SSZBlockAccessList, BALBuilder
# Import both columnar formats with different aliases
from BALs_columnar import BlockAccessListColumnar as BALColumnarNoReads, BALColumnarBuilder as BALBuilderNoReads
from BALs_columnar_with_reads import BlockAccessListColumnar as BALColumnarWithReads, BALColumnarBuilder as BALBuilderWithReads

# Import RLP formats with explicit names to avoid conflicts
from BALs_rlp import (
    BlockAccessList as RLPBlockAccessList,
    AccountChanges as RLPAccountChanges,
    StorageChange as RLPStorageChange,
    SlotChanges as RLPSlotChanges,
    SlotRead as RLPSlotRead,
    BalanceChange as RLPBalanceChange,
    NonceChange as RLPNonceChange,
    CodeChange as RLPCodeChange
)
from BALs_columnar_rlp import BlockAccessListColumnarRLP as BALColumnarRLPNoReads, BALColumnarRLPBuilder as BALRLPBuilderNoReads
from BALs_columnar_with_reads_rlp import BlockAccessListColumnarRLP as BALColumnarRLPWithReads, BALColumnarRLPBuilder as BALRLPBuilderWithReads

# Import builders and helpers
from bal_builder import (
    extract_balance_touches_from_block,
    process_storage_changes,
    process_balance_changes,
    process_code_changes,
    process_nonce_changes,
    collect_touched_addresses,
    extract_reads_from_block,
    _get_nonce,
    extract_non_empty_code,
    decode_hex_code,
    sort_block_access_list
)
from helpers import *
from eth_utils import to_canonical_address

# Constants
CHECKPOINT_FILE = "bal_size_collection_all_formats_checkpoint.json"
OUTPUT_FILE = "bal_sizes_all_formats.json"
BLOCKS_PER_CHECKPOINT = 50
BLOCKS_PER_STATUS = 5

# RPC configuration
rpc_file = os.path.join(project_root, "rpc.txt")
with open(rpc_file, "r") as file:
    RPC_URL = file.read().strip()


class UniversalBALBuilder:
    """Builder that can generate BALs in all formats from the same data."""
    
    def __init__(self):
        # Storage for all collected data
        self.storage_writes = defaultdict(lambda: defaultdict(list))  # address -> slot -> [(tx_idx, value)]
        self.storage_reads = defaultdict(set)  # address -> {slots}
        self.balance_changes = defaultdict(list)  # address -> [(tx_idx, post_balance)]
        self.nonce_changes = defaultdict(list)  # address -> [(tx_idx, new_nonce)]
        self.code_changes = defaultdict(list)  # address -> [(tx_idx, new_code)]
        self.touched_addresses = set()
    
    def add_storage_write(self, address: bytes, slot: bytes, tx_index: int, new_value: bytes):
        """Add a storage write."""
        self.storage_writes[address][slot].append((tx_index, new_value))
        self.touched_addresses.add(address)
    
    def add_storage_read(self, address: bytes, slot: bytes):
        """Add a storage read."""
        self.storage_reads[address].add(slot)
        self.touched_addresses.add(address)
    
    def add_balance_change(self, address: bytes, tx_index: int, post_balance: bytes):
        """Add a balance change."""
        self.balance_changes[address].append((tx_index, post_balance))
        self.touched_addresses.add(address)
    
    def add_nonce_change(self, address: bytes, tx_index: int, new_nonce: int):
        """Add a nonce change."""
        self.nonce_changes[address].append((tx_index, new_nonce))
        self.touched_addresses.add(address)
    
    def add_code_change(self, address: bytes, tx_index: int, new_code: bytes):
        """Add a code change."""
        self.code_changes[address].append((tx_index, new_code))
        self.touched_addresses.add(address)
    
    def build_ssz_standard(self, ignore_reads: bool = False) -> bytes:
        """Build standard SSZ format BAL."""
        builder = BALBuilder()
        
        # Add all data to SSZ builder
        for address in self.storage_writes:
            for slot, changes in self.storage_writes[address].items():
                for tx_idx, value in changes:
                    builder.add_storage_write(address, slot, tx_idx, value)
        
        if not ignore_reads:
            for address, slots in self.storage_reads.items():
                for slot in slots:
                    # Only add reads for slots that weren't written
                    if slot not in self.storage_writes.get(address, {}):
                        builder.add_storage_read(address, slot)
        
        for address, changes in self.balance_changes.items():
            for tx_idx, post_balance in changes:
                builder.add_balance_change(address, tx_idx, post_balance)
        
        for address, changes in self.nonce_changes.items():
            for tx_idx, new_nonce in changes:
                builder.add_nonce_change(address, tx_idx, new_nonce)
        
        for address, changes in self.code_changes.items():
            for tx_idx, new_code in changes:
                builder.add_code_change(address, tx_idx, new_code)
        
        # Add touched addresses if not ignoring reads
        if not ignore_reads:
            for address in self.touched_addresses:
                builder.add_touched_account(address)
        
        # Build and encode
        bal = builder.build(ignore_reads=ignore_reads)
        bal_sorted = sort_block_access_list(bal)
        return ssz.encode(bal_sorted, sedes=SSZBlockAccessList)
    
    def build_ssz_columnar(self, ignore_reads: bool = False) -> bytes:
        """Build columnar SSZ format BAL."""
        # Use appropriate builder based on ignore_reads
        if ignore_reads:
            builder = BALBuilderNoReads()
        else:
            builder = BALBuilderWithReads()
        
        # Add all data to columnar builder
        for address in self.storage_writes:
            for slot, changes in self.storage_writes[address].items():
                for tx_idx, value in changes:
                    builder.add_storage_write(address, slot, tx_idx, value)
        
        if not ignore_reads:
            for address, slots in self.storage_reads.items():
                for slot in slots:
                    # Only add reads for slots that weren't written
                    if slot not in self.storage_writes.get(address, {}):
                        builder.add_storage_read(address, slot)
        
        for address, changes in self.balance_changes.items():
            for tx_idx, post_balance in changes:
                builder.add_balance_change(address, tx_idx, post_balance)
        
        for address, changes in self.nonce_changes.items():
            for tx_idx, new_nonce in changes:
                builder.add_nonce_change(address, tx_idx, new_nonce)
        
        for address, changes in self.code_changes.items():
            for tx_idx, new_code in changes:
                builder.add_code_change(address, tx_idx, new_code)
        
        # Add touched addresses if not ignoring reads
        if not ignore_reads:
            for address in self.touched_addresses:
                builder.add_touched_account(address)
        
        # Build and encode
        bal = builder.build(ignore_reads=ignore_reads)
        # Use appropriate format for encoding
        if ignore_reads:
            return ssz.encode(bal, sedes=BALColumnarNoReads)
        else:
            return ssz.encode(bal, sedes=BALColumnarWithReads)
    
    def build_rlp_standard(self, ignore_reads: bool = False) -> bytes:
        """Build standard RLP format BAL."""
        # Convert to RLP format
        account_changes_list = []
        
        for address in sorted(self.touched_addresses):
            # Ensure address is 20 bytes
            address_20 = address if len(address) == 20 else address[-20:].rjust(20, b'\x00')
            
            # Storage changes
            storage_changes = []
            for slot in sorted(self.storage_writes.get(address, {}).keys()):
                # Ensure slot is 32 bytes
                slot_32 = slot if len(slot) == 32 else slot.rjust(32, b'\x00')
                changes = []
                for tx_idx, value in sorted(self.storage_writes[address][slot], key=lambda x: x[0]):
                    # Ensure value is 32 bytes
                    value_32 = value if len(value) == 32 else value.rjust(32, b'\x00')
                    changes.append(RLPStorageChange(tx_idx, value_32))  # Use positional args
                storage_changes.append(RLPSlotChanges(slot_32, changes))  # Use positional args
            
            # Storage reads
            storage_reads = []
            if not ignore_reads:
                written_slots = set(self.storage_writes.get(address, {}).keys())
                for slot in sorted(self.storage_reads.get(address, set())):
                    if slot not in written_slots:
                        # Ensure slot is 32 bytes
                        slot_32 = slot if len(slot) == 32 else slot.rjust(32, b'\x00')
                        storage_reads.append(RLPSlotRead(slot_32))  # Use positional args
            
            # Balance changes
            balance_changes = []
            for tx_idx, post_balance in sorted(self.balance_changes.get(address, []), key=lambda x: x[0]):
                # Truncate balance to 12 bytes for RLP (removes leading zeros)
                balance_12 = post_balance[-12:] if len(post_balance) > 12 else post_balance
                balance_changes.append(RLPBalanceChange(tx_idx, balance_12))  # Use positional args
            
            # Nonce changes
            nonce_changes = []
            for tx_idx, new_nonce in sorted(self.nonce_changes.get(address, []), key=lambda x: x[0]):
                nonce_changes.append(RLPNonceChange(tx_idx, new_nonce))  # Use positional args
            
            # Code changes
            code_changes = []
            for tx_idx, new_code in sorted(self.code_changes.get(address, []), key=lambda x: x[0]):
                code_changes.append(RLPCodeChange(tx_idx, new_code))  # Use positional args
            
            # Only add account if it has changes
            if storage_changes or balance_changes or nonce_changes or code_changes or (storage_reads and not ignore_reads):
                # Use positional arguments for RLP Serializable
                account_changes_list.append(RLPAccountChanges(
                    address_20,        # address (20 bytes)
                    storage_changes,   # storage_changes
                    storage_reads,     # storage_reads
                    balance_changes,   # balance_changes
                    nonce_changes,     # nonce_changes
                    code_changes       # code_changes
                ))
        
        # Create and encode BlockAccessList
        bal = RLPBlockAccessList(account_changes_list)  # Use positional args
        return rlp.encode(bal)
    
    def build_rlp_columnar(self, ignore_reads: bool = False) -> bytes:
        """Build columnar RLP format BAL."""
        # Use appropriate builder based on ignore_reads
        if ignore_reads:
            builder = BALRLPBuilderNoReads()
        else:
            builder = BALRLPBuilderWithReads()
        
        # Add all data to columnar RLP builder
        for address in self.storage_writes:
            for slot, changes in self.storage_writes[address].items():
                for tx_idx, value in changes:
                    builder.add_storage_write(address, slot, tx_idx, value)
        
        if not ignore_reads:
            for address, slots in self.storage_reads.items():
                for slot in slots:
                    # Only add reads for slots that weren't written
                    if slot not in self.storage_writes.get(address, {}):
                        builder.add_storage_read(address, slot)
        
        for address, changes in self.balance_changes.items():
            for tx_idx, post_balance in changes:
                builder.add_balance_change(address, tx_idx, post_balance)
        
        for address, changes in self.nonce_changes.items():
            for tx_idx, new_nonce in changes:
                builder.add_nonce_change(address, tx_idx, new_nonce)
        
        for address, changes in self.code_changes.items():
            for tx_idx, new_code in changes:
                builder.add_code_change(address, tx_idx, new_code)
        
        # Add touched addresses if not ignoring reads
        if not ignore_reads:
            for address in self.touched_addresses:
                builder.add_touched_account(address)
        
        # Build and encode
        bal = builder.build(ignore_reads=ignore_reads)
        return rlp.encode(bal)


def process_block_all_formats(block_number: int) -> Dict[str, Dict[str, int]]:
    """Process a block and generate BALs in all formats."""
    try:
        # Get block timestamp
        block_info = fetch_block_info(block_number, RPC_URL)
        timestamp = int(block_info["timestamp"], 16) if block_info else 0
        
        # Fetch trace data
        trace_result = fetch_block_trace(block_number, RPC_URL)
        
        # Fetch additional data for reads
        block_reads = extract_reads_from_block(block_number, RPC_URL)
        
        # Fetch balance touches
        balance_touches = extract_balance_touches_from_block(block_number, RPC_URL)
        
        # Fetch receipts to identify reverted transactions
        receipts = fetch_block_receipts(block_number, RPC_URL)
        reverted_tx_indices = set()
        for i, receipt in enumerate(receipts):
            if receipt and receipt.get("status") == "0x0":
                reverted_tx_indices.add(i)
        
        # Create universal builder
        universal_builder = UniversalBALBuilder()
        
        # Process trace data and populate universal builder
        for tx_id, tx in enumerate(trace_result):
            result = tx.get("result")
            if not isinstance(result, dict):
                continue
                
            if tx_id in reverted_tx_indices:
                # Handle reverted transaction gas fees
                if receipts and tx_id < len(receipts) and block_info and tx_id < len(block_info.get("transactions", [])):
                    receipt = receipts[tx_id]
                    tx_info = block_info["transactions"][tx_id]
                    
                    # Calculate gas fee components
                    gas_used = int(receipt.get("gasUsed", "0x0"), 16)
                    
                    # Get effective gas price
                    if "effectiveGasPrice" in receipt:
                        effective_gas_price = int(receipt["effectiveGasPrice"], 16)
                    elif "gasPrice" in tx_info:
                        effective_gas_price = int(tx_info["gasPrice"], 16)
                    else:
                        effective_gas_price = 0
                    
                    # Get base fee for EIP-1559
                    base_fee_per_gas = int(block_info.get("baseFeePerGas", "0x0"), 16)
                    
                    # Calculate fees
                    total_gas_fee = gas_used * effective_gas_price
                    
                    # For EIP-1559 transactions, only priority fee goes to miner
                    if base_fee_per_gas > 0:
                        priority_fee_per_gas = effective_gas_price - base_fee_per_gas
                        priority_fee_total = gas_used * priority_fee_per_gas
                    else:
                        # Pre-EIP-1559, all gas fee goes to miner
                        priority_fee_total = total_gas_fee
                    
                    # Get addresses
                    sender = tx_info.get("from", "").lower()
                    fee_recipient = block_info.get("miner", "").lower()
                    
                    # Get accurate pre-balances from balance touches
                    balance_touches_for_tx = balance_touches.get(tx_id, {}) if balance_touches else {}
                    
                    # Calculate post-balances
                    sender_pre = parse_hex_or_zero(balance_touches_for_tx.get(sender, "0x0"))
                    fee_recipient_pre = parse_hex_or_zero(balance_touches_for_tx.get(fee_recipient, "0x0"))
                    
                    # Sender pays full gas fee
                    sender_post = sender_pre - total_gas_fee
                    # Fee recipient only gets priority fee (base fee is burned)
                    fee_recipient_post = fee_recipient_pre + priority_fee_total
                    
                    # Add balance changes
                    sender_canonical = to_canonical_address(sender)
                    sender_post_bytes = sender_post.to_bytes(16, "big", signed=False)
                    universal_builder.add_balance_change(sender_canonical, tx_id, sender_post_bytes)
                    
                    fee_recipient_canonical = to_canonical_address(fee_recipient)
                    fee_recipient_post_bytes = fee_recipient_post.to_bytes(16, "big", signed=False)
                    universal_builder.add_balance_change(fee_recipient_canonical, tx_id, fee_recipient_post_bytes)
            else:
                # Normal (non-reverted) transaction processing
                pre_state = result.get("pre", {})
                post_state = result.get("post", {})
                all_addresses = set(pre_state) | set(post_state)
                
                for address in all_addresses:
                    address_canonical = to_canonical_address(address)
                    
                    # Process storage changes
                    pre_storage = pre_state.get(address, {}).get("storage", {})
                    post_storage = post_state.get(address, {}).get("storage", {})
                    all_slots = set(pre_storage) | set(post_storage)
                    
                    for slot in all_slots:
                        slot_bytes = hex_to_bytes32(slot)
                        pre_val = pre_storage.get(slot)
                        post_val = post_storage.get(slot)
                        
                        if post_val is not None:
                            pre_bytes = hex_to_bytes32(pre_val) if pre_val is not None else b"\x00" * 32
                            post_bytes = hex_to_bytes32(post_val)
                            if pre_bytes != post_bytes:
                                universal_builder.add_storage_write(address_canonical, slot_bytes, tx_id, post_bytes)
                        elif pre_val is not None and slot not in post_storage:
                            # Deletion
                            zero_value = b"\x00" * 32
                            universal_builder.add_storage_write(address_canonical, slot_bytes, tx_id, zero_value)
                    
                    # Process balance changes
                    pre_balance_hex = pre_state.get(address, {}).get("balance")
                    post_balance_hex = post_state.get(address, {}).get("balance")
                    
                    if post_balance_hex and pre_balance_hex != post_balance_hex:
                        post_balance = parse_hex_or_zero(post_balance_hex)
                        post_balance_bytes = post_balance.to_bytes(16, "big", signed=False)
                        universal_builder.add_balance_change(address_canonical, tx_id, post_balance_bytes)
                    
                    # Process nonce changes
                    pre_nonce = _get_nonce(pre_state.get(address, {}))
                    post_nonce = _get_nonce(post_state.get(address, {}))
                    
                    if post_nonce > pre_nonce:
                        universal_builder.add_nonce_change(address_canonical, tx_id, post_nonce)
                    
                    # Process code changes
                    pre_code = extract_non_empty_code(pre_state, address)
                    post_code = extract_non_empty_code(post_state, address)
                    
                    if post_code is not None and post_code != pre_code:
                        code_bytes = decode_hex_code(post_code)
                        universal_builder.add_code_change(address_canonical, tx_id, code_bytes)
        
        # Add storage reads
        if block_reads:
            for address, slots in block_reads.items():
                address_canonical = to_canonical_address(address)
                for slot in slots:
                    slot_bytes = hex_to_bytes32(slot)
                    universal_builder.add_storage_read(address_canonical, slot_bytes)
        
        # Add touched addresses from balance touches
        if balance_touches:
            for tx_id, touched_addrs in balance_touches.items():
                for address in touched_addrs:
                    address_canonical = to_canonical_address(address)
                    universal_builder.touched_addresses.add(address_canonical)
        
        # Generate all formats
        results = {
            "timestamp": timestamp,
            "formats": {}
        }
        
        # Generate each format
        formats = [
            ("ssz_standard_with_reads", lambda: universal_builder.build_ssz_standard(ignore_reads=False)),
            ("ssz_standard_without_reads", lambda: universal_builder.build_ssz_standard(ignore_reads=True)),
            ("ssz_columnar_with_reads", lambda: universal_builder.build_ssz_columnar(ignore_reads=False)),
            ("ssz_columnar_without_reads", lambda: universal_builder.build_ssz_columnar(ignore_reads=True)),
            ("rlp_standard_with_reads", lambda: universal_builder.build_rlp_standard(ignore_reads=False)),
            ("rlp_standard_without_reads", lambda: universal_builder.build_rlp_standard(ignore_reads=True)),
            ("rlp_columnar_with_reads", lambda: universal_builder.build_rlp_columnar(ignore_reads=False)),
            ("rlp_columnar_without_reads", lambda: universal_builder.build_rlp_columnar(ignore_reads=True)),
        ]
        
        for format_name, build_func in formats:
            try:
                encoded = build_func()
                compressed = gzip.compress(encoded)
                results["formats"][format_name] = {
                    "raw_size": len(encoded),
                    "compressed_size": len(compressed)
                }
            except Exception as e:
                print(f"    Error building {format_name}: {e}")
                results["formats"][format_name] = {
                    "raw_size": 0,
                    "compressed_size": 0,
                    "error": str(e)
                }
        
        return results
        
    except Exception as e:
        print(f"Error processing block {block_number}: {e}")
        return {"timestamp": 0, "formats": {}}


def _get_nonce(info: dict, fallback: str = "0") -> int:
    """Helper to extract nonce from state info."""
    nonce_str = info.get("nonce", fallback)
    return int(nonce_str, 16) if isinstance(nonce_str, str) and nonce_str.startswith('0x') else int(nonce_str)


def load_checkpoint():
    """Load checkpoint data if it exists."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return json.load(f)
    return None


def save_checkpoint(data: dict):
    """Save checkpoint data."""
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Collect BAL sizes for all formats')
    parser.add_argument('--start-block', type=int, help='Starting block number')
    parser.add_argument('--end-block', type=int, help='Ending block number')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint')
    parser.add_argument('--blocks', type=int, default=1000, help='Number of blocks to process')
    args = parser.parse_args()
    
    # Initialize or load checkpoint
    if args.resume:
        checkpoint = load_checkpoint()
        if checkpoint:
            print(f"Resuming from checkpoint: {checkpoint['blocks_processed']} blocks processed")
            start_block = checkpoint['last_block'] + 1
            end_block = checkpoint['end_block']
            results = checkpoint['results']
            start_time = checkpoint['start_time']
        else:
            print("No checkpoint found, starting fresh")
            args.resume = False
    
    if not args.resume:
        if args.start_block and args.end_block:
            start_block = args.start_block
            end_block = args.end_block
        else:
            # Default to recent blocks if not specified
            latest_block = 21650000  # Approximate recent block
            start_block = latest_block - args.blocks
            end_block = latest_block
        
        results = []
        start_time = time.time()
    
    total_blocks = end_block - start_block
    blocks_processed = len(results)
    
    print(f"Processing blocks {start_block} to {end_block} ({total_blocks} blocks)")
    print(f"Starting from block {start_block + blocks_processed}")
    print("Generating BALs in 8 formats:")
    print("  - SSZ Standard (with/without reads)")
    print("  - SSZ Columnar (with/without reads)")
    print("  - RLP Standard (with/without reads)")
    print("  - RLP Columnar (with/without reads)")
    print()
    
    # Process blocks
    for i, block_number in enumerate(range(start_block + blocks_processed, end_block)):
        try:
            print(f"Processing block {block_number}...")
            
            # Process block in all formats
            block_results = process_block_all_formats(block_number)
            
            if block_results["timestamp"] > 0:
                results.append({
                    "block_number": block_number,
                    "timestamp": block_results["timestamp"],
                    "date": datetime.fromtimestamp(block_results["timestamp"]).isoformat(),
                    "formats": block_results["formats"]
                })
            
            blocks_processed = len(results)
            
            # Status update
            if (i + 1) % BLOCKS_PER_STATUS == 0:
                elapsed = time.time() - start_time
                rate = blocks_processed / elapsed if elapsed > 0 else 0
                eta = (total_blocks - blocks_processed) / rate if rate > 0 else 0
                
                print(f"\nProgress: {blocks_processed}/{total_blocks} blocks "
                      f"({blocks_processed/total_blocks*100:.1f}%) - "
                      f"Rate: {rate:.2f} blocks/s - "
                      f"ETA: {timedelta(seconds=int(eta))}\n")
            
            # Save checkpoint
            if (i + 1) % BLOCKS_PER_CHECKPOINT == 0:
                checkpoint_data = {
                    "start_block": start_block,
                    "end_block": end_block,
                    "last_block": block_number,
                    "blocks_processed": blocks_processed,
                    "results": results,
                    "start_time": start_time,
                    "timestamp": datetime.now().isoformat()
                }
                save_checkpoint(checkpoint_data)
                print(f"Checkpoint saved at block {block_number}")
                
        except KeyboardInterrupt:
            print("\nInterrupted! Saving checkpoint...")
            checkpoint_data = {
                "start_block": start_block,
                "end_block": end_block,
                "last_block": block_number - 1,
                "blocks_processed": blocks_processed,
                "results": results,
                "start_time": start_time,
                "timestamp": datetime.now().isoformat()
            }
            save_checkpoint(checkpoint_data)
            print("Checkpoint saved. Use --resume to continue.")
            sys.exit(0)
        except Exception as e:
            print(f"Error processing block {block_number}: {e}")
            continue
    
    # Save final results
    print(f"\nProcessing complete! Saving results to {OUTPUT_FILE}")
    
    # Calculate summary statistics
    format_stats = defaultdict(lambda: {"total_raw": 0, "total_compressed": 0, "count": 0})
    
    for result in results:
        for format_name, sizes in result["formats"].items():
            if sizes.get("raw_size", 0) > 0:
                format_stats[format_name]["total_raw"] += sizes["raw_size"]
                format_stats[format_name]["total_compressed"] += sizes["compressed_size"]
                format_stats[format_name]["count"] += 1
    
    summary = {}
    for format_name, stats in format_stats.items():
        if stats["count"] > 0:
            summary[format_name] = {
                "avg_raw_size": stats["total_raw"] / stats["count"],
                "avg_compressed_size": stats["total_compressed"] / stats["count"],
                "avg_raw_kb": (stats["total_raw"] / stats["count"]) / 1024,
                "avg_compressed_kb": (stats["total_compressed"] / stats["count"]) / 1024,
                "blocks_processed": stats["count"]
            }
    
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({
            "start_block": start_block,
            "end_block": end_block,
            "total_blocks": len(results),
            "summary": summary,
            "data": results
        }, f, indent=2)
    
    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
    
    # Print summary
    print("\nSummary by format:")
    print("-" * 80)
    print(f"{'Format':<30} {'Avg Raw (KB)':<15} {'Avg Compressed (KB)':<20} {'Compression':<10}")
    print("-" * 80)
    
    for format_name in sorted(summary.keys()):
        stats = summary[format_name]
        compression_ratio = (1 - stats["avg_compressed_size"] / stats["avg_raw_size"]) * 100
        print(f"{format_name:<30} {stats['avg_raw_kb']:<15.2f} {stats['avg_compressed_kb']:<20.2f} {compression_ratio:<10.1f}%")
    
    # Compare formats
    print("\n\nFormat Comparisons:")
    print("-" * 50)
    
    # SSZ vs RLP (standard)
    if "ssz_standard_without_reads" in summary and "rlp_standard_without_reads" in summary:
        ssz_size = summary["ssz_standard_without_reads"]["avg_compressed_kb"]
        rlp_size = summary["rlp_standard_without_reads"]["avg_compressed_kb"]
        diff = ((rlp_size - ssz_size) / ssz_size) * 100
        print(f"Standard format: RLP is {diff:+.1f}% compared to SSZ")
    
    # SSZ vs RLP (columnar)
    if "ssz_columnar_without_reads" in summary and "rlp_columnar_without_reads" in summary:
        ssz_size = summary["ssz_columnar_without_reads"]["avg_compressed_kb"]
        rlp_size = summary["rlp_columnar_without_reads"]["avg_compressed_kb"]
        diff = ((rlp_size - ssz_size) / ssz_size) * 100
        print(f"Columnar format: RLP is {diff:+.1f}% compared to SSZ")
    
    # Standard vs Columnar (SSZ)
    if "ssz_standard_without_reads" in summary and "ssz_columnar_without_reads" in summary:
        std_size = summary["ssz_standard_without_reads"]["avg_compressed_kb"]
        col_size = summary["ssz_columnar_without_reads"]["avg_compressed_kb"]
        diff = ((col_size - std_size) / std_size) * 100
        print(f"SSZ encoding: Columnar is {diff:+.1f}% compared to Standard")
    
    # Standard vs Columnar (RLP)
    if "rlp_standard_without_reads" in summary and "rlp_columnar_without_reads" in summary:
        std_size = summary["rlp_standard_without_reads"]["avg_compressed_kb"]
        col_size = summary["rlp_columnar_without_reads"]["avg_compressed_kb"]
        diff = ((col_size - std_size) / std_size) * 100
        print(f"RLP encoding: Columnar is {diff:+.1f}% compared to Standard")


if __name__ == "__main__":
    main()