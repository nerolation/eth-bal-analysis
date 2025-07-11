import os
import ssz
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from eth_utils import to_canonical_address

project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import *
from helpers import *
from helpers import fetch_block_info

rpc_file = os.path.join(project_root, "rpc.txt")
with open(rpc_file, "r") as file:
    RPC_URL = file.read().strip()

# Will be set based on command line arguments
IGNORE_STORAGE_LOCATIONS = False

def extract_balances(state):
    balances = {}
    for addr, changes in state.items():
        if "balance" in changes:
            balances[addr] = parse_hex_or_zero(changes["balance"])
    return balances

def parse_pre_and_post_balances(pre_state, post_state):
    return extract_balances(pre_state), extract_balances(post_state)

def get_balance_delta(pres, posts, pre_balances, post_balances):
    all_addresses = pres.union(posts)
    balance_delta = {}
    for addr in all_addresses:
        pre_balance = pre_balances.get(addr, 0)
        post_balance = post_balances.get(addr, pre_balance)
        delta = post_balance - pre_balance
        if delta != 0:  # Include all non-zero deltas (positive and negative)
            balance_delta[addr] = delta
    return balance_delta

def extract_balance_touches_from_block(block_number: int, rpc_url: str) -> Dict[int, Dict[str, str]]:
    """Extract all addresses that had balance reads/writes using diff_mode=False.
    
    Returns:
        Dict mapping tx_index to dict of address -> balance value
    """
    trace_result = fetch_block_trace(block_number, rpc_url, diff_mode=False)
    balance_touches = {}
    
    for tx_id, tx_trace in enumerate(trace_result):
        result = tx_trace.get("result", {})
        touched_addrs = {}
        for address, acc_data in result.items():
            if "balance" in acc_data:
                touched_addrs[address.lower()] = acc_data["balance"]
        if touched_addrs:
            balance_touches[tx_id] = touched_addrs
    
    return balance_touches

def identify_gas_related_addresses(block_info: dict, tx_index: int) -> Tuple[Optional[str], Optional[str]]:
    """Identify the sender and fee recipient for a transaction.
    
    Returns:
        Tuple of (sender_address, fee_recipient_address)
    """
    if not block_info or "transactions" not in block_info:
        return None, None
        
    transactions = block_info.get("transactions", [])
    if tx_index >= len(transactions):
        return None, None
        
    tx = transactions[tx_index]
    sender = tx.get("from", "").lower() if tx.get("from") else None
    
    # Fee recipient is the block's miner/fee recipient
    fee_recipient = block_info.get("miner", "").lower() if block_info.get("miner") else None
    
    return sender, fee_recipient

def process_balance_changes(trace_result, builder: BALBuilder, touched_addresses: set, 
                          balance_touches: Dict[int, Dict[str, str]] = None, 
                          reverted_tx_indices: set = None,
                          block_info: dict = None,
                          ignore_reads: bool = False):
    """Extract balance changes and add them to the builder.
    
    Args:
        trace_result: The trace result from debug_traceBlockByNumber (diff mode)
        builder: The BALBuilder instance
        touched_addresses: Set to track all touched addresses
        balance_touches: Dict of tx_id -> set of addresses that had balance touches (from non-diff trace)
        reverted_tx_indices: Set of transaction indices that were reverted
        block_info: Block information including transactions (for identifying senders)
    """
    if reverted_tx_indices is None:
        reverted_tx_indices = set()
        
    # Track which addresses have been processed per transaction
    processed_per_tx = {}
    
    for tx_id, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
            continue

        pre_state, post_state = tx["result"]["pre"], tx["result"]["post"]
        pre_balances, post_balances = parse_pre_and_post_balances(pre_state, post_state)
        pres, posts = set(pre_balances.keys()), set(post_balances.keys())
        balance_delta = get_balance_delta(pres, posts, pre_balances, post_balances)

        # Track all addresses that had balance checks (even zero-value transfers)
        all_balance_addresses = pres.union(posts)
        for address in all_balance_addresses:
            touched_addresses.add(address.lower())

        # Track processed addresses for this tx
        processed_addrs = set()
        
        # Process all balance changes - now using bytes16 format
        for address, delta_val in balance_delta.items():
            # For reverted transactions, only include gas-related balance changes
            if tx_id in reverted_tx_indices:
                sender, fee_recipient = identify_gas_related_addresses(block_info, tx_id)
                
                # Only include balance changes for:
                # 1. The sender (who pays gas)
                # 2. The fee recipient (who receives gas payment)
                if address.lower() not in (sender, fee_recipient):
                    # Skip non-gas related balance changes
                    continue
                
            canonical = to_canonical_address(address)
            # Calculate post balance for this address
            post_balance = post_balances.get(address, 0)
            # Convert to bytes16 format
            post_balance_bytes = post_balance.to_bytes(16, "big", signed=False)
            builder.add_balance_change(canonical, tx_id, post_balance_bytes)
            processed_addrs.add(address.lower())
        
        processed_per_tx[tx_id] = processed_addrs
    
    # Add addresses with temporary balance changes (zero net change)
    # Only do this when NOT ignoring reads
    if balance_touches and not ignore_reads:
        for tx_id, touched_addrs_balances in balance_touches.items():
            processed = processed_per_tx.get(tx_id, set())
            # Find addresses that were touched but not in the diff
            for address, balance_hex in touched_addrs_balances.items():
                if address not in processed:
                    touched_addresses.add(address)
                    canonical = to_canonical_address(address)
                    # Just mark as touched - no balance change since net change is zero
                    builder.add_touched_account(canonical)

