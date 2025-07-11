#!/usr/bin/env python3

import os
import sys
import json
import argparse
from pathlib import Path

# Add src to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import BlockAccessList
import ssz

def bytes_to_hex(b):
    """Convert bytes to hex string"""
    return '0x' + b.hex()

def bal_to_dict(bal):
    """Convert BlockAccessList to JSON-serializable dict"""
    return {
        "account_changes": [
            {
                "address": bytes_to_hex(account.address),
                "storage_writes": [
                    {
                        "slot": bytes_to_hex(sw.slot),
                        "changes": [
                            {
                                "tx_index": change.tx_index,
                                "new_value": bytes_to_hex(change.new_value)
                            }
                            for change in sw.changes
                        ]
                    }
                    for sw in account.storage_writes
                ],
                "storage_reads": [bytes_to_hex(slot) for slot in account.storage_reads],
                "balance_changes": [
                    {
                        "tx_index": bc.tx_index,
                        "post_balance": bytes_to_hex(bc.post_balance)
                    }
                    for bc in account.balance_changes
                ],
                "nonce_changes": [
                    {
                        "tx_index": nc.tx_index,
                        "new_nonce": nc.new_nonce
                    }
                    for nc in account.nonce_changes
                ],
                "code_changes": [
                    {
                        "tx_index": cc.tx_index,
                        "new_code": bytes_to_hex(cc.new_code)
                    }
                    for cc in account.code_changes
                ]
            }
            for account in bal.account_changes
        ]
    }

def main():
    parser = argparse.ArgumentParser(description='Convert SSZ BAL files to JSON')
    parser.add_argument('input_file', help='Input SSZ BAL file')
    parser.add_argument('-o', '--output', help='Output JSON file (default: input_file.json)')
    args = parser.parse_args()
    
    # Read and decode SSZ file
    with open(args.input_file, 'rb') as f:
        encoded_data = f.read()
    
    bal = ssz.decode(encoded_data, BlockAccessList)
    
    # Convert to JSON
    json_data = bal_to_dict(bal)
    
    # Determine output file
    output_file = args.output or f"{args.input_file}.json"
    
    # Write JSON
    with open(output_file, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"Converted {args.input_file} to {output_file}")

if __name__ == "__main__":
    main()