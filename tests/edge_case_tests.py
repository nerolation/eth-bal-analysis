#!/usr/bin/env python3
"""
Edge case tests for EIP-7928 compliance - focusing on complex scenarios
that might break the implementation.
"""

import sys
import os
from pathlib import Path
import json
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

# Add src to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import *
from bal_builder import *
from helpers import *

class EdgeCaseValidator:
    """Validator for edge cases and complex scenarios"""
    
    def __init__(self, trace_result: List[dict], block_obj: BlockAccessList):
        self.trace_result = trace_result
        self.block_obj = block_obj
    
    def test_transaction_index_ordering(self) -> Dict[str, Any]:
        """Test that transaction indices are strictly ordered within each slot"""
        results = {
            "violations": [],
            "total_slots_checked": 0,
            "slots_with_multiple_accesses": 0
        }
        
        for account in self.block_obj.account_accesses:
            for slot_access in account.accesses:
                results["total_slots_checked"] += 1
                
                if len(slot_access.accesses) > 1:
                    results["slots_with_multiple_accesses"] += 1
                    
                    # Check ordering
                    tx_indices = [access.tx_index for access in slot_access.accesses]
                    sorted_indices = sorted(tx_indices)
                    
                    if tx_indices != sorted_indices:
                        results["violations"].append({
                            "address": account.address.hex(),
                            "slot": slot_access.slot.hex(),
                            "found_order": tx_indices,
                            "expected_order": sorted_indices
                        })
        
        return results
    
    def test_address_ordering(self) -> Dict[str, Any]:
        """Test that addresses are lexicographically ordered across all diff types"""
        results = {
            "violations": [],
            "account_accesses_ordered": True,
            "balance_diffs_ordered": True,
            "code_diffs_ordered": True,
            "nonce_diffs_ordered": True
        }
        
        # Check account accesses
        prev_addr = None
        for account in self.block_obj.account_accesses:
            if prev_addr is not None and bytes(account.address) <= prev_addr:
                results["account_accesses_ordered"] = False
                results["violations"].append({
                    "type": "account_accesses",
                    "violation": f"Address {account.address.hex()} not ordered after {prev_addr.hex()}"
                })
            prev_addr = bytes(account.address)
        
        # Check balance diffs
        prev_addr = None
        for account in self.block_obj.balance_diffs:
            if prev_addr is not None and bytes(account.address) <= prev_addr:
                results["balance_diffs_ordered"] = False
                results["violations"].append({
                    "type": "balance_diffs",
                    "violation": f"Address {account.address.hex()} not ordered after {prev_addr.hex()}"
                })
            prev_addr = bytes(account.address)
        
        # Check code diffs
        prev_addr = None
        for account in self.block_obj.code_diffs:
            if prev_addr is not None and bytes(account.address) <= prev_addr:
                results["code_diffs_ordered"] = False
                results["violations"].append({
                    "type": "code_diffs",
                    "violation": f"Address {account.address.hex()} not ordered after {prev_addr.hex()}"
                })
            prev_addr = bytes(account.address)
        
        # Check nonce diffs
        prev_addr = None
        for account in self.block_obj.nonce_diffs:
            if prev_addr is not None and bytes(account.address) <= prev_addr:
                results["nonce_diffs_ordered"] = False
                results["violations"].append({
                    "type": "nonce_diffs",
                    "violation": f"Address {account.address.hex()} not ordered after {prev_addr.hex()}"
                })
            prev_addr = bytes(account.address)
        
        return results
    
    def test_storage_key_ordering(self) -> Dict[str, Any]:
        """Test that storage keys are lexicographically ordered within each account"""
        results = {
            "violations": [],
            "total_accounts_checked": 0,
            "accounts_with_multiple_slots": 0
        }
        
        for account in self.block_obj.account_accesses:
            results["total_accounts_checked"] += 1
            
            if len(account.accesses) > 1:
                results["accounts_with_multiple_slots"] += 1
                
                # Check slot ordering
                prev_slot = None
                for slot_access in account.accesses:
                    if prev_slot is not None and bytes(slot_access.slot) <= prev_slot:
                        results["violations"].append({
                            "address": account.address.hex(),
                            "violation": f"Slot {slot_access.slot.hex()} not ordered after {prev_slot.hex()}"
                        })
                    prev_slot = bytes(slot_access.slot)
        
        return results
    
    def test_read_write_consistency(self) -> Dict[str, Any]:
        """Test consistency between reads and writes - no slot should be both read and written"""
        results = {
            "read_write_conflicts": [],
            "total_read_slots": 0,
            "total_write_slots": 0
        }
        
        # Collect all writes
        write_slots = set()  # (address, slot) tuples
        read_slots = set()   # (address, slot) tuples
        
        for account in self.block_obj.account_accesses:
            addr_hex = account.address.hex()
            
            for slot_access in account.accesses:
                slot_hex = slot_access.slot.hex()
                slot_tuple = (addr_hex, slot_hex)
                
                if len(slot_access.accesses) == 0:
                    # Read-only
                    read_slots.add(slot_tuple)
                    results["total_read_slots"] += 1
                else:
                    # Write
                    write_slots.add(slot_tuple)
                    results["total_write_slots"] += 1
        
        # Check for conflicts
        conflicts = read_slots.intersection(write_slots)
        results["read_write_conflicts"] = [
            {"address": addr, "slot": slot} for addr, slot in conflicts
        ]
        
        return results
    
    def test_transaction_coverage(self) -> Dict[str, Any]:
        """Test that all transactions that modify state are represented in the BAL"""
        results = {
            "missing_transactions": [],
            "total_transactions": len(self.trace_result),
            "transactions_with_storage_writes": 0,
            "transactions_with_balance_changes": 0,
            "transactions_in_bal": set()
        }
        
        # Collect all transaction indices from BAL
        bal_tx_indices = set()
        
        # From storage accesses
        for account in self.block_obj.account_accesses:
            for slot_access in account.accesses:
                for access in slot_access.accesses:
                    bal_tx_indices.add(access.tx_index)
        
        # From balance changes
        for account in self.block_obj.balance_diffs:
            for change in account.changes:
                bal_tx_indices.add(change.tx_index)
        
        # From code changes
        for account in self.block_obj.code_diffs:
            for change in account.changes:
                bal_tx_indices.add(change.tx_index)
        
        # From nonce changes
        for account in self.block_obj.nonce_diffs:
            for change in account.changes:
                bal_tx_indices.add(change.tx_index)
        
        results["transactions_in_bal"] = list(bal_tx_indices)
        
        # Check each transaction in trace
        for tx_id, tx in enumerate(self.trace_result):
            result = tx.get("result")
            if not isinstance(result, dict):
                continue
            
            pre_state = result.get("pre", {})
            post_state = result.get("post", {})
            
            has_storage_writes = False
            has_balance_changes = False
            
            # Check for storage writes
            for address in set(pre_state.keys()) | set(post_state.keys()):
                pre_storage = pre_state.get(address, {}).get("storage", {})
                post_storage = post_state.get(address, {}).get("storage", {})
                
                for slot in set(pre_storage.keys()) | set(post_storage.keys()):
                    pre_val = pre_storage.get(slot)
                    post_val = post_storage.get(slot)
                    
                    if post_val is not None:
                        pre_bytes = hex_to_bytes32(pre_val) if pre_val else b"\x00" * 32
                        post_bytes = hex_to_bytes32(post_val)
                        if pre_bytes != post_bytes:
                            has_storage_writes = True
                            break
                
                # Check for balance changes
                pre_balance = parse_hex_or_zero(pre_state.get(address, {}).get("balance"))
                post_balance = parse_hex_or_zero(post_state.get(address, {}).get("balance"))
                if pre_balance != post_balance:
                    has_balance_changes = True
                
                if has_storage_writes and has_balance_changes:
                    break
            
            if has_storage_writes:
                results["transactions_with_storage_writes"] += 1
            if has_balance_changes:
                results["transactions_with_balance_changes"] += 1
            
            # Check if transaction is missing from BAL
            if (has_storage_writes or has_balance_changes) and tx_id not in bal_tx_indices:
                results["missing_transactions"].append({
                    "tx_id": tx_id,
                    "has_storage_writes": has_storage_writes,
                    "has_balance_changes": has_balance_changes
                })
        
        return results
    
    def test_value_consistency(self) -> Dict[str, Any]:
        """Test that values in BAL match the trace data"""
        results = {
            "value_mismatches": [],
            "total_values_checked": 0
        }
        
        # Build mapping from trace
        trace_final_values = {}  # (address, slot) -> final_value
        
        for tx_id, tx in enumerate(self.trace_result):
            result = tx.get("result")
            if not isinstance(result, dict):
                continue
            
            post_state = result.get("post", {})
            
            for address, info in post_state.items():
                storage = info.get("storage", {})
                for slot, value in storage.items():
                    addr_canonical = to_canonical_address(address).hex()
                    slot_canonical = hex_to_bytes32(slot).hex()
                    trace_final_values[(addr_canonical, slot_canonical)] = hex_to_bytes32(value).hex()
        
        # Check BAL values
        for account in self.block_obj.account_accesses:
            addr_hex = account.address.hex()
            
            for slot_access in account.accesses:
                slot_hex = slot_access.slot.hex()
                
                if len(slot_access.accesses) > 0:  # Has writes
                    # Check final value
                    final_access = slot_access.accesses[-1]  # Last write
                    bal_final_value = final_access.value_after.hex()
                    
                    trace_key = (addr_hex, slot_hex)
                    if trace_key in trace_final_values:
                        trace_final_value = trace_final_values[trace_key]
                        
                        if bal_final_value != trace_final_value:
                            results["value_mismatches"].append({
                                "address": addr_hex,
                                "slot": slot_hex,
                                "bal_value": bal_final_value,
                                "trace_value": trace_final_value
                            })
                    
                    results["total_values_checked"] += 1
        
        return results

