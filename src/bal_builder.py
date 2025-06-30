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
from helpers import identify_simple_eth_transfers

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

def process_balance_changes(trace_result, builder: BALBuilder, touched_addresses: set, simple_transfers: dict = None):
    """Extract balance changes and add them to the builder.
    
    Args:
        trace_result: The trace result from debug_traceBlockByNumber
        builder: The BALBuilder instance
        touched_addresses: Set to track all touched addresses
        simple_transfers: Dict mapping tx_index to simple transfer info (from/to addresses)
    """
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

        # Check if this is a simple ETH transfer
        is_simple_transfer = simple_transfers and tx_id in simple_transfers
        
        for address, delta_val in balance_delta.items():
            # Skip balance changes for sender and recipient of simple ETH transfers
            if is_simple_transfer:
                transfer_info = simple_transfers[tx_id]
                if address.lower() in (transfer_info["from"], transfer_info["to"]):
                    continue
            
            canonical = to_canonical_address(address)
            # Calculate post balance for this address
            post_balance = post_balances.get(address, 0)
            post_balance_bytes = post_balance.to_bytes(12, "big", signed=False)
            builder.add_balance_change(canonical, tx_id, post_balance_bytes)

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

def process_code_changes(trace_result: List[dict], builder: BALBuilder):
    """Extract code changes and add them to the builder."""
    for tx_id, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
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
    builder: BALBuilder = None
):
    """Extract storage changes and add them to the builder."""
    # Track all writes and reads across the entire block
    block_writes: Dict[str, Dict[str, List[Tuple[int, str]]]] = {}
    block_reads: Dict[str, Set[str]] = {}

    for tx_id, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
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

def _should_record_nonce_diff(pre_info: dict, post_info: dict) -> bool:
    """Determine whether a nonce diff should be recorded.
    
    Per EIP-7928, we only record nonce changes for contracts that perform
    CREATE/CREATE2 operations. We do NOT record nonce changes that can be
    statically inferred from the block:
    - Transaction sender nonce increments
    - Type 4 transaction 'to' address nonce increments
    
    This function assumes it's called for accounts that have code (contracts).
    """
    if "nonce" not in pre_info or "code" not in pre_info:
        return False

    # Only record if this is a contract (has code)
    if not pre_info.get("code") or pre_info["code"] in ("", "0x", "0x0"):
        return False

    pre_nonce_str = pre_info["nonce"]
    pre_nonce = int(pre_nonce_str, 16) if isinstance(pre_nonce_str, str) and pre_nonce_str.startswith('0x') else int(pre_nonce_str)
    post_nonce = _get_nonce(post_info, fallback=str(pre_nonce))
    return post_nonce > pre_nonce

def process_nonce_changes(trace_result: List[Dict[str, Any]], builder: BALBuilder):
    """Extract nonce changes and add them to the builder."""
    for tx_index, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
            continue

        pre_state = result.get("pre", {})
        post_state = result.get("post", {})

        for address_hex, pre_info in pre_state.items():
            post_info = post_state.get(address_hex, {})
            if not _should_record_nonce_diff(pre_info, post_info):
                continue
            
            post_nonce = _get_nonce(post_info, fallback=pre_info["nonce"])
            canonical = to_canonical_address(address_hex)
            # Follows pattern: address -> nonce -> tx_index -> new_nonce
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