def extract_non_empty_code(state: dict, address: str) -> Optional[str]:
    """Returns the code from state if it's non-empty, else None."""
    code = state.get(address, {}).get("code")
    if code and code not in ("", "0x"):
        return code
    return None

def decode_hex_code(code_hex: str) -> bytes:
    """Converts a hex code string (with or without 0x) to raw bytes."""
    code_str = code_hex[2:] if code_hex.startswith("0x") else code_hex
    return bytes.fromhex(code_str)

def process_code_changes(trace_result: List[dict], builder: BALBuilder, reverted_tx_indices: set = None):
    """Extract code changes and add them to the builder."""
    if reverted_tx_indices is None:
        reverted_tx_indices = set()
        
    for tx_id, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
            continue
            
        # Skip code changes for reverted transactions entirely
        if tx_id in reverted_tx_indices:
            continue

        pre_state, post_state = result.get("pre", {}), result.get("post", {})
        all_addresses = set(pre_state) | set(post_state)

        for address in all_addresses:
            pre_code = extract_non_empty_code(pre_state, address)
            post_code = extract_non_empty_code(post_state, address)
            
            if post_code is None or post_code == pre_code:
                continue

            code_bytes = decode_hex_code(post_code)
            if len(code_bytes) > MAX_CODE_SIZE:
                raise ValueError(
                    f"Contract code too large in tx {tx_id} for {address}: "
                    f"{len(code_bytes)} > {MAX_CODE_SIZE}"
                )

            canonical = to_canonical_address(address)
            builder.add_code_change(canonical, tx_id, code_bytes)

def extract_reads_from_block(block_number: int, rpc_url: str) -> Dict[str, Set[str]]:
    """Extract reads from a block using diff_mode=False."""
    trace_result = fetch_block_trace(block_number, rpc_url, diff_mode=False)
    reads = defaultdict(set)
    
    for tx_trace in trace_result:
        result = tx_trace.get("result", {})
        for address, acc_data in result.items():
            storage = acc_data.get("storage", {})
            for slot in storage.keys():
                reads[address.lower()].add(slot.lower())
    
    return reads

def _is_non_write_read(pre_val_hex: Optional[str], post_val_hex: Optional[str]) -> bool:
    """Check if a storage slot qualifies as a pure read."""
    return pre_val_hex is not None and post_val_hex is None

