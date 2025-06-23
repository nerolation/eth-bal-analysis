#!/usr/bin/env python3
"""
Test suite for RLP implementation to ensure data integrity
"""

import os
import sys
import json
from pathlib import Path

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from helpers import *
from BALs import *
from BALs_rlp import *
import bal_builder
import bal_builder_rlp
from bal_builder import extract_reads_from_block

# Load RPC URL
rpc_file = os.path.join(project_root, "rpc.txt")
with open(rpc_file, "r") as file:
    RPC_URL = file.read().strip()


def test_encoding_consistency():
    """Test that RLP and SSZ produce identical logical data"""
    print("Testing encoding consistency...")
    
    # Use a smaller, recent block for testing
    test_block = 22616032 - 1000
    
    try:
        # Fetch trace data
        trace_result = fetch_block_trace(test_block, RPC_URL)
        block_reads = extract_reads_from_block(test_block, RPC_URL)
        
        # Build SSZ BAL
        ssz_storage_diff, ssz_account_access_list = bal_builder.get_storage_diff_from_block(
            trace_result, block_reads, False
        )
        ssz_balance_diff, ssz_acc_bal_diffs = bal_builder.get_balance_diff_from_block(trace_result)
        ssz_code_diff, ssz_acc_code_diffs = bal_builder.get_code_diff_from_block(trace_result)
        ssz_nonce_diff, ssz_account_nonce_list = bal_builder.build_contract_nonce_diffs_from_state(trace_result)
        
        # Build RLP BAL
        rlp_storage_diff, rlp_account_access_list = bal_builder_rlp.get_storage_diff_from_block(
            trace_result, block_reads, False
        )
        rlp_balance_diff, rlp_acc_bal_diffs = bal_builder_rlp.get_balance_diff_from_block(trace_result)
        rlp_code_diff, rlp_acc_code_diffs = bal_builder_rlp.get_code_diff_from_block(trace_result)
        rlp_nonce_diff, rlp_account_nonce_list = bal_builder_rlp.build_contract_nonce_diffs_from_state(trace_result)
        
        # Compare lengths
        print(f"  Account access lists - SSZ: {len(ssz_account_access_list)}, RLP: {len(rlp_account_access_list)}")
        print(f"  Balance diffs - SSZ: {len(ssz_acc_bal_diffs)}, RLP: {len(rlp_acc_bal_diffs)}")
        print(f"  Code diffs - SSZ: {len(ssz_acc_code_diffs)}, RLP: {len(rlp_acc_code_diffs)}")
        print(f"  Nonce diffs - SSZ: {len(ssz_account_nonce_list)}, RLP: {len(rlp_account_nonce_list)}")
        
        # Test that we have the same number of objects
        assert len(ssz_account_access_list) == len(rlp_account_access_list), "Account access list length mismatch"
        assert len(ssz_acc_bal_diffs) == len(rlp_acc_bal_diffs), "Balance diff length mismatch"
        assert len(ssz_acc_code_diffs) == len(rlp_acc_code_diffs), "Code diff length mismatch"
        assert len(ssz_account_nonce_list) == len(rlp_account_nonce_list), "Nonce diff length mismatch"
        
        print("  ✓ All object counts match")
        
        # Test address consistency
        ssz_bal_addresses = set(bytes(acc.address) for acc in ssz_acc_bal_diffs)
        rlp_bal_addresses = set(bytes(acc.address) for acc in rlp_acc_bal_diffs)
        assert ssz_bal_addresses == rlp_bal_addresses, "Balance diff addresses don't match"
        
        print("  ✓ Address sets match")
        
        # Test balance delta consistency (sample a few)
        for ssz_acc, rlp_acc in zip(ssz_acc_bal_diffs[:5], rlp_acc_bal_diffs[:5]):
            assert bytes(ssz_acc.address) == bytes(rlp_acc.address), f"Address mismatch"
            assert len(ssz_acc.changes) == len(rlp_acc.changes), f"Change count mismatch for {ssz_acc.address.hex()}"
            
            for ssz_change, rlp_change in zip(ssz_acc.changes, rlp_acc.changes):
                assert ssz_change.tx_index == rlp_change.tx_index, "Transaction index mismatch"
                # Convert RLP delta back to compare
                rlp_delta_int = decode_balance_delta(rlp_change.delta)
                ssz_delta_int = int.from_bytes(ssz_change.delta, byteorder='big', signed=True)
                assert ssz_delta_int == rlp_delta_int, f"Balance delta mismatch: SSZ={ssz_delta_int}, RLP={rlp_delta_int}"
        
        print("  ✓ Balance deltas match (sampled)")
        print("✓ Encoding consistency test passed!")
        
    except Exception as e:
        print(f"✗ Encoding consistency test failed: {str(e)}")
        raise


