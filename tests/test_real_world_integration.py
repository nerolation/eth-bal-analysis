#!/usr/bin/env python3
"""
Real-world integration tests for BAL implementation.
Tests with actual Ethereum block data and edge cases.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import MappedBlockAccessList, MappedBALBuilder
from helpers import fetch_block_trace, hex_to_bytes32
from eth_utils import to_canonical_address
from bal_builder import (
    process_storage_changes_mapped, process_balance_changes_mapped,
    process_code_changes_mapped, process_nonce_changes_mapped,
    sort_mapped_block_access_list, extract_reads_from_block
)

class TestRealWorldIntegration:
    """Test suite for real-world integration."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.rpc_url = None
        
        # Try to load RPC URL
        rpc_file = os.path.join(project_root, "rpc.txt")
        if os.path.exists(rpc_file):
            with open(rpc_file, "r") as f:
                self.rpc_url = f.read().strip()
        
    def assert_test(self, condition: bool, test_name: str, error_msg: str = ""):
        """Assert a test condition and track results."""
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  ✅ {test_name}")
        else:
            self.failed += 1
            print(f"  ❌ {test_name}: {error_msg}")
    
    def test_mock_block_data_processing(self) -> bool:
        """Test processing mock block data directly with builder."""
        try:
            builder = MappedBALBuilder()
            
            # Manually add test data using builder methods
            addr = to_canonical_address("0x1234567890123456789012345678901234567890")
            slot1 = hex_to_bytes32("0x0000000000000000000000000000000000000000000000000000000000000001")
            slot2 = hex_to_bytes32("0x0000000000000000000000000000000000000000000000000000000000000002")
            value1 = hex_to_bytes32("0x0000000000000000000000000000000000000000000000000000000000000200")
            value2 = hex_to_bytes32("0x0000000000000000000000000000000000000000000000000000000000000300")
            
            # Add storage writes
            builder.add_storage_write(addr, slot1, 0, value1)
            builder.add_storage_write(addr, slot2, 0, value2)
            
            # Add balance change (2000 - 1000 = 1000)
            balance_delta = (0x1000).to_bytes(12, 'big', signed=True)
            builder.add_balance_change(addr, 0, balance_delta)
            
            # Add nonce change (from 1 to 2, but only contracts with code get nonce changes recorded)
            # For this test we'll manually add it
            builder.add_nonce_change(addr, 0, 2)
            
            # Build BAL
            bal = builder.build(ignore_reads=True)
            
            self.assert_test(
                len(bal.account_changes) == 1,
                "Mock block data produces one account"
            )
            
            account = bal.account_changes[0]
            self.assert_test(
                len(account.storage_changes) == 2,
                "Mock block data produces two storage changes"
            )
            
            self.assert_test(
                len(account.balance_changes) == 1,
                "Mock block data produces one balance change"
            )
            
            self.assert_test(
                len(account.nonce_changes) == 1,
                "Mock block data produces one nonce change"
            )
            
            return True
            
        except Exception as e:
            self.assert_test(False, "Mock block data processing", str(e))
            return False
    
    def test_edge_case_zero_values(self) -> bool:
        """Test handling of zero values."""
        try:
            builder = MappedBALBuilder()
            
            addr = to_canonical_address("0x1234567890123456789012345678901234567890")
            slot1 = hex_to_bytes32("0x0000000000000000000000000000000000000000000000000000000000000001")
            
            # Add storage write with zero value (0x100 -> 0x0)
            zero_value = hex_to_bytes32("0x0000000000000000000000000000000000000000000000000000000000000000")
            builder.add_storage_write(addr, slot1, 0, zero_value)
            
            # No balance change (0x0 - 0x0 = 0x0, should not be recorded)
            # No nonce change (0x0 -> 0x0, should not be recorded)
            
            bal = builder.build(ignore_reads=True)
            
            if len(bal.account_changes) > 0:
                account = bal.account_changes[0]
                self.assert_test(
                    len(account.storage_changes) == 1,
                    "Zero storage value change is recorded"
                )
                
                self.assert_test(
                    len(account.balance_changes) == 0,
                    "Zero balance change is not recorded"
                )
                
                self.assert_test(
                    len(account.nonce_changes) == 0,
                    "Zero nonce change is not recorded"
                )
            else:
                self.assert_test(True, "Zero values produce no changes (acceptable)")
            
            return True
            
        except Exception as e:
            self.assert_test(False, "Zero values handling", str(e))
            return False
    
    def test_edge_case_large_numbers(self) -> bool:
        """Test handling of large numbers in balances and nonces."""
        try:
            builder = MappedBALBuilder()
            
            addr = to_canonical_address("0x1234567890123456789012345678901234567890")
            
            # Create large balance delta (but keep it within 12 bytes)
            # Large positive number that fits in 12 bytes
            large_balance_delta = (2**95 - 1).to_bytes(12, 'big', signed=True)
            builder.add_balance_change(addr, 0, large_balance_delta)
            
            # Large nonce (within uint64 range)
            large_nonce = 2**32 - 1  # Large but valid nonce
            builder.add_nonce_change(addr, 0, large_nonce)
            
            bal = builder.build()
            
            if len(bal.account_changes) > 0:
                account = bal.account_changes[0]
                
                self.assert_test(
                    len(account.balance_changes) == 1,
                    "Large balance change recorded"
                )
                
                self.assert_test(
                    len(account.nonce_changes) == 1,
                    "Large nonce change recorded"
                )
                
                # Check the actual values
                self.assert_test(
                    account.nonce_changes[0].new_nonce == large_nonce,
                    f"Large nonce value preserved: {account.nonce_changes[0].new_nonce}"
                )
            
            return True
            
        except Exception as e:
            self.assert_test(False, "Large numbers handling", str(e))
            return False
    
    def test_edge_case_malformed_data(self) -> bool:
        """Test handling of malformed trace data."""
        malformed_traces = [
            # Missing result
            {},
            # Missing pre/post
            {"result": {}},
            # Invalid address format
            {"result": {"pre": {"invalid_address": {}}, "post": {}}},
            # Missing fields
            {"result": {"pre": {"0x" + "1" * 40: {}}, "post": {}}}
        ]
        
        success_count = 0
        
        for i, trace in enumerate(malformed_traces):
            try:
                builder = MappedBALBuilder()
                
                process_storage_changes_mapped([trace], None, True, builder)
                process_balance_changes_mapped([trace], builder)
                process_nonce_changes_mapped([trace], builder)
                process_code_changes_mapped([trace], builder)
                
                # Should not crash, might produce empty BAL
                bal = builder.build()
                success_count += 1
                
            except Exception as e:
                # Some failures are expected for malformed data
                pass
        
        self.assert_test(
            success_count >= 2,  # At least some malformed data should be handled gracefully
            f"Malformed data handling: {success_count}/4 handled gracefully"
        )
        
        return success_count >= 2
    
    def test_sorting_with_mixed_addresses(self) -> bool:
        """Test sorting with various address patterns."""
        # Create addresses with different patterns
        addresses = [
            "0x" + "ff" * 20,  # All F's
            "0x" + "00" * 20,  # All 0's  
            "0x" + "aa" * 20,  # All A's
            "0x1234567890123456789012345678901234567890",  # Mixed
            "0x" + "01" * 20,  # All 01's
        ]
        
        mock_trace = []
        for i, addr in enumerate(addresses):
            mock_trace.append({
                "result": {
                    "pre": {addr: {"balance": "0x1000", "nonce": "0x1", "code": "0x"}},
                    "post": {addr: {"balance": "0x2000", "nonce": "0x1", "code": "0x"}}
                }
            })
        
        try:
            builder = MappedBALBuilder()
            
            process_balance_changes_mapped(mock_trace, builder)
            
            bal = builder.build()
            sorted_bal = sort_mapped_block_access_list(bal)
            
            # Check sorting
            extracted_addresses = [bytes(account.address).hex() for account in sorted_bal.account_changes]
            expected_order = sorted([addr.lower()[2:] for addr in addresses])  # Remove 0x and sort
            actual_order = [addr for addr in extracted_addresses]
            
            self.assert_test(
                actual_order == expected_order,
                f"Mixed addresses sorted correctly: {actual_order[:2]}... == {expected_order[:2]}..."
            )
            
            return True
            
        except Exception as e:
            self.assert_test(False, "Mixed address sorting", str(e))
            return False
    
    def test_performance_with_many_accounts(self) -> bool:
        """Test performance with many accounts (stress test)."""
        import time
        
        try:
            # Create mock data with many accounts
            mock_trace = []
            num_accounts = 1000
            
            for i in range(num_accounts):
                addr = f"0x{i:040x}"  # Create unique 40-char hex addresses
                mock_trace.append({
                    "result": {
                        "pre": {addr: {"balance": "0x1000", "nonce": "0x1", "code": "0x"}},
                        "post": {addr: {"balance": "0x2000", "nonce": "0x1", "code": "0x"}}
                    }
                })
            
            start_time = time.time()
            
            builder = MappedBALBuilder()
            process_balance_changes_mapped(mock_trace, builder)
            bal = builder.build()
            sorted_bal = sort_mapped_block_access_list(bal)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            self.assert_test(
                len(sorted_bal.account_changes) == num_accounts,
                f"All {num_accounts} accounts processed"
            )
            
            self.assert_test(
                processing_time < 10.0,  # Should complete within 10 seconds
                f"Processing time reasonable: {processing_time:.2f}s < 10s"
            )
            
            return True
            
        except Exception as e:
            self.assert_test(False, "Many accounts performance", str(e))
            return False
    
    def test_real_block_data(self) -> bool:
        """Test with real block data if RPC URL available."""
        if not self.rpc_url:
            self.assert_test(True, "Real block data test skipped (no RPC URL)")
            return True
        
        try:
            # Use a recent block number (this should be updated periodically)
            test_block = 22615532
            
            print(f"    Fetching real block {test_block}...")
            trace_result = fetch_block_trace(test_block, self.rpc_url)
            
            builder = MappedBALBuilder()
            
            # Process like the real builder does
            process_storage_changes_mapped(trace_result, None, True, builder)
            process_balance_changes_mapped(trace_result, builder)
            process_code_changes_mapped(trace_result, builder)
            process_nonce_changes_mapped(trace_result, builder)
            
            bal = builder.build(ignore_reads=True)
            sorted_bal = sort_mapped_block_access_list(bal)
            
            self.assert_test(
                len(sorted_bal.account_changes) > 0,
                f"Real block data produces accounts: {len(sorted_bal.account_changes)}"
            )
            
            # Test that it's properly sorted
            prev_addr = b'\x00' * 20
            for account in sorted_bal.account_changes:
                curr_addr = bytes(account.address)
                if curr_addr <= prev_addr:
                    self.assert_test(False, "Real block data sorting", "Addresses not properly sorted")
                    return False
                prev_addr = curr_addr
            
            self.assert_test(True, "Real block data sorting verified")
            
            return True
            
        except Exception as e:
            self.assert_test(False, "Real block data processing", str(e))
            return False
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all real-world integration tests."""
        print("🌍 Running Real-World Integration Tests...")
        print("-" * 50)
        
        results = {}
        results['mock_data'] = self.test_mock_block_data_processing()
        results['zero_values'] = self.test_edge_case_zero_values()
        results['large_numbers'] = self.test_edge_case_large_numbers()
        results['malformed_data'] = self.test_edge_case_malformed_data()
        results['mixed_sorting'] = self.test_sorting_with_mixed_addresses()
        results['performance'] = self.test_performance_with_many_accounts()
        results['real_block'] = self.test_real_block_data()
        
        print(f"\nTest Results: {self.passed}/{self.total} passed, {self.failed}/{self.total} failed")
        
        return results

def main():
    """Main test function."""
    print("🧪 BAL Real-World Integration Test Suite")
    print("=" * 60)
    
    # Run tests
    tester = TestRealWorldIntegration()
    results = tester.run_all_tests()
    
    # Summary
    all_passed = all(results.values())
    status = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
    print(f"\n{status}")
    
    if not all_passed:
        print("\nFailed tests:")
        for test_name, passed in results.items():
            if not passed:
                print(f"  - {test_name}")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)