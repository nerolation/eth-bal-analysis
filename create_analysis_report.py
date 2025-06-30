#!/usr/bin/env python3
"""
Create comprehensive BAL size analysis report comparing:
- SSZ vs RLP encoding
- With reads vs Without reads
- Component breakdowns and efficiency stats
"""

import json
import os
import statistics
from pathlib import Path

def load_analysis_data():
    """Load all analysis JSON files."""
    project_root = Path(__file__).parent
    
    # Load SSZ data
    ssz_with_reads_path = project_root / "bal_raw" / "ssz" / "bal_analysis_with_reads.json"
    ssz_without_reads_path = project_root / "bal_raw" / "ssz" / "bal_analysis_without_reads.json"
    
    # Load RLP data
    rlp_without_reads_path = project_root / "bal_raw" / "rlp" / "bal_analysis_rlp_without_reads.json"
    
    data = {}
    
    if ssz_with_reads_path.exists():
        with open(ssz_with_reads_path, 'r') as f:
            data['ssz_with_reads'] = json.load(f)
    
    if ssz_without_reads_path.exists():
        with open(ssz_without_reads_path, 'r') as f:
            data['ssz_without_reads'] = json.load(f)
            
    if rlp_without_reads_path.exists():
        with open(rlp_without_reads_path, 'r') as f:
            data['rlp_without_reads'] = json.load(f)
    
    return data

def calculate_averages(data_list, field_path):
    """Calculate average for a nested field path."""
    values = []
    for item in data_list:
        current = item
        for field in field_path:
            current = current.get(field, {})
        if isinstance(current, (int, float)):
            values.append(current)
    
    if values:
        return {
            'avg': statistics.mean(values),
            'median': statistics.median(values),
            'min': min(values),
            'max': max(values)
        }
    return {'avg': 0, 'median': 0, 'min': 0, 'max': 0}

def analyze_component_sizes(data_list):
    """Analyze component sizes from data list."""
    components = ['storage_changes_kb', 'storage_reads_kb', 'storage_total_kb', 
                  'balance_diffs_kb', 'nonce_diffs_kb', 'code_diffs_kb', 'total_kb']
    
    results = {}
    for component in components:
        results[component] = calculate_averages(data_list, ['sizes', component])
    
    return results

def analyze_efficiency_stats(data_list):
    """Analyze efficiency statistics."""
    stats = ['total_accounts', 'total_storage_writes', 'total_storage_reads']
    
    results = {}
    for stat in stats:
        results[stat] = calculate_averages(data_list, ['bal_stats', stat])
    
    return results

def create_comparison_table(ssz_data, rlp_data, title):
    """Create a comparison table between SSZ and RLP."""
    lines = [f"\n### {title}\n"]
    lines.append("| Component | SSZ Avg (KiB) | RLP Avg (KiB) | RLP/SSZ Ratio | Difference (KiB) |")
    lines.append("|-----------|---------------|---------------|---------------|------------------|")
    
    components = ['storage_changes_kb', 'storage_reads_kb', 'storage_total_kb', 
                  'balance_diffs_kb', 'nonce_diffs_kb', 'code_diffs_kb', 'total_kb']
    
    for component in components:
        ssz_avg = ssz_data.get(component, {}).get('avg', 0)
        rlp_avg = rlp_data.get(component, {}).get('avg', 0)
        
        if ssz_avg > 0:
            ratio = rlp_avg / ssz_avg
            diff = rlp_avg - ssz_avg
        else:
            ratio = 0
            diff = rlp_avg
        
        component_name = component.replace('_kb', '').replace('_', ' ').title()
        lines.append(f"| {component_name} | {ssz_avg:.2f} | {rlp_avg:.2f} | {ratio:.2f}x | {diff:+.2f} |")
    
    return '\n'.join(lines)

def create_reads_impact_analysis(with_reads, without_reads, encoding):
    """Analyze the impact of including reads."""
    lines = [f"\n### {encoding} - Impact of Including Reads\n"]
    
    with_total = with_reads.get('total_kb', {}).get('avg', 0)
    without_total = without_reads.get('total_kb', {}).get('avg', 0)
    
    if without_total > 0:
        size_increase = with_total - without_total
        percentage_increase = (size_increase / without_total) * 100
        
        lines.append(f"- **Without reads**: {without_total:.2f} KiB")
        lines.append(f"- **With reads**: {with_total:.2f} KiB")
        lines.append(f"- **Size increase**: {size_increase:.2f} KiB ({percentage_increase:.1f}%)")
        
        # Component breakdown
        lines.append(f"\n#### Component Breakdown:")
        lines.append(f"- Storage writes: {without_reads.get('storage_changes_kb', {}).get('avg', 0):.2f} KiB")
        lines.append(f"- Storage reads: {with_reads.get('storage_reads_kb', {}).get('avg', 0):.2f} KiB")
        lines.append(f"- Balance diffs: {without_reads.get('balance_diffs_kb', {}).get('avg', 0):.2f} KiB")
        lines.append(f"- Code diffs: {without_reads.get('code_diffs_kb', {}).get('avg', 0):.2f} KiB")
        lines.append(f"- Nonce diffs: {without_reads.get('nonce_diffs_kb', {}).get('avg', 0):.2f} KiB")
    
    return '\n'.join(lines)

