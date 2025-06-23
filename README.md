# EIP-7928 Block Access Lists Implementation

Implementation of [EIP-7928 Block-Level Access Lists (BALs)](https://eips.ethereum.org/EIPS/eip-7928) for Ethereum blockchain analysis with comprehensive SSZ vs RLP encoding comparison.

## Overview

Block Access Lists provide a structured way to represent storage accesses, balance changes, code deployments, and nonce modifications within an Ethereum block. This implementation includes both SSZ and RLP encodings for detailed size analysis and performance comparison.

## Features

- **Full EIP-7928 compliance** with both standard and optimized variants
- **Dual encoding support**: SSZ (Ethereum 2.0 standard) and RLP (Ethereum 1.0 standard)
- **Comprehensive size analysis** with raw and snappy-compressed comparisons  
- **Extensive testing framework** with unit, integration, and compliance tests
- **Real block validation** against actual Ethereum mainnet blocks
- **Performance optimization** with separate read/write storage tracking  

## Setup

```bash
git clone https://github.com/your-username/eth-bal-analysis.git
cd eth-bal-analysis
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "YOUR_RPC_URL" > rpc.txt
```

## Usage

### Quick Size Comparison

```bash
# Run a quick SSZ vs RLP comparison on a single block
python examples/quick_comparison.py --block 22616000

# Run comprehensive analysis across multiple blocks
python analysis/encoding_comparison.py --num-blocks 5
```

### SSZ Implementation (Standard)

```python
from src.bal_builder import *
from src.BALs import *

# Generate SSZ BAL for a block
trace_result = fetch_block_trace(18000000, rpc_url)
storage_diff, account_access_list = get_storage_diff_from_block(trace_result)
balance_diff, acc_bal_diffs = get_balance_diff_from_block(trace_result)
code_diff, acc_code_diffs = get_code_diff_from_block(trace_result)
nonce_diff, account_nonce_list = build_contract_nonce_diffs_from_state(trace_result)

# Build and sort BAL
block_obj = BlockAccessList(
    account_accesses=account_access_list,
    balance_diffs=acc_bal_diffs,
    code_diffs=acc_code_diffs,
    nonce_diffs=account_nonce_list,
)
sorted_bal = sort_block_access_list(block_obj)
encoded_bal = ssz.encode(sorted_bal, sedes=BlockAccessList)
```

### RLP Implementation (Standard)

```python
from src.bal_builder_rlp import *
from src.BALs_rlp import *

# Generate RLP BAL for a block (identical data, different encoding)
trace_result = fetch_block_trace(18000000, rpc_url)
storage_diff, account_access_list = get_storage_diff_from_block(trace_result)
balance_diff, acc_bal_diffs = get_balance_diff_from_block(trace_result)
code_diff, acc_code_diffs = get_code_diff_from_block(trace_result)
nonce_diff, account_nonce_list = build_contract_nonce_diffs_from_state(trace_result)

# Build and sort BAL
block_obj = BlockAccessListRLP(
    account_accesses=account_access_list,
    balance_diffs=acc_bal_diffs,
    code_diffs=acc_code_diffs,
    nonce_diffs=account_nonce_list,
)
sorted_bal = sort_block_access_list(block_obj)
encoded_bal = rlp.encode(sorted_bal)
```

### Size Analysis

```python
from src.helpers import compare_ssz_rlp_sizes, analyze_component_sizes

# Compare encoding sizes
comparison = compare_ssz_rlp_sizes(ssz_encoded, rlp_encoded)
print(f"Raw size ratio (RLP/SSZ): {comparison['comparison']['raw_size_ratio']:.3f}")
print(f"Compressed size ratio: {comparison['comparison']['compressed_size_ratio']:.3f}")

# Component-level analysis
ssz_components = {'storage': ssz_storage_diff, 'balance': ssz_balance_diff}
rlp_components = {'storage': rlp_storage_diff, 'balance': rlp_balance_diff}
analysis = analyze_component_sizes(ssz_components, rlp_components, ['storage', 'balance'])
```

## Testing

```bash
cd tests
python test_recent_blocks.py
python comprehensive_eip7928_tests.py
python edge_case_tests.py
```

## Components

- `src/BALs.py` - EIP-7928 data structures with SSZ serialization
- `src/bal_builder.py` - Main logic for building Block Access Lists  
- `src/helpers.py` - RPC and utility functions
- `tests/` - Comprehensive test suite

## License

MIT License - see [LICENSE](LICENSE) file.