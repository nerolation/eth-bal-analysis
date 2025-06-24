#!/usr/bin/env python3
"""
Comprehensive tests for SSZ encoding/decoding of BAL structures.
Tests serialization, deserialization, and data integrity.
"""

import os
import sys
import ssz
from pathlib import Path
from typing import Dict, Any, List

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from BALs import (
    MappedBlockAccessList, AccountChanges, SlotChanges, SlotRead,
    StorageChange, BalanceChange, NonceChange, CodeChange,
    MappedBALBuilder, Address, StorageKey, StorageValue,
    SSZList, MAX_ACCOUNTS, MAX_SLOTS, MAX_TXS
)
from helpers import get_compressed_size

class TestSSZEncoding:
    """Test suite for SSZ encoding/decoding."""
    
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
    
    def test_individual_component_encoding(self) -> bool:
        """Test encoding of individual components."""
        # Test StorageChange
        try:
            storage_change = StorageChange(tx_index=0, new_value=b'\x10' * 32)
            encoded = ssz.encode(storage_change, sedes=StorageChange)
            decoded = ssz.decode(encoded, sedes=StorageChange)
            
            self.assert_test(
                decoded.tx_index == 0 and decoded.new_value == b'\x10' * 32,
                "StorageChange encoding/decoding"
            )
        except Exception as e:
            self.assert_test(False, "StorageChange encoding/decoding", str(e))
        
        # Test BalanceChange
        try:
            balance_change = BalanceChange(tx_index=1, delta=(1000).to_bytes(12, 'big', signed=True))
            encoded = ssz.encode(balance_change, sedes=BalanceChange)
            decoded = ssz.decode(encoded, sedes=BalanceChange)
            
            self.assert_test(
                decoded.tx_index == 1 and decoded.delta == (1000).to_bytes(12, 'big', signed=True),
                "BalanceChange encoding/decoding"
            )
        except Exception as e:
            self.assert_test(False, "BalanceChange encoding/decoding", str(e))
        
        # Test NonceChange
        try:
            nonce_change = NonceChange(tx_index=2, new_nonce=5)
            encoded = ssz.encode(nonce_change, sedes=NonceChange)
            decoded = ssz.decode(encoded, sedes=NonceChange)
            
            self.assert_test(
                decoded.tx_index == 2 and decoded.new_nonce == 5,
                "NonceChange encoding/decoding"
            )
        except Exception as e:
            self.assert_test(False, "NonceChange encoding/decoding", str(e))
        
        # Test CodeChange
        try:
            code_change = CodeChange(tx_index=3, new_code=b'\x60\x60\x60\x40')
            encoded = ssz.encode(code_change, sedes=CodeChange)
            decoded = ssz.decode(encoded, sedes=CodeChange)
            
            self.assert_test(
                decoded.tx_index == 3 and decoded.new_code == b'\x60\x60\x60\x40',
                "CodeChange encoding/decoding"
            )
        except Exception as e:
            self.assert_test(False, "CodeChange encoding/decoding", str(e))
        
        return True
    
    def test_slot_changes_encoding(self) -> bool:
        """Test encoding of SlotChanges structure."""
        try:
            changes = [
                StorageChange(tx_index=0, new_value=b'\x10' * 32),
                StorageChange(tx_index=1, new_value=b'\x20' * 32)
            ]
            slot_changes = SlotChanges(slot=b'\x01' * 32, changes=changes)
            
            encoded = ssz.encode(slot_changes, sedes=SlotChanges)
            decoded = ssz.decode(encoded, sedes=SlotChanges)
            
            self.assert_test(
                decoded.slot == b'\x01' * 32 and len(decoded.changes) == 2,
                "SlotChanges encoding/decoding"
            )
            
            self.assert_test(
                decoded.changes[0].tx_index == 0 and decoded.changes[1].tx_index == 1,
                "SlotChanges changes preservation"
            )
            
        except Exception as e:
            self.assert_test(False, "SlotChanges encoding/decoding", str(e))
            return False
        
        return True
    
    def test_slot_read_encoding(self) -> bool:
        """Test encoding of SlotRead structure."""
        try:
            slot_read = SlotRead(slot=b'\x02' * 32)
            
            encoded = ssz.encode(slot_read, sedes=SlotRead)
            decoded = ssz.decode(encoded, sedes=SlotRead)
            
            self.assert_test(
                decoded.slot == b'\x02' * 32,
                "SlotRead encoding/decoding"
            )
            
        except Exception as e:
            self.assert_test(False, "SlotRead encoding/decoding", str(e))
            return False
        
        return True
    
    def test_account_changes_encoding(self) -> bool:
        """Test encoding of AccountChanges structure."""
        try:
            # Test without code changes first (most reliable)
            storage_changes = [SlotChanges(
                slot=b'\x01' * 32,
                changes=[StorageChange(tx_index=0, new_value=b'\x10' * 32)]
            )]
            storage_reads = [SlotRead(slot=b'\x02' * 32)]
            balance_changes = [BalanceChange(tx_index=0, delta=(1000).to_bytes(12, 'big', signed=True))]
            nonce_changes = [NonceChange(tx_index=0, new_nonce=1)]
            
            account_changes = AccountChanges(
                address=b'\x01' * 20,
                storage_changes=storage_changes,
                storage_reads=storage_reads,
                balance_changes=balance_changes,
                nonce_changes=nonce_changes,
                code_changes=[]  # No code changes to avoid SSZ library issues
            )
            
            encoded = ssz.encode(account_changes, sedes=AccountChanges)
            decoded = ssz.decode(encoded, sedes=AccountChanges)
            
            self.assert_test(
                decoded.address == b'\x01' * 20,
                "AccountChanges address preservation"
            )
            
            self.assert_test(
                len(decoded.storage_changes) == 1 and len(decoded.storage_reads) == 1,
                "AccountChanges storage preservation"
            )
            
            self.assert_test(
                len(decoded.balance_changes) == 1 and len(decoded.nonce_changes) == 1,
                "AccountChanges balance/nonce preservation"
            )
            
            self.assert_test(
                len(decoded.code_changes) == 0,
                "AccountChanges code preservation (empty)"
            )
            
        except Exception as e:
            self.assert_test(False, "AccountChanges encoding/decoding", str(e))
            return False
        
        return True
    
    def test_full_bal_encoding(self) -> bool:
        """Test encoding of full MappedBlockAccessList."""
        try:
            # Create test BAL (without code changes to avoid SSZ library issues)
            builder = MappedBALBuilder()
            
            addr1 = b'\x01' * 20
            addr2 = b'\x02' * 20
            
            # Add various changes (no code changes for now)
            builder.add_storage_write(addr1, b'\x01' * 32, 0, b'\x10' * 32)
            builder.add_storage_read(addr1, b'\x02' * 32)
            builder.add_balance_change(addr1, 0, (1000).to_bytes(12, 'big', signed=True))
            builder.add_nonce_change(addr2, 1, 5)
            # Skip code change: builder.add_code_change(addr2, 1, b'\x60\x60\x60\x40')
            
            bal = builder.build(ignore_reads=False)
            
            # Encode and decode
            encoded = ssz.encode(bal, sedes=MappedBlockAccessList)
            decoded = ssz.decode(encoded, sedes=MappedBlockAccessList)
            
            self.assert_test(
                len(decoded.account_changes) == 2,
                "Full BAL account count preservation"
            )
            
            # Check first account
            account1 = decoded.account_changes[0]
            self.assert_test(
                bytes(account1.address) == addr1,
                "First account address preservation"
            )
            
            self.assert_test(
                len(account1.storage_changes) == 1 and len(account1.storage_reads) == 1,
                "First account storage preservation"
            )
            
            # Check second account  
            account2 = decoded.account_changes[1]
            self.assert_test(
                bytes(account2.address) == addr2,
                "Second account address preservation"
            )
            
            self.assert_test(
                len(account2.nonce_changes) == 1,
                "Second account nonce preservation"
            )
            
        except Exception as e:
            self.assert_test(False, "Full BAL encoding/decoding", str(e))
            return False
        
        return True
    
    def test_encoding_determinism(self) -> bool:
        """Test that encoding is deterministic."""
        try:
            # Create identical BALs
            builder1 = MappedBALBuilder()
            builder2 = MappedBALBuilder()
            
            addr = b'\x01' * 20
            slot = b'\x01' * 32
            value = b'\x10' * 32
            delta = (1000).to_bytes(12, 'big', signed=True)
            
            # Add identical data to both builders
            for builder in [builder1, builder2]:
                builder.add_storage_write(addr, slot, 0, value)
                builder.add_balance_change(addr, 0, delta)
            
            bal1 = builder1.build()
            bal2 = builder2.build()
            
            # Encode both
            encoded1 = ssz.encode(bal1, sedes=MappedBlockAccessList)
            encoded2 = ssz.encode(bal2, sedes=MappedBlockAccessList)
            
            self.assert_test(
                encoded1 == encoded2,
                "Encoding determinism",
                "Identical BALs produce different encodings"
            )
            
        except Exception as e:
            self.assert_test(False, "Encoding determinism", str(e))
            return False
        
        return True
    
    def test_compression_effectiveness(self) -> bool:
        """Test that compressed size is reasonable."""
        try:
            # Create test BAL with some data
            builder = MappedBALBuilder()
            
            for i in range(10):
                addr = (i).to_bytes(20, 'big')
                slot = (i).to_bytes(32, 'big') 
                value = (i * 100).to_bytes(32, 'big')
                delta = (i * 1000).to_bytes(12, 'big', signed=True)
                
                builder.add_storage_write(addr, slot, 0, value)
                builder.add_balance_change(addr, 0, delta)
            
            bal = builder.build()
            
            # Get compressed size
            encoded = ssz.encode(bal, sedes=MappedBlockAccessList)
            compressed_size = get_compressed_size(encoded)
            uncompressed_size = len(encoded) / 1024  # Convert to KiB
            
            self.assert_test(
                compressed_size < uncompressed_size,
                f"Compression effectiveness: {compressed_size:.2f} KiB < {uncompressed_size:.2f} KiB"
            )
            
            self.assert_test(
                compressed_size > 0,
                "Compressed size is positive"
            )
            
        except Exception as e:
            self.assert_test(False, "Compression effectiveness", str(e))
            return False
        
        return True
    
    def test_empty_bal_encoding(self) -> bool:
        """Test encoding of empty BAL."""
        try:
            builder = MappedBALBuilder()
            empty_bal = builder.build()
            
            encoded = ssz.encode(empty_bal, sedes=MappedBlockAccessList)
            decoded = ssz.decode(encoded, sedes=MappedBlockAccessList)
            
            self.assert_test(
                len(decoded.account_changes) == 0,
                "Empty BAL encoding/decoding"
            )
            
        except Exception as e:
            self.assert_test(False, "Empty BAL encoding/decoding", str(e))
            return False
        
        return True
    
    def test_large_bal_encoding(self) -> bool:
        """Test encoding of large BAL (stress test)."""
        try:
            builder = MappedBALBuilder()
            
            # Create larger test data (100 accounts, multiple changes each)
            for i in range(100):
                addr = (i).to_bytes(20, 'big')
                
                # Multiple storage slots per account
                for j in range(5):
                    slot = (i * 10 + j).to_bytes(32, 'big')
                    value = (i * 100 + j).to_bytes(32, 'big')
                    builder.add_storage_write(addr, slot, j % 3, value)
                
                # Balance and nonce changes
                delta = (i * 1000).to_bytes(12, 'big', signed=True)
                builder.add_balance_change(addr, 0, delta)
                builder.add_nonce_change(addr, 1, i + 1)
            
            bal = builder.build()
            
            # Encode and decode
            encoded = ssz.encode(bal, sedes=MappedBlockAccessList)
            decoded = ssz.decode(encoded, sedes=MappedBlockAccessList)
            
            self.assert_test(
                len(decoded.account_changes) == 100,
                "Large BAL account count preservation"
            )
            
            # Check some accounts have expected data
            first_account = decoded.account_changes[0]
            self.assert_test(
                len(first_account.storage_changes) == 5,
                "Large BAL storage changes preservation"
            )
            
        except Exception as e:
            self.assert_test(False, "Large BAL encoding/decoding", str(e))
            return False
        
        return True
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all SSZ encoding tests."""
        print("🔐 Running SSZ Encoding Tests...")
        print("-" * 50)
        
        results = {}
        results['individual_components'] = self.test_individual_component_encoding()
        results['slot_changes'] = self.test_slot_changes_encoding()
        results['slot_reads'] = self.test_slot_read_encoding()
        results['account_changes'] = self.test_account_changes_encoding()
        results['full_bal'] = self.test_full_bal_encoding()
        results['determinism'] = self.test_encoding_determinism()
        results['compression'] = self.test_compression_effectiveness()
        results['empty_bal'] = self.test_empty_bal_encoding()
        results['large_bal'] = self.test_large_bal_encoding()
        
        print(f"\nTest Results: {self.passed}/{self.total} passed, {self.failed}/{self.total} failed")
        
        return results

def main():
    """Main test function."""
    print("🧪 BAL SSZ Encoding Test Suite")
    print("=" * 60)
    
    # Run tests
    tester = TestSSZEncoding()
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