def process_storage_changes(
    trace_result: List[dict], 
    additional_reads: Optional[Dict[str, Set[str]]] = None,
    ignore_reads: bool = IGNORE_STORAGE_LOCATIONS,
    builder: BALBuilder = None,
    reverted_tx_indices: set = None
):
    """Extract storage changes and add them to the builder."""
    if reverted_tx_indices is None:
        reverted_tx_indices = set()
        
    # Track all writes and reads across the entire block
    block_writes: Dict[str, Dict[str, List[Tuple[int, str]]]] = {}
    block_reads: Dict[str, Set[str]] = {}

    for tx_id, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
            continue
            
        # Skip storage changes for reverted transactions entirely
        if tx_id in reverted_tx_indices:
            continue

        pre_state = result.get("pre", {})
        post_state = result.get("post", {})
        all_addresses = set(pre_state) | set(post_state)

        for address in all_addresses:
            pre_storage = pre_state.get(address, {}).get("storage", {})
            post_storage = post_state.get(address, {}).get("storage", {})
            all_slots = set(pre_storage) | set(post_storage)

            for slot in all_slots:
                pre_val = pre_storage.get(slot)
                post_val = post_storage.get(slot)

                # Determine if this is a write operation
                # A write occurs when:
                # 1. post_val exists and differs from pre_val, OR
                # 2. pre_val exists but post_val is None (writing zero, slot omitted)
                if post_val is not None:
                    # Case 1: Explicit value in post state
                    pre_bytes = (
                        hex_to_bytes32(pre_val) if pre_val is not None else b"\x00" * 32
                    )
                    post_bytes = hex_to_bytes32(post_val)
                    if pre_bytes != post_bytes:
                        # Changed write
                        block_writes.setdefault(address, {}).setdefault(slot, []).append(
                            (tx_id, post_val)
                        )
                    else:
                        # Unchanged write - treat as read per EIP-7928
                        # Storage writes that don't change value still consume gas
                        # and must be included in the BAL as reads
                        if not ignore_reads:
                            if address not in block_writes or slot not in block_writes.get(address, {}):
                                block_reads.setdefault(address, set()).add(slot)
                elif pre_val is not None and slot not in post_storage:
                    # Case 2: Slot was non-zero in pre but omitted in post (zeroed)
                    # This is a write to zero, not a read!
                    zero_value = "0x" + "00" * 32  # Proper 32-byte zero value
                    block_writes.setdefault(address, {}).setdefault(slot, []).append(
                        (tx_id, zero_value)
                    )
                # If read-only (appears in pre but not modified in post)
                elif not ignore_reads and _is_non_write_read(pre_val, post_val):
                    if address not in block_writes or slot not in block_writes.get(address, {}):
                        block_reads.setdefault(address, set()).add(slot)

    # Add additional reads from diff_mode=False if provided and not ignoring reads
    if not ignore_reads and additional_reads is not None:
        for address, read_slots in additional_reads.items():
            if address not in block_writes:
                for slot in read_slots:
                    block_reads.setdefault(address, set()).add(slot)
            else:
                written_slots = set(block_writes[address].keys())
                for slot in read_slots:
                    if slot not in written_slots:
                        block_reads.setdefault(address, set()).add(slot)

    # Add writes to builder - follows pattern: address -> slot -> tx_index -> new_value
    for address, slots in block_writes.items():
        canonical_addr = to_canonical_address(address)
        for slot, write_entries in slots.items():
            slot_bytes = hex_to_bytes32(slot)
            for tx_id, val_hex in write_entries:
                value_bytes = hex_to_bytes32(val_hex)
                builder.add_storage_write(canonical_addr, slot_bytes, tx_id, value_bytes)

    # Add reads to builder - follows pattern: address -> slot (read-only)
    for address, read_slots in block_reads.items():
        canonical_addr = to_canonical_address(address)
        for slot in read_slots:
            slot_bytes = hex_to_bytes32(slot)
            builder.add_storage_read(canonical_addr, slot_bytes)

def _get_nonce(info: dict, fallback: str = "0") -> int:
    """Safely parse a nonce string from a state dict, with fallback."""
    nonce_str = info.get("nonce", fallback)
    return int(nonce_str, 16) if isinstance(nonce_str, str) and nonce_str.startswith('0x') else int(nonce_str)

