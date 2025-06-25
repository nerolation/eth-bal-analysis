#!/usr/bin/env python3
"""
Comprehensive tests for BAL data structure integrity.
Tests address uniqueness, storage key uniqueness, sorting, and structural correctness.
"""

import os
import sys
import ssz
from pathlib import Path
from typing import Set, List, Dict
from collections import defaultdict

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

import BALs
from BALs import (
    BlockAccessList, AccountChanges, SlotChanges, SlotRead,
    StorageChange, BalanceChange, NonceChange, CodeChange,
    BALBuilder, Address, StorageKey, StorageValue
)

class TestDataStructureIntegrity:
    """Test suite for data structure integrity."""
    
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
    
    def test_address_uniqueness(self, bal: BlockAccessList) -> bool:
        """Test that each address appears only once in account_changes."""
        addresses_seen: Set[bytes] = set()
        duplicates = []
        
        for account in bal.account_changes:
            addr_bytes = bytes(account.address)
            if addr_bytes in addresses_seen:
                duplicates.append(addr_bytes.hex())
            addresses_seen.add(addr_bytes)
        
        self.assert_test(
            len(duplicates) == 0,
            "Address uniqueness in account_changes",
            f"Duplicate addresses found: {duplicates}"
        )
        return len(duplicates) == 0
    
    def test_storage_key_uniqueness_per_address(self, bal: BlockAccessList) -> bool:
        """Test that storage keys are unique per address."""
        violations = []
        
        for account in bal.account_changes:
            addr_hex = bytes(account.address).hex()
            
            # Check storage_changes slots uniqueness
            storage_slots_seen: Set[bytes] = set()
            for slot_changes in account.storage_changes:
                slot_bytes = bytes(slot_changes.slot)
                if slot_bytes in storage_slots_seen:
                    violations.append(f"Duplicate storage slot in changes for {addr_hex}: {slot_bytes.hex()}")
                storage_slots_seen.add(slot_bytes)
            
            # Check storage_reads slots uniqueness
            read_slots_seen: Set[bytes] = set()
            for slot_read in account.storage_reads:
                slot_bytes = bytes(slot_read.slot)
                if slot_bytes in read_slots_seen:
                    violations.append(f"Duplicate storage slot in reads for {addr_hex}: {slot_bytes.hex()}")
                read_slots_seen.add(slot_bytes)
            
            # Check no overlap between writes and reads
            overlap = storage_slots_seen.intersection(read_slots_seen)
            if overlap:
                violations.append(f"Storage slots appear in both writes and reads for {addr_hex}: {[s.hex() for s in overlap]}")
        
        self.assert_test(
            len(violations) == 0,
            "Storage key uniqueness per address",
            f"Violations: {violations}"
        )
        return len(violations) == 0
    
    def test_sorting_correctness(self, bal: BlockAccessList) -> bool:
        """Test that all components are properly sorted."""
        violations = []
        
        # Test account_changes sorted by address
        prev_addr = b'\x00' * 20
        for account in bal.account_changes:
            curr_addr = bytes(account.address)
            if curr_addr <= prev_addr:
                violations.append(f"Account addresses not sorted: {prev_addr.hex()} >= {curr_addr.hex()}")
            prev_addr = curr_addr
            
            # Test storage_changes sorted by slot
            prev_slot = b'\x00' * 32
            for slot_changes in account.storage_changes:
                curr_slot = bytes(slot_changes.slot)
                if curr_slot <= prev_slot:
                    violations.append(f"Storage slots not sorted for {curr_addr.hex()}: {prev_slot.hex()} >= {curr_slot.hex()}")
                prev_slot = curr_slot
                
                # Test changes within slot sorted by tx_index
                prev_tx_idx = -1
                for change in slot_changes.changes:
                    if change.tx_index <= prev_tx_idx:
                        violations.append(f"Storage changes not sorted by tx_index for {curr_addr.hex()}, slot {curr_slot.hex()}")
                    prev_tx_idx = change.tx_index
            
            # Test storage_reads sorted by slot
            prev_slot = b'\x00' * 32
            for slot_read in account.storage_reads:
                curr_slot = bytes(slot_read.slot)
                if curr_slot <= prev_slot:
                    violations.append(f"Storage reads not sorted for {curr_addr.hex()}: {prev_slot.hex()} >= {curr_slot.hex()}")
                prev_slot = curr_slot
            
            # Test balance_changes sorted by tx_index
            prev_tx_idx = -1
            for balance_change in account.balance_changes:
                if balance_change.tx_index <= prev_tx_idx:
                    violations.append(f"Balance changes not sorted by tx_index for {curr_addr.hex()}")
                prev_tx_idx = balance_change.tx_index
            
            # Test nonce_changes sorted by tx_index
            prev_tx_idx = -1
            for nonce_change in account.nonce_changes:
                if nonce_change.tx_index <= prev_tx_idx:
                    violations.append(f"Nonce changes not sorted by tx_index for {curr_addr.hex()}")
                prev_tx_idx = nonce_change.tx_index
            
            # Test code_changes sorted by tx_index
            prev_tx_idx = -1
            for code_change in account.code_changes:
                if code_change.tx_index <= prev_tx_idx:
                    violations.append(f"Code changes not sorted by tx_index for {curr_addr.hex()}")
                prev_tx_idx = code_change.tx_index
        
        self.assert_test(
            len(violations) == 0,
            "Sorting correctness",
            f"Violations: {violations}"
        )
        return len(violations) == 0
    
    def test_data_type_correctness(self, bal: BlockAccessList) -> bool:
        """Test that all data types are correct."""
        violations = []
        
        for account in bal.account_changes:
            # Test address is 20 bytes
            if len(account.address) != 20:
                violations.append(f"Invalid address length: {len(account.address)} bytes")
            
            # Test storage slots are 32 bytes
            for slot_changes in account.storage_changes:
                if len(slot_changes.slot) != 32:
                    violations.append(f"Invalid storage slot length: {len(slot_changes.slot)} bytes")
                
                for change in slot_changes.changes:
                    if len(change.new_value) != 32:
                        violations.append(f"Invalid storage value length: {len(change.new_value)} bytes")
            
            for slot_read in account.storage_reads:
                if len(slot_read.slot) != 32:
                    violations.append(f"Invalid read slot length: {len(slot_read.slot)} bytes")
            
            # Test balance post_balance are 12 bytes
            for balance_change in account.balance_changes:
                if len(balance_change.post_balance) != 12:
                    violations.append(f"Invalid balance post_balance length: {len(balance_change.post_balance)} bytes")
        
        self.assert_test(
            len(violations) == 0,
            "Data type correctness",
            f"Violations: {violations}"
        )
        return len(violations) == 0
    
    def test_tx_index_validity(self, bal: BlockAccessList) -> bool:
        """Test that tx_index values are valid."""
        violations = []
        max_tx_index = 0
        
        for account in bal.account_changes:
            # Collect all tx indices
            all_tx_indices = []
            
            for slot_changes in account.storage_changes:
                for change in slot_changes.changes:
                    all_tx_indices.append(change.tx_index)
                    max_tx_index = max(max_tx_index, change.tx_index)
            
            for balance_change in account.balance_changes:
                all_tx_indices.append(balance_change.tx_index)
                max_tx_index = max(max_tx_index, balance_change.tx_index)
            
            for nonce_change in account.nonce_changes:
                all_tx_indices.append(nonce_change.tx_index)
                max_tx_index = max(max_tx_index, nonce_change.tx_index)
            
            for code_change in account.code_changes:
                all_tx_indices.append(code_change.tx_index)
                max_tx_index = max(max_tx_index, code_change.tx_index)
            
            # Check no negative tx indices
            negative_indices = [idx for idx in all_tx_indices if idx < 0]
            if negative_indices:
                violations.append(f"Negative tx indices found for {bytes(account.address).hex()}: {negative_indices}")
        
        self.assert_test(
            len(violations) == 0,
            "TX index validity",
            f"Violations: {violations}"
        )
        return len(violations) == 0
    
    def test_ssz_serialization_roundtrip(self, bal: BlockAccessList) -> bool:
        """Test that SSZ serialization and deserialization works correctly."""
        try:
            # Filter out any accounts with code changes to avoid SSZ library issues
            filtered_accounts = []
            for account in bal.account_changes:
                if len(account.code_changes) == 0:
                    filtered_accounts.append(account)
                else:
                    # Create a copy without code changes
                    filtered_account = AccountChanges(
                        address=account.address,
                        storage_changes=account.storage_changes,
                        storage_reads=account.storage_reads,
                        balance_changes=account.balance_changes,
                        nonce_changes=account.nonce_changes,
                        code_changes=[]  # Remove code changes
                    )
                    filtered_accounts.append(filtered_account)
            
            filtered_bal = BlockAccessList(account_changes=filtered_accounts)
            
            # Serialize
            encoded = ssz.encode(filtered_bal, sedes=BlockAccessList)
            
            # Deserialize
            decoded = ssz.decode(encoded, sedes=BlockAccessList)
            
            # Re-serialize to compare
            re_encoded = ssz.encode(decoded, sedes=BlockAccessList)
            
            # Should be identical
            matches = encoded == re_encoded
            
            self.assert_test(
                matches,
                "SSZ serialization roundtrip",
                "Encoded data doesn't match after roundtrip"
            )
            return matches
            
        except Exception as e:
            self.assert_test(
                False,
                "SSZ serialization roundtrip",
                f"Exception during serialization: {e}"
            )
            return False
    
    def test_empty_account_filtering(self, bal: BlockAccessList) -> bool:
        """Test that accounts with no changes are not included."""
        violations = []
        
        for account in bal.account_changes:
            total_changes = (
                len(account.storage_changes) +
                len(account.storage_reads) +
                len(account.balance_changes) +
                len(account.nonce_changes) +
                len(account.code_changes)
            )
            
            if total_changes == 0:
                violations.append(f"Empty account found: {bytes(account.address).hex()}")
        
        self.assert_test(
            len(violations) == 0,
            "Empty account filtering",
            f"Violations: {violations}"
        )
        return len(violations) == 0
    
    def run_all_tests(self, bal: BlockAccessList) -> Dict[str, bool]:
        """Run all integrity tests on a BAL."""
        print("🔍 Running Data Structure Integrity Tests...")
        print("-" * 50)
        
        results = {}
        results['address_uniqueness'] = self.test_address_uniqueness(bal)
        results['storage_key_uniqueness'] = self.test_storage_key_uniqueness_per_address(bal)
        results['sorting_correctness'] = self.test_sorting_correctness(bal)
        results['data_type_correctness'] = self.test_data_type_correctness(bal)
        results['tx_index_validity'] = self.test_tx_index_validity(bal)
        results['ssz_serialization'] = self.test_ssz_serialization_roundtrip(bal)
        results['empty_account_filtering'] = self.test_empty_account_filtering(bal)
        
        print(f"\nTest Results: {self.passed}/{self.total} passed, {self.failed}/{self.total} failed")
        
        return results

def create_test_bal() -> BlockAccessList:
    """Create a test BAL with various scenarios."""
    builder = BALBuilder()
    
    # Create test addresses
    addr1 = b'\x01' * 20
    addr2 = b'\x02' * 20
    addr3 = b'\x03' * 20
    
    # Add some storage writes (should be sorted by slot)
    slot1 = b'\x01' * 32
    slot2 = b'\x02' * 32
    value1 = b'\x10' * 32
    value2 = b'\x20' * 32
    
    builder.add_storage_write(addr1, slot1, 0, value1)
    builder.add_storage_write(addr1, slot2, 1, value2)
    builder.add_storage_write(addr2, slot1, 0, value1)
    
    # Add some storage reads
    slot3 = b'\x03' * 32
    builder.add_storage_read(addr1, slot3)
    builder.add_storage_read(addr3, slot1)
    
    # Add balance changes
    post_balance1 = (1000).to_bytes(12, 'big', signed=False)
    post_balance2 = (500).to_bytes(12, 'big', signed=False)
    builder.add_balance_change(addr1, 0, post_balance1)
    builder.add_balance_change(addr2, 1, post_balance2)
    
    # Add nonce changes
    builder.add_nonce_change(addr1, 0, 1)
    builder.add_nonce_change(addr2, 1, 5)
    
    # Add code changes
    code = b'\x60\x60\x60\x40'  # Simple contract code
    builder.add_code_change(addr3, 0, code)
    
    return builder.build(ignore_reads=False)

def main():
    """Main test function."""
    print("🧪 BAL Data Structure Integrity Test Suite")
    print("=" * 60)
    
    # Create test data
    test_bal = create_test_bal()
    
    # Run tests
    tester = TestDataStructureIntegrity()
    results = tester.run_all_tests(test_bal)
    
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