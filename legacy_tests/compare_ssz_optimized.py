#!/usr/bin/env python3
"""
Compare non-optimized SSZ vs optimized SSZ BAL encoding sizes from generated analysis files.
"""

import json
import statistics
from typing import Dict, List

def load_analysis_data(filename: str) -> List[Dict]:
    """Load analysis data from JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ File {filename} not found. Please run the corresponding BAL builder first.")
        return None

def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of values."""
    if not values:
        return {'mean': 0, 'median': 0, 'std_dev': 0, 'min': 0, 'max': 0}
    
    return {
        'mean': statistics.mean(values),
        'median': statistics.median(values),
        'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
        'min': min(values),
        'max': max(values)
    }

def map_component_names(component: str, is_optimized: bool = False) -> str:
    """Map component names between non-optimized and optimized formats."""
    mapping = {
        # Non-optimized components
        'storage_access_kb': 'storage_writes_kb' if is_optimized else 'storage_access_kb',
        'balance_diffs_kb': 'balance_diffs_kb',
        'code_diffs_kb': 'code_diffs_kb', 
        'nonce_diffs_kb': 'nonce_diffs_kb',
        'total_kb': 'total_kb'
    }
    return mapping.get(component, component)

def get_component_value(block_data: Dict, component: str, is_optimized: bool = False) -> float:
    """Extract component value, handling different formats between optimized and non-optimized."""
    sizes = block_data.get('sizes', {})
    
    if is_optimized:
        if component == 'storage_access_kb':
            # For optimized version, combine storage writes and reads
            writes = sizes.get('storage_writes_kb', 0)
            reads = sizes.get('storage_reads_kb', 0)
            return writes + reads
        elif component == 'mapping_overhead_kb':
            # Calculate total mapping overhead for optimized version
            address_mapping = sizes.get('address_mapping_kb', 0)
            slot_mapping = sizes.get('slot_mapping_kb', 0)
            return address_mapping + slot_mapping
    
    return sizes.get(component, 0)

