# EIP-7928 Component Size & Compression Analysis

## Dataset
- **Blocks Analyzed**: 50 blocks (23,759,939 to 23,759,988)
- **Encoding**: RLP format
- **Compression**: Snappy algorithm

## Per-Block Component Statistics (KiB)

| Component | Avg Raw | Median Raw | Avg Compressed | Median Compressed | Avg Ratio | Median Ratio |
|-----------|---------|------------|----------------|-------------------|-----------|--------------|
| Storage Writes | 58.0 | 52.5 | 28.8 | 26.1 | 1.99x | 1.76x |
| Storage Reads | 29.6 | 26.5 | 18.7 | 17.0 | 1.59x | 1.59x |
| Balance Changes | 9.6 | 9.5 | 9.6 | 9.4 | 1.00x | 1.00x |
| Nonce Changes | 4.9 | 4.4 | 4.8 | 4.3 | 1.00x | 1.00x |
| Code Changes | 2.9 | 0.0 | 1.2 | 0.0 | 2.12x | 2.54x |
| **Full BAL** | **102.8** | **93.7** | **58.7** | **56.6** | **1.74x** | **1.61x** |

## Component Size Distribution (KiB)

| Component | Min Raw | Max Raw | Std Dev Raw | Min Compressed | Max Compressed | Std Dev Compressed |
|-----------|---------|---------|-------------|----------------|----------------|-------------------|
| Storage Writes | 8.2 | 117.4 | 26.0 | 5.1 | 48.6 | 11.2 |
| Storage Reads | 4.7 | 74.8 | 13.7 | 2.7 | 55.1 | 8.7 |
| Balance Changes | 3.5 | 16.3 | 3.0 | 3.5 | 16.3 | 3.0 |
| Nonce Changes | 1.4 | 9.5 | 2.2 | 1.4 | 9.4 | 2.2 |
| Code Changes | 0.0 | 31.0 | 5.4 | 0.0 | 17.5 | 2.5 |
| **Full BAL** | **17.2** | **212.5** | **43.9** | **11.3** | **119.7** | **22.5** |

## Compression Ratio Distribution

| Component | Min Ratio | Max Ratio | Std Dev | 25th Percentile | 75th Percentile |
|-----------|-----------|-----------|---------|-----------------|-----------------|
| Storage Writes | 1.63x | 3.05x | 0.35x | 1.72x | 2.23x |
| Storage Reads | 1.17x | 2.03x | 0.15x | 1.52x | 1.66x |
| Balance Changes | 1.00x | 1.02x | 0.00x | 1.00x | 1.00x |
| Nonce Changes | 1.00x | 1.06x | 0.01x | 1.00x | 1.00x |
| Code Changes | 0.96x | 3.02x | 0.68x | 1.85x | 2.99x |
| **Full BAL** | **1.42x** | **2.66x** | **0.27x** | **1.53x** | **1.86x** |

## Per-Block Combined Metrics (KiB)

| Metric | Average | Median | Min | Max | Std Dev |
|--------|---------|--------|-----|-----|---------|
| **Full BAL Raw** | 102.8 | 93.7 | 17.2 | 212.5 | 43.9 |
| **Full BAL Compressed** | 58.7 | 56.6 | 11.3 | 119.7 | 22.5 |
| **Storage Total Raw** | 87.7 | 86.0 | 12.7 | 187.9 | 33.7 |
| **Storage Total Compressed** | 47.5 | 44.7 | 7.6 | 98.6 | 17.7 |
| **Balance+Nonce Raw** | 14.5 | 14.5 | 5.1 | 24.0 | 4.3 |
| **Balance+Nonce Compressed** | 14.4 | 14.4 | 5.1 | 23.9 | 4.3 |

## Component Percentage of Full BAL

| Component | % of Raw Size | % of Compressed Size |
|-----------|---------------|---------------------|
| Storage Writes | 56.5% | 49.0% |
| Storage Reads | 28.8% | 31.9% |
| Balance Changes | 9.3% | 16.3% |
| Nonce Changes | 4.7% | 8.2% |
| Code Changes | 2.9% | 2.0% |

## Block Activity Metrics (per block)

| Metric | Average | Median | Min | Max |
|--------|---------|--------|-----|-----|
| Total Accounts | 501 | 519 | 137 | 810 |
| Storage Writes Count | 836 | 783 | 115 | 1,695 |
| Storage Reads Count | 808 | 739 | 121 | 2,170 |
| Balance Changes Count | 411 | 407 | 173 | 715 |
| Nonce Changes Count | 170 | 156 | 56 | 290 |

## Code Presence Statistics

| Metric | Value |
|--------|-------|
| Blocks with Code Changes | 19/50 (38%) |
| Average Code Size (when present) | 7.8 KiB raw |
| Average Code Size (when present) | 3.1 KiB compressed |
| Average Code Compression (when present) | 2.54x |
