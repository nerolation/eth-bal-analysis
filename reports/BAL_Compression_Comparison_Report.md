# Block Access List (BAL) Comparison Report - Static Information

## Executive Summary

This report analyzes the compression impact of simplifying the BAL builder by removing special case logic for simple ETH transfers and instead including all state changes directly from the state diff.

## Methodology

### Data Collection
- Analyzed 50 Ethereum blocks (every 10th block from 22615532 to 22616032)
- Used SSZ encoding with Snappy compression

### Key Simplifications
- **Removed simple transfer detection** and special case handling
- **Simplified nonce processing** to include all nonce increments
- **Streamlined balance processing** to include all balance changes
- **Eliminated conditional logic** based on transaction type

## Results

### Compressed Size Comparison

| Variant | Total Size (KB) | Balance Component (KB) | Nonce Component (KB) | Storage Component (KB) |
|---------|-----------------|------------------------|---------------------|----------------------|
| Original (with reads) | 39.00 | 4.51 | 0.02 | 33.88 |
| Simplified (with reads) | 40.73 | 5.28 | 0.99 | 33.88 |
| Original (without reads) | 26.34 | 4.51 | 0.02 | 21.22 |
| Simplified (without reads) | 28.08 | 5.28 | 0.99 | 21.22 |

### Size Impact Analysis

The simplified approach results in:

**With storage reads enabled:**
- Total size increase: **1.74 KB (4.5%)**
- Balance component increase: 0.77 KB (17.1%)
- Nonce component increase: 0.97 KB (5644.1%)

**Without storage reads:**
- Total size increase: **1.74 KB (6.6%)**
- Balance component increase: 0.77 KB (17.1%)
- Nonce component increase: 0.97 KB (5644.1%)

### Data Volume Changes

The simplified approach includes:
- **68.1 additional balance changes** per block
- **160.6 additional nonce changes** per block
- Same number of accounts and storage operations