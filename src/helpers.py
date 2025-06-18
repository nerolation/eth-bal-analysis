import pandas as pd
import requests
import snappy


def count_accounts_and_slots(trace_result):
    accounts_set = set()
    total_slots = 0

    for tx in trace_result:
        post = tx.get("result", {}).get("post", {})
        for addr, changes in post.items():
            accounts_set.add(addr)
            if "storage" in changes:
                total_slots += len(changes["storage"])

    return len(accounts_set), total_slots


def get_tracer_payload(block_number_hex, diff_mode=True):
    return {
        "method": "debug_traceBlockByNumber",
        "params": [
            block_number_hex,
            {"tracer": "prestateTracer", "tracerConfig": {"diffMode": diff_mode}},
        ],
        "id": 1,
        "jsonrpc": "2.0",
    }


def fetch_block_trace(block_number, rpc_url, diff_mode=True):
    block_number_hex = hex(block_number)
    payload = get_tracer_payload(block_number_hex, diff_mode)
    response = requests.post(rpc_url, json=payload)
    data = response.json()
    if "error" in data:
        raise Exception(f"RPC Error: {data['error']}")
    return data["result"]


def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    if isinstance(x, (int, float)):
        return int(x)
    if isinstance(x, str):
        if x.startswith("0x"):
            return int(x, 16)
        else:
            return int(x) if x.isdigit() else 0
    return 0


def get_compressed_size(obj, extra_data=None):
    compressed_data = snappy.compress(obj)
    compressed_size = len(compressed_data)

    # If extra data is provided (like contract code), compress that too
    if extra_data:
        for data in extra_data:
            if data:
                compressed_size += len(snappy.compress(data))

    return compressed_size / 1024


def hex_to_bytes32(hexstr: str) -> bytes:
    """Convert a hex string like '0x...' into exactly 32 bytes (big‐endian)."""
    no_pref = hexstr[2:] if hexstr.startswith("0x") else hexstr
    raw = bytes.fromhex(no_pref)
    return raw.rjust(32, b"\x00")
