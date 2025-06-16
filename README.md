# EIP-7928 Block Access Lists Implementation

Implementation of [EIP-7928 Block-Level Access Lists (BALs)](https://eips.ethereum.org/EIPS/eip-7928) for Ethereum blockchain analysis.

## Overview

Block Access Lists provide a structured way to represent storage accesses, balance changes, code deployments, and nonce modifications within an Ethereum block.

## Features

- Full EIP-7928 compliance
- Comprehensive testing framework
- SSZ serialization support  

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

```python
from src.bal_builder import *
from src.BALs import *

# Generate BAL for a block
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