def process_nonce_changes(trace_result: List[Dict[str, Any]], builder: BALBuilder, reverted_tx_indices: set = None):
    """Extract all nonce changes and add them to the builder.
    
    Captures all statically inferrable nonce changes:
    - EOA/sender nonce increments 
    - New contracts (nonce 1)
    - EIP-7702 delegations
    
    For reverted transactions, only the sender's nonce increment is included.
    """
    if reverted_tx_indices is None:
        reverted_tx_indices = set()
        
    for tx_index, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
            continue

        pre_state = result.get("pre", {})
        post_state = result.get("post", {})

        # Process existing addresses with nonce changes
        for address_hex, pre_info in pre_state.items():
            post_info = post_state.get(address_hex, {})
            
            if "nonce" in pre_info:
                pre_nonce = _get_nonce(pre_info)
                post_nonce = _get_nonce(post_info, fallback=pre_info["nonce"])
                
                if post_nonce > pre_nonce:
                    # For reverted transactions, only include sender nonce change
                    # (we can't easily identify the sender here without tx data)
                    canonical = to_canonical_address(address_hex)
                    builder.add_nonce_change(canonical, tx_index, post_nonce)
        
        # Process new addresses that appear only in post_state (new contracts, EIP-7702)
        # Skip these for reverted transactions
        if tx_index not in reverted_tx_indices:
            for address_hex, post_info in post_state.items():
                if address_hex not in pre_state and "nonce" in post_info:
                    post_nonce = _get_nonce(post_info)
                    if post_nonce > 0:  # New address with non-zero nonce
                        canonical = to_canonical_address(address_hex)
                        builder.add_nonce_change(canonical, tx_index, post_nonce)

def collect_touched_addresses(trace_result: List[dict]) -> Set[str]:
    """Collect all addresses that were touched during execution (including read-only access)."""
    touched = set()
    
    for tx in trace_result:
        result = tx.get("result")
        if not isinstance(result, dict):
            continue
            
        pre_state = result.get("pre", {})
        post_state = result.get("post", {})
        
        # Any address in pre or post state was touched
        all_addresses = set(pre_state.keys()) | set(post_state.keys())
        for addr in all_addresses:
            touched.add(addr.lower())
    
    return touched

def sort_block_access_list(bal: BlockAccessList) -> BlockAccessList:
    """Sort the block access list for deterministic encoding."""
    sorted_accounts = []
    
    for account in sorted(bal.account_changes, key=lambda x: bytes(x.address)):
        # Sort storage writes by slot and recreate with sorted changes
        sorted_storage_writes = []
        for storage_access in sorted(account.storage_writes, key=lambda x: bytes(x.slot)):
            # Sort changes within each slot by tx_index and recreate StorageAccess
            sorted_changes = sorted(storage_access.changes, key=lambda x: x.tx_index)
            sorted_storage_access = StorageAccess(slot=storage_access.slot, changes=sorted_changes)
            sorted_storage_writes.append(sorted_storage_access)
        
        # Sort storage reads by slot (storage_reads is now a list of StorageKey bytes)
        sorted_storage_reads = sorted(account.storage_reads, key=lambda x: bytes(x))
        
        # Sort other changes by tx_index
        sorted_balance_changes = sorted(account.balance_changes, key=lambda x: x.tx_index)
        sorted_nonce_changes = sorted(account.nonce_changes, key=lambda x: x.tx_index)
        sorted_code_changes = sorted(account.code_changes, key=lambda x: x.tx_index)
        
        sorted_account = AccountChanges(
            address=account.address,
            storage_writes=sorted_storage_writes,
            storage_reads=sorted_storage_reads,
            balance_changes=sorted_balance_changes,
            nonce_changes=sorted_nonce_changes,
            code_changes=sorted_code_changes
        )
        sorted_accounts.append(sorted_account)
    
    return BlockAccessList(account_changes=sorted_accounts)

