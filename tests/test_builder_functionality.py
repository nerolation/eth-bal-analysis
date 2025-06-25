#!/usr/bin/env python3
"""
Comprehensive tests for BAL builder functionality.
Tests builder operations, edge cases, and data consistency.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import (
    BlockAccessList, AccountChanges, SlotChanges, SlotRead,
    StorageChange, BalanceChange, NonceChange, CodeChange,
    BALBuilder, Address, StorageKey, StorageValue
)

class TestBuilderFunctionality:
    """Test suite for builder functionality."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        
    def assert_test(self, condition: bool, test_name: str, error_msg: str = ""):
        """Assert a test condition and track results."""
        self.total += 1
        if condition:
            self.passed += 1
            print(f"  ✅ {test_name}")
        else:
            self.failed += 1
            print(f"  ❌ {test_name}: {error_msg}")
    
    def test_builder_initialization(self) -> bool:
        """Test builder initializes correctly."""
        builder = BALBuilder()
        
        self.assert_test(
            hasattr(builder, 'accounts'),
            "Builder has accounts attribute"
        )
        
        self.assert_test(
            len(builder.accounts) == 0,
            "Builder starts with empty accounts"
        )
        
        return True
    
    def test_storage_write_operations(self) -> bool:
        """Test storage write operations."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        slot = b'\x01' * 32
        value = b'\x10' * 32
        
        # Add storage write
        builder.add_storage_write(addr, slot, 0, value)
        
        # Check internal state
        self.assert_test(
            addr in builder.accounts,
            "Address added to accounts after storage write"
        )
        
        self.assert_test(
            'storage_changes' in builder.accounts[addr],
            "Storage changes section created"
        )
        
        self.assert_test(
            slot in builder.accounts[addr]['storage_changes'],
            "Storage slot added"
        )
        
        # Add another write to same slot (different tx)
        value2 = b'\x20' * 32
        builder.add_storage_write(addr, slot, 1, value2)
        
        self.assert_test(
            len(builder.accounts[addr]['storage_changes'][slot]) == 2,
            "Multiple writes to same slot stored correctly"
        )
        
        return True
    
    def test_storage_read_operations(self) -> bool:
        """Test storage read operations."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        slot = b'\x01' * 32
        
        # Add storage read
        builder.add_storage_read(addr, slot)
        
        # Check internal state
        self.assert_test(
            addr in builder.accounts,
            "Address added to accounts after storage read"
        )
        
        self.assert_test(
            'storage_reads' in builder.accounts[addr],
            "Storage reads section created"
        )
        
        self.assert_test(
            slot in builder.accounts[addr]['storage_reads'],
            "Storage read slot added"
        )
        
        # Add duplicate read (should be deduplicated)
        builder.add_storage_read(addr, slot)
        
        self.assert_test(
            len(builder.accounts[addr]['storage_reads']) == 1,
            "Duplicate reads are deduplicated"
        )
        
        return True
    
    def test_balance_change_operations(self) -> bool:
        """Test balance change operations."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        delta = (1000).to_bytes(12, 'big', signed=True)
        
        # Add balance change
        builder.add_balance_change(addr, 0, delta)
        
        # Check internal state
        self.assert_test(
            addr in builder.accounts,
            "Address added to accounts after balance change"
        )
        
        self.assert_test(
            'balance_changes' in builder.accounts[addr],
            "Balance changes section created"
        )
        
        self.assert_test(
            len(builder.accounts[addr]['balance_changes']) == 1,
            "Balance change added"
        )
        
        # Add another balance change for same address
        delta2 = (-500).to_bytes(12, 'big', signed=True)
        builder.add_balance_change(addr, 1, delta2)
        
        self.assert_test(
            len(builder.accounts[addr]['balance_changes']) == 2,
            "Multiple balance changes stored correctly"
        )
        
        return True
    
    def test_nonce_change_operations(self) -> bool:
        """Test nonce change operations."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        nonce = 5
        
        # Add nonce change
        builder.add_nonce_change(addr, 0, nonce)
        
        # Check internal state
        self.assert_test(
            'nonce_changes' in builder.accounts[addr],
            "Nonce changes section created"
        )
        
        self.assert_test(
            len(builder.accounts[addr]['nonce_changes']) == 1,
            "Nonce change added"
        )
        
        return True
    
    def test_code_change_operations(self) -> bool:
        """Test code change operations."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        code = b'\x60\x60\x60\x40'  # Simple contract code
        
        # Add code change
        builder.add_code_change(addr, 0, code)
        
        # Check internal state
        self.assert_test(
            'code_changes' in builder.accounts[addr],
            "Code changes section created"
        )
        
        self.assert_test(
            len(builder.accounts[addr]['code_changes']) == 1,
            "Code change added"
        )
        
        return True
    
    def test_build_with_reads(self) -> bool:
        """Test building BAL with reads included."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        slot_write = b'\x01' * 32
        slot_read = b'\x02' * 32
        value = b'\x10' * 32
        
        # Add storage write and read
        builder.add_storage_write(addr, slot_write, 0, value)
        builder.add_storage_read(addr, slot_read)
        
        # Build with reads
        bal = builder.build(ignore_reads=False)
        
        self.assert_test(
            len(bal.account_changes) == 1,
            "Built BAL has one account"
        )
        
        account = bal.account_changes[0]
        self.assert_test(
            len(account.storage_changes) == 1,
            "Account has one storage change"
        )
        
        self.assert_test(
            len(account.storage_reads) == 1,
            "Account has one storage read"
        )
        
        return True
    
    def test_build_without_reads(self) -> bool:
        """Test building BAL with reads ignored."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        slot_write = b'\x01' * 32
        slot_read = b'\x02' * 32
        value = b'\x10' * 32
        
        # Add storage write and read
        builder.add_storage_write(addr, slot_write, 0, value)
        builder.add_storage_read(addr, slot_read)
        
        # Build without reads
        bal = builder.build(ignore_reads=True)
        
        account = bal.account_changes[0]
        self.assert_test(
            len(account.storage_reads) == 0,
            "Storage reads ignored when ignore_reads=True"
        )
        
        self.assert_test(
            len(account.storage_changes) == 1,
            "Storage writes still included when ignore_reads=True"
        )
        
        return True
    
    def test_edge_case_empty_builder(self) -> bool:
        """Test building from empty builder."""
        builder = BALBuilder()
        
        # Build empty
        bal = builder.build()
        
        self.assert_test(
            len(bal.account_changes) == 0,
            "Empty builder produces empty BAL"
        )
        
        return True
    
    def test_edge_case_large_tx_index(self) -> bool:
        """Test with large transaction indices."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        slot = b'\x01' * 32
        value = b'\x10' * 32
        large_tx_idx = 29999  # Near MAX_TXS limit
        
        # Add storage write with large tx index
        builder.add_storage_write(addr, slot, large_tx_idx, value)
        
        # Build and verify
        bal = builder.build()
        
        self.assert_test(
            len(bal.account_changes) == 1,
            "Large tx index handled correctly"
        )
        
        account = bal.account_changes[0]
        change = account.storage_changes[0].changes[0]
        self.assert_test(
            change.tx_index == large_tx_idx,
            f"Large tx index preserved: expected {large_tx_idx}, got {change.tx_index}"
        )
        
        return True
    
    def test_edge_case_max_code_size(self) -> bool:
        """Test with maximum code size."""
        builder = BALBuilder()
        
        addr = b'\x01' * 20
        # Create code at maximum allowed size (24576 bytes)
        max_code = b'\x60' * 24576
        
        try:
            builder.add_code_change(addr, 0, max_code)
            bal = builder.build()
            
            self.assert_test(
                len(bal.account_changes[0].code_changes[0].new_code) == 24576,
                "Maximum code size handled correctly"
            )
            return True
            
        except Exception as e:
            self.assert_test(
                False,
                "Maximum code size handling",
                f"Exception with max code size: {e}"
            )
            return False
    
    def test_multiple_addresses_sorting(self) -> bool:
        """Test that multiple addresses are sorted correctly."""
        builder = BALBuilder()
        
        # Add addresses in reverse order
        addr3 = b'\x03' * 20
        addr1 = b'\x01' * 20
        addr2 = b'\x02' * 20
        
        value = b'\x10' * 32
        slot = b'\x01' * 32
        
        builder.add_storage_write(addr3, slot, 0, value)
        builder.add_storage_write(addr1, slot, 0, value)
        builder.add_storage_write(addr2, slot, 0, value)
        
        bal = builder.build()
        
        # Check sorting
        addresses = [bytes(account.address) for account in bal.account_changes]
        sorted_addresses = sorted(addresses)
        
        self.assert_test(
            addresses == sorted_addresses,
            "Multiple addresses are sorted correctly"
        )
        
        return True
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all builder functionality tests."""
        print("🔧 Running Builder Functionality Tests...")
        print("-" * 50)
        
        results = {}
        results['initialization'] = self.test_builder_initialization()
        results['storage_writes'] = self.test_storage_write_operations()
        results['storage_reads'] = self.test_storage_read_operations()
        results['balance_changes'] = self.test_balance_change_operations()
        results['nonce_changes'] = self.test_nonce_change_operations()
        results['code_changes'] = self.test_code_change_operations()
        results['build_with_reads'] = self.test_build_with_reads()
        results['build_without_reads'] = self.test_build_without_reads()
        results['empty_builder'] = self.test_edge_case_empty_builder()
        results['large_tx_index'] = self.test_edge_case_large_tx_index()
        results['max_code_size'] = self.test_edge_case_max_code_size()
        results['address_sorting'] = self.test_multiple_addresses_sorting()
        
        print(f"\nTest Results: {self.passed}/{self.total} passed, {self.failed}/{self.total} failed")
        
        return results

def main():
    """Main test function."""
    print("🧪 BAL Builder Functionality Test Suite")
    print("=" * 60)
    
    # Run tests
    tester = TestBuilderFunctionality()
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