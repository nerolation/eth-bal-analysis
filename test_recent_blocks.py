#!/usr/bin/env python3
"""
Test cases for EIP-7928 Block Access Lists using recent Ethereum blocks.
This script tests the BAL implementation against real block data.
"""

import sys
import os
from pathlib import Path
import json
from typing import Dict, List, Any

# Add src to path
project_root = str(Path(__file__).parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import *
from bal_builder import *
from helpers import *

# Test configuration - using blocks that should exist
TEST_BLOCKS = [
    18000000,  # Different block
    18500000,  # Another block
    19000000,  # Block from early 2024
]

def test_block_access_list_generation(block_number: int, rpc_url: str) -> Dict[str, Any]:
    """
    Test BAL generation for a specific block and validate against EIP-7928.
    Returns test results and metrics.
    """
    print(f"\n=== Testing Block {block_number} ===")
    
    try:
        # Fetch block trace
        trace_result = fetch_block_trace(block_number, rpc_url)
        print(f"✓ Fetched trace for block {block_number} with {len(trace_result)} transactions")
        
        # Generate BAL components
        storage_diff, account_access_list = get_storage_diff_from_block(trace_result)
        balance_diff, acc_bal_diffs = get_balance_diff_from_block(trace_result)
        code_diff, acc_code_diffs = get_code_diff_from_block(trace_result)
        nonce_diff, account_nonce_list = build_contract_nonce_diffs_from_state(trace_result)
        
        # Build complete BAL
        block_obj = BlockAccessList(
            account_accesses=account_access_list,
            balance_diffs=acc_bal_diffs,
            code_diffs=acc_code_diffs,
            nonce_diffs=account_nonce_list,
        )
        
        # Sort the BAL
        block_obj_sorted = sort_block_access_list(block_obj)
        
        # Validate EIP-7928 compliance
        validation_results = validate_eip7928_compliance(block_obj_sorted)
        
        # Get metrics
        metrics = {
            "block_number": block_number,
            "tx_count": len(trace_result),
            "account_accesses_count": len(account_access_list),
            "balance_diffs_count": len(acc_bal_diffs),
            "code_diffs_count": len(acc_code_diffs),
            "nonce_diffs_count": len(account_nonce_list),
            "storage_size_bytes": len(storage_diff),
            "balance_size_bytes": len(balance_diff),
            "code_size_bytes": len(code_diff),
            "nonce_size_bytes": len(nonce_diff),
        }
        
        # Test SSZ encoding
        try:
            block_al = ssz.encode(block_obj_sorted, sedes=BlockAccessList)
            metrics["total_bal_size_bytes"] = len(block_al)
            print(f"✓ SSZ encoding successful: {len(block_al)} bytes")
        except Exception as e:
            print(f"✗ SSZ encoding failed: {e}")
            metrics["encoding_error"] = str(e)
        
        print(f"✓ Block {block_number} processed successfully")
        return {
            "success": True,
            "metrics": metrics,
            "validation": validation_results,
            "block_obj": block_obj_sorted
        }
        
    except Exception as e:
        print(f"✗ Error processing block {block_number}: {e}")
        return {
            "success": False,
            "error": str(e),
            "block_number": block_number
        }

def validate_eip7928_compliance(block_obj: BlockAccessList) -> Dict[str, Any]:
    """
    Validate that the generated BAL complies with EIP-7928 requirements.
    """
    results = {
        "addresses_sorted": True,
        "tx_indices_sorted": True,
        "storage_keys_sorted": True,
        "errors": []
    }
    
    # Check account addresses are sorted
    account_accesses = block_obj.account_accesses
    for i in range(1, len(account_accesses)):
        if bytes(account_accesses[i-1].address) >= bytes(account_accesses[i].address):
            results["addresses_sorted"] = False
            results["errors"].append(f"Account addresses not sorted at index {i}")
    
    # Check storage keys are sorted within each account
    for account in account_accesses:
        accesses = account.accesses
        for i in range(1, len(accesses)):
            if bytes(accesses[i-1].slot) >= bytes(accesses[i].slot):
                results["storage_keys_sorted"] = False
                results["errors"].append(f"Storage keys not sorted for account {account.address.hex()}")
        
        # Check tx indices are sorted within each slot access
        for slot_access in accesses:
            for i in range(1, len(slot_access.accesses)):
                if slot_access.accesses[i-1].tx_index >= slot_access.accesses[i].tx_index:
                    results["tx_indices_sorted"] = False
                    results["errors"].append(f"TX indices not sorted for slot {slot_access.slot.hex()}")
    
    # Check balance diffs are sorted by address
    balance_diffs = block_obj.balance_diffs
    for i in range(1, len(balance_diffs)):
        if bytes(balance_diffs[i-1].address) >= bytes(balance_diffs[i].address):
            results["addresses_sorted"] = False
            results["errors"].append(f"Balance diff addresses not sorted at index {i}")
    
    # Check code diffs are sorted by address
    code_diffs = block_obj.code_diffs
    for i in range(1, len(code_diffs)):
        if bytes(code_diffs[i-1].address) >= bytes(code_diffs[i].address):
            results["addresses_sorted"] = False
            results["errors"].append(f"Code diff addresses not sorted at index {i}")
    
    # Check nonce diffs are sorted by address
    nonce_diffs = block_obj.nonce_diffs
    for i in range(1, len(nonce_diffs)):
        if bytes(nonce_diffs[i-1].address) >= bytes(nonce_diffs[i].address):
            results["addresses_sorted"] = False
            results["errors"].append(f"Nonce diff addresses not sorted at index {i}")
    
    return results

def analyze_read_write_patterns(block_obj: BlockAccessList) -> Dict[str, Any]:
    """
    Analyze read vs write patterns to identify potential issues.
    """
    analysis = {
        "read_only_slots": 0,
        "write_slots": 0,
        "total_accesses": 0,
        "addresses_with_reads": 0,
        "addresses_with_writes": 0,
    }
    
    for account in block_obj.account_accesses:
        has_reads = False
        has_writes = False
        
        for slot_access in account.accesses:
            analysis["total_accesses"] += 1
            
            if len(slot_access.accesses) == 0:
                # Empty access list = read-only
                analysis["read_only_slots"] += 1
                has_reads = True
            else:
                # Non-empty access list = write
                analysis["write_slots"] += 1
                has_writes = True
        
        if has_reads:
            analysis["addresses_with_reads"] += 1
        if has_writes:
            analysis["addresses_with_writes"] += 1
    
    return analysis

def main():
    """Run tests on recent blocks."""
    # Read RPC URL
    rpc_file = os.path.join(project_root, "rpc.txt")
    if not os.path.exists(rpc_file):
        print("Error: rpc.txt file not found. Please create it with your RPC URL.")
        return
    
    with open(rpc_file, "r") as f:
        rpc_url = f.read().strip()
    
    print("Testing EIP-7928 Block Access List Implementation")
    print("=" * 50)
    
    results = []
    
    for block_number in TEST_BLOCKS:
        result = test_block_access_list_generation(block_number, rpc_url)
        results.append(result)
        
        if result["success"]:
            # Analyze read/write patterns
            analysis = analyze_read_write_patterns(result["block_obj"])
            print(f"\nRead/Write Analysis for Block {block_number}:")
            for key, value in analysis.items():
                print(f"  {key}: {value}")
            
            # Print validation results
            validation = result["validation"]
            print(f"\nEIP-7928 Compliance for Block {block_number}:")
            print(f"  Addresses sorted: {validation['addresses_sorted']}")
            print(f"  TX indices sorted: {validation['tx_indices_sorted']}")
            print(f"  Storage keys sorted: {validation['storage_keys_sorted']}")
            if validation["errors"]:
                print(f"  Errors: {len(validation['errors'])}")
                for error in validation["errors"][:3]:  # Show first 3 errors
                    print(f"    - {error}")
    
    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"Successful: {len(successful)}/{len(results)}")
    print(f"Failed: {len(failed)}/{len(results)}")
    
    if successful:
        avg_metrics = {}
        for key in successful[0]["metrics"]:
            if isinstance(successful[0]["metrics"][key], (int, float)):
                avg_metrics[key] = sum(r["metrics"][key] for r in successful) / len(successful)
        
        print(f"\nAverage Metrics:")
        for key, value in avg_metrics.items():
            if isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
    
    # Save detailed results
    output_file = os.path.join(project_root, "test_results.json")
    with open(output_file, "w") as f:
        # Convert any non-serializable objects
        serializable_results = []
        for r in results:
            clean_result = {k: v for k, v in r.items() if k != "block_obj"}
            serializable_results.append(clean_result)
        json.dump(serializable_results, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()