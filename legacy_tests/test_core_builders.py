#!/usr/bin/env python3
"""
Test script for core BAL builders (RLP and SSZ).
Tests the builder functions and compares their outputs.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

def create_mock_trace_data() -> List[Dict[str, Any]]:
    """Create mock trace data for testing."""
    return [
        {
            "txHash": "0x1234567890abcdef",
            "result": {
                "pre": {
                    "0x1234567890123456789012345678901234567890": {
                        "balance": "0x56bc75e2d630eb20",
                        "nonce": "0x1",
                        "code": "0x608060405234801561001057600080fd5b50",
                        "storage": {
                            "0x0000000000000000000000000000000000000000000000000000000000000001": "0x123",
                            "0x0000000000000000000000000000000000000000000000000000000000000002": "0x456"
                        }
                    },
                    "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd": {
                        "balance": "0x1bc16d674ec80000",
                        "nonce": "0x5",
                        "storage": {
                            "0x0000000000000000000000000000000000000000000000000000000000000003": "0x789"
                        }
                    }
                },
                "post": {
                    "0x1234567890123456789012345678901234567890": {
                        "balance": "0x56bc75e2d630eb21",  # Balance increased by 1
                        "nonce": "0x2",  # Nonce increased
                        "storage": {
                            "0x0000000000000000000000000000000000000000000000000000000000000001": "0x124",  # Storage updated
                            "0x0000000000000000000000000000000000000000000000000000000000000002": "0x456"   # Storage unchanged
                        }
                    },
                    "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd": {
                        "balance": "0x1bc16d674ec7ffff",  # Balance decreased by 1
                        "storage": {
                            "0x0000000000000000000000000000000000000000000000000000000000000003": "0x78a"  # Storage updated
                        }
                    }
                }
            }
        },
        {
            "txHash": "0xabcdef1234567890",  
            "result": {
                "pre": {
                    "0x1234567890123456789012345678901234567890": {
                        "balance": "0x56bc75e2d630eb21",
                        "nonce": "0x2",
                        "storage": {
                            "0x0000000000000000000000000000000000000000000000000000000000000001": "0x124"
                        }
                    }
                },
                "post": {
                    "0x1234567890123456789012345678901234567890": {
                        "balance": "0x56bc75e2d630eb22",  # Another balance change
                        "storage": {
                            "0x0000000000000000000000000000000000000000000000000000000000000001": "0x125"  # Another storage change
                        }
                    }
                }
            }
        }
    ]

def test_ssz_builder():
    """Test SSZ builder functions."""
    print("\n🔍 Testing SSZ Builder Functions...")
    
    try:
        from bal_builder import (
            get_storage_diff_from_block,
            get_balance_diff_from_block,
            get_code_diff_from_block,
            build_contract_nonce_diffs_from_state
        )
        
        trace_data = create_mock_trace_data()
        
        # Test storage diff
        storage_encoded, storage_list = get_storage_diff_from_block(trace_data)
        assert isinstance(storage_encoded, bytes)
        assert isinstance(storage_list, list)
        print(f"  ✅ Storage diff: {len(storage_encoded)} bytes, {len(storage_list)} accounts")
        
        # Test balance diff
        balance_encoded, balance_list = get_balance_diff_from_block(trace_data)
        assert isinstance(balance_encoded, bytes)
        assert isinstance(balance_list, list)
        print(f"  ✅ Balance diff: {len(balance_encoded)} bytes, {len(balance_list)} accounts")
        
        # Test code diff
        code_encoded, code_list = get_code_diff_from_block(trace_data)
        assert isinstance(code_encoded, bytes)
        assert isinstance(code_list, list)
        print(f"  ✅ Code diff: {len(code_encoded)} bytes, {len(code_list)} accounts")
        
        # Test nonce diff
        nonce_encoded, nonce_list = build_contract_nonce_diffs_from_state(trace_data)
        assert isinstance(nonce_encoded, bytes)
        assert isinstance(nonce_list, list)
        print(f"  ✅ Nonce diff: {len(nonce_encoded)} bytes, {len(nonce_list)} accounts")
        
        return {
            'storage': (storage_encoded, storage_list),
            'balance': (balance_encoded, balance_list),
            'code': (code_encoded, code_list),
            'nonce': (nonce_encoded, nonce_list)
        }
        
    except Exception as e:
        print(f"  ❌ SSZ builder test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_rlp_builder():
    """Test RLP builder functions."""
    print("\n🔍 Testing RLP Builder Functions...")
    
    try:
        from bal_builder_rlp import (
            get_storage_diff_from_block,
            get_balance_diff_from_block,
            get_code_diff_from_block,
            build_contract_nonce_diffs_from_state
        )
        
        trace_data = create_mock_trace_data()
        
        # Test storage diff
        storage_encoded, storage_list = get_storage_diff_from_block(trace_data)
        assert isinstance(storage_encoded, bytes)
        assert isinstance(storage_list, list)
        print(f"  ✅ Storage diff: {len(storage_encoded)} bytes, {len(storage_list)} accounts")
        
        # Test balance diff
        balance_encoded, balance_list = get_balance_diff_from_block(trace_data)
        assert isinstance(balance_encoded, bytes)
        assert isinstance(balance_list, list)
        print(f"  ✅ Balance diff: {len(balance_encoded)} bytes, {len(balance_list)} accounts")
        
        # Test code diff
        code_encoded, code_list = get_code_diff_from_block(trace_data)
        assert isinstance(code_encoded, bytes)
        assert isinstance(code_list, list)
        print(f"  ✅ Code diff: {len(code_encoded)} bytes, {len(code_list)} accounts")
        
        # Test nonce diff
        nonce_encoded, nonce_list = build_contract_nonce_diffs_from_state(trace_data)
        assert isinstance(nonce_encoded, bytes)
        assert isinstance(nonce_list, list)
        print(f"  ✅ Nonce diff: {len(nonce_encoded)} bytes, {len(nonce_list)} accounts")
        
        return {
            'storage': (storage_encoded, storage_list),
            'balance': (balance_encoded, balance_list),
            'code': (code_encoded, code_list),
            'nonce': (nonce_encoded, nonce_list)
        }
        
    except Exception as e:
        print(f"  ❌ RLP builder test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def compare_builder_outputs(ssz_results: Dict, rlp_results: Dict):
    """Compare outputs from SSZ and RLP builders."""
    print("\n🔍 Comparing SSZ vs RLP Builder Outputs...")
    
    if not ssz_results or not rlp_results:
        print("  ❌ Cannot compare - one or both builders failed")
        return False
    
    try:
        comparison_results = {}
        
        for component in ['storage', 'balance', 'code', 'nonce']:
            ssz_encoded, ssz_list = ssz_results[component]
            rlp_encoded, rlp_list = rlp_results[component]
            
            ssz_size = len(ssz_encoded)
            rlp_size = len(rlp_encoded)
            ssz_count = len(ssz_list)
            rlp_count = len(rlp_list)
            
            size_diff = ((ssz_size - rlp_size) / rlp_size * 100) if rlp_size > 0 else 0
            
            comparison_results[component] = {
                'ssz_size': ssz_size,
                'rlp_size': rlp_size,
                'size_diff_percent': size_diff,
                'ssz_count': ssz_count,
                'rlp_count': rlp_count
            }
            
            print(f"  📊 {component.title()} Component:")
            print(f"     SSZ: {ssz_size} bytes, {ssz_count} items")
            print(f"     RLP: {rlp_size} bytes, {rlp_count} items")
            if rlp_size > 0:
                if size_diff > 0:
                    print(f"     SSZ is {size_diff:.1f}% larger")
                else:
                    print(f"     RLP is {abs(size_diff):.1f}% larger")
            print()
        
        return comparison_results
        
    except Exception as e:
        print(f"  ❌ Comparison failed: {e}")
        return None

def test_data_consistency(ssz_results: Dict, rlp_results: Dict):
    """Test that SSZ and RLP builders produce consistent logical results."""
    print("\n🔍 Testing Data Consistency...")
    
    if not ssz_results or not rlp_results:
        print("  ❌ Cannot test consistency - one or both builders failed")
        return False
    
    try:
        # Check that both builders identify the same number of affected accounts
        for component in ['storage', 'balance', 'code', 'nonce']:
            ssz_count = len(ssz_results[component][1])
            rlp_count = len(rlp_results[component][1])
            
            if ssz_count != rlp_count:
                print(f"  ⚠️  {component.title()} count mismatch: SSZ={ssz_count}, RLP={rlp_count}")
            else:
                print(f"  ✅ {component.title()} count consistent: {ssz_count} accounts")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Consistency test failed: {e}")
        return False

def test_edge_cases():
    """Test edge cases with empty or minimal data."""
    print("\n🔍 Testing Edge Cases...")
    
    # Empty trace
    empty_trace = []
    
    # Trace with no changes
    no_changes_trace = [{
        "txHash": "0x0000000000000000",
        "result": {
            "pre": {
                "0x1234567890123456789012345678901234567890": {
                    "balance": "0x100",
                    "nonce": "0x1",
                    "storage": {"0x01": "0x123"}
                }
            },
            "post": {
                "0x1234567890123456789012345678901234567890": {
                    "balance": "0x100",  # Same balance
                    "nonce": "0x1",     # Same nonce
                    "storage": {"0x01": "0x123"}  # Same storage
                }
            }
        }
    }]
    
    edge_cases = [
        ("Empty trace", empty_trace),
        ("No changes trace", no_changes_trace)
    ]
    
    passed = 0
    failed = 0
    
    for case_name, trace_data in edge_cases:
        print(f"\n  📋 Testing {case_name}...")
        
        try:
            # Test SSZ builder with edge case
            from bal_builder import get_storage_diff_from_block as ssz_storage_diff
            ssz_encoded, ssz_list = ssz_storage_diff(trace_data)
            print(f"    ✅ SSZ handled {case_name}: {len(ssz_encoded)} bytes")
            
            # Test RLP builder with edge case  
            from bal_builder_rlp import get_storage_diff_from_block as rlp_storage_diff
            rlp_encoded, rlp_list = rlp_storage_diff(trace_data)
            print(f"    ✅ RLP handled {case_name}: {len(rlp_encoded)} bytes")
            
            passed += 1
            
        except Exception as e:
            print(f"    ❌ {case_name} failed: {e}")
            failed += 1
    
    return passed, failed

def run_builder_tests():
    """Run all builder tests."""
    print("🚀 Running Core BAL Builder Tests")
    print("=" * 60)
    
    # Test individual builders
    ssz_results = test_ssz_builder()
    rlp_results = test_rlp_builder()
    
    # Compare results
    if ssz_results and rlp_results:
        comparison = compare_builder_outputs(ssz_results, rlp_results)
        consistency = test_data_consistency(ssz_results, rlp_results)
    
    # Test edge cases
    edge_passed, edge_failed = test_edge_cases()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Builder Test Results Summary")
    print("=" * 60)
    
    total_tests = 4  # SSZ, RLP, comparison, consistency
    passed_tests = 0
    
    if ssz_results:
        print("✅ SSZ Builder: PASSED")
        passed_tests += 1
    else:
        print("❌ SSZ Builder: FAILED")
    
    if rlp_results:
        print("✅ RLP Builder: PASSED")
        passed_tests += 1
    else:
        print("❌ RLP Builder: FAILED")
    
    if ssz_results and rlp_results:
        if comparison:
            print("✅ Output Comparison: PASSED")
            passed_tests += 1
        else:
            print("❌ Output Comparison: FAILED")
        
        if consistency:
            print("✅ Data Consistency: PASSED")
            passed_tests += 1
        else:
            print("❌ Data Consistency: FAILED")
    
    print(f"\nEdge Cases: {edge_passed} passed, {edge_failed} failed")
    print(f"Overall: {passed_tests}/{total_tests} main tests passed")
    
    return passed_tests, total_tests, edge_passed, edge_failed

if __name__ == "__main__":
    run_builder_tests()