def generate_report(data):
    """Generate the comprehensive analysis report."""
    
    # Analyze each dataset
    analyses = {}
    for key, dataset in data.items():
        if dataset:
            analyses[key] = {
                'components': analyze_component_sizes(dataset),
                'efficiency': analyze_efficiency_stats(dataset),
                'count': len(dataset)
            }
    
    # Start building the report
    report_lines = [
        "# Comprehensive BAL Size Analysis: SSZ vs RLP, Reads vs No Reads",
        "",
        "## Executive Summary",
        "",
        "This report provides a comprehensive analysis of Block Access List (BAL) sizes across different encoding formats (SSZ vs RLP) and inclusion strategies (with vs without storage reads). The analysis is based on 50 Ethereum mainnet blocks.",
        "",
        "## Dataset Overview",
        ""
    ]
    
    # Dataset summary
    for key, analysis in analyses.items():
        encoding = "SSZ" if "ssz" in key else "RLP"
        reads = "with reads" if "with_reads" in key else "without reads"
        count = analysis['count']
        total_avg = analysis['components'].get('total_kb', {}).get('avg', 0)
        
        report_lines.append(f"- **{encoding} {reads}**: {count} blocks, average size {total_avg:.2f} KiB")
    
    # Main comparisons
    if 'ssz_without_reads' in analyses and 'rlp_without_reads' in analyses:
        report_lines.append(create_comparison_table(
            analyses['ssz_without_reads']['components'],
            analyses['rlp_without_reads']['components'],
            "SSZ vs RLP (Without Reads)"
        ))
    
    # Reads impact analysis
    if 'ssz_with_reads' in analyses and 'ssz_without_reads' in analyses:
        report_lines.append(create_reads_impact_analysis(
            analyses['ssz_with_reads']['components'],
            analyses['ssz_without_reads']['components'],
            "SSZ"
        ))
    
    # Efficiency statistics
    report_lines.extend([
        "\n## Efficiency Statistics\n",
        "Average statistics per block across all encoding formats:\n"
    ])
    
    for key, analysis in analyses.items():
        encoding = "SSZ" if "ssz" in key else "RLP"
        reads = "with reads" if "with_reads" in key else "without reads"
        efficiency = analysis['efficiency']
        
        accounts = efficiency.get('total_accounts', {}).get('avg', 0)
        writes = efficiency.get('total_storage_writes', {}).get('avg', 0)
        storage_reads = efficiency.get('total_storage_reads', {}).get('avg', 0)
        
        report_lines.extend([
            f"### {encoding} {reads}",
            f"- Average accounts per block: {accounts:.1f}",
            f"- Average storage writes per block: {writes:.1f}",
            f"- Average storage reads per block: {storage_reads:.1f}",
            ""
        ])
    
    # Key findings
    report_lines.extend([
        "\n## Key Findings\n",
        "### 1. Encoding Format Comparison",
        "When comparing SSZ vs RLP encoding without reads:",
    ])
    
    if 'ssz_without_reads' in analyses and 'rlp_without_reads' in analyses:
        ssz_total = analyses['ssz_without_reads']['components'].get('total_kb', {}).get('avg', 0)
        rlp_total = analyses['rlp_without_reads']['components'].get('total_kb', {}).get('avg', 0)
        
        if ssz_total > 0:
            ratio = rlp_total / ssz_total
            diff = rlp_total - ssz_total
            
            if ratio > 1:
                report_lines.append(f"- RLP encoding is {ratio:.2f}x larger than SSZ ({diff:+.2f} KiB difference)")
            else:
                report_lines.append(f"- SSZ encoding is {1/ratio:.2f}x larger than RLP ({-diff:+.2f} KiB difference)")
    
    report_lines.extend([
        "",
        "### 2. Storage Reads Impact",
        "Including storage reads significantly increases BAL size:",
    ])
    
    if 'ssz_with_reads' in analyses and 'ssz_without_reads' in analyses:
        with_total = analyses['ssz_with_reads']['components'].get('total_kb', {}).get('avg', 0)
        without_total = analyses['ssz_without_reads']['components'].get('total_kb', {}).get('avg', 0)
        
        if without_total > 0:
            increase = ((with_total - without_total) / without_total) * 100
            report_lines.append(f"- SSZ: {increase:.1f}% size increase when including reads")
    
    # Recommendations
    report_lines.extend([
        "",
        "## Recommendations\n",
        "Based on the analysis:\n",
        "1. **For minimal size**: Use the more compact encoding format without reads",
        "2. **For parallel execution**: Include reads for complete access information",
        "3. **Encoding choice**: Consider the size vs compatibility trade-offs between SSZ and RLP",
        "",
        "## Technical Implementation Notes\n",
        "- All measurements use Snappy compression",
        "- Simple ETH transfers are optimized using gas-based detection (21k gas limit/used)",
        "- Storage reads are extracted using both diff mode and non-diff mode tracing",
        "- Component sizes are measured independently for accurate breakdown analysis",
        "",
        "---",
        "",
        f"*Report generated from {sum(a['count'] for a in analyses.values())} total block analyses*"
    ])
    
    return '\n'.join(report_lines)

def main():
    """Main function to generate the analysis report."""
    print("Loading analysis data...")
    data = load_analysis_data()
    
    if not data:
        print("No analysis data found!")
        return
    
    print(f"Found data for: {list(data.keys())}")
    
    print("Generating comprehensive report...")
    report = generate_report(data)
    
    # Save the report
    output_path = Path(__file__).parent / "reports" / "Comprehensive_BAL_Size_Analysis_Latest.md"
    output_path.parent.mkdir(exist_ok=True)
    
    with open(output_path, 'w') as f:
        f.write(report)
    
    print(f"Report saved to: {output_path}")
    print(f"Report preview:\n{report[:1000]}...")

if __name__ == "__main__":
    main()