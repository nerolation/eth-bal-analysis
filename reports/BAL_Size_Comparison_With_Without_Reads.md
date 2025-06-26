# BAL Size Comparison: With vs Without Reads

## Executive Summary

This report analyzes the size impact of including storage reads and touched-but-unchanged accounts in Block Access Lists (BALs) as specified in EIP-7928. The analysis covers 50 blocks from the Ethereum mainnet.

## Key Findings

### 1. Size Impact

- **Without reads**: Average BAL size is **27.34 KiB** (compressed SSZ)
- **With reads**: Average BAL size is **39.69 KiB** (compressed SSZ)
- **Size increase**: **12.35 KiB (45.2%)**

### 2. Component Breakdown

#### Without Reads (27.34 KiB total):
- Storage writes: 21.22 KiB (77.6%)
- Balance diffs: 5.52 KiB (20.2%)
- Code diffs: 0.58 KiB (2.1%)
- Nonce diffs: 0.02 KiB (0.1%)

#### With Reads (39.69 KiB total):
- Storage (total): 33.57 KiB (84.6%)
  - Writes: 21.22 KiB (53.5%)
  - Reads: 12.35 KiB (31.1%)
- Balance diffs: 5.52 KiB (13.9%)
- Code diffs: 0.58 KiB (1.5%)
- Nonce diffs: 0.02 KiB (0.0%)

### 3. Account Statistics

- Average accounts per block (without reads): **340.3**
- Average accounts per block (with reads): **388.2**
- Additional accounts when including reads: **48.0** per block
- Touched-but-unchanged accounts: **132.3** per block (34.1% of total)

### 4. Storage Access Patterns

- Average storage writes per block: **532.2**
- Average storage reads per block: **763.6** (when included)
- Read-to-write ratio: **1.43:1**

## Comparison with Previous Analysis

Our earlier analysis (from the summary) indicated:
- Touched-but-unchanged addresses comprise ~24.8% of accessed addresses
- Including reads would add ~48 accounts per block
- Size increase would be approximately 1.8%

Current findings show:
- Touched-but-unchanged accounts are 34.1% of total accounts
- Including reads adds exactly 48.0 accounts per block (matches prediction)
- Size increase is 45.2% (much higher than the 1.8% estimate)

The discrepancy in size increase is due to:
1. Storage reads add significant data (12.35 KiB average)
2. The previous estimate likely only considered account addresses, not the storage read slots

## Technical Implications

### For Parallel Execution
Including reads provides complete information for parallel disk I/O:
- All 388.2 accounts can be pre-loaded
- All 763.6 storage slots can be pre-fetched
- No sequential dependency for data loading

### For State Reconstruction
The without-reads variant still enables state reconstruction:
- Contains all state changes (writes)
- Missing read information doesn't affect final state
- Smaller size benefits network propagation

## Recommendations

1. **For maximum parallelization**: Use BALs with reads (39.69 KiB average)
2. **For minimal size**: Use BALs without reads (27.34 KiB average)
3. **Consider a hybrid approach**: 
   - Include touched accounts without their read slots
   - This would add the 48 accounts but not the 12.35 KiB of read data

## Conclusion

Including storage reads in BALs adds significant size (45.2% increase) but provides complete access information for optimal parallel execution. The trade-off between size and parallelization benefits should be carefully considered based on network constraints and performance requirements.

The current implementation correctly handles both variants as specified in EIP-7928, with the conditional inclusion of touched-but-unchanged accounts based on the `--no-reads` flag.