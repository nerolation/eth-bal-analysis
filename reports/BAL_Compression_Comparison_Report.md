# Block Access List (BAL) Compression Comparison Report

## Executive Summary

This report analyzes the impact on compressed size when including sender and recipient balance changes and sender nonces for simple ETH transfers in Block Access Lists (BALs). The analysis compares the original BAL implementation (which excludes simple transfer data) with a modified version that includes this data.

## Methodology

### Data Collection
- Analyzed 50 Ethereum blocks (every 10th block from 22615532 to 22616032)
- Used SSZ encoding with Snappy compression
- Identified simple ETH transfers using gas-based method (21k gas limit and usage)

### Variants Tested
1. **Original BAL**: Excludes balance changes and nonces for simple ETH transfer participants
2. **Modified BAL**: Includes all balance changes and nonces, including simple transfers

Both variants were tested with and without storage read tracking.

## Results

### Compressed Size Comparison

| Variant | Total Size (KB) | Balance Component (KB) | Nonce Component (KB) | Storage Component (KB) |
|---------|-----------------|------------------------|---------------------|----------------------|
| Original (with reads) | 39.00 | 4.51 | 0.02 | 33.88 |
| Modified (with reads) | 40.05 | 5.28 | 0.30 | 33.88 |
| Original (without reads) | 26.34 | 4.51 | 0.02 | 21.22 |
| Modified (without reads) | 27.39 | 5.28 | 0.30 | 21.22 |

### Size Impact Analysis

Including simple ETH transfer data results in:

**With storage reads enabled:**
- Total size increase: **1.05 KB (2.7%)**
- Balance component increase: 0.77 KB (17.1%)
- Nonce component increase: 0.29 KB (1661.2%)

**Without storage reads:**
- Total size increase: **1.05 KB (4.0%)**
- Balance component increase: 0.77 KB (17.1%)
- Nonce component increase: 0.29 KB (1661.2%)

### Data Volume Changes

The modified BAL includes approximately:
- **68.1 additional balance changes** per block
- **71.0 additional nonce changes** per block
- No change in storage or code components

## Technical Details

### Simple Transfer Identification
Simple ETH transfers were identified using the following criteria:
- Gas limit: exactly 21,000
- Gas used: exactly 21,000
- No input data (empty or "0x")

### Compression Efficiency
The high compression efficiency is maintained despite including additional data:
- Balance changes compress well due to similar value patterns
- Nonce changes are highly compressible (sequential increments)
- SSZ encoding provides efficient field grouping

## Conclusions

**Minimal Size Impact**: Including simple transfer data adds only 2.7-4.0% to the compressed BAL size, demonstrating excellent compression efficiency.

**Component-Specific Impact**: 
   - Balance component increases by ~17% due to additional sender/recipient entries
   - Nonce component shows large percentage increase but small absolute size
   - Storage component remains unchanged