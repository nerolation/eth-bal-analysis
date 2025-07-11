# RLP vs SSZ Block Access List (BAL) Encoding Comparison Report

**Generated:** July 2025
**Ethereum Blocks Analyzed:** 50 blocks (22886414 - 22886904)
**Analysis Type:** Comprehensive comparison with and without storage reads

## Executive Summary

This report presents a comprehensive comparison of RLP and SSZ encoding formats for Ethereum Block Access Lists (BALs) as proposed in EIP-7928. The analysis demonstrates that **RLP encoding provides superior space efficiency**, with SSZ showing a moderate overhead.

## Key Findings

### 🎯 Overall Performance

**Without Storage Reads:**
- **RLP Average Size**: 45.83 KB per block (compressed)
- **SSZ Average Size**: 49.09 KB per block (compressed)
- **SSZ Overhead**: 7.1% larger than RLP (3.26 KB)

**With Storage Reads:**
- **RLP Average Size**: 66.35 KB per block (compressed)
- **SSZ Average Size**: 69.69 KB per block (compressed)
- **SSZ Overhead**: 5.0% larger than RLP (3.34 KB)

### 📊 Consistency Analysis

- **Blocks where RLP is smaller (without reads)**: 50/50 (100%)
- **Blocks where RLP is smaller (with reads)**: 41/41 (100%)

### 📈 Size Distribution

**Without Storage Reads:**
- **Min size**: RLP 12.5 KB, SSZ 13.7 KB
- **Max size**: RLP 75.8 KB, SSZ 79.4 KB
- **Std deviation**: RLP ±12.4 KB, SSZ ±13.1 KB

**With Storage Reads:**
- **Min size**: RLP 17.2 KB, SSZ 18.5 KB
- **Max size**: RLP 99.0 KB, SSZ 104.6 KB
- **Std deviation**: RLP ±17.1 KB, SSZ ±17.7 KB

## Compression Efficiency

Average compression ratios (compressed/raw):
- **SSZ**: 79.3 KB → 49.1 KB (61.9%)
- **RLP**: 68.7 KB → 45.8 KB (66.7%)

## Impact of Storage Reads

Including storage reads increases BAL size by:
- **SSZ**: +42.0% (49.1 KB → 69.7 KB)
- **RLP**: +44.8% (45.8 KB → 66.4 KB)

## Block Activity Analysis

### Top 5 Largest Blocks (without reads):

| Block | SSZ Size | RLP Size | Difference |
|-------|----------|----------|------------|
| 22886664 | 79.4 KB | 75.8 KB | SSZ +3.6 KB (+4.8%) |
| 22886804 | 73.6 KB | 69.3 KB | SSZ +4.3 KB (+6.2%) |
| 22886834 | 68.5 KB | 64.3 KB | SSZ +4.2 KB (+6.6%) |
| 22886614 | 67.9 KB | 63.7 KB | SSZ +4.3 KB (+6.7%) |
| 22886754 | 66.4 KB | 62.4 KB | SSZ +4.0 KB (+6.4%) |

### Top 5 Smallest Blocks (without reads):

| Block | SSZ Size | RLP Size | Difference |
|-------|----------|----------|------------|
| 22886474 | 13.7 KB | 12.5 KB | SSZ +1.2 KB (+9.5%) |
| 22886554 | 18.1 KB | 16.5 KB | SSZ +1.6 KB (+9.5%) |
| 22886654 | 24.4 KB | 22.5 KB | SSZ +1.9 KB (+8.5%) |
| 22886894 | 28.8 KB | 26.7 KB | SSZ +2.0 KB (+7.7%) |
| 22886604 | 34.8 KB | 32.4 KB | SSZ +2.4 KB (+7.5%) |

## Methodology

### Test Environment
- **Builders Used**: Current implementations
  - `src/bal_builder_rlp.py` (RLP implementation)
  - `src/bal_builder.py` (SSZ implementation)
- **Block Range**: Recent Ethereum mainnet blocks (every 10th block)
- **Configurations**: Both with and without storage reads
- **Compression**: Snappy compression applied to all measurements

## Conclusions

1. **RLP is consistently more space-efficient**: Across all tested blocks, RLP encoding produces smaller compressed BALs
2. **SSZ overhead is moderate**: SSZ files are 7.1% larger without reads
, 5.0% larger with reads
3. **Both formats compress well**: Achieving ~60% compression ratios with Snappy
4. **Storage reads significantly impact size**: Adding reads increases BAL size by ~40-45% for both formats
5. **Consistency is high**: RLP is smaller in 100% of tested blocks

## Recommendations

1. **For pure space efficiency**: RLP encoding offers the best compression
2. **For consensus and merkleization**: SSZ provides better structure and type safety despite the ~7% size overhead
3. **For gas calculation only**: Use the --no-reads variant to reduce size by ~40%
4. **For archival storage**: The consistent ~7% overhead of SSZ may be acceptable given its other benefits
