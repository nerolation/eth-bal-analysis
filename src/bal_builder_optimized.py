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

from BALs_ssz_optimized_reads import *
from helpers import *

rpc_file = os.path.join(project_root, "rpc.txt")
with open(rpc_file, "r") as file:
    RPC_URL = file.read().strip()

# Will be set based on command line arguments
IGNORE_STORAGE_LOCATIONS = False


def extract_balances(state):
    return {
        addr: parse_hex_or_zero(changes.get("balance"))
        for addr, changes in state.items()
    }


def parse_pre_and_post_balances(pre_state, post_state):
    return extract_balances(pre_state), extract_balances(post_state)


def get_deltas(tx_id, pres, posts, pre_balances, post_balances):
    balance_delta = get_balance_delta(pres, posts, pre_balances, post_balances)
    acc_map: dict[bytes, AccountBalanceDiff] = {}
    for address, delta_val in balance_delta.items():
        if delta_val == 0:
            continue
        bal_diff = BalanceChange(
            tx_index=tx_id, delta=delta_val.to_bytes(12, "big", signed=True)
        )
        if address in acc_map:
            acc_map[address].changes.append(bal_diff)
        else:
            canonical = to_canonical_address(address)
            acc_map[address] = AccountBalanceDiff(address=canonical, changes=[bal_diff])
    return acc_map


def get_balance_delta(pres, posts, pre_balances, post_balances):
    all_addresses = pres.union(posts)  # Use union instead of intersection
    balance_delta = {}
    for addr in all_addresses:
        pre_balance = pre_balances.get(addr, 0)
        post_balance = post_balances.get(addr, 0)
        delta = post_balance - pre_balance
        if delta > 0:  # Only include non-zero deltas
            balance_delta[addr] = delta
    return balance_delta


def get_balance_diff_from_block(trace_result):
    # Aggregate all balance changes per address across the entire block
    address_balance_changes: Dict[str, List[BalanceChange]] = {}

    for tx_id, tx in enumerate(trace_result):
        tx_hash = tx.get("txHash")
        result = tx.get("result")
        if not isinstance(result, dict):
            print(type(result))
            continue

        pre_state, post_state = tx["result"]["pre"], tx["result"]["post"]
        pre_balances, post_balances = parse_pre_and_post_balances(pre_state, post_state)
        pres, posts = set(pre_balances.keys()), set(post_balances.keys())
        acc_map = get_deltas(tx_id, pres, posts, pre_balances, post_balances)

        # Aggregate changes by address
        for address, account_diff in acc_map.items():
            if address not in address_balance_changes:
                address_balance_changes[address] = []
            address_balance_changes[address].extend(account_diff.changes)

    # Build final list of AccountBalanceDiff objects
    acc_bal_diffs = []
    for address, changes in address_balance_changes.items():
        canonical = to_canonical_address(address)
        acc_bal_diffs.append(AccountBalanceDiff(address=canonical, changes=changes))

    balance_diff = ssz.encode(acc_bal_diffs, sedes=BalanceDiffs)
    return balance_diff, acc_bal_diffs


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


def process_code_change(
    tx_id: int,
    address_hex: str,
    pre_code: Optional[str],
    post_code: Optional[str],
    acc_map: Dict[str, AccountCodeDiff],
):
    """If there's a code change, update acc_map with a new CodeChange."""
    if post_code is None or post_code == pre_code:
        return

    code_bytes = decode_hex_code(post_code)

    if len(code_bytes) > MAX_CODE_SIZE:
        raise ValueError(
            f"Contract code too large in tx {tx_id} for {address_hex}: "
            f"{len(code_bytes)} > {MAX_CODE_SIZE}"
        )

    change = CodeChange(tx_index=tx_id, new_code=code_bytes)

    # Each account can only have one code change per block
    acc_map[address_hex] = AccountCodeDiff(
        address=to_canonical_address(address_hex), change=change
    )


