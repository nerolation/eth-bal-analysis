# Block Access List (BAL) Compression Analysis Report

## Executive Summary

Compression analysis of BAL builder with comprehensive nonce detection for EOA increments, new contracts, and EIP-7702 delegations.

## Methodology

- Comprehensive nonce detection for all statically inferrable changes
- Simplified logic removing complex filtering and edge cases  
- Direct inclusion of all state changes from state diff
- Dataset: 50 Ethereum blocks (22615532 to 22616022) using SSZ with Snappy compression

## Results

### Compression Impact Analysis

| Metric | Original (with reads) | Current (with reads) | Change |
|--------|----------------------|----------------------|---------|
| **Total Size** | 39.00 KB | 40.74 KB | **+4.5%** |
| Balance Component | 4.51 KB | 5.28 KB | +17.1% |
| Nonce Component | 0.02 KB | 0.99 KB | +5664.4% |
| Storage Component | 33.88 KB | 33.88 KB | 0.0% |
| Code Component | 0.59 KB | 0.59 KB | 0.0% |

| Metric | Original (without reads) | Current (without reads) | Change |
|--------|--------------------------|--------------------------|---------|
| **Total Size** | 26.34 KB | 28.08 KB | **+6.6%** |
| Balance Component | 4.51 KB | 5.28 KB | +17.1% |
| Nonce Component | 0.02 KB | 0.99 KB | +5664.4% |
| Storage Component | 21.22 KB | 21.22 KB | 0.0% |
| Code Component | 0.59 KB | 0.59 KB | 0.0% |

### Data Volume Changes

| Change Type | Original | Current | Additional |
|-------------|----------|----------|------------|
| **Balance Changes** | 413.1/block | 481.2/block | **+68.1** (+16.5%) |
| **Nonce Changes** | 1.8/block | 163.3/block | **+161.5** (+8972%) |
| Storage Operations | 532.2/block | 532.2/block | 0 |

## Analysis

**Key Changes:**
- **Nonce**: 0.02 KB → 0.99 KB (+5664%) - captures all sender increments, new contracts, and EIP-7702 delegations
- **Balance**: 4.51 KB → 5.28 KB (+17.1%) - includes all balance changes without filtering  
- **Storage**: Unchanged
- **Overall**: +1.74 KB (+4.5% with reads, +6.6% without reads)

## Component Breakdown

BAL with reads (40.74 KB total):
- **Storage**: 33.88 KB (83.2%)
- **Balance**: 5.28 KB (13.0%)  
- **Nonce**: 0.99 KB (2.4%)
- **Code**: 0.59 KB (1.5%)

## Benefits vs. Costs

**Benefits:** Complete static inference, simplified implementation, EIP-7702 ready, no missed changes

**Costs:** +4.5% size increase, 50x nonce component growth

## Recommendation

The 4.5% size increase is justified by simplified code.

**Optimizations:** Nonce delta encoding, balance delta optimization, or configurable filtering.