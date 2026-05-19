"""Bulk-build RLP BALs (with storage reads) over a contiguous range of blocks.

Designed for long unattended runs (e.g. 72,000 blocks = ~10 days of mainnet).
Writes one .rlp file per block plus a JSONL manifest with size + gas stats,
so downstream analysis doesn't need to re-fetch from RPC.

Usage:
    python build_bal_range_bulk.py                       # last 72,064 blocks
    python build_bal_range_bulk.py --start 25000000 --count 72000
    python build_bal_range_bulk.py --workers 16          # adjust parallelism
    python build_bal_range_bulk.py --no-rlp-files        # manifest only

Resumable: rerunning skips any block already present in the manifest with a
matching .rlp file on disk.
"""
import argparse
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
import snappy
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
from bal_builder_rlp import encode_bal_to_rlp

RPC_URL = (project_root / "rpc.txt").read_text().strip()

DEFAULT_COUNT = 72_000
TIP_BUFFER = 64
RPC_TIMEOUT = 60


def rpc_call(method: str, params: list, timeout: int = RPC_TIMEOUT):
    r = requests.post(
        RPC_URL,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"{method} {params}: {data['error']}")
    return data["result"]


def fetch_latest_block() -> int:
    return int(rpc_call("eth_blockNumber", []), 16)


def fetch_raw_block(block_number: int) -> bytes:
    hex_block = hex(block_number)
    raw_hex = rpc_call("debug_getRawBlock", [hex_block])
    return bytes.fromhex(raw_hex[2:])


def compressed_size(data: bytes) -> int:
    return len(snappy.compress(data))


def build_bal(block_number: int) -> bytes:
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

    bal = builder.build(ignore_reads=False)
    bal_sorted = sort_block_access_list(bal)
    return encode_bal_to_rlp(bal_sorted), bal_sorted, block_info


def process_block(block_number: int, save_rlp: bool, rlp_dir: Path) -> dict:
    bal_bytes, bal_sorted, block_info = build_bal(block_number)
    raw_block = fetch_raw_block(block_number)
    gas_used = int(block_info["gasUsed"], 16)
    tx_count = len(block_info.get("transactions", []))
    timestamp = int(block_info["timestamp"], 16)

    if save_rlp:
        out = rlp_dir / f"{block_number}_with_reads.rlp"
        out.write_bytes(bal_bytes)

    stats = get_account_stats(bal_sorted)
    return {
        "block": block_number,
        "timestamp": timestamp,
        "gas_used": gas_used,
        "tx_count": tx_count,
        "bal_raw_bytes": len(bal_bytes),
        "bal_snappy_bytes": compressed_size(bal_bytes),
        "block_raw_bytes": len(raw_block),
        "block_snappy_bytes": compressed_size(raw_block),
        "total_accounts": stats["total_accounts"],
        "total_storage_writes": stats["total_storage_writes"],
        "total_storage_reads": stats["total_storage_reads"],
        "total_balance_changes": stats["total_balance_changes"],
        "total_nonce_changes": stats["total_nonce_changes"],
        "total_code_changes": stats["total_code_changes"],
    }


def load_completed_blocks(manifest_path: Path, rlp_dir: Path, save_rlp: bool) -> set[int]:
    if not manifest_path.exists():
        return set()
    done: set[int] = set()
    with manifest_path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            blk = row.get("block")
            if blk is None:
                continue
            if save_rlp:
                rlp_path = rlp_dir / f"{blk}_with_reads.rlp"
                if not rlp_path.exists() or rlp_path.stat().st_size == 0:
                    continue
            done.add(blk)
    return done


class ManifestWriter:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._fh = path.open("a", buffering=1)  # line-buffered

    def append(self, row: dict) -> None:
        line = json.dumps(row, separators=(",", ":"))
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            self._fh.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=int, default=None,
                        help="First block to process (inclusive). Default: latest - TIP_BUFFER - count.")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help=f"Number of blocks to process. Default: {DEFAULT_COUNT}.")
    parser.add_argument("--workers", type=int, default=16,
                        help="Number of concurrent worker threads. Default: 16.")
    parser.add_argument("--no-rlp-files", action="store_true",
                        help="Skip writing per-block .rlp files (manifest only).")
    parser.add_argument("--rlp-dir", type=Path,
                        default=project_root / "bal_raw" / "rlp",
                        help="Directory for per-block .rlp files.")
    parser.add_argument("--manifest", type=Path,
                        default=project_root / "reports" / "bal_range_manifest.jsonl",
                        help="JSONL output manifest path.")
    args = parser.parse_args()

    save_rlp = not args.no_rlp_files
    args.rlp_dir.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)

    if args.start is None:
        latest = fetch_latest_block()
        end = latest - TIP_BUFFER
        start = end - args.count + 1
    else:
        start = args.start
        end = start + args.count - 1

    print(f"Range: [{start}, {end}]  ({end - start + 1} blocks)")
    print(f"Workers: {args.workers}  save_rlp={save_rlp}")
    print(f"Manifest: {args.manifest}")
    if save_rlp:
        print(f"RLP dir:  {args.rlp_dir}")

    done = load_completed_blocks(args.manifest, args.rlp_dir, save_rlp)
    if done:
        print(f"Resuming: {len(done)} blocks already complete.")

    pending = [b for b in range(start, end + 1) if b not in done]
    if not pending:
        print("Nothing to do.")
        return
    print(f"To process: {len(pending)} blocks.")

    writer = ManifestWriter(args.manifest)
    t0 = time.time()
    completed = 0
    failed = 0
    failed_blocks: list[tuple[int, str]] = []

    def run(blk: int):
        try:
            return blk, process_block(blk, save_rlp, args.rlp_dir), None
        except Exception as exc:
            return blk, None, f"{type(exc).__name__}: {exc}"

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run, b) for b in pending]
            for fut in as_completed(futures):
                blk, row, err = fut.result()
                if err is not None:
                    failed += 1
                    failed_blocks.append((blk, err))
                    if failed <= 20:
                        print(f"FAIL {blk}: {err}", flush=True)
                    continue
                writer.append(row)
                completed += 1
                if completed % 50 == 0 or completed == len(pending):
                    elapsed = time.time() - t0
                    rate = completed / elapsed if elapsed > 0 else 0
                    remaining = (len(pending) - completed) / rate if rate > 0 else float("inf")
                    print(
                        f"[{completed}/{len(pending)}] last={blk}  "
                        f"rate={rate:.2f} blocks/s  "
                        f"eta={remaining/60:.1f} min  "
                        f"failed={failed}",
                        flush=True,
                    )
    finally:
        writer.close()

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed/60:.1f} min.  succeeded={completed}  failed={failed}")
    if failed_blocks:
        fail_log = args.manifest.with_suffix(".failures.txt")
        with fail_log.open("a") as f:
            for blk, err in failed_blocks:
                f.write(f"{blk}\t{err}\n")
        print(f"Failure list appended to {fail_log}")


if __name__ == "__main__":
    main()
