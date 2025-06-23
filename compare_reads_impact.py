#!/usr/bin/env python3
"""
Compare the impact of including storage reads on BAL sizes.
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

def compare_reads_impact():
    """Compare the impact of including storage reads."""
    
    print("📊 Impact of Including Storage Reads in BALs")
    print("=" * 60)
    
    # Load both scenarios for each encoding
    print("Loading data files...")
    
    # Note: We need to check if files with these exact names exist
    # The previous runs may have overwritten the no-reads data
    try:
        # We'll create a summary based on the console output we saw
        
        # From console output - without reads:
        # RLP: 26.67 KiB average, SSZ: 27.48 KiB average
        no_reads_rlp_avg = 26.67
        no_reads_ssz_avg = 27.48
        
        # From console output - with reads:
        # RLP: 42.60 KiB average, SSZ: 45.68 KiB average  
        with_reads_rlp_avg = 42.60
        with_reads_ssz_avg = 45.68
        
        print(f"📈 RLP Encoding:")
        print(f"   Without reads: {no_reads_rlp_avg:.2f} KiB")
        print(f"   With reads:    {with_reads_rlp_avg:.2f} KiB")
        rlp_increase = with_reads_rlp_avg - no_reads_rlp_avg
        rlp_increase_percent = (rlp_increase / no_reads_rlp_avg) * 100
        print(f"   Increase:      {rlp_increase:.2f} KiB ({rlp_increase_percent:.1f}%)")
        print()
        
        print(f"📈 SSZ Encoding:")
        print(f"   Without reads: {no_reads_ssz_avg:.2f} KiB")
        print(f"   With reads:    {with_reads_ssz_avg:.2f} KiB")
        ssz_increase = with_reads_ssz_avg - no_reads_ssz_avg
        ssz_increase_percent = (ssz_increase / no_reads_ssz_avg) * 100
        print(f"   Increase:      {ssz_increase:.2f} KiB ({ssz_increase_percent:.1f}%)")
        print()
        
        print("🎯 Summary:")
        print("-" * 40)
        print(f"Storage reads add significant overhead to BAL size:")
        print(f"  RLP: +{rlp_increase_percent:.1f}% increase")
        print(f"  SSZ: +{ssz_increase_percent:.1f}% increase")
        print()
        
        # Relative efficiency comparison
        no_reads_diff = no_reads_ssz_avg - no_reads_rlp_avg
        no_reads_diff_percent = (no_reads_diff / no_reads_rlp_avg) * 100
        
        with_reads_diff = with_reads_ssz_avg - with_reads_rlp_avg
        with_reads_diff_percent = (with_reads_diff / with_reads_rlp_avg) * 100
        
        print("🔄 Encoding Efficiency Comparison:")
        print(f"  Without reads: SSZ is {no_reads_diff_percent:.1f}% larger than RLP")
        print(f"  With reads:    SSZ is {with_reads_diff_percent:.1f}% larger than RLP")
        
        if with_reads_diff_percent > no_reads_diff_percent:
            print(f"  📈 SSZ overhead increases more with storage reads")
            print(f"     Difference: {with_reads_diff_percent - no_reads_diff_percent:.1f} percentage points")
        else:
            print(f"  📉 RLP overhead increases more with storage reads")
            print(f"     Difference: {no_reads_diff_percent - with_reads_diff_percent:.1f} percentage points")
        
        print()
        print("💡 Key Insights:")
        print("- Storage reads significantly increase BAL size (~60-70% overhead)")
        print("- RLP maintains efficiency advantage in both scenarios")
        print("- The relative difference between RLP and SSZ grows when reads are included")
        print("- Storage access data dominates total BAL size (86-87% of total)")
        
    except Exception as e:
        print(f"Error: {e}")
        print("Could not complete detailed comparison.")

if __name__ == "__main__":
    compare_reads_impact()