def identify_simple_eth_transfers_from_trace(trace_result: List[dict]) -> Dict[int, Dict[str, str]]:
    """
    Identify simple ETH transfers using the trace data we already have.
    
    A simple ETH transfer is characterized by:
    1. Only balance changes (no storage, code, or nonce changes beyond sender nonce)
    2. One sender (balance decreases, nonce increases by 1)
    3. May have fee recipient (miner/validator) - balance increases, no nonce change
    4. Recipient may not appear in state diff if they don't have prior balance
    5. No contract code deployment or execution
    
    Args:
        trace_result: The trace result from debug_traceBlockByNumber
        
    Returns:
        dict: Maps tx_index to dict with 'from' and 'to' addresses for simple transfers
    """
    simple_transfers = {}
    
    for tx_id, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
            continue
            
        pre_state = result.get("pre", {})
        post_state = result.get("post", {})
        
        # Get all addresses involved in this transaction
        all_addresses = set(pre_state.keys()) | set(post_state.keys())
        
        # For simple ETH transfers, we expect 1-3 addresses:
        # - Sender (always present)
        # - Recipient (may not be in state diff if new account)
        # - Fee recipient/miner (usually present)
        if len(all_addresses) == 0 or len(all_addresses) > 3:
            continue
            
        # Check that only balance changes occurred (no storage, code changes)
        is_simple_transfer = True
        sender_addr = None
        potential_recipients = []
        fee_recipient = None
        
        for addr in all_addresses:
            pre_info = pre_state.get(addr, {})
            post_info = post_state.get(addr, {})
            
            # Check for storage changes
            pre_storage = pre_info.get("storage", {})
            post_storage = post_info.get("storage", {})
            if pre_storage or post_storage:
                is_simple_transfer = False
                break
                
            # Check for code changes
            pre_code = pre_info.get("code", "")
            post_code = post_info.get("code", "")
            if pre_code != post_code:
                is_simple_transfer = False
                break
                
            # Check balance changes
            pre_balance = parse_hex_or_zero(pre_info.get("balance", "0"))
            post_balance = parse_hex_or_zero(post_info.get("balance", "0"))
            balance_delta = post_balance - pre_balance
            
            # Check nonce changes
            pre_nonce_val = pre_info.get("nonce", "0")
            post_nonce_val = post_info.get("nonce", pre_nonce_val)  # Default to pre value if missing
            
            if isinstance(pre_nonce_val, str) and pre_nonce_val.startswith("0x"):
                pre_nonce = int(pre_nonce_val, 16)
            else:
                pre_nonce = int(pre_nonce_val)
                
            if isinstance(post_nonce_val, str) and post_nonce_val.startswith("0x"):
                post_nonce = int(post_nonce_val, 16)
            else:
                post_nonce = int(post_nonce_val)
                
            nonce_delta = post_nonce - pre_nonce
            
            # Classify the address role
            if balance_delta < 0 and nonce_delta == 1:
                # This is the sender (lost balance and nonce increased)
                if sender_addr is not None:
                    # Multiple senders - not a simple transfer
                    is_simple_transfer = False
                    break
                sender_addr = addr.lower()
            elif balance_delta > 0 and nonce_delta == 0:
                # This could be recipient or fee recipient
                potential_recipients.append(addr.lower())
            elif balance_delta == 0 and nonce_delta == 0:
                # Account appeared but no changes - possible recipient with 0 previous balance
                potential_recipients.append(addr.lower())
            else:
                # Unexpected pattern - not a simple transfer
                is_simple_transfer = False
                break
        
        # Validate we found exactly one sender
        if not is_simple_transfer or sender_addr is None:
            continue
            
        # For simple transfers, handle the main case we can detect:
        # Sender exists and we have 1-2 additional addresses that gained balance
        if len(all_addresses) >= 1 and sender_addr is not None:
            # Check if we can identify a clear recipient (gained significant balance)
            recipient_found = False
            
            if len(potential_recipients) == 1:
                # Only one potential recipient - could be the actual recipient
                recipient_addr = potential_recipients[0]
                recipient_pre = pre_state.get(recipient_addr, {})
                recipient_post = post_state.get(recipient_addr, {})
                recipient_pre_balance = parse_hex_or_zero(recipient_pre.get("balance", "0"))
                recipient_post_balance = parse_hex_or_zero(recipient_post.get("balance", "0"))
                
                if recipient_post_balance > recipient_pre_balance:
                    simple_transfers[tx_id] = {
                        "from": sender_addr,
                        "to": recipient_addr
                    }
                    recipient_found = True
                    
            # If we couldn't identify a clear recipient, it might be a transfer to a new account
            if not recipient_found:
                # This is likely a simple transfer where recipient is new (not in state diff)
                simple_transfers[tx_id] = {
                    "from": sender_addr,
                    "to": "unknown_new_account"  # Placeholder
                }
    
    return simple_transfers

