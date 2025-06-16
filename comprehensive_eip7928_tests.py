#!/usr/bin/env python3
"""
Comprehensive EIP-7928 compliance tests focusing on transaction index completeness
and read/write detection accuracy.
"""

import sys
import os
from pathlib import Path
import json
from typing import Dict, List, Any, Set, Tuple
from collections import defaultdict

# Add src to path
project_root = str(Path(__file__).parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import *
from bal_builder import *
from helpers import *

class EIP7928ComplianceValidator:
    """Comprehensive validator for EIP-7928 compliance"""
    
    def __init__(self, trace_result: List[dict], block_obj: BlockAccessList):
        self.trace_result = trace_result
        self.block_obj = block_obj
        self.validation_results = {}
        
        # Extract ground truth from trace
        self.ground_truth = self._extract_ground_truth()
        
    def _extract_ground_truth(self) -> Dict[str, Any]:
        """Extract ground truth access patterns from raw trace data"""
        ground_truth = {
            "writes": defaultdict(lambda: defaultdict(list)),  # address -> slot -> [(tx_id, value)]
            "reads": defaultdict(set),  # address -> set of slots
            "all_accesses": defaultdict(lambda: defaultdict(set)),  # address -> slot -> set of tx_ids
            "tx_storage_accesses": defaultdict(lambda: defaultdict(set)),  # tx_id -> address -> set of slots
            "balance_changes": defaultdict(list),  # address -> [(tx_id, pre_bal, post_bal)]
            "code_changes": defaultdict(list),  # address -> [(tx_id, pre_code, post_code)]
            "nonce_changes": defaultdict(list),  # address -> [(tx_id, pre_nonce, post_nonce)]
        }
        
        for tx_id, tx in enumerate(self.trace_result):
            result = tx.get("result")
            if not isinstance(result, dict):
                continue
                
            pre_state = result.get("pre", {})
            post_state = result.get("post", {})
            
            # Analyze storage accesses
            all_addresses = set(pre_state.keys()) | set(post_state.keys())
            
            for address in all_addresses:
                pre_info = pre_state.get(address, {})
                post_info = post_state.get(address, {})
                
                pre_storage = pre_info.get("storage", {})
                post_storage = post_info.get("storage", {})
                
                # Track balance changes
                pre_balance = parse_hex_or_zero(pre_info.get("balance"))
                post_balance = parse_hex_or_zero(post_info.get("balance"))
                if pre_balance != post_balance:
                    ground_truth["balance_changes"][address].append((tx_id, pre_balance, post_balance))
                
                # Track code changes
                pre_code = pre_info.get("code", "")
                post_code = post_info.get("code", "")
                if pre_code != post_code and post_code not in ("", "0x"):
                    ground_truth["code_changes"][address].append((tx_id, pre_code, post_code))
                
                # Track nonce changes
                pre_nonce = int(pre_info.get("nonce", "0"))
                post_nonce = int(post_info.get("nonce", "0"))
                if pre_nonce != post_nonce:
                    ground_truth["nonce_changes"][address].append((tx_id, pre_nonce, post_nonce))
                
                # Track storage accesses
                all_slots = set(pre_storage.keys()) | set(post_storage.keys())
                
                for slot in all_slots:
                    pre_val = pre_storage.get(slot)
                    post_val = post_storage.get(slot)
                    
                    # Record that this tx accessed this slot
                    ground_truth["all_accesses"][address][slot].add(tx_id)
                    ground_truth["tx_storage_accesses"][tx_id][address].add(slot)
                    
                    # Determine if it's a read or write
                    if post_val is not None:
                        # Storage value in post-state
                        pre_bytes = hex_to_bytes32(pre_val) if pre_val is not None else b"\x00" * 32
                        post_bytes = hex_to_bytes32(post_val)
                        
                        if pre_bytes != post_bytes:
                            # Value changed - this is a write
                            ground_truth["writes"][address][slot].append((tx_id, post_val))
                        else:
                            # Value didn't change but appears in post - could be read or no-op write
                            # According to EIP-7928, no-op writes should not be recorded
                            # This is likely a read
                            ground_truth["reads"][address].add(slot)
                    else:
                        # Only in pre-state, not in post-state - this is a read
                        if pre_val is not None:
                            ground_truth["reads"][address].add(slot)
        
        return ground_truth
    
    def validate_transaction_indices_completeness(self) -> Dict[str, Any]:
        """Validate that all transaction indices are correctly included for writes"""
        results = {
            "missing_tx_indices": [],
            "extra_tx_indices": [],
            "total_writes_expected": 0,
            "total_writes_found": 0,
            "errors": []
        }
        
        # Build lookup for our BAL
        bal_writes = {}  # address -> slot -> {tx_indices, value_after}
        for account in self.block_obj.account_accesses:
            addr_hex = account.address.hex()
            bal_writes[addr_hex] = {}
            
            for slot_access in account.accesses:
                slot_hex = slot_access.slot.hex()
                
                if len(slot_access.accesses) > 0:  # This is a write
                    tx_indices = [access.tx_index for access in slot_access.accesses]
                    values_after = [access.value_after.hex() for access in slot_access.accesses]
                    bal_writes[addr_hex][slot_hex] = {
                        "tx_indices": tx_indices,
                        "values_after": values_after
                    }
        
        # Compare with ground truth
        for address, slots in self.ground_truth["writes"].items():
            addr_canonical = to_canonical_address(address).hex()
            
            for slot, writes in slots.items():
                slot_canonical = hex_to_bytes32(slot).hex()
                results["total_writes_expected"] += len(writes)
                
                expected_tx_indices = [tx_id for tx_id, _ in writes]
                expected_values = [hex_to_bytes32(val).hex() for _, val in writes]
                
                if addr_canonical in bal_writes and slot_canonical in bal_writes[addr_canonical]:
                    found_tx_indices = bal_writes[addr_canonical][slot_canonical]["tx_indices"]
                    found_values = bal_writes[addr_canonical][slot_canonical]["values_after"]
                    
                    results["total_writes_found"] += len(found_tx_indices)
                    
                    # Check for missing tx indices
                    missing = set(expected_tx_indices) - set(found_tx_indices)
                    if missing:
                        results["missing_tx_indices"].extend([
                            {
                                "address": addr_canonical,
                                "slot": slot_canonical,
                                "missing_tx_id": tx_id,
                                "expected_value": expected_values[expected_tx_indices.index(tx_id)]
                            }
                            for tx_id in missing
                        ])
                    
                    # Check for extra tx indices
                    extra = set(found_tx_indices) - set(expected_tx_indices)
                    if extra:
                        results["extra_tx_indices"].extend([
                            {
                                "address": addr_canonical,
                                "slot": slot_canonical,
                                "extra_tx_id": tx_id,
                                "found_value": found_values[found_tx_indices.index(tx_id)]
                            }
                            for tx_id in extra
                        ])
                    
                    # Check values match
                    for i, tx_id in enumerate(expected_tx_indices):
                        if tx_id in found_tx_indices:
                            found_idx = found_tx_indices.index(tx_id)
                            if expected_values[i] != found_values[found_idx]:
                                results["errors"].append(
                                    f"Value mismatch for {addr_canonical}:{slot_canonical} tx {tx_id}: "
                                    f"expected {expected_values[i]}, got {found_values[found_idx]}"
                                )
                else:
                    # Entire slot missing from BAL
                    results["missing_tx_indices"].extend([
                        {
                            "address": addr_canonical,
                            "slot": slot_canonical,
                            "missing_tx_id": tx_id,
                            "expected_value": expected_values[i],
                            "error": "Entire slot missing from BAL"
                        }
                        for i, (tx_id, _) in enumerate(writes)
                    ])
        
        return results
    
    def validate_read_only_slots(self) -> Dict[str, Any]:
        """Validate that read-only slots have empty SlotAccess and no reads are missed"""
        results = {
            "missing_read_slots": [],
            "incorrect_read_slots": [],  # Slots marked as reads but have writes
            "total_reads_expected": 0,
            "total_reads_found": 0,
            "errors": []
        }
        
        # Build lookup for our BAL reads
        bal_reads = {}  # address -> set of slots with empty accesses
        bal_writes_slots = {}  # address -> set of slots with non-empty accesses
        
        for account in self.block_obj.account_accesses:
            addr_hex = account.address.hex()
            bal_reads[addr_hex] = set()
            bal_writes_slots[addr_hex] = set()
            
            for slot_access in account.accesses:
                slot_hex = slot_access.slot.hex()
                
                if len(slot_access.accesses) == 0:
                    # Empty access list = read-only
                    bal_reads[addr_hex].add(slot_hex)
                else:
                    # Non-empty access list = write
                    bal_writes_slots[addr_hex].add(slot_hex)
        
        # Check expected reads from ground truth
        for address, read_slots in self.ground_truth["reads"].items():
            addr_canonical = to_canonical_address(address).hex()
            
            for slot in read_slots:
                slot_canonical = hex_to_bytes32(slot).hex()
                
                # Only count as expected read if this slot wasn't written to in the block
                if (address not in self.ground_truth["writes"] or 
                    slot not in self.ground_truth["writes"][address]):
                    
                    results["total_reads_expected"] += 1
                    
                    if (addr_canonical in bal_reads and 
                        slot_canonical in bal_reads[addr_canonical]):
                        results["total_reads_found"] += 1
                    else:
                        results["missing_read_slots"].append({
                            "address": addr_canonical,
                            "slot": slot_canonical,
                            "error": "Read-only slot missing from BAL"
                        })
        
        # Check for incorrectly marked reads (slots that should be writes)
        for addr_hex, read_slots in bal_reads.items():
            address = bytes.fromhex(addr_hex[2:] if addr_hex.startswith('0x') else addr_hex)
            address_str = '0x' + address.hex()
            
            for slot_hex in read_slots:
                slot = bytes.fromhex(slot_hex[2:] if slot_hex.startswith('0x') else slot_hex)
                slot_str = '0x' + slot.hex()
                
                # Check if this slot was actually written to
                if (address_str in self.ground_truth["writes"] and 
                    slot_str in self.ground_truth["writes"][address_str]):
                    
                    results["incorrect_read_slots"].append({
                        "address": addr_hex,
                        "slot": slot_hex,
                        "error": "Slot marked as read-only but has writes in ground truth"
                    })
        
        return results
    
    def validate_balance_diffs_completeness(self) -> Dict[str, Any]:
        """Validate that all balance changes are captured"""
        results = {
            "missing_balance_changes": [],
            "extra_balance_changes": [],
            "total_expected": 0,
            "total_found": 0,
            "errors": []
        }
        
        # Build BAL balance changes lookup
        bal_balance_changes = {}  # address -> [(tx_id, delta)]
        for account_diff in self.block_obj.balance_diffs:
            addr_hex = account_diff.address.hex()
            bal_balance_changes[addr_hex] = []
            
            for change in account_diff.changes:
                # Convert delta to signed integer
                delta_bytes = change.delta
                delta_int = int.from_bytes(delta_bytes, byteorder='big', signed=True)
                bal_balance_changes[addr_hex].append((change.tx_index, delta_int))
        
        # Compare with ground truth
        for address, changes in self.ground_truth["balance_changes"].items():
            addr_canonical = to_canonical_address(address).hex()
            results["total_expected"] += len(changes)
            
            expected_changes = [(tx_id, post - pre) for tx_id, pre, post in changes]
            
            if addr_canonical in bal_balance_changes:
                found_changes = bal_balance_changes[addr_canonical]
                results["total_found"] += len(found_changes)
                
                # Check each expected change
                for tx_id, expected_delta in expected_changes:
                    found_change = None
                    for found_tx_id, found_delta in found_changes:
                        if found_tx_id == tx_id:
                            found_change = (found_tx_id, found_delta)
                            break
                    
                    if found_change is None:
                        results["missing_balance_changes"].append({
                            "address": addr_canonical,
                            "tx_id": tx_id,
                            "expected_delta": expected_delta
                        })
                    elif found_change[1] != expected_delta:
                        results["errors"].append(
                            f"Balance delta mismatch for {addr_canonical} tx {tx_id}: "
                            f"expected {expected_delta}, got {found_change[1]}"
                        )
            else:
                # Entire address missing
                for tx_id, expected_delta in expected_changes:
                    results["missing_balance_changes"].append({
                        "address": addr_canonical,
                        "tx_id": tx_id,
                        "expected_delta": expected_delta,
                        "error": "Address missing from balance diffs"
                    })
        
        return results
    
    def generate_detailed_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        print("🔍 Running comprehensive EIP-7928 compliance validation...")
        
        # Run all validations
        tx_indices_results = self.validate_transaction_indices_completeness()
        read_slots_results = self.validate_read_only_slots()
        balance_results = self.validate_balance_diffs_completeness()
        
        report = {
            "block_summary": {
                "total_transactions": len(self.trace_result),
                "total_account_accesses": len(self.block_obj.account_accesses),
                "total_balance_diffs": len(self.block_obj.balance_diffs),
                "total_code_diffs": len(self.block_obj.code_diffs),
                "total_nonce_diffs": len(self.block_obj.nonce_diffs),
            },
            "transaction_indices_validation": tx_indices_results,
            "read_slots_validation": read_slots_results,
            "balance_diffs_validation": balance_results,
            "ground_truth_summary": {
                "total_write_operations": sum(
                    len(slots) for slots in self.ground_truth["writes"].values()
                ),
                "total_read_operations": sum(
                    len(slots) for slots in self.ground_truth["reads"].values()
                ),
                "total_balance_changes": sum(
                    len(changes) for changes in self.ground_truth["balance_changes"].values()
                ),
                "addresses_with_storage_access": len(self.ground_truth["all_accesses"]),
            }
        }
        
        # Calculate overall compliance scores
        write_completeness = (
            (tx_indices_results["total_writes_found"] / tx_indices_results["total_writes_expected"] * 100)
            if tx_indices_results["total_writes_expected"] > 0 else 100
        )
        
        read_completeness = (
            (read_slots_results["total_reads_found"] / read_slots_results["total_reads_expected"] * 100)
            if read_slots_results["total_reads_expected"] > 0 else 100
        )
        
        balance_completeness = (
            (balance_results["total_found"] / balance_results["total_expected"] * 100)
            if balance_results["total_expected"] > 0 else 100
        )
        
        report["compliance_scores"] = {
            "write_completeness_percent": write_completeness,
            "read_completeness_percent": read_completeness,
            "balance_completeness_percent": balance_completeness,
            "overall_compliance": (write_completeness + read_completeness + balance_completeness) / 3,
        }
        
        return report

def test_block_comprehensive(block_number: int, rpc_url: str) -> Dict[str, Any]:
    """Run comprehensive compliance tests on a single block"""
    print(f"\n{'='*60}")
    print(f"COMPREHENSIVE EIP-7928 COMPLIANCE TEST - Block {block_number}")
    print(f"{'='*60}")
    
    try:
        # Fetch trace and generate BAL
        trace_result = fetch_block_trace(block_number, rpc_url)
        print(f"✓ Fetched trace: {len(trace_result)} transactions")
        
        # Generate BAL components
        storage_diff, account_access_list = get_storage_diff_from_block(trace_result)
        balance_diff, acc_bal_diffs = get_balance_diff_from_block(trace_result)
        code_diff, acc_code_diffs = get_code_diff_from_block(trace_result)
        nonce_diff, account_nonce_list = build_contract_nonce_diffs_from_state(trace_result)
        
        # Build and sort BAL
        block_obj = BlockAccessList(
            account_accesses=account_access_list,
            balance_diffs=acc_bal_diffs,
            code_diffs=acc_code_diffs,
            nonce_diffs=account_nonce_list,
        )
        block_obj_sorted = sort_block_access_list(block_obj)
        print("✓ Generated and sorted BAL")
        
        # Run comprehensive validation
        validator = EIP7928ComplianceValidator(trace_result, block_obj_sorted)
        report = validator.generate_detailed_report()
        
        # Print summary
        scores = report["compliance_scores"]
        print(f"\n📊 COMPLIANCE SCORES:")
        print(f"  Write Completeness: {scores['write_completeness_percent']:.1f}%")
        print(f"  Read Completeness: {scores['read_completeness_percent']:.1f}%") 
        print(f"  Balance Completeness: {scores['balance_completeness_percent']:.1f}%")
        print(f"  Overall Compliance: {scores['overall_compliance']:.1f}%")
        
        # Print detailed results
        tx_results = report["transaction_indices_validation"]
        print(f"\n📝 TRANSACTION INDICES VALIDATION:")
        print(f"  Expected writes: {tx_results['total_writes_expected']}")
        print(f"  Found writes: {tx_results['total_writes_found']}")
        print(f"  Missing tx indices: {len(tx_results['missing_tx_indices'])}")
        print(f"  Extra tx indices: {len(tx_results['extra_tx_indices'])}")
        
        read_results = report["read_slots_validation"]
        print(f"\n📖 READ-ONLY SLOTS VALIDATION:")
        print(f"  Expected reads: {read_results['total_reads_expected']}")
        print(f"  Found reads: {read_results['total_reads_found']}")
        print(f"  Missing read slots: {len(read_results['missing_read_slots'])}")
        print(f"  Incorrect read slots: {len(read_results['incorrect_read_slots'])}")
        
        # Show errors if any
        all_errors = (
            tx_results.get("errors", []) + 
            read_results.get("errors", []) + 
            report["balance_diffs_validation"].get("errors", [])
        )
        
        if all_errors:
            print(f"\n❌ ERRORS FOUND ({len(all_errors)}):")
            for i, error in enumerate(all_errors[:5]):  # Show first 5 errors
                print(f"  {i+1}. {error}")
            if len(all_errors) > 5:
                print(f"  ... and {len(all_errors) - 5} more")
        
        return {
            "success": True,
            "block_number": block_number,
            "report": report,
            "block_obj": block_obj_sorted
        }
        
    except Exception as e:
        print(f"❌ Error testing block {block_number}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "block_number": block_number,
            "error": str(e)
        }

def main():
    """Run comprehensive tests"""
    # Read RPC URL
    rpc_file = os.path.join(project_root, "rpc.txt")
    if not os.path.exists(rpc_file):
        print("Error: rpc.txt file not found.")
        return
    
    with open(rpc_file, "r") as f:
        rpc_url = f.read().strip()
    
    # Test blocks - using smaller blocks for detailed analysis
    test_blocks = [18000000, 18500000]
    
    print("🧪 COMPREHENSIVE EIP-7928 COMPLIANCE TESTING")
    print("=" * 60)
    
    results = []
    for block_number in test_blocks:
        result = test_block_comprehensive(block_number, rpc_url)
        results.append(result)
    
    # Overall summary
    successful = [r for r in results if r["success"]]
    print(f"\n{'='*60}")
    print(f"OVERALL SUMMARY")
    print(f"{'='*60}")
    print(f"Blocks tested: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(results) - len(successful)}")
    
    if successful:
        avg_compliance = sum(
            r["report"]["compliance_scores"]["overall_compliance"] 
            for r in successful
        ) / len(successful)
        print(f"Average compliance: {avg_compliance:.1f}%")
        
        # Check if any critical issues
        critical_issues = 0
        for r in successful:
            tx_val = r["report"]["transaction_indices_validation"]
            read_val = r["report"]["read_slots_validation"]
            
            critical_issues += len(tx_val["missing_tx_indices"])
            critical_issues += len(read_val["missing_read_slots"])
        
        if critical_issues == 0:
            print("🎉 NO CRITICAL COMPLIANCE ISSUES FOUND!")
        else:
            print(f"⚠️  {critical_issues} critical issues found")
    
    # Save detailed results
    output_file = os.path.join(project_root, "comprehensive_test_results.json")
    with open(output_file, "w") as f:
        # Remove non-serializable objects
        clean_results = []
        for r in results:
            clean_r = {k: v for k, v in r.items() if k != "block_obj"}
            clean_results.append(clean_r)
        json.dump(clean_results, f, indent=2)
    
    print(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main()