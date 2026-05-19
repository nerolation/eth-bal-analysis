"""Build RLP-encoded BALs (with storage reads) for 50 random recent blocks."""
import os
import sys
import random
import traceback
from pathlib import Path
from collections import defaultdict

import requests
from eth_utils import to_canonical_address

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

from BALs import BALBuilder, get_account_stats
from helpers import fetch_block_trace, fetch_block_info, fetch_block_receipts
from bal_builder import (
    extract_balance_touches_from_block,
    process_balance_changes,
    process_code_changes,
    extract_reads_from_block,
    process_storage_changes,
    process_nonce_changes,
    collect_touched_addresses,
    sort_block_access_list,
    process_system_contract_changes,
)
from bal_builder_rlp import encode_bal_to_rlp, get_rlp_compressed_size

RPC_URL = (project_root / "rpc.txt").read_text().strip()
OUTPUT_DIR = project_root / "bal_raw" / "rlp"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NUM_BLOCKS = 100
RECENT_WINDOW = 50_000  # sample within roughly the last ~7 days of blocks


def get_latest_block(rpc_url: str) -> int:
    r = requests.post(
        rpc_url,
        json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
        timeout=30,
    )
    r.raise_for_status()
    return int(r.json()["result"], 16)


def build_block(block_number: int) -> dict:
    trace_result = fetch_block_trace(block_number, RPC_URL)
    block_reads = extract_reads_from_block(block_number, RPC_URL)
    balance_touches = extract_balance_touches_from_block(block_number, RPC_URL)
    receipts = fetch_block_receipts(block_number, RPC_URL)
    reverted_tx_indices = {
        i for i, rcpt in enumerate(receipts) if rcpt and rcpt.get("status") == "0x0"
    }
    block_info = fetch_block_info(block_number, RPC_URL)

    builder = BALBuilder()
    touched_addresses = collect_touched_addresses(trace_result)

    process_storage_changes(trace_result, block_reads, False, builder, reverted_tx_indices)
    process_balance_changes(
        trace_result, builder, touched_addresses, balance_touches,
        reverted_tx_indices, block_info, receipts, False,
    )
    process_code_changes(trace_result, builder, reverted_tx_indices)
    process_nonce_changes(trace_result, builder, reverted_tx_indices)

    tx_count = len(block_info.get("transactions", []))
    process_system_contract_changes(block_info, builder, tx_count)

    for addr in touched_addresses:
        builder.add_touched_account(to_canonical_address(addr))

    block_obj = builder.build(ignore_reads=False)
    block_obj_sorted = sort_block_access_list(block_obj)
    encoded = encode_bal_to_rlp(block_obj_sorted)

    out_path = OUTPUT_DIR / f"{block_number}_with_reads.rlp"
    out_path.write_bytes(encoded)

    stats = get_account_stats(block_obj_sorted)
    return {
        "block_number": block_number,
        "raw_size": len(encoded),
        "compressed_kb": get_rlp_compressed_size(encoded),
        "path": str(out_path),
        "stats": stats,
    }


def main() -> None:
    latest = get_latest_block(RPC_URL)
    # Avoid the very tip in case of reorgs/RPC trace lag.
    safe_tip = latest - 64
    lo = safe_tip - RECENT_WINDOW
    rng = random.Random(0xBA1)  # reproducible-ish sampling
    blocks = sorted(rng.sample(range(lo, safe_tip + 1), NUM_BLOCKS))

    print(f"Latest block: {latest}")
    print(f"Sampling {NUM_BLOCKS} blocks from [{lo}, {safe_tip}]")
    print(f"Selected blocks: {blocks}")

    results = []
    failures = []
    for idx, blk in enumerate(blocks, 1):
        print(f"\n[{idx}/{NUM_BLOCKS}] Block {blk}")
        existing = OUTPUT_DIR / f"{blk}_with_reads.rlp"
        if existing.exists() and existing.stat().st_size > 0:
            print(f"  Reusing existing BAL: {existing}")
            data = existing.read_bytes()
            results.append({
                "block_number": blk,
                "raw_size": len(data),
                "compressed_kb": get_rlp_compressed_size(data),
                "path": str(existing),
                "stats": {
                    "total_accounts": 0,
                    "total_storage_writes": 0,
                    "total_storage_reads": 0,
                },
            })
            continue
        try:
            res = build_block(blk)
            print(
                f"  raw={res['raw_size']:,} bytes  compressed={res['compressed_kb']:.2f} KB"
                f"  accounts={res['stats']['total_accounts']}"
                f"  writes={res['stats']['total_storage_writes']}"
                f"  reads={res['stats']['total_storage_reads']}"
            )
            results.append(res)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            traceback.print_exc()
            failures.append((blk, str(exc)))

    print("\n=== Summary ===")
    print(f"Succeeded: {len(results)} / {NUM_BLOCKS}")
    if results:
        avg_raw = sum(r["raw_size"] for r in results) / len(results)
        avg_kb = sum(r["compressed_kb"] for r in results) / len(results)
        avg_reads = sum(r["stats"]["total_storage_reads"] for r in results) / len(results)
        avg_writes = sum(r["stats"]["total_storage_writes"] for r in results) / len(results)
        print(f"Avg raw size: {avg_raw:,.0f} bytes")
        print(f"Avg compressed size: {avg_kb:.2f} KB")
        print(f"Avg storage reads/block: {avg_reads:.1f}")
        print(f"Avg storage writes/block: {avg_writes:.1f}")
    if failures:
        print(f"\nFailed blocks ({len(failures)}):")
        for blk, err in failures:
            print(f"  {blk}: {err}")


if __name__ == "__main__":
    main()