def get_code_diff_from_block(trace_result: List[dict]) -> bytes:
    """
    Builds and SSZ‐encodes all AccountCodeDiff entries for the given trace_result.
    Returns an SSZ-encoded byte blob using `CodeDiffs` as the top-level sedes.
    """
    # Track code changes per address across the entire block
    acc_map: Dict[str, AccountCodeDiff] = {}

    for tx_id, tx in enumerate(trace_result):
        tx_hash = tx.get("txHash")
        result = tx.get("result")
        if not isinstance(result, dict):
            print(f"Unexpected result type for tx {tx_hash}: {type(result)}")
            continue

        pre_state, post_state = result.get("pre", {}), result.get("post", {})
        all_addresses = set(pre_state) | set(post_state)

        for address in all_addresses:
            pre_code = extract_non_empty_code(pre_state, address)
            post_code = extract_non_empty_code(post_state, address)
            process_code_change(tx_id, address, pre_code, post_code, acc_map)

    # Build final list of AccountCodeDiff objects
    acc_code_diffs = list(acc_map.values())

    return ssz.encode(acc_code_diffs, sedes=CodeDiffs), acc_code_diffs


def _is_non_write_read(pre_val_hex: Optional[str], post_val_hex: Optional[str]) -> bool:
    """Check if a storage slot qualifies as a pure read."""
    return pre_val_hex is not None and post_val_hex is None


def _add_write(
    acc_map_write: Dict[str, Dict[str, List[Tuple[int, str]]]],
    address: str,
    slot: str,
    tx_id: int,
    new_val_hex: str,
) -> None:
    acc_map_write.setdefault(address, {}).setdefault(slot, []).append(
        (tx_id, new_val_hex)
    )


def _add_read(acc_map_reads: Dict[str, Set[str]], address: str, slot: str) -> None:
    acc_map_reads.setdefault(address, set()).add(slot)


def _build_slot_writes(
    acc_map_write: Dict[str, Dict[str, List[Tuple[int, str]]]],
    address_hex: str,
) -> List[SlotWrite]:
    """Build all SlotWrite entries for one address."""
    slot_writes: List[SlotWrite] = []

    # Handle writes
    for slot_hex, write_entries in acc_map_write.get(address_hex, {}).items():
        slot = hex_to_bytes32(slot_hex)
        writes = [
            PerTxWrite(tx_index=tx_id, value_after=hex_to_bytes32(val_hex))
            for tx_id, val_hex in write_entries
        ]
        slot_writes.append(SlotWrite(slot=slot, writes=writes))

    return slot_writes


def _build_slot_reads(
    acc_map_reads: Dict[str, Set[str]],
    acc_map_write: Dict[str, Dict[str, List[Tuple[int, str]]]],
    address_hex: str,
) -> List[SlotRead]:
    """Build all SlotRead entries for one address (excluding written slots)."""
    slot_reads: List[SlotRead] = []

    # Handle reads (only if not written)
    written_slots = set(acc_map_write.get(address_hex, {}).keys())
    for slot_hex in acc_map_reads.get(address_hex, set()):
        if slot_hex in written_slots:
            continue
        slot = hex_to_bytes32(slot_hex)
        slot_reads.append(SlotRead(slot=slot))

    return slot_reads


def extract_reads_from_block(block_number: int, rpc_url: str) -> Dict[str, Set[str]]:
    """
    Extract reads from a block using diff_mode=False.
    Returns a dictionary mapping addresses to sets of storage slots that were read.
    """
    trace_result = fetch_block_trace(block_number, rpc_url, diff_mode=False)
    reads = defaultdict(set)
    
    for tx_trace in trace_result:
        result = tx_trace.get("result", {})
        for address, acc_data in result.items():
            storage = acc_data.get("storage", {})
            for slot in storage.keys():
                reads[address.lower()].add(slot.lower())
    
    return reads


