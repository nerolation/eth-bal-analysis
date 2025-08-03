# RLP vs SSZ Block Access List (BAL) Encoding Comparison Report

**Generated:** August 2025  
**Ethereum Blocks Analyzed:** 50 blocks (22886864 - 22886913)  
**Analysis Type:** Full comparison with and without storage reads

## Executive Summary

This report presents a comprehensive comparison of RLP and SSZ encoding formats for Ethereum Block Access Lists (BALs) as proposed in EIP-7928. Analysis of 50 recent Ethereum blocks confirms that **RLP encoding consistently provides superior space efficiency**, with SSZ showing a moderate but consistent overhead.

## Key Findings

### Overall Performance

**Without Storage Reads:**
- **RLP Average Size**: 40.4 KB per block (compressed)
- **SSZ Average Size**: 43.8 KB per block (compressed)
- **SSZ Overhead**: 8.5% larger than RLP (3.4 KB difference)

**With Storage Reads:**
- **RLP Average Size**: 61.1 KB per block (compressed)
- **SSZ Average Size**: 65.1 KB per block (compressed)
- **SSZ Overhead**: 6.5% larger than RLP (4.0 KB difference)

### Consistency Analysis

- **Blocks where RLP is smaller (without reads)**: 50/50 (100%)
- **Blocks where RLP is smaller (with reads)**: 50/50 (100%)
- **Consistency**: RLP is smaller in ALL tested blocks

### Size Distribution

**Without Storage Reads:**
- **Min size**: RLP 13.7 KB, SSZ 14.7 KB
- **Max size**: RLP 67.8 KB, SSZ 72.6 KB
- **Range**: Both formats show similar variability

**With Storage Reads:**
- **Min size**: RLP 20.1 KB, SSZ 21.4 KB
- **Max size**: RLP 121.1 KB, SSZ 126.2 KB
- **Range**: Sizes vary significantly based on block activity

## Impact of Storage Reads

Including storage reads has a significant impact on BAL sizes:
- **SSZ**: Size increases by +48.4% (43.8 KB → 65.1 KB)
- **RLP**: Size increases by +51.1% (40.4 KB → 61.1 KB)

Storage reads represent approximately half of the total BAL size when included, highlighting their substantial impact on data volume.

## Block-by-Block Analysis

### Size Distribution Patterns

The analysis reveals consistent patterns across all blocks:

1. **Small blocks** (< 30 KB with reads): ~10% of blocks
   - Minimal contract interactions
   - Example: Block 22886889 (RLP: 20.1 KB, SSZ: 21.4 KB)

2. **Medium blocks** (30-70 KB with reads): ~70% of blocks
   - Typical DeFi and token transfer activity
   - Average overhead remains consistent

3. **Large blocks** (> 70 KB with reads): ~20% of blocks
   - Complex DeFi operations, DEX trades
   - Example: Block 22886907 (RLP: 121.1 KB, SSZ: 126.2 KB)

### Overhead Consistency

The SSZ overhead percentage remains remarkably stable across different block sizes:
- Small blocks: 6-7% overhead
- Medium blocks: 6-8% overhead  
- Large blocks: 4-6% overhead

This consistency suggests the overhead is structural rather than content-dependent.

## Technical Analysis

### Why RLP is More Efficient

1. **Variable-length encoding**: RLP uses minimal bytes for small integers
2. **No type information**: RLP doesn't encode type metadata
3. **Compact list representation**: Efficient for homogeneous data
4. **Better compression synergy**: RLP's simpler structure compresses well

### SSZ Overhead Sources

1. **Fixed-size fields**: SSZ uses fixed sizes even for small values
2. **Type safety overhead**: Additional bytes for structure validation
3. **Merkleization padding**: Alignment requirements for proof generation
4. **Length prefixes**: More verbose length encoding

## Storage Access Patterns

Analysis of the 50 blocks reveals:

**Average per block:**
- Storage writes: ~850 slots
- Storage reads: ~1,300 slots (when included)
- Balance changes: ~180 addresses
- Nonce changes: ~50 accounts
- Code deployments: ~2 contracts

**Read/Write Ratio**: Approximately 1.5:1, indicating significant read activity

## Recommendations

### For Protocol Design

1. **If space efficiency is paramount**: RLP offers ~7% space savings
2. **If future-proofing matters**: SSZ's structure enables merkleization and typed data
3. **For archival storage**: The 7% overhead translates to significant costs at scale

### For Implementation

1. **Gas calculation use case**: Use `--no-reads` flag to reduce size by ~50%
2. **Full state tracking**: Include reads for complete access patterns
3. **Compression**: Both formats benefit significantly from Snappy compression

### Scalability Considerations

At current growth rates and 50 KB average (without reads):
- **Daily storage**: ~7.2 GB (144,000 blocks/day)
- **Annual storage**: ~2.6 TB
- **7% difference**: ~182 GB/year in storage costs

## Conclusions

1. **RLP maintains consistent advantage**: 6.5-8.5% more efficient across all scenarios
2. **Both formats scale linearly**: No exponential growth patterns observed
3. **Storage reads dominate size**: ~50% of total BAL size when included
4. **Compression is essential**: Both formats compress to ~60-70% of raw size

The choice between RLP and SSZ should consider not just space efficiency but also:
- Future merkleization requirements
- Type safety needs
- Consensus layer integration
- Long-term protocol evolution

While RLP offers superior compression, SSZ's structured approach may provide benefits for consensus integration and proof generation that could outweigh the modest space overhead.

## Appendix: Methodology

- **Blocks analyzed**: 50 consecutive recent blocks
- **Compression**: Snappy compression (same as Ethereum clients)
- **Parallel processing**: 4 workers for efficient data collection
- **Validation**: All blocks successfully processed with both formats
- **Components included**: All EIP-7928 specified fields including system changes