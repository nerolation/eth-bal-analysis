#!/usr/bin/env python3
"""
Compare RLP vs SSZ BAL encoding sizes from generated analysis files.
"""

import json
import statistics
from typing import Dict, List

def load_analysis_data(filename: str) -> List[Dict]:
    """Load analysis data from JSON file."""
    with open(filename, 'r') as f:
        return json.load(f)

def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of values."""
    return {
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
        'min': min(values),
        'max': max(values)
    }

def compare_encodings():
    """Compare RLP and SSZ encoding sizes."""
    
    # Load data
    rlp_data = load_analysis_data('bal_analysis_rlp_with_reads.json')
    ssz_data = load_analysis_data('bal_analysis_with_reads.json')
    
    print("🔍 RLP vs SSZ BAL Encoding Size Comparison")
    print("=" * 60)
    
    # Ensure same number of blocks
    assert len(rlp_data) == len(ssz_data), f"Data length mismatch: RLP={len(rlp_data)}, SSZ={len(ssz_data)}"
    
    print(f"📊 Analyzed {len(rlp_data)} blocks")
    print()
    
    # Component-wise comparison
    components = ['storage_access_kb', 'balance_diffs_kb', 'code_diffs_kb', 'nonce_diffs_kb', 'total_kb']
    
    results = {}
    
    for component in components:
        rlp_sizes = [block['sizes'][component] for block in rlp_data]
        ssz_sizes = [block['sizes'][component] for block in ssz_data]
        
        # Calculate statistics
        rlp_stats = calculate_statistics(rlp_sizes)
        ssz_stats = calculate_statistics(ssz_sizes)
        
        # Calculate differences
        absolute_diffs = [rlp - ssz for rlp, ssz in zip(rlp_sizes, ssz_sizes)]
        relative_diffs = [(rlp - ssz) / ssz * 100 if ssz > 0 else 0 for rlp, ssz in zip(rlp_sizes, ssz_sizes)]
        
        diff_stats = calculate_statistics(absolute_diffs)
        rel_diff_stats = calculate_statistics(relative_diffs)
        
        results[component] = {
            'rlp': rlp_stats,
            'ssz': ssz_stats,
            'absolute_diff': diff_stats,
            'relative_diff_percent': rel_diff_stats
        }
        
        # Display results for this component
        component_name = component.replace('_', ' ').title().replace('Kb', 'KiB')
        print(f"📈 {component_name}")
        print(f"   RLP:  {rlp_stats['mean']:.3f} ± {rlp_stats['std_dev']:.3f} KiB")
        print(f"   SSZ:  {ssz_stats['mean']:.3f} ± {ssz_stats['std_dev']:.3f} KiB")
        print(f"   Diff: {diff_stats['mean']:.3f} ± {diff_stats['std_dev']:.3f} KiB ({rel_diff_stats['mean']:.2f}%)")
        
        if diff_stats['mean'] > 0:
            print(f"   📊 RLP is {abs(rel_diff_stats['mean']):.1f}% larger on average")
        else:
            print(f"   📊 SSZ is {abs(rel_diff_stats['mean']):.1f}% larger on average")
        print()
    
    # Overall summary
    print("🎯 Summary")
    print("-" * 40)
    
    total_rlp_avg = results['total_kb']['rlp']['mean']
    total_ssz_avg = results['total_kb']['ssz']['mean']
    total_diff_percent = results['total_kb']['relative_diff_percent']['mean']
    
    print(f"Average Total Size:")
    print(f"  RLP: {total_rlp_avg:.2f} KiB")
    print(f"  SSZ: {total_ssz_avg:.2f} KiB")
    print(f"  Difference: {total_diff_percent:.2f}%")
    
    if total_diff_percent > 0:
        print(f"  🔴 RLP is {abs(total_diff_percent):.1f}% larger than SSZ")
    else:
        print(f"  🟢 SSZ is {abs(total_diff_percent):.1f}% larger than RLP")
    
    print()
    print("📋 Component Breakdown (% of total size):")
    for component in ['storage_access_kb', 'balance_diffs_kb', 'code_diffs_kb', 'nonce_diffs_kb']:
        rlp_percent = (results[component]['rlp']['mean'] / total_rlp_avg) * 100
        ssz_percent = (results[component]['ssz']['mean'] / total_ssz_avg) * 100
        component_name = component.replace('_kb', '').replace('_', ' ').title()
        print(f"  {component_name:15} - RLP: {rlp_percent:5.1f}%, SSZ: {ssz_percent:5.1f}%")
    
    # Block-by-block analysis
    print()
    print("🔍 Block-by-Block Analysis:")
    print("-" * 40)
    
    total_diffs = results['total_kb']['absolute_diff']
    rlp_larger_count = sum(1 for diff in [rlp['sizes']['total_kb'] - ssz['sizes']['total_kb'] 
                                         for rlp, ssz in zip(rlp_data, ssz_data)] if diff > 0)
    ssz_larger_count = len(rlp_data) - rlp_larger_count
    
    print(f"Blocks where RLP is larger: {rlp_larger_count}/{len(rlp_data)} ({rlp_larger_count/len(rlp_data)*100:.1f}%)")
    print(f"Blocks where SSZ is larger: {ssz_larger_count}/{len(rlp_data)} ({ssz_larger_count/len(rlp_data)*100:.1f}%)")
    print(f"Largest RLP advantage: {max(total_diffs['max'], 0):.3f} KiB")
    print(f"Largest SSZ advantage: {abs(min(total_diffs['min'], 0)):.3f} KiB")
    
    return results

if __name__ == "__main__":
    results = compare_encodings()