def get_component_sizes(bal: BlockAccessList) -> Dict[str, float]:
    """Calculate component sizes for BAL structure."""
    
    # Encode each component separately to measure sizes
    storage_writes_data = []
    storage_reads_data = []
    balance_changes_data = []
    nonce_changes_data = []
    code_changes_data = []
    
    for account in bal.account_changes:
        if account.storage_writes:
            storage_writes_data.extend(account.storage_writes)
        if account.storage_reads:
            storage_reads_data.extend(account.storage_reads)
        if account.balance_changes:
            balance_changes_data.extend(account.balance_changes)
        if account.nonce_changes:
            nonce_changes_data.extend(account.nonce_changes)
        if account.code_changes:
            code_changes_data.extend(account.code_changes)
    
    # Calculate compressed sizes
    storage_writes_size = get_compressed_size(
        ssz.encode(storage_writes_data, sedes=SSZList(StorageAccess, MAX_SLOTS))
    ) if storage_writes_data else 0
    
    storage_reads_size = get_compressed_size(
        ssz.encode(storage_reads_data, sedes=SSZList(StorageKey, MAX_SLOTS))
    ) if storage_reads_data else 0
    
    balance_size = get_compressed_size(
        ssz.encode(balance_changes_data, sedes=SSZList(BalanceChange, MAX_TXS))
    ) if balance_changes_data else 0
    
    nonce_size = get_compressed_size(
        ssz.encode(nonce_changes_data, sedes=SSZList(NonceChange, MAX_TXS))
    ) if nonce_changes_data else 0
    
    code_size = get_compressed_size(
        ssz.encode(code_changes_data, sedes=SSZList(CodeChange, MAX_TXS))
    ) if code_changes_data else 0
    
    # Total storage size combines writes and reads
    total_storage_size = storage_writes_size + storage_reads_size
    total_size = total_storage_size + balance_size + code_size + nonce_size
    
    return {
        'storage_writes_kb': storage_writes_size,
        'storage_reads_kb': storage_reads_size,
        'storage_total_kb': total_storage_size,
        'balance_diffs_kb': balance_size,
        'nonce_diffs_kb': nonce_size,
        'code_diffs_kb': code_size,
        'total_kb': total_size,
    }