def run_edge_case_tests(block_number: int, rpc_url: str) -> Dict[str, Any]:
    """Run comprehensive edge case tests on a block"""
    print(f"\n{'='*60}")
    print(f"EDGE CASE TESTING - Block {block_number}")
    print(f"{'='*60}")
    
    try:
        # Generate BAL
        trace_result = fetch_block_trace(block_number, rpc_url)
        
        storage_diff, account_access_list = get_storage_diff_from_block(trace_result)
        balance_diff, acc_bal_diffs = get_balance_diff_from_block(trace_result)
        code_diff, acc_code_diffs = get_code_diff_from_block(trace_result)
        nonce_diff, account_nonce_list = build_contract_nonce_diffs_from_state(trace_result)
        
        block_obj = BlockAccessList(
            account_accesses=account_access_list,
            balance_diffs=acc_bal_diffs,
            code_diffs=acc_code_diffs,
            nonce_diffs=account_nonce_list,
        )
        block_obj_sorted = sort_block_access_list(block_obj)
        
        print(f"✓ Generated BAL with {len(account_access_list)} account accesses")
        
        # Run edge case tests
        validator = EdgeCaseValidator(trace_result, block_obj_sorted)
        
        tx_ordering = validator.test_transaction_index_ordering()
        address_ordering = validator.test_address_ordering()
        storage_ordering = validator.test_storage_key_ordering()
        read_write_consistency = validator.test_read_write_consistency()
        tx_coverage = validator.test_transaction_coverage()
        value_consistency = validator.test_value_consistency()
        
        # Print results
        print(f"\n📋 EDGE CASE TEST RESULTS:")
        
        print(f"  Transaction Index Ordering:")
        print(f"    Slots checked: {tx_ordering['total_slots_checked']}")
        print(f"    Multi-access slots: {tx_ordering['slots_with_multiple_accesses']}")
        print(f"    Violations: {len(tx_ordering['violations'])}")
        
        print(f"  Address Ordering:")
        print(f"    Account accesses ordered: {address_ordering['account_accesses_ordered']}")
        print(f"    Balance diffs ordered: {address_ordering['balance_diffs_ordered']}")
        print(f"    Code diffs ordered: {address_ordering['code_diffs_ordered']}")
        print(f"    Nonce diffs ordered: {address_ordering['nonce_diffs_ordered']}")
        print(f"    Total violations: {len(address_ordering['violations'])}")
        
        print(f"  Storage Key Ordering:")
        print(f"    Accounts checked: {storage_ordering['total_accounts_checked']}")
        print(f"    Multi-slot accounts: {storage_ordering['accounts_with_multiple_slots']}")
        print(f"    Violations: {len(storage_ordering['violations'])}")
        
        print(f"  Read/Write Consistency:")
        print(f"    Total read slots: {read_write_consistency['total_read_slots']}")
        print(f"    Total write slots: {read_write_consistency['total_write_slots']}")
        print(f"    Conflicts: {len(read_write_consistency['read_write_conflicts'])}")
        
        print(f"  Transaction Coverage:")
        print(f"    Total transactions: {tx_coverage['total_transactions']}")
        print(f"    Transactions in BAL: {len(tx_coverage['transactions_in_bal'])}")
        print(f"    Missing transactions: {len(tx_coverage['missing_transactions'])}")
        
        print(f"  Value Consistency:")
        print(f"    Values checked: {value_consistency['total_values_checked']}")
        print(f"    Mismatches: {len(value_consistency['value_mismatches'])}")
        
        # Calculate pass/fail
        all_tests_passed = (
            len(tx_ordering['violations']) == 0 and
            len(address_ordering['violations']) == 0 and
            len(storage_ordering['violations']) == 0 and
            len(read_write_consistency['read_write_conflicts']) == 0 and
            len(tx_coverage['missing_transactions']) == 0 and
            len(value_consistency['value_mismatches']) == 0
        )
        
        if all_tests_passed:
            print(f"\n🎉 ALL EDGE CASE TESTS PASSED!")
        else:
            print(f"\n❌ EDGE CASE FAILURES DETECTED")
        
        return {
            "success": True,
            "block_number": block_number,
            "all_tests_passed": all_tests_passed,
            "results": {
                "transaction_ordering": tx_ordering,
                "address_ordering": address_ordering,
                "storage_ordering": storage_ordering,
                "read_write_consistency": read_write_consistency,
                "transaction_coverage": tx_coverage,
                "value_consistency": value_consistency
            }
        }
        
    except Exception as e:
        print(f"❌ Error in edge case testing: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "block_number": block_number,
            "error": str(e)
        }

def main():
    """Run edge case tests"""
    # Read RPC URL
    rpc_file = os.path.join(project_root, "rpc.txt")
    with open(rpc_file, "r") as f:
        rpc_url = f.read().strip()
    
    # Test blocks with different characteristics
    test_blocks = [
        18000000,  # Normal block
        18500000,  # Higher activity block  
        19000000,  # Another test block
    ]
    
    print("🧪 COMPREHENSIVE EDGE CASE TESTING")
    
    results = []
    for block_number in test_blocks:
        result = run_edge_case_tests(block_number, rpc_url)
        results.append(result)
    
    # Summary
    successful = [r for r in results if r["success"]]
    all_passed = [r for r in successful if r["all_tests_passed"]]
    
    print(f"\n{'='*60}")
    print(f"EDGE CASE SUMMARY")
    print(f"{'='*60}")
    print(f"Blocks tested: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"All tests passed: {len(all_passed)}")
    
    if len(all_passed) == len(successful):
        print("🎉 ALL EDGE CASE TESTS PASSED FOR ALL BLOCKS!")
    else:
        print("⚠️  Some edge case tests failed")
    
    # Save results
    output_file = os.path.join(project_root, "edge_case_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()