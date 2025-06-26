# SSZ BAL Encoding: With vs Without Storage Reads

**Analysis Date:** December 2024  
**Blocks Analyzed:** 50 Ethereum mainnet blocks  
**Block Range:** 22615532-22616022 (every 10th block)

## Key Findings

### Size Impact
- **Without reads:** 27.34 KiB average
- **With reads:** 39.69 KiB average  
- **Increase:** +12.35 KiB (+45.2%)

### Component Breakdown

| Component | Without Reads | With Reads | Difference |
|-----------|--------------|------------|------------|
| Storage Writes | 21.22 KiB (77.6%) | 21.22 KiB (53.5%) | 0.00 KiB |
| Storage Reads | 0.00 KiB (0.0%) | 12.35 KiB (31.1%) | +12.35 KiB |
| Balance Diffs | 5.52 KiB (20.2%) | 5.52 KiB (13.9%) | 0.00 KiB |
| Code Diffs | 0.58 KiB (2.1%) | 0.58 KiB (1.5%) | 0.00 KiB |
| Nonce Diffs | 0.02 KiB (0.1%) | 0.02 KiB (0.0%) | 0.00 KiB |

### Account Statistics
- Accounts (without reads): 340.3 average
- Accounts (with reads): 388.2 average (+48.0)
- Touched-only accounts: 132.3 (34.1% of total)
- Storage writes: 532.2 average
- Storage reads: 763.6 average (when included)

## Implementation

### Command Line Usage
```bash
# Write-only (default)
python src/bal_builder.py --no-reads

# Include reads
python src/bal_builder.py
```

### Technical Details
- **Read inclusion**: Adds storage slots accessed via SLOAD but not written
- **Touched accounts**: Addresses accessed via BALANCE/EXTCODEHASH/EXTCODESIZE opcodes
- **Conditional logic**: Only includes touched accounts when reads are enabled (per EIP-7928)

## Recommendations

### Use Cases
1. **Maximum parallelization**: Use with reads (39.69 KiB) - complete access information
2. **Minimal size**: Use without reads (27.34 KiB) - state changes only
3. **Network propagation**: Consider 45.2% bandwidth increase with reads

### Trade-offs
- **With reads**: +45.2% size for complete parallel execution capability
- **Without reads**: Smaller size, still enables state reconstruction

## Conclusion

Including storage reads adds significant overhead (45.2%) but provides complete access information for optimal parallel execution. The implementation correctly follows EIP-7928 specifications with conditional read inclusion based on the `--no-reads` flag.