def main():
    global IGNORE_STORAGE_LOCATIONS
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Build Block Access Lists (BALs) from Ethereum blocks using latest EIP-7928 format')
    parser.add_argument('--no-reads', action='store_true', 
                        help='Ignore storage read locations (only include writes)')
    args = parser.parse_args()
    
    # Set IGNORE_STORAGE_LOCATIONS based on command line flag
    IGNORE_STORAGE_LOCATIONS = args.no_reads
    
    print(f"Running EIP-7928 SSZ BAL builder with IGNORE_STORAGE_LOCATIONS = {IGNORE_STORAGE_LOCATIONS}")
    totals = defaultdict(list)
    block_totals = []
    data = []

    # Use 50 blocks for comparison testing (every 10th block from recent range)
    random_blocks = range(22616032 - 500, 22616032, 10)

    for block_number in random_blocks:
        print(f"Processing block {block_number}...")
        trace_result = fetch_block_trace(block_number, RPC_URL)
        
        # Fetch reads separately only if not ignoring storage locations
        block_reads = None
        if not IGNORE_STORAGE_LOCATIONS:
            print(f"  Fetching reads for block {block_number}...")
            block_reads = extract_reads_from_block(block_number, RPC_URL)

        # Fetch balance touches to capture temporary balance changes
        print(f"  Fetching balance touches for block {block_number}...")
        balance_touches = extract_balance_touches_from_block(block_number, RPC_URL)
        
        # Fetch transaction receipts to identify reverted transactions
        print(f"  Fetching transaction receipts for block {block_number}...")
        receipts = fetch_block_receipts(block_number, RPC_URL)
        reverted_tx_indices = set()
        for i, receipt in enumerate(receipts):
            if receipt and receipt.get("status") == "0x0":
                reverted_tx_indices.add(i)
        if reverted_tx_indices:
            print(f"    Found {len(reverted_tx_indices)} reverted transactions: {sorted(reverted_tx_indices)}")
            
        # Fetch block info for transaction details (needed for reverted tx handling)
        block_info = None
        if reverted_tx_indices:
            print(f"  Fetching block info for reverted transaction handling...")
            block_info = fetch_block_info(block_number, RPC_URL)

        # Create builder - follows address->field->tx_index->change pattern
        builder = BALBuilder()
        
        # Collect all touched addresses
        touched_addresses = collect_touched_addresses(trace_result)
        
        # Extract all components into the builder
        process_storage_changes(trace_result, block_reads, IGNORE_STORAGE_LOCATIONS, builder, reverted_tx_indices)
        process_balance_changes(trace_result, builder, touched_addresses, balance_touches, reverted_tx_indices, block_info, IGNORE_STORAGE_LOCATIONS)
        process_code_changes(trace_result, builder, reverted_tx_indices)
        process_nonce_changes(trace_result, builder, reverted_tx_indices)
        
        # Add any touched addresses that don't already have changes
        # Only include touched addresses when NOT ignoring reads (per EIP-7928)
        # This ensures that with --no-reads, the BAL only contains addresses with actual changes
        if not IGNORE_STORAGE_LOCATIONS:
            for addr in touched_addresses:
                canonical = to_canonical_address(addr)
                builder.add_touched_account(canonical)
        
        # Build the block access list
        block_obj = builder.build(ignore_reads=IGNORE_STORAGE_LOCATIONS)
        block_obj_sorted = sort_block_access_list(block_obj)
        
        # Encode the entire block
        full_block_encoded = ssz.encode(block_obj_sorted, sedes=BlockAccessList)

        # Create bal_raw/ssz directory 
        bal_raw_dir = os.path.join(project_root, "bal_raw", "ssz")
        os.makedirs(bal_raw_dir, exist_ok=True)
        
        # Create filename indicating with/without reads
        reads_suffix = "without_reads" if IGNORE_STORAGE_LOCATIONS else "with_reads"
        filename = f"{block_number}_block_access_list_{reads_suffix}_eip7928.txt"
        filepath = os.path.join(bal_raw_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(full_block_encoded)

        # Calculate component sizes
        component_sizes = get_component_sizes(block_obj_sorted)

        # Count affected accounts and slots from original trace for comparison
        accs, slots = count_accounts_and_slots(trace_result)
        
        # Get BAL stats
        bal_stats = get_account_stats(block_obj_sorted)

        # Store stats
        data.append({
            "block_number": block_number,
            "sizes": component_sizes,
            "counts": {
                "accounts": accs,
                "slots": slots,
            },
            "bal_stats": bal_stats,
        })

        # Totals for averages
        totals["storage_writes"].append(component_sizes["storage_writes_kb"])
        totals["storage_reads"].append(component_sizes["storage_reads_kb"])
        totals["storage_total"].append(component_sizes["storage_total_kb"])
        totals["balance"].append(component_sizes["balance_diffs_kb"])
        totals["code"].append(component_sizes["code_diffs_kb"])
        totals["nonce"].append(component_sizes["nonce_diffs_kb"])
        block_totals.append(component_sizes["total_kb"])

    # Save JSON to file with appropriate name based on reads flag
    filename = "bal_analysis_without_reads_eip7928.json" if IGNORE_STORAGE_LOCATIONS else "bal_analysis_with_reads_eip7928.json"
    filepath = os.path.join(project_root, "bal_raw", "ssz", filename)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    # Averages
    print("\nAverage compressed size per component (in KiB):")
    for name, sizes in totals.items():
        avg = sum(sizes) / len(sizes) if sizes else 0
        print(f"{name}: {avg:.2f} KiB")

    overall_avg = sum(block_totals) / len(block_totals) if block_totals else 0
    print(f"\nOverall average compressed size per block: {overall_avg:.2f} KiB")
    
    # Show efficiency stats
    if data:
        avg_accounts = sum(d["bal_stats"]["total_accounts"] for d in data) / len(data)
        avg_storage_writes = sum(d["bal_stats"]["total_storage_writes"] for d in data) / len(data)
        avg_storage_reads = sum(d["bal_stats"]["total_storage_reads"] for d in data) / len(data)
        avg_balance_changes = sum(d["bal_stats"]["total_balance_changes"] for d in data) / len(data)
        avg_nonce_changes = sum(d["bal_stats"]["total_nonce_changes"] for d in data) / len(data)
        
        print(f"\nEfficiency stats:")
        print(f"Average accounts per block: {avg_accounts:.1f}")
        print(f"Average storage writes per block: {avg_storage_writes:.1f}")
        print(f"Average storage reads per block: {avg_storage_reads:.1f}")
        print(f"Average balance changes per block: {avg_balance_changes:.1f}")
        print(f"Average nonce changes per block: {avg_nonce_changes:.1f}")

if __name__ == "__main__":
    main()