def get_storage_diff_from_block_optimized(
    trace_result: List[dict], 
    additional_reads: Optional[Dict[str, Set[str]]] = None,
    ignore_reads: bool = IGNORE_STORAGE_LOCATIONS
) -> Tuple[bytes, bytes, List[AccountWrites], List[AccountReads]]:
    """
    Build and SSZ‐encode separate AccountWrites and AccountReads for optimized format.
    Returns:
        A tuple of (writes_encoded, reads_encoded, account_writes_list, account_reads_list)
    """
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

                # If written (non-equal values or fresh write)
                if post_val is not None:
                    pre_bytes = (
                        hex_to_bytes32(pre_val) if pre_val is not None else b"\x00" * 32
                    )
                    post_bytes = hex_to_bytes32(post_val)
                    if pre_bytes != post_bytes:
                        _add_write(block_writes, address, slot, tx_id, post_val)

                # If read-only (appears in pre but not modified in post)
                elif not ignore_reads and _is_non_write_read(pre_val, post_val):
                    # Only add as read if this slot wasn't written to in this block
                    if address not in block_writes or slot not in block_writes.get(
                        address, {}
                    ):
                        _add_read(block_reads, address, slot)

    # Add additional reads from diff_mode=False if provided and not ignoring reads
    if not ignore_reads and additional_reads is not None:
        for address, read_slots in additional_reads.items():
            # Only add reads that aren't already written to
            if address not in block_writes:
                for slot in read_slots:
                    _add_read(block_reads, address, slot)
            else:
                written_slots = set(block_writes[address].keys())
                for slot in read_slots:
                    if slot not in written_slots:
                        _add_read(block_reads, address, slot)

    # Build separate writes and reads lists
    account_writes_list = []
    account_reads_list = []

    # Build writes
    for address in block_writes.keys():
        canonical = to_canonical_address(address)
        slot_writes = _build_slot_writes(block_writes, address)
        if slot_writes:
            account_writes_list.append(AccountWrites(address=canonical, slot_writes=slot_writes))

    # Build reads
    if not ignore_reads:
        for address in block_reads.keys():
            canonical = to_canonical_address(address)
            slot_reads = _build_slot_reads(block_reads, block_writes, address)
            if slot_reads:
                account_reads_list.append(AccountReads(address=canonical, slot_reads=slot_reads))

    writes_encoded = ssz.encode(account_writes_list, sedes=AccountWritesList)
    reads_encoded = ssz.encode(account_reads_list, sedes=AccountReadsList)
    
    return writes_encoded, reads_encoded, account_writes_list, account_reads_list


def _get_nonce(info: dict, fallback: str = "0") -> int:
    """Safely parse a nonce string from a state dict, with fallback."""
    nonce_str = info.get("nonce", fallback)
    return int(nonce_str, 16) if isinstance(nonce_str, str) and nonce_str.startswith('0x') else int(nonce_str)


def _should_record_nonce_diff(pre_info: dict, post_info: dict) -> bool:
    """
    Determine whether a nonce diff should be recorded:
    - pre_info has both 'nonce' and 'code'
    - post_nonce > pre_nonce
    """
    if "nonce" not in pre_info or "code" not in pre_info:
        return False

    pre_nonce_str = pre_info["nonce"]
    pre_nonce = int(pre_nonce_str, 16) if isinstance(pre_nonce_str, str) and pre_nonce_str.startswith('0x') else int(pre_nonce_str)
    post_nonce = _get_nonce(post_info, fallback=str(pre_nonce))
    return post_nonce > pre_nonce


def _record_nonce_diff(
    nonce_map: Dict[str, List[Tuple[int, int]]],
    address: str,
    tx_index: int,
    nonce_after: int,
) -> None:
    """Add a nonce change entry to the map."""
    nonce_map.setdefault(address, []).append((tx_index, nonce_after))


def _build_account_nonce_diffs(
    nonce_map: Dict[str, List[Tuple[int, int]]],
) -> List[AccountNonceDiff]:
    """Convert raw nonce map into SSZ-serializable objects."""
    account_nonce_list: List[AccountNonceDiff] = []
    for address_hex, changes in nonce_map.items():
        addr_bytes20 = to_canonical_address(address_hex)
        nonce_changes = [
            TxNonceDiff(tx_index=tx_idx, nonce_after=nonce_after) for tx_idx, nonce_after in changes
        ]
        account_nonce_list.append(
            AccountNonceDiff(address=addr_bytes20, changes=nonce_changes)
        )
    return account_nonce_list


def build_contract_nonce_diffs_from_state(
    trace_result: List[Dict[str, Any]],
) -> Tuple[bytes, List[AccountNonceDiff]]:
    """
    Scan trace_result for contract accounts whose nonce increased during the tx
    (i.e., they executed a CREATE/CREATE2). Returns:
      1) the SSZ-encoded bytes of NonceDiffs,
      2) the raw list[AccountNonceDiff].
    """
    nonce_map: Dict[str, List[Tuple[int, int]]] = {}

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
            _record_nonce_diff(nonce_map, address_hex, tx_index, post_nonce)

    account_nonce_list = _build_account_nonce_diffs(nonce_map)
    encoded_bytes = ssz.encode(account_nonce_list, sedes=NonceDiffs)
    return encoded_bytes, account_nonce_list


def sort_block_access_list_optimized(block_access_list: BlockAccessList) -> BlockAccessList:
    def sort_account_writes(account_writes):
        sorted_accounts = []
        for account in sorted(account_writes, key=lambda a: bytes(a.address)):
            sorted_slot_writes = []
            for slot_write in account.slot_writes:
                # Sort the per-tx writes by tx_index
                writes_sorted = sorted(slot_write.writes, key=lambda x: x.tx_index)
                slot_write_sorted = SlotWrite(slot=slot_write.slot, writes=writes_sorted)
                sorted_slot_writes.append(slot_write_sorted)

            # Sort slots by slot key
            sorted_slot_writes = sorted(sorted_slot_writes, key=lambda s: bytes(s.slot))

            account_sorted = AccountWrites(
                address=account.address, slot_writes=sorted_slot_writes
            )
            sorted_accounts.append(account_sorted)

        return sorted_accounts

    def sort_account_reads(account_reads):
        sorted_accounts = []
        for account in sorted(account_reads, key=lambda a: bytes(a.address)):
            # Sort slots by slot key
            sorted_slot_reads = sorted(account.slot_reads, key=lambda s: bytes(s.slot))

            account_sorted = AccountReads(
                address=account.address, slot_reads=sorted_slot_reads
            )
            sorted_accounts.append(account_sorted)

        return sorted_accounts

    def sort_diffs(diffs, container_cls):
        sorted_accounts = []
        for account in sorted(diffs, key=lambda d: bytes(d.address)):
            changes_sorted = sorted(account.changes, key=lambda x: x.tx_index)

            account_sorted = container_cls(
                address=account.address, changes=changes_sorted
            )
            sorted_accounts.append(account_sorted)

        return sorted_accounts

    def sort_code_diffs(diffs):
        sorted_accounts = []
        for account in sorted(diffs, key=lambda d: bytes(d.address)):
            account_sorted = AccountCodeDiff(
                address=account.address, change=account.change
            )
            sorted_accounts.append(account_sorted)

        return sorted_accounts

    return BlockAccessList(
        storage_writes=sort_account_writes(block_access_list.storage_writes),
        storage_reads=sort_account_reads(block_access_list.storage_reads),
        balance_diffs=sort_diffs(block_access_list.balance_diffs, AccountBalanceDiff),
        code_diffs=sort_code_diffs(block_access_list.code_diffs),
        nonce_diffs=sort_diffs(block_access_list.nonce_diffs, AccountNonceDiff),
    )


def main():
    global IGNORE_STORAGE_LOCATIONS
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Build optimized Block Access Lists (BALs) from Ethereum blocks')
    parser.add_argument('--no-reads', action='store_true', 
                        help='Ignore storage read locations (only include writes)')
    args = parser.parse_args()
    
    # Set IGNORE_STORAGE_LOCATIONS based on command line flag
    IGNORE_STORAGE_LOCATIONS = args.no_reads
    
    print(f"Running optimized BAL builder with IGNORE_STORAGE_LOCATIONS = {IGNORE_STORAGE_LOCATIONS}")
    totals = defaultdict(list)
    block_totals = []
    data = []

    # random_blocks = random.sample(range(22616032 - 7200 * 30, 22616032 + 1), 1000)
    random_blocks = range(22616032 - 7200 * 30, 22616032 + 1, 216)

    for block_number in random_blocks:
        print(f"Processing block {block_number}...")
        trace_result = fetch_block_trace(block_number, RPC_URL)
        
        # Fetch reads separately only if not ignoring storage locations
        block_reads = None
        if not IGNORE_STORAGE_LOCATIONS:
            print(f"  Fetching reads for block {block_number}...")
            block_reads = extract_reads_from_block(block_number, RPC_URL)

        # Get diffs using optimized format
        writes_encoded, reads_encoded, account_writes_list, account_reads_list = get_storage_diff_from_block_optimized(
            trace_result, block_reads, IGNORE_STORAGE_LOCATIONS
        )
        balance_diff, acc_bal_diffs = get_balance_diff_from_block(trace_result)
        code_diff, acc_code_diffs = get_code_diff_from_block(trace_result)
        nonce_diff, account_nonce_list = build_contract_nonce_diffs_from_state(
            trace_result
        )

        block_obj = BlockAccessList(
            storage_writes=account_writes_list,
            storage_reads=account_reads_list,
            balance_diffs=acc_bal_diffs,
            code_diffs=acc_code_diffs,
            nonce_diffs=account_nonce_list,
        )

        block_obj_sorted = sort_block_access_list_optimized(block_obj)

        block_al = ssz.encode(block_obj_sorted, sedes=BlockAccessList)

        # Create bal_raw directory in main project directory if it doesn't exist
        bal_raw_dir = os.path.join(project_root, "bal_raw")
        os.makedirs(bal_raw_dir, exist_ok=True)
        
        # Create filename indicating optimized version and with/without reads
        reads_suffix = "without_reads" if IGNORE_STORAGE_LOCATIONS else "with_reads"
        filename = f"{block_number}_block_access_list_optimized_{reads_suffix}.txt"
        filepath = os.path.join(bal_raw_dir, filename)
        
        with open(filepath, "w") as f:
            f.write(block_al.hex())

        # Get sizes (in KiB)
        writes_size = get_compressed_size(writes_encoded)
        reads_size = get_compressed_size(reads_encoded) if not IGNORE_STORAGE_LOCATIONS else 0
        balance_size = get_compressed_size(balance_diff)
        code_size = get_compressed_size(code_diff)
        nonce_size = get_compressed_size(nonce_diff)

        total_size = writes_size + reads_size + balance_size + code_size + nonce_size

        # Count affected accounts and slots
        accs, slots = count_accounts_and_slots(trace_result)

        # Store stats
        data.append(
            {
                "block_number": block_number,
                "sizes": {
                    "storage_writes_kb": writes_size,
                    "storage_reads_kb": reads_size,
                    "balance_diffs_kb": balance_size,
                    "nonce_diffs_kb": nonce_size,
                    "code_diffs_kb": code_size,
                    "total_kb": total_size,
                },
                "counts": {
                    "accounts": accs,
                    "slots": slots,
                },
            }
        )

        # Totals for averages
        totals["writes"].append(writes_size)
        totals["reads"].append(reads_size)
        totals["balance"].append(balance_size)
        totals["code"].append(code_size)
        totals["nonce"].append(nonce_size)
        block_totals.append(total_size)

    # Save JSON to file
    reads_suffix = "without_reads" if IGNORE_STORAGE_LOCATIONS else "with_reads"
    json_filename = f"bal_analysis_optimized_{reads_suffix}.json"
    with open(json_filename, "w") as f:
        json.dump(data, f, indent=2)

    # Averages
    print("\nAverage compressed size per diff type (in KiB):")
    for name, sizes in totals.items():
        avg = sum(sizes) / len(sizes) if sizes else 0
        print(f"{name}: {avg:.2f} KiB")

    overall_avg = sum(block_totals) / len(block_totals) if block_totals else 0
    print(f"\nOverall average compressed size per block: {overall_avg:.2f} KiB")


if __name__ == "__main__":
    main()