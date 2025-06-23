# RLP vs SSZ Block Access List (BAL) Encoding Comparison Report

**Generated:** December 2024  
**Ethereum Blocks Analyzed:** 50 blocks (22615532 - 22616022)  
**Analysis Type:** Implementations without storage reads  

## Executive Summary

This report presents a comprehensive comparison of RLP and SSZ encoding formats for Ethereum Block Access Lists (BALs) as proposed in EIP-7928. The analysis demonstrates that **RLP encoding provides superior space efficiency**, offering approximately **3.2% smaller compressed sizes** compared to SSZ encoding.

## Key Findings

### 🎯 Overall Performance
- **RLP Average Size**: 26.67 KiB per block
- **SSZ Average Size**: 27.49 KiB per block  
- **RLP Advantage**: 3.2% smaller (0.82 KiB savings per block)
- **Consistency**: RLP was smaller in 100% of tested blocks (50/50)

### 📊 Component-wise Analysis

| Component | RLP (KiB) | SSZ (KiB) | Difference | % of Total |
|-----------|-----------|-----------|------------|------------|
| **Storage Access** | 20.99 ± 8.77 | 21.66 ± 9.01 | **SSZ +3.2%** | ~78.7% |
| **Balance Diffs** | 5.03 ± 1.75 | 5.17 ± 1.77 | **SSZ +2.8%** | ~18.8% |
| **Code Diffs** | 0.59 ± 2.34 | 0.60 ± 2.34 | **SSZ +126.6%** | ~2.2% |
| **Nonce Diffs** | 0.054 ± 0.043 | 0.069 ± 0.056 | **SSZ +25.8%** | ~0.2% |

## Methodology

### Test Environment
- **Builders Used**: Non-optimized versions
  - `src/bal_builder_rlp.py` (RLP implementation)
  - `src/bal_builder.py` (SSZ implementation)
- **Block Range**: Recent Ethereum mainnet blocks (every 10th block over 500 block span)
- **Configuration**: `--no-reads` flag (storage reads excluded)
- **Compression**: Snappy compression applied to all measurements

### Data Generation Process
1. **Block Processing**: Each builder processed identical sets of 50 blocks
2. **Component Extraction**: Separate analysis of storage access, balance diffs, code diffs, and nonce diffs
3. **Encoding**: RLP vs SSZ serialization with proper sorting and EIP-7928 compliance
4. **Output**: Generated 100 raw BAL files (50 RLP + 50 SSZ) in `bal_raw/` directory

## Detailed Analysis

### Storage Access (Primary Component - 78.7% of total size)
Storage access data represents the largest portion of BAL size. RLP shows a **3.2% advantage** over SSZ:
- **RLP**: 20.99 ± 8.77 KiB
- **SSZ**: 21.66 ± 9.01 KiB
- **Impact**: This component drives the overall size difference

### Balance Diffs (Secondary Component - 18.8% of total size)  
Balance change tracking shows consistent RLP efficiency:
- **RLP**: 5.03 ± 1.75 KiB
- **SSZ**: 5.17 ± 1.77 KiB
- **Advantage**: RLP is 2.8% more compact

### Code & Nonce Diffs (Minor Components - 2.4% of total size)
While showing larger percentage differences, these components have minimal absolute impact:
- **Code Diffs**: Small absolute sizes make percentage differences less meaningful
- **Nonce Diffs**: Represent <0.3% of total BAL size

## Block-by-Block Consistency

The analysis reveals remarkable consistency in RLP's advantage:
- **Blocks where RLP is smaller**: 50/50 (100%)
- **Blocks where SSZ is smaller**: 0/50 (0%)
- **Largest RLP advantage**: 1.40 KiB
- **Standard deviation**: ±0.29 KiB (consistent difference)