def compare_encodings():
    """Compare non-optimized SSZ and optimized SSZ encoding sizes."""
    
    # Load data - try multiple possible filenames
    non_optimized_files = [
        'bal_analysis_with_reads.json',
        'bal_analysis_ssz_with_reads.json'
    ]
    
    optimized_files = [
        'bal_analysis_both_mapped_with_reads.json',
        'bal_analysis_both_mapped_with_reads_quick.json'
    ]
    
    non_optimized_data = None
    for filename in non_optimized_files:
        non_optimized_data = load_analysis_data(filename)
        if non_optimized_data:
            print(f"✅ Loaded non-optimized data from: {filename}")
            break
    
    optimized_data = None
    for filename in optimized_files:
        optimized_data = load_analysis_data(filename)
        if optimized_data:
            print(f"✅ Loaded optimized data from: {filename}")
            break
    
    if not non_optimized_data or not optimized_data:
        print("❌ Could not load required data files. Please ensure you have run both:")
        print("   1. Non-optimized SSZ builder (bal_builder.py)")
        print("   2. Optimized SSZ builder (bal_builder_optimized_address_slot_mapping.py)")
        return None
    
    print("\n🔍 Non-Optimized vs Optimized SSZ BAL Encoding Size Comparison")
    print("=" * 70)
    
    print(f"📊 Non-optimized blocks analyzed: {len(non_optimized_data)}")
    print(f"📊 Optimized blocks analyzed: {len(optimized_data)}")
    print()
    
    # For fair comparison, use the smaller dataset size
    min_blocks = min(len(non_optimized_data), len(optimized_data))
    non_optimized_data = non_optimized_data[:min_blocks]
    optimized_data = optimized_data[:min_blocks]
    
    print(f"📊 Using {min_blocks} blocks for comparison")
    print()
    
    # Component-wise comparison
    components = ['storage_access_kb', 'balance_diffs_kb', 'code_diffs_kb', 'nonce_diffs_kb', 'total_kb']
    
    results = {}
    
    for component in components:
        non_opt_sizes = [get_component_value(block, component, False) for block in non_optimized_data]
        opt_sizes = [get_component_value(block, component, True) for block in optimized_data]
        
        # Calculate statistics
        non_opt_stats = calculate_statistics(non_opt_sizes)
        opt_stats = calculate_statistics(opt_sizes)
        
        # Calculate differences (negative means optimized is smaller)
        absolute_diffs = [non_opt - opt for non_opt, opt in zip(non_opt_sizes, opt_sizes)]
        relative_diffs = [(non_opt - opt) / non_opt * 100 if non_opt > 0 else 0 
                         for non_opt, opt in zip(non_opt_sizes, opt_sizes)]
        
        diff_stats = calculate_statistics(absolute_diffs)
        rel_diff_stats = calculate_statistics(relative_diffs)
        
        results[component] = {
            'non_optimized': non_opt_stats,
            'optimized': opt_stats,
            'absolute_diff': diff_stats,
            'relative_diff_percent': rel_diff_stats
        }
        
        # Display results for this component
        component_name = component.replace('_', ' ').title().replace('Kb', 'KiB')
        print(f"📈 {component_name}")
        print(f"   Non-Opt: {non_opt_stats['mean']:.3f} ± {non_opt_stats['std_dev']:.3f} KiB")
        print(f"   Optimized: {opt_stats['mean']:.3f} ± {opt_stats['std_dev']:.3f} KiB")
        print(f"   Difference: {diff_stats['mean']:.3f} ± {diff_stats['std_dev']:.3f} KiB ({rel_diff_stats['mean']:.2f}%)")
        
        if diff_stats['mean'] > 0:
            print(f"   📊 Optimization saves {abs(rel_diff_stats['mean']):.1f}% on average")
        else:
            print(f"   📊 Optimization adds {abs(rel_diff_stats['mean']):.1f}% overhead on average")
        print()
    
    # Add mapping overhead analysis for optimized version
    mapping_overhead_sizes = [get_component_value(block, 'mapping_overhead_kb', True) for block in optimized_data]
    mapping_stats = calculate_statistics(mapping_overhead_sizes)
    
    print(f"📈 Mapping Overhead (Optimized Only)")
    print(f"   Total: {mapping_stats['mean']:.3f} ± {mapping_stats['std_dev']:.3f} KiB")
    
    # Break down mapping overhead
    address_overhead = [block['sizes'].get('address_mapping_kb', 0) for block in optimized_data]
    slot_overhead = [block['sizes'].get('slot_mapping_kb', 0) for block in optimized_data]
    address_stats = calculate_statistics(address_overhead)
    slot_stats = calculate_statistics(slot_overhead)
    
    print(f"   Address Mapping: {address_stats['mean']:.3f} ± {address_stats['std_dev']:.3f} KiB")
    print(f"   Slot Mapping: {slot_stats['mean']:.3f} ± {slot_stats['std_dev']:.3f} KiB")
    print()
    
    # Overall summary
    print("🎯 Summary")
    print("-" * 40)
    
    total_non_opt_avg = results['total_kb']['non_optimized']['mean']
    total_opt_avg = results['total_kb']['optimized']['mean']
    total_diff_percent = results['total_kb']['relative_diff_percent']['mean']
    
    print(f"Average Total Size:")
    print(f"  Non-Optimized: {total_non_opt_avg:.2f} KiB")
    print(f"  Optimized: {total_opt_avg:.2f} KiB")
    print(f"  Difference: {total_diff_percent:.2f}%")
    
    if total_diff_percent > 0:
        print(f"  🟢 Optimization saves {abs(total_diff_percent):.1f}% space")
    else:
        print(f"  🔴 Optimization adds {abs(total_diff_percent):.1f}% overhead")
    
    print()
    print("📋 Component Breakdown (% of total size):")
    for component in ['storage_access_kb', 'balance_diffs_kb', 'code_diffs_kb', 'nonce_diffs_kb']:
        non_opt_percent = (results[component]['non_optimized']['mean'] / total_non_opt_avg) * 100
        opt_percent = (results[component]['optimized']['mean'] / total_opt_avg) * 100
        component_name = component.replace('_kb', '').replace('_', ' ').title()
        print(f"  {component_name:15} - Non-Opt: {non_opt_percent:5.1f}%, Optimized: {opt_percent:5.1f}%")
    
    # Mapping overhead percentage
    mapping_percent = (mapping_stats['mean'] / total_opt_avg) * 100
    print(f"  {'Mapping Overhead':15} - Non-Opt:   0.0%, Optimized: {mapping_percent:5.1f}%")
    
    # Block-by-block analysis
    print()
    print("🔍 Block-by-Block Analysis:")
    print("-" * 40)
    
    total_diffs = [non_opt['sizes']['total_kb'] - get_component_value(opt, 'total_kb', True)
                   for non_opt, opt in zip(non_optimized_data, optimized_data)]
    
    opt_better_count = sum(1 for diff in total_diffs if diff > 0)
    non_opt_better_count = len(total_diffs) - opt_better_count
    
    print(f"Blocks where optimization helps: {opt_better_count}/{len(total_diffs)} ({opt_better_count/len(total_diffs)*100:.1f}%)")
    print(f"Blocks where non-optimized is better: {non_opt_better_count}/{len(total_diffs)} ({non_opt_better_count/len(total_diffs)*100:.1f}%)")
    print(f"Largest optimization benefit: {max(total_diffs):.3f} KiB")
    print(f"Largest optimization penalty: {abs(min(total_diffs)):.3f} KiB")
    
    # Efficiency analysis
    print()
    print("🧠 Optimization Efficiency Analysis:")
    print("-" * 40)
    
    if optimized_data and 'address_stats' in optimized_data[0]:
        avg_unique_addresses = statistics.mean([block.get('address_stats', {}).get('unique_addresses', 0) 
                                              for block in optimized_data])
        avg_unique_slots = statistics.mean([block.get('slot_stats', {}).get('unique_slots', 0) 
                                           for block in optimized_data])
        
        print(f"Average unique addresses per block: {avg_unique_addresses:.1f}")
        print(f"Average unique slots per block: {avg_unique_slots:.1f}")
        print(f"Address mapping efficiency: {address_stats['mean']/avg_unique_addresses*1024:.1f} bytes per unique address")
        print(f"Slot mapping efficiency: {slot_stats['mean']/avg_unique_slots*1024:.1f} bytes per unique slot")
    
    return results

if __name__ == "__main__":
    results = compare_encodings()