def sort_block_access_list(bal: BlockAccessList) -> BlockAccessList:
    """Sort the block access list for deterministic encoding."""
    sorted_accounts = []
    
    for account in sorted(bal.account_changes, key=lambda x: bytes(x.address)):
        # Sort storage changes by slot and recreate with sorted changes
        sorted_storage_changes = []
        for slot_changes in sorted(account.storage_changes, key=lambda x: bytes(x.slot)):
            # Sort changes within each slot by tx_index and recreate SlotChanges
            sorted_changes = sorted(slot_changes.changes, key=lambda x: x.tx_index)
            sorted_slot_changes = SlotChanges(slot=slot_changes.slot, changes=sorted_changes)
            sorted_storage_changes.append(sorted_slot_changes)
        
        # Sort storage reads by slot
        sorted_storage_reads = sorted(account.storage_reads, key=lambda x: bytes(x.slot))
        
        # Sort other changes by tx_index
        sorted_balance_changes = sorted(account.balance_changes, key=lambda x: x.tx_index)
        sorted_nonce_changes = sorted(account.nonce_changes, key=lambda x: x.tx_index)
        sorted_code_changes = sorted(account.code_changes, key=lambda x: x.tx_index)
        
        sorted_account = AccountChanges(
            address=account.address,
            storage_changes=sorted_storage_changes,
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
    storage_changes_data = []
    storage_reads_data = []
    balance_changes_data = []
    nonce_changes_data = []
    code_changes_data = []
    
    for account in bal.account_changes:
        if account.storage_changes:
            storage_changes_data.extend(account.storage_changes)
        if account.storage_reads:
            storage_reads_data.extend(account.storage_reads)
        if account.balance_changes:
            balance_changes_data.extend(account.balance_changes)
        if account.nonce_changes:
            nonce_changes_data.extend(account.nonce_changes)
        if account.code_changes:
            code_changes_data.extend(account.code_changes)
    
    # Calculate compressed sizes
    storage_changes_size = get_compressed_size(
        ssz.encode(storage_changes_data, sedes=SSZList(SlotChanges, MAX_SLOTS))
    ) if storage_changes_data else 0
    
    storage_reads_size = get_compressed_size(
        ssz.encode(storage_reads_data, sedes=SSZList(SlotRead, MAX_SLOTS))
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
    total_storage_size = storage_changes_size + storage_reads_size
    total_size = total_storage_size + balance_size + code_size + nonce_size
    
    return {
        'storage_changes_kb': storage_changes_size,
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
    parser = argparse.ArgumentParser(description='Build Block Access Lists (BALs) from Ethereum blocks')
    parser.add_argument('--no-reads', action='store_true', 
                        help='Ignore storage read locations (only include writes)')
    args = parser.parse_args()
    
    # Set IGNORE_STORAGE_LOCATIONS based on command line flag
    IGNORE_STORAGE_LOCATIONS = args.no_reads
    
    print(f"Running SSZ BAL builder with IGNORE_STORAGE_LOCATIONS = {IGNORE_STORAGE_LOCATIONS}")
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

        # Create builder - follows address->field->tx_index->change pattern
        builder = BALBuilder()
        
        # Collect all touched addresses
        touched_addresses = collect_touched_addresses(trace_result)
        
        # Identify simple ETH transfers using gas-based method (correct)
        print(f"  Identifying simple ETH transfers for block {block_number}...")
        simple_transfers = identify_simple_eth_transfers(block_number, RPC_URL)
        if simple_transfers:
            print(f"    Found {len(simple_transfers)} simple ETH transfers")
        
        # Extract all components into the builder
        process_storage_changes(trace_result, block_reads, IGNORE_STORAGE_LOCATIONS, builder)
        process_balance_changes(trace_result, builder, touched_addresses, simple_transfers)
        process_code_changes(trace_result, builder)
        process_nonce_changes(trace_result, builder)
        
        # Add any touched addresses that don't already have changes
        # Only include touched addresses when NOT ignoring reads (per EIP-7928)
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
        filename = f"{block_number}_block_access_list_{reads_suffix}.txt"
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
        totals["storage_changes"].append(component_sizes["storage_changes_kb"])
        totals["storage_reads"].append(component_sizes["storage_reads_kb"])
        totals["storage_total"].append(component_sizes["storage_total_kb"])
        totals["balance"].append(component_sizes["balance_diffs_kb"])
        totals["code"].append(component_sizes["code_diffs_kb"])
        totals["nonce"].append(component_sizes["nonce_diffs_kb"])
        block_totals.append(component_sizes["total_kb"])

    # Save JSON to file with appropriate name based on reads flag
    filename = "bal_analysis_without_reads.json" if IGNORE_STORAGE_LOCATIONS else "bal_analysis_with_reads.json"
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
        
        print(f"\nEfficiency stats:")
        print(f"Average accounts per block: {avg_accounts:.1f}")
        print(f"Average storage writes per block: {avg_storage_writes:.1f}")
        print(f"Average storage reads per block: {avg_storage_reads:.1f}")

if __name__ == "__main__":
    main()
