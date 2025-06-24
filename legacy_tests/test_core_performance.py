#!/usr/bin/env python3
"""
Performance comparison test for core RLP vs SSZ implementations.
Focuses on encoding efficiency and size comparisons.
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

def generate_test_scenarios():
    """Generate various test scenarios with different data sizes."""
    scenarios = []
    
    # Small scenario - single transaction, minimal changes
    small_scenario = {
        "name": "Small (1 tx, 1 account, 1 slot)",
        "trace": [{
            "txHash": "0x1234567890abcdef",
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
                        "balance": "0x101", 
                        "storage": {"0x01": "0x124"}
                    }
                }
            }
        }]
    }
    scenarios.append(small_scenario)
    
    # Medium scenario - multiple transactions and accounts
    medium_trace = []
    for tx_id in range(5):
        tx_data = {
            "txHash": f"0x{tx_id:064x}",
            "result": {
                "pre": {},
                "post": {}
            }
        }
        
        # Add 3 accounts per transaction
        for acc_id in range(3):
            addr = f"0x{(tx_id * 3 + acc_id + 1):040x}"
            
            # Pre state
            tx_data["result"]["pre"][addr] = {
                "balance": f"0x{100 + tx_id * 10 + acc_id}",
                "nonce": f"0x{tx_id + 1}",
                "storage": {
                    f"0x{i:064x}": f"0x{100 + i + tx_id * 10 + acc_id}"
                    for i in range(2)  # 2 storage slots per account
                }
            }
            
            # Post state (with changes)
            tx_data["result"]["post"][addr] = {
                "balance": f"0x{100 + tx_id * 10 + acc_id + 1}",  # Balance increased
                "storage": {
                    f"0x{i:064x}": f"0x{100 + i + tx_id * 10 + acc_id + 1}"
                    for i in range(2)  # Storage values increased
                }
            }
        
        medium_trace.append(tx_data)
    
    medium_scenario = {
        "name": "Medium (5 tx, 15 accounts, 30 slots)",
        "trace": medium_trace
    }
    scenarios.append(medium_scenario)
    
    # Large scenario - many transactions and accounts
    large_trace = []
    for tx_id in range(20):
        tx_data = {
            "txHash": f"0x{tx_id:064x}",
            "result": {
                "pre": {},
                "post": {}
            }
        }
        
        # Add 5 accounts per transaction
        for acc_id in range(5):
            addr = f"0x{(tx_id * 5 + acc_id + 1):040x}"
            
            # Pre state with more storage slots
            storage_pre = {}
            storage_post = {}
            for slot_id in range(5):  # 5 storage slots per account
                slot_key = f"0x{slot_id:064x}"
                storage_pre[slot_key] = f"0x{200 + slot_id + tx_id * 20 + acc_id * 5}"
                storage_post[slot_key] = f"0x{200 + slot_id + tx_id * 20 + acc_id * 5 + 1}"
            
            tx_data["result"]["pre"][addr] = {
                "balance": f"0x{1000 + tx_id * 50 + acc_id * 10}",
                "nonce": f"0x{tx_id + 1}",
                "storage": storage_pre
            }
            
            tx_data["result"]["post"][addr] = {
                "balance": f"0x{1000 + tx_id * 50 + acc_id * 10 + 5}",
                "storage": storage_post
            }
        
        large_trace.append(tx_data)
    
    large_scenario = {
        "name": "Large (20 tx, 100 accounts, 500 slots)",
        "trace": large_trace
    }
    scenarios.append(large_scenario)
    
    return scenarios

def benchmark_encoding(builder_func, trace_data, iterations=1):
    """Benchmark encoding performance."""
    total_time = 0
    results = None
    
    for _ in range(iterations):
        start_time = time.time()
        results = builder_func(trace_data)
        end_time = time.time()
        total_time += (end_time - start_time)
    
    avg_time = total_time / iterations
    return results, avg_time

def test_scenario_performance(scenario):
    """Test performance for a specific scenario."""
    print(f"\n📊 Testing Scenario: {scenario['name']}")
    print("-" * 60)
    
    trace_data = scenario['trace']
    results = {}
    
    try:
        # Test SSZ builder
        from bal_builder import (
            get_storage_diff_from_block as ssz_storage,
            get_balance_diff_from_block as ssz_balance,
            get_code_diff_from_block as ssz_code,
            build_contract_nonce_diffs_from_state as ssz_nonce
        )
        
        print("  🔍 Testing SSZ Builder...")
        
        # Storage diff
        ssz_storage_result, ssz_storage_time = benchmark_encoding(ssz_storage, trace_data)
        storage_encoded, storage_list = ssz_storage_result
        
        # Balance diff
        ssz_balance_result, ssz_balance_time = benchmark_encoding(ssz_balance, trace_data)
        balance_encoded, balance_list = ssz_balance_result
        
        # Code diff
        ssz_code_result, ssz_code_time = benchmark_encoding(ssz_code, trace_data)
        code_encoded, code_list = ssz_code_result
        
        # Nonce diff
        ssz_nonce_result, ssz_nonce_time = benchmark_encoding(ssz_nonce, trace_data)
        nonce_encoded, nonce_list = ssz_nonce_result
        
        ssz_total_size = len(storage_encoded) + len(balance_encoded) + len(code_encoded) + len(nonce_encoded)
        ssz_total_time = ssz_storage_time + ssz_balance_time + ssz_code_time + ssz_nonce_time
        
        results['ssz'] = {
            'storage_size': len(storage_encoded),
            'balance_size': len(balance_encoded),
            'code_size': len(code_encoded),
            'nonce_size': len(nonce_encoded),
            'total_size': ssz_total_size,
            'total_time': ssz_total_time,
            'storage_count': len(storage_list),
            'balance_count': len(balance_list),
            'code_count': len(code_list),
            'nonce_count': len(nonce_list)
        }
        
        print(f"    ✅ SSZ: {ssz_total_size} bytes, {ssz_total_time:.4f}s")
        
    except Exception as e:
        print(f"    ❌ SSZ Builder failed: {e}")
        results['ssz'] = None
    
    try:
        # Test RLP builder
        from bal_builder_rlp import (
            get_storage_diff_from_block as rlp_storage,
            get_balance_diff_from_block as rlp_balance,
            get_code_diff_from_block as rlp_code,
            build_contract_nonce_diffs_from_state as rlp_nonce
        )
        
        print("  🔍 Testing RLP Builder...")
        
        # Storage diff
        rlp_storage_result, rlp_storage_time = benchmark_encoding(rlp_storage, trace_data)
        storage_encoded, storage_list = rlp_storage_result
        
        # Balance diff
        rlp_balance_result, rlp_balance_time = benchmark_encoding(rlp_balance, trace_data)
        balance_encoded, balance_list = rlp_balance_result
        
        # Code diff
        rlp_code_result, rlp_code_time = benchmark_encoding(rlp_code, trace_data)
        code_encoded, code_list = rlp_code_result
        
        # Nonce diff
        rlp_nonce_result, rlp_nonce_time = benchmark_encoding(rlp_nonce, trace_data)
        nonce_encoded, nonce_list = rlp_nonce_result
        
        rlp_total_size = len(storage_encoded) + len(balance_encoded) + len(code_encoded) + len(nonce_encoded)
        rlp_total_time = rlp_storage_time + rlp_balance_time + rlp_code_time + rlp_nonce_time
        
        results['rlp'] = {
            'storage_size': len(storage_encoded),
            'balance_size': len(balance_encoded),
            'code_size': len(code_encoded),
            'nonce_size': len(nonce_encoded),
            'total_size': rlp_total_size,
            'total_time': rlp_total_time,
            'storage_count': len(storage_list),
            'balance_count': len(balance_list),
            'code_count': len(code_list),
            'nonce_count': len(nonce_list)
        }
        
        print(f"    ✅ RLP: {rlp_total_size} bytes, {rlp_total_time:.4f}s")
        
    except Exception as e:
        print(f"    ❌ RLP Builder failed: {e}")
        results['rlp'] = None
    
    # Compare results
    if results['ssz'] and results['rlp']:
        ssz_data = results['ssz']
        rlp_data = results['rlp']
        
        size_diff_percent = ((ssz_data['total_size'] - rlp_data['total_size']) / rlp_data['total_size']) * 100
        time_diff_percent = ((ssz_data['total_time'] - rlp_data['total_time']) / rlp_data['total_time']) * 100 if rlp_data['total_time'] > 0 else 0
        
        print(f"\n  📈 Comparison:")
        print(f"    Size: SSZ={ssz_data['total_size']} bytes, RLP={rlp_data['total_size']} bytes")
        if size_diff_percent > 0:
            print(f"    SSZ is {size_diff_percent:.1f}% larger")
        else:
            print(f"    RLP is {abs(size_diff_percent):.1f}% larger")
        
        print(f"    Time: SSZ={ssz_data['total_time']:.4f}s, RLP={rlp_data['total_time']:.4f}s")
        if time_diff_percent > 0:
            print(f"    SSZ is {time_diff_percent:.1f}% slower")
        else:
            print(f"    RLP is {abs(time_diff_percent):.1f}% slower")
        
        # Component breakdown
        print(f"\n  📋 Component Breakdown:")
        components = ['storage', 'balance', 'code', 'nonce']
        for comp in components:
            ssz_size = ssz_data[f'{comp}_size']
            rlp_size = rlp_data[f'{comp}_size']
            ssz_count = ssz_data[f'{comp}_count']
            rlp_count = rlp_data[f'{comp}_count']
            
            comp_diff = ((ssz_size - rlp_size) / rlp_size * 100) if rlp_size > 0 else 0
            
            print(f"    {comp.title():8}: SSZ={ssz_size:4d}b ({ssz_count:2d}), RLP={rlp_size:4d}b ({rlp_count:2d})", end="")
            if rlp_size > 0:
                if comp_diff > 0:
                    print(f" [SSZ +{comp_diff:.1f}%]")
                else:
                    print(f" [RLP +{abs(comp_diff):.1f}%]")
            else:
                print()
    
    return results

def analyze_scaling_patterns(all_results):
    """Analyze how the encoding efficiency scales with data size."""
    print(f"\n📈 Scaling Pattern Analysis")  
    print("=" * 60)
    
    if not all_results:
        print("No results to analyze")
        return
    
    # Extract size and efficiency data
    scenarios = []
    for scenario_name, results in all_results.items():
        if results['ssz'] and results['rlp']:
            ssz_size = results['ssz']['total_size']
            rlp_size = results['rlp']['total_size']
            efficiency_ratio = ssz_size / rlp_size if rlp_size > 0 else 1
            
            scenarios.append({
                'name': scenario_name,
                'ssz_size': ssz_size,
                'rlp_size': rlp_size,
                'efficiency_ratio': efficiency_ratio
            })
    
    # Sort by RLP size (as a proxy for data complexity)
    scenarios.sort(key=lambda x: x['rlp_size'])
    
    print("Size scaling (RLP size used as complexity measure):")
    for scenario in scenarios:
        print(f"  {scenario['name']:30}: RLP={scenario['rlp_size']:5d}b, SSZ={scenario['ssz_size']:5d}b, Ratio={scenario['efficiency_ratio']:.2f}")
    
    # Calculate trends
    if len(scenarios) >= 2:
        first_ratio = scenarios[0]['efficiency_ratio']
        last_ratio = scenarios[-1]['efficiency_ratio']
        
        print(f"\nEfficiency trend:")
        print(f"  Small data ratio: {first_ratio:.2f}")
        print(f"  Large data ratio: {last_ratio:.2f}")
        
        if last_ratio > first_ratio:
            print(f"  📈 SSZ becomes less efficient with larger data (+{((last_ratio - first_ratio) / first_ratio * 100):.1f}% worse)")
        else:
            print(f"  📉 SSZ becomes more efficient with larger data ({((first_ratio - last_ratio) / first_ratio * 100):.1f}% better)")

def run_performance_tests():
    """Run all performance tests."""
    print("🚀 Running Core BAL Performance Tests")
    print("=" * 60)
    
    scenarios = generate_test_scenarios()
    all_results = {}
    
    for scenario in scenarios:
        results = test_scenario_performance(scenario)
        all_results[scenario['name']] = results
    
    # Analyze scaling patterns
    analyze_scaling_patterns(all_results)
    
    # Generate summary report
    print(f"\n📊 Performance Test Summary")
    print("=" * 60)
    
    successful_tests = sum(1 for results in all_results.values() if results['ssz'] and results['rlp'])
    total_tests = len(all_results)
    
    print(f"Successful comparisons: {successful_tests}/{total_tests}")
    
    if successful_tests > 0:
        # Calculate averages
        avg_ssz_size = sum(r['ssz']['total_size'] for r in all_results.values() if r['ssz']) / successful_tests
        avg_rlp_size = sum(r['rlp']['total_size'] for r in all_results.values() if r['rlp']) / successful_tests
        avg_ratio = avg_ssz_size / avg_rlp_size
        
        print(f"Average sizes: SSZ={avg_ssz_size:.0f}b, RLP={avg_rlp_size:.0f}b")
        print(f"Average efficiency ratio: {avg_ratio:.2f}")
        
        if avg_ratio > 1:
            print(f"📈 SSZ is {((avg_ratio - 1) * 100):.1f}% larger on average")
        else:
            print(f"📉 RLP is {((1 - avg_ratio) * 100):.1f}% larger on average")
    
    return all_results

if __name__ == "__main__":
    run_performance_tests()