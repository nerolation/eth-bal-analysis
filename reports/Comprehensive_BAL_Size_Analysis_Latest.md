# Comprehensive BAL Size Analysis: SSZ vs RLP, Reads vs No Reads

## Executive Summary

This report provides a comprehensive analysis of Block Access List (BAL) sizes across different encoding formats (SSZ vs RLP) and inclusion strategies (with vs without storage reads). The analysis is based on 50 Ethereum mainnet blocks.

## Dataset Overview

- **SSZ with reads**: 50 blocks, average size 39.00 KiB
- **SSZ without reads**: 50 blocks, average size 26.34 KiB
- **RLP without reads**: 50 blocks, average size 25.19 KiB

### SSZ vs RLP (Without Reads)

| Component | SSZ Avg (KiB) | RLP Avg (KiB) | RLP/SSZ Ratio | Difference (KiB) |
|-----------|---------------|---------------|---------------|------------------|
| Storage Changes | 21.22 | 19.77 | 0.93x | -1.45 |
| Storage Reads | 0.00 | 0.00 | 0.00x | +0.00 |
| Storage Total | 21.22 | 19.77 | 0.93x | -1.45 |
| Balance Diffs | 4.51 | 4.83 | 1.07x | +0.32 |
| Nonce Diffs | 0.02 | 0.01 | 0.61x | -0.01 |
| Code Diffs | 0.59 | 0.58 | 0.98x | -0.01 |
| Total | 26.34 | 25.19 | 0.96x | -1.15 |

### SSZ - Impact of Including Reads

- **Without reads**: 26.34 KiB
- **With reads**: 39.00 KiB
- **Size increase**: 12.66 KiB (48.1%)

#### Component Breakdown:
- Storage writes: 21.22 KiB
- Storage reads: 12.66 KiB
- Balance diffs: 4.51 KiB
- Code diffs: 0.59 KiB
- Nonce diffs: 0.02 KiB

## Efficiency Statistics

Average statistics per block across all encoding formats:

### SSZ with reads
- Average accounts per block: 389.4
- Average storage writes per block: 532.2
- Average storage reads per block: 788.7

### SSZ without reads
- Average accounts per block: 280.0
- Average storage writes per block: 532.2
- Average storage reads per block: 0.0

### RLP without reads
- Average accounts per block: 280.0
- Average storage writes per block: 532.2
- Average storage reads per block: 0.0


## Key Findings

### 1. Encoding Format Comparison
When comparing SSZ vs RLP encoding without reads:
- SSZ encoding is 1.05x larger than RLP (+1.15 KiB difference)

### 2. Storage Reads Impact
Including storage reads significantly increases BAL size:
- SSZ: 48.1% size increase when including reads

## Recommendations

Based on the analysis:

1. **For minimal size**: Use the more compact encoding format without reads
2. **For parallel execution**: Include reads for complete access information
3. **Encoding choice**: Consider the size vs compatibility trade-offs between SSZ and RLP

## Technical Implementation Notes

- All measurements use Snappy compression
- Simple ETH transfers are optimized using gas-based detection (21k gas limit/used)
- Storage reads are extracted using both diff mode and non-diff mode tracing
- Component sizes are measured independently for accurate breakdown analysis

---

*Report generated from 150 total block analyses*