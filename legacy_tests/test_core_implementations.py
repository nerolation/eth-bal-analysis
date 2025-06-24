#!/usr/bin/env python3
"""
Comprehensive test suite for core RLP and SSZ BAL implementations.
Tests the basic BAL structures and their encoding/decoding capabilities.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

def test_imports():
    """Test that core BAL implementations can be imported."""
    try:
        from BALs import *
        print("✅ BALs.py (SSZ) import successful")
    except ImportError as e:
        print(f"❌ BALs.py (SSZ) import failed: {e}")
        return False
    
    try:
        from BALs_rlp import *
        print("✅ BALs_rlp.py (RLP) import successful")
    except ImportError as e:
        print(f"❌ BALs_rlp.py (RLP) import failed: {e}")
        return False
    
    return True

def test_ssz_structures():
    """Test SSZ structure creation and basic operations."""
    print("\n🔍 Testing SSZ Structures...")
    
    try:
        from BALs import (
            PerTxAccess, SlotAccess, AccountAccess, 
            BalanceChange, AccountBalanceDiff,
            TxNonceDiff, AccountNonceDiff,
            CodeChange, AccountCodeDiff,
            BlockAccessList
        )
        
        # Test PerTxAccess
        per_tx = PerTxAccess(tx_index=1, value_after=b'\x00' * 32)
        assert per_tx.tx_index == 1
        print("  ✅ PerTxAccess creation")
        
        # Test SlotAccess
        slot = SlotAccess(slot=b'\x01' * 32, accesses=[per_tx])
        assert len(slot.accesses) == 1
        print("  ✅ SlotAccess creation")
        
        # Test AccountAccess
        account = AccountAccess(address=b'\x02' * 20, accesses=[slot])
        assert len(account.accesses) == 1
        print("  ✅ AccountAccess creation")
        
        # Test BalanceChange
        balance_change = BalanceChange(tx_index=1, delta=b'\x03' * 12)
        assert balance_change.tx_index == 1
        print("  ✅ BalanceChange creation")
        
        # Test AccountBalanceDiff
        account_balance = AccountBalanceDiff(address=b'\x04' * 20, changes=[balance_change])
        assert len(account_balance.changes) == 1
        print("  ✅ AccountBalanceDiff creation")
        
        # Test TxNonceDiff
        nonce_diff = TxNonceDiff(tx_index=1, nonce_after=100)
        assert nonce_diff.nonce_after == 100
        print("  ✅ TxNonceDiff creation")
        
        # Test AccountNonceDiff
        account_nonce = AccountNonceDiff(address=b'\x05' * 20, changes=[nonce_diff])
        assert len(account_nonce.changes) == 1
        print("  ✅ AccountNonceDiff creation")
        
        # Test CodeChange
        code_change = CodeChange(tx_index=1, new_code=b'\x60\x60\x60')
        assert code_change.tx_index == 1
        print("  ✅ CodeChange creation")
        
        # Test AccountCodeDiff
        account_code = AccountCodeDiff(address=b'\x06' * 20, change=code_change)
        assert account_code.change.tx_index == 1
        print("  ✅ AccountCodeDiff creation")
        
        # Test BlockAccessList
        block_al = BlockAccessList(
            account_accesses=[account],
            balance_diffs=[account_balance],
            code_diffs=[account_code],
            nonce_diffs=[account_nonce]
        )
        assert len(block_al.account_accesses) == 1
        assert len(block_al.balance_diffs) == 1
        assert len(block_al.code_diffs) == 1
        assert len(block_al.nonce_diffs) == 1
        print("  ✅ BlockAccessList creation")
        
        return True
        
    except Exception as e:
        print(f"  ❌ SSZ structure test failed: {e}")
        return False

def test_rlp_structures():
    """Test RLP structure creation and basic operations."""
    print("\n🔍 Testing RLP Structures...")
    
    try:
        from BALs_rlp import (
            PerTxAccessRLP, SlotAccessRLP, AccountAccessRLP,
            BalanceChangeRLP, AccountBalanceDiffRLP,
            TxNonceDiffRLP, AccountNonceDiffRLP,
            CodeChangeRLP, AccountCodeDiffRLP,
            BlockAccessListRLP
        )
        
        # Test PerTxAccessRLP
        per_tx = PerTxAccessRLP(tx_index=1, value_after=b'\x00' * 32)
        assert per_tx.tx_index == 1
        print("  ✅ PerTxAccessRLP creation")
        
        # Test SlotAccessRLP
        slot = SlotAccessRLP(slot=b'\x01' * 32, accesses=[per_tx])
        assert len(slot.accesses) == 1
        print("  ✅ SlotAccessRLP creation")
        
        # Test AccountAccessRLP
        account = AccountAccessRLP(address=b'\x02' * 20, accesses=[slot])
        assert len(account.accesses) == 1
        print("  ✅ AccountAccessRLP creation")
        
        # Test BalanceChangeRLP
        balance_change = BalanceChangeRLP(tx_index=1, delta=b'\x03' * 12)
        assert balance_change.tx_index == 1
        print("  ✅ BalanceChangeRLP creation")
        
        # Test AccountBalanceDiffRLP
        account_balance = AccountBalanceDiffRLP(address=b'\x04' * 20, changes=[balance_change])
        assert len(account_balance.changes) == 1
        print("  ✅ AccountBalanceDiffRLP creation")
        
        # Test TxNonceDiffRLP
        nonce_diff = TxNonceDiffRLP(tx_index=1, nonce_after=100)
        assert nonce_diff.nonce_after == 100
        print("  ✅ TxNonceDiffRLP creation")
        
        # Test AccountNonceDiffRLP
        account_nonce = AccountNonceDiffRLP(address=b'\x05' * 20, changes=[nonce_diff])
        assert len(account_nonce.changes) == 1
        print("  ✅ AccountNonceDiffRLP creation")
        
        # Test CodeChangeRLP
        code_change = CodeChangeRLP(tx_index=1, new_code=b'\x60\x60\x60')
        assert code_change.tx_index == 1
        print("  ✅ CodeChangeRLP creation")
        
        # Test AccountCodeDiffRLP
        account_code = AccountCodeDiffRLP(address=b'\x06' * 20, change=code_change)
        assert account_code.change.tx_index == 1
        print("  ✅ AccountCodeDiffRLP creation")
        
        # Test BlockAccessListRLP
        block_al = BlockAccessListRLP(
            account_accesses=[account],
            balance_diffs=[account_balance],
            code_diffs=[account_code],
            nonce_diffs=[account_nonce]
        )
        assert len(block_al.account_accesses) == 1
        assert len(block_al.balance_diffs) == 1
        assert len(block_al.code_diffs) == 1
        assert len(block_al.nonce_diffs) == 1
        print("  ✅ BlockAccessListRLP creation")
        
        return True
        
    except Exception as e:
        print(f"  ❌ RLP structure test failed: {e}")
        return False

def test_helper_functions():
    """Test helper functions in RLP implementation."""
    print("\n🔍 Testing Helper Functions...")
    
    try:
        from BALs_rlp import (
            encode_balance_delta, decode_balance_delta,
            encode_storage_key, encode_storage_value,
            encode_address
        )
        
        # Test balance delta encoding/decoding
        positive_delta = 1000
        negative_delta = -500
        
        pos_encoded = encode_balance_delta(positive_delta)
        neg_encoded = encode_balance_delta(negative_delta)
        
        assert decode_balance_delta(pos_encoded) == positive_delta
        assert decode_balance_delta(neg_encoded) == negative_delta
        print("  ✅ Balance delta encoding/decoding")
        
        # Test storage key encoding
        key_hex = "0x0000000000000000000000000000000000000000000000000000000000000001"
        key_encoded = encode_storage_key(key_hex)
        assert len(key_encoded) == 32
        assert key_encoded[-1] == 1  # Last byte should be 1
        print("  ✅ Storage key encoding")
        
        # Test storage value encoding
        value_hex = "0x0000000000000000000000000000000000000000000000000000000000000123"
        value_encoded = encode_storage_value(value_hex)
        assert len(value_encoded) == 32
        assert int.from_bytes(value_encoded, 'big') == 0x123
        print("  ✅ Storage value encoding")
        
        # Test address encoding
        addr_hex = "0x1234567890123456789012345678901234567890"
        addr_encoded = encode_address(addr_hex)
        assert len(addr_encoded) == 20
        print("  ✅ Address encoding")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Helper function test failed: {e}")
        return False

def test_constants_and_limits():
    """Test that constants are properly defined."""
    print("\n🔍 Testing Constants and Limits...")
    
    try:
        from BALs import MAX_TXS, MAX_SLOTS, MAX_ACCOUNTS, MAX_CODE_SIZE
        from BALs_rlp import MAX_TXS as RLP_MAX_TXS, MAX_SLOTS as RLP_MAX_SLOTS, MAX_ACCOUNTS as RLP_MAX_ACCOUNTS, MAX_CODE_SIZE as RLP_MAX_CODE_SIZE
        
        # Check that constants are defined and reasonable
        assert MAX_TXS == 30_000
        assert MAX_SLOTS == 300_000
        assert MAX_ACCOUNTS == 300_000
        assert MAX_CODE_SIZE == 24_576
        print("  ✅ SSZ constants defined correctly")
        
        # Check that RLP constants match SSZ
        assert RLP_MAX_TXS == MAX_TXS
        assert RLP_MAX_SLOTS == MAX_SLOTS
        assert RLP_MAX_ACCOUNTS == MAX_ACCOUNTS
        assert RLP_MAX_CODE_SIZE == MAX_CODE_SIZE
        print("  ✅ RLP constants match SSZ constants")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Constants test failed: {e}")
        return False

def test_parsing_functions():
    """Test parsing utility functions."""
    print("\n🔍 Testing Parsing Functions...")
    
    try:
        from BALs import parse_hex_or_zero
        from BALs_rlp import parse_hex_or_zero as rlp_parse_hex_or_zero
        
        # Test hex parsing
        assert parse_hex_or_zero("0x1a") == 26
        assert parse_hex_or_zero("0x0") == 0
        assert parse_hex_or_zero(None) == 0
        assert parse_hex_or_zero("") == 0
        print("  ✅ SSZ hex parsing")
        
        # Test RLP hex parsing
        assert rlp_parse_hex_or_zero("0x1a") == 26
        assert rlp_parse_hex_or_zero("0x0") == 0
        assert rlp_parse_hex_or_zero(None) == 0
        assert rlp_parse_hex_or_zero("") == 0
        print("  ✅ RLP hex parsing")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Parsing function test failed: {e}")
        return False

def create_sample_data():
    """Create sample data for testing encodings."""
    print("\n🔍 Creating Sample Test Data...")
    
    try:
        # Sample addresses and slots
        addr1 = b'\x01' * 20
        addr2 = b'\x02' * 20
        slot1 = b'\x00' * 31 + b'\x01'
        slot2 = b'\x00' * 31 + b'\x02'
        
        # Sample transaction data
        sample_data = {
            'addresses': [addr1, addr2],
            'slots': [slot1, slot2],
            'tx_indices': [0, 1, 2],
            'values': [b'\x00' * 32, b'\x01' * 32, b'\x02' * 32],
            'balances': [b'\x00' * 12, b'\x01' * 12],
            'nonces': [100, 101, 102],
            'code': [b'\x60\x60\x60', b'\x61\x61\x61']
        }
        
        print("  ✅ Sample data created")
        return sample_data
        
    except Exception as e:
        print(f"  ❌ Sample data creation failed: {e}")
        return None

def run_all_tests():
    """Run all tests and report results."""
    print("🚀 Running Core BAL Implementation Tests")
    print("=" * 60)
    
    tests = [
        ("Import Tests", test_imports),
        ("SSZ Structure Tests", test_ssz_structures),
        ("RLP Structure Tests", test_rlp_structures),
        ("Helper Function Tests", test_helper_functions),
        ("Constants Tests", test_constants_and_limits),
        ("Parsing Function Tests", test_parsing_functions),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        try:
            if test_func():
                print(f"✅ {test_name} PASSED")
                passed += 1
            else:
                print(f"❌ {test_name} FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} FAILED with exception: {e}")
            failed += 1
    
    # Create sample data for manual inspection
    sample_data = create_sample_data()
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("🎉 All tests passed! Core implementations are working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the implementations.")
    
    return passed, failed

if __name__ == "__main__":
    run_all_tests()