def test_size_analysis_functions():
    """Test the size analysis helper functions"""
    print("Testing size analysis functions...")
    
    try:
        # Create test data
        test_ssz_data = b"test_ssz_data" * 100
        test_rlp_data = b"test_rlp_data" * 90
        
        # Test basic compression
        ssz_compressed_size = get_compressed_size(test_ssz_data)
        rlp_compressed_size = get_rlp_compressed_size(test_rlp_data)
        
        print(f"  SSZ compressed size: {ssz_compressed_size:.3f} KiB")
        print(f"  RLP compressed size: {rlp_compressed_size:.3f} KiB")
        
        # Test comparison function
        comparison = compare_ssz_rlp_sizes(test_ssz_data, test_rlp_data)
        
        assert 'ssz' in comparison
        assert 'rlp' in comparison
        assert 'comparison' in comparison
        assert 'raw_bytes' in comparison['ssz']
        assert 'compressed_bytes' in comparison['ssz']
        
        print(f"  Raw size ratio: {comparison['comparison']['raw_size_ratio']:.3f}")
        print(f"  Compressed size ratio: {comparison['comparison']['compressed_size_ratio']:.3f}")
        
        # Test component analysis
        ssz_components = {'test': test_ssz_data}
        rlp_components = {'test': test_rlp_data}
        
        analysis = analyze_component_sizes(ssz_components, rlp_components, ['test'])
        
        assert 'test' in analysis
        assert 'ssz_raw_kb' in analysis['test']
        assert 'rlp_raw_kb' in analysis['test']
        
        print("✓ Size analysis functions test passed!")
        
    except Exception as e:
        print(f"✗ Size analysis functions test failed: {str(e)}")
        raise


def test_encoding_roundtrip():
    """Test that RLP objects can be encoded and decoded correctly"""
    print("Testing RLP encoding roundtrip...")
    
    try:
        # Create test objects
        test_balance_change = BalanceChangeRLP(
            tx_index=42,
            delta=encode_balance_delta(1000000000000000000)  # 1 ETH
        )
        
        test_account_balance_diff = AccountBalanceDiffRLP(
            address=encode_address("0x1234567890123456789012345678901234567890"),
            changes=[test_balance_change]
        )
        
        # Test encoding
        encoded = rlp.encode(test_account_balance_diff)
        print(f"  Encoded size: {len(encoded)} bytes")
        
        # Test decoding
        decoded = rlp.decode(encoded, AccountBalanceDiffRLP)
        
        # Verify data integrity
        assert decoded.address == test_account_balance_diff.address
        assert len(decoded.changes) == 1
        assert decoded.changes[0].tx_index == 42
        assert decode_balance_delta(decoded.changes[0].delta) == 1000000000000000000
        
        print("✓ RLP encoding roundtrip test passed!")
        
    except Exception as e:
        print(f"✗ RLP encoding roundtrip test failed: {str(e)}")
        raise


def run_all_tests():
    """Run all tests"""
    print("Running RLP implementation tests...\n")
    
    test_encoding_roundtrip()
    print()
    test_size_analysis_functions()
    print()
    test_encoding_consistency()
    
    print("\n✓ All tests passed!")


if __name__ == "__main__":
    run_all_tests()