import os
import sys
import json
import random
import requests
import asyncio
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from web3 import Web3
from eth_utils import to_canonical_address
import ssz

from BALs import *
from helpers import *

with open("../../rpc.txt", "r") as file:
    RPC_URL = file.read().strip()
    
IGNORE_STORAGE_LOCATIONS = False


def extract_balances(state):
    return {
        addr: bal for addr, changes in state.items()
        if (bal := parse_hex_or_zero(changes.get("balance")))
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
            tx_index=tx_id,
            delta=delta_val.to_bytes(12, "big", signed=True)
        )
        if address in acc_map:
            acc_map[address].changes.append(bal_diff)
        else:
            canonical = to_canonical_address(address)
            acc_map[address] = AccountBalanceDiff(
                address=canonical,
                changes=[bal_diff]
            )
    return acc_map

def get_balance_delta(pres, posts, pre_balances, post_balances):
    all_addresses = pres.intersection(posts)
    balance_delta = {addr: post_balances[addr] - pre_balances[addr] for addr in all_addresses}
    return balance_delta
    
def get_balance_diff_from_block(trace_result):
    acc_bal_diffs = []
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
        acc_bal_diffs.extend(list(acc_map.values()))

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
    acc_map: Dict[str, AccountCodeDiff]
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

    if address_hex in acc_map:
        acc_map[address_hex].changes.append(change)
    else:
        acc_map[address_hex] = AccountCodeDiff(
            address=to_canonical_address(address_hex),
            changes=[change]
        )


def get_code_diff_from_block(trace_result: List[dict]) -> bytes:
    """
    Builds and SSZ‐encodes all AccountCodeDiff entries for the given trace_result.
    Returns an SSZ-encoded byte blob using `CodeDiffs` as the top-level sedes.
    """
    acc_code_diffs: List[AccountCodeDiff] = []

    for tx_id, tx in enumerate(trace_result):
        tx_hash = tx.get("txHash")
        result = tx.get("result")
        if not isinstance(result, dict):
            print(f"Unexpected result type for tx {tx_hash}: {type(result)}")
            continue

        pre_state, post_state = result.get("pre", {}), result.get("post", {})
        acc_map: Dict[str, AccountCodeDiff] = {}

        all_addresses = set(pre_state) | set(post_state)

        for address in all_addresses:
            pre_code = extract_non_empty_code(pre_state, address)
            post_code = extract_non_empty_code(post_state, address)
            process_code_change(tx_id, address, pre_code, post_code, acc_map)

        acc_code_diffs.extend(acc_map.values())

    return ssz.encode(acc_code_diffs, sedes=CodeDiffs), acc_code_diffs


def _is_non_write_read(pre_val_hex: Optional[str], post_val_hex: Optional[str]) -> bool:
    """Check if a storage slot qualifies as a pure read."""
    return pre_val_hex is not None and post_val_hex is None


def _add_write(
    acc_map_write: Dict[str, Dict[str, List[Tuple[int, str]]]],
    address: str,
    slot: str,
    tx_id: int,
    new_val_hex: str
) -> None:
    acc_map_write.setdefault(address, {}).setdefault(slot, []).append((tx_id, new_val_hex))


def _add_read(
    acc_map_reads: Dict[str, Set[str]],
    address: str,
    slot: str
) -> None:
    acc_map_reads.setdefault(address, set()).add(slot)


def _build_slot_accesses(
    acc_map_write: Dict[str, Dict[str, List[Tuple[int, str]]]],
    acc_map_reads: Dict[str, Set[str]],
    address_hex: str
) -> List[SlotAccess]:
    """Build all SlotAccess entries (writes + pure reads) for one address."""
    slot_accesses: List[SlotAccess] = []

    # Handle writes
    for slot_hex, write_entries in acc_map_write.get(address_hex, {}).items():
        slot = hex_to_bytes32(slot_hex)
        accesses = [
            PerTxAccess(tx_index=tx_id, value_after=hex_to_bytes32(val_hex))
            for tx_id, val_hex in write_entries
        ]
        slot_accesses.append(SlotAccess(slot=slot, accesses=accesses))

    # Handle reads (only if not written)
    written_slots = set(acc_map_write.get(address_hex, {}))
    for slot_hex in acc_map_reads.get(address_hex, set()):
        if slot_hex in written_slots:
            continue
        slot = hex_to_bytes32(slot_hex)
        slot_accesses.append(SlotAccess(slot=slot, accesses=[]))  # empty list → pure read

    return slot_accesses


def get_storage_diff_from_block(trace_result: List[dict]) -> bytes:
    """
    Build and SSZ‐encode the BlockAccessList for a given list of tx‐trace dictionaries.
    Returns:
        A single SSZ‐encoded byte blob using `BlockAccessList` as the top-level sedes.
    """
    per_address_slotaccesses: Dict[bytes, List[SlotAccess]] = {}

    for tx_id, tx in enumerate(trace_result):
        result = tx.get("result")
        if not isinstance(result, dict):
            continue

        pre_state = result.get("pre", {})
        post_state = result.get("post", {})

        acc_map_write: Dict[str, Dict[str, List[Tuple[int, str]]]] = {}
        acc_map_reads: Dict[str, Set[str]] = {}

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
                    pre_bytes = hex_to_bytes32(pre_val) if pre_val is not None else b"\x00" * 32
                    post_bytes = hex_to_bytes32(post_val)
                    if pre_bytes != post_bytes:
                        _add_write(acc_map_write, address, slot, tx_id, post_val)

                # If read-only
                elif _is_non_write_read(pre_val, post_val):
                    if slot not in acc_map_write.get(address, {}):
                        _add_read(acc_map_reads, address, slot)

        # Add slot accesses for this tx to the global per-address list
        for address in set(acc_map_write) | set(acc_map_reads):
            canonical = to_canonical_address(address)
            if canonical not in per_address_slotaccesses:
                per_address_slotaccesses[canonical] = []

            per_address_slotaccesses[canonical].extend(
                _build_slot_accesses(acc_map_write, acc_map_reads, address)
            )

    account_access_list = [
        AccountAccess(address=addr, accesses=slots)
        for addr, slots in per_address_slotaccesses.items()
        if slots
    ]

    return ssz.encode(account_access_list, sedes=AccountAccessList), account_access_list


def _get_nonce(info: dict, fallback: str = "0") -> int:
    """Safely parse a nonce string from a state dict, with fallback."""
    return int(info.get("nonce", fallback))


def _should_record_nonce_diff(pre_info: dict, post_info: dict) -> bool:
    """
    Determine whether a nonce diff should be recorded:
    - pre_info has both 'nonce' and 'code'
    - post_nonce > pre_nonce
    """
    if "nonce" not in pre_info or "code" not in pre_info:
        return False

    pre_nonce = int(pre_info["nonce"])
    post_nonce = _get_nonce(post_info, fallback=pre_info["nonce"])
    return post_nonce > pre_nonce


def _record_nonce_diff(
    nonce_map: Dict[str, List[Tuple[int, int]]],
    address: str,
    tx_index: int,
    pre_nonce: int
) -> None:
    """Add a nonce change entry to the map."""
    nonce_map.setdefault(address, []).append((tx_index, pre_nonce))


def _build_account_nonce_diffs(
    nonce_map: Dict[str, List[Tuple[int, int]]]
) -> List[AccountNonceDiff]:
    """Convert raw nonce map into SSZ-serializable objects."""
    account_nonce_list: List[AccountNonceDiff] = []
    for address_hex, changes in nonce_map.items():
        addr_bytes20 = to_canonical_address(address_hex)
        nonce_changes = [NonceChange(tx_index=tx_idx, nonce=pre_n) for tx_idx, pre_n in changes]
        account_nonce_list.append(AccountNonceDiff(address=addr_bytes20, changes=nonce_changes))
    return account_nonce_list


def build_contract_nonce_diffs_from_state(
    trace_result: List[Dict[str, Any]]
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
            if not _should_record_nonce_diff(pre_info, post_state.get(address_hex, {})):
                continue
            pre_nonce = int(pre_info["nonce"])
            _record_nonce_diff(nonce_map, address_hex, tx_index, pre_nonce)

    account_nonce_list = _build_account_nonce_diffs(nonce_map)
    encoded_bytes = ssz.encode(account_nonce_list, sedes=NonceDiffs)
    return encoded_bytes, account_nonce_list


async def main():
    totals = defaultdict(list)
    block_totals = []
    data = []

    #random_blocks = random.sample(range(22616032 - 7200 * 30, 22616032 + 1), 1000)
    random_blocks = range(22616032 - 7200 * 30, 22616032 + 1, 216)

    for block_number in random_blocks:
        print(f"Processing block {block_number}...")
        trace_result = fetch_block_trace(block_number, RPC_URL)

        # Get diffs
        storage_diff, account_access_list = get_storage_diff_from_block(trace_result.copy())
        balance_diff, acc_bal_diffs = get_balance_diff_from_block(trace_result.copy())
        code_diff, acc_code_diffs = get_code_diff_from_block(trace_result.copy())
        nonce_diff, account_nonce_list = build_contract_nonce_diffs_from_state(trace_result.copy())
        
        
        block_obj = BlockAccessList(
            account_accesses=account_access_list,
            balance_diffs=acc_bal_diffs,
            code_diffs=acc_code_diffs,
            nonce_diffs=account_nonce_list,
        )
        block_al = ssz.encode(block_obj, sedes=BlockAccessList)

        # Get sizes (in KiB)
        storage_size = get_compressed_size(storage_diff)
        balance_size = get_compressed_size(balance_diff)
        code_size = get_compressed_size(code_diff)
        nonce_size = get_compressed_size(nonce_diff)

        total_size = storage_size + balance_size + code_size + nonce_size

        # Count affected accounts and slots
        accs, slots = count_accounts_and_slots(trace_result)

        # Store stats
        data.append({
            "block_number": block_number,
            "sizes": {
                "storage_access_kb": storage_size,
                "balance_diffs_kb": balance_size,
                "nonce_diffs_kb": nonce_size,
                "code_diffs_kb": code_size,
                "total_kb": total_size,
            },
            "counts": {
                "accounts": accs,
                "slots": slots,
            }
        })

        # Totals for averages
        totals["storage"].append(storage_size)
        totals["balance"].append(balance_size)
        totals["code"].append(code_size)
        totals["nonce"].append(nonce_size)
        block_totals.append(total_size)

    # Save JSON to file
    with open("bal_analysis_with_reads.json", "w") as f:
        json.dump(data, f, indent=2)

    # Averages
    print("\nAverage compressed size per diff type (in KiB):")
    for name, sizes in totals.items():
        avg = sum(sizes) / len(sizes) if sizes else 0
        print(f"{name}: {avg:.2f} KiB")

    overall_avg = sum(block_totals) / len(block_totals) if block_totals else 0
    print(f"\nOverall average compressed size per block: {overall_avg:.2f} KiB")

if __name__ == "__main__":
    asyncio.run(main())
