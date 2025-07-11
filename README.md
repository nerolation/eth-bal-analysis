# EIP-7928 Block Access Lists Implementation

Implementation of [EIP-7928 Block-Level Access Lists (BALs)](https://eips.ethereum.org/EIPS/eip-7928) for Ethereum blockchain analysis with comprehensive SSZ vs RLP encoding comparison.

## Overview

Block Access Lists provide a structured way to represent storage accesses, balance changes, code deployments, and nonce modifications within an Ethereum block. This implementation includes both SSZ and RLP encodings for detailed size analysis and performance comparison.

## Features

- **Full EIP-7928 compliance** with both standard and optimized variants
- **Dual encoding support**: SSZ (Ethereum 2.0 standard) and RLP (Ethereum 1.0 standard)
- **Comprehensive size analysis** with raw and snappy-compressed comparisons  
- **Optimized simple ETH transfer detection** using gas-based method with batch RPC calls
- **Real block validation** against actual Ethereum mainnet blocks
- **Performance optimization** with separate read/write storage tracking
- **Builder pattern architecture** for flexible BAL construction  

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

### Generate BALs with Current Implementation

```bash
# Generate SSZ BALs without storage reads
python src/bal_builder.py --no-reads

# Generate SSZ BALs with storage reads (default)
python src/bal_builder.py

# Generate RLP BALs without storage reads
python src/bal_builder_rlp.py --no-reads

# Generate RLP BALs with storage reads (default)
python src/bal_builder_rlp.py

# Create comprehensive analysis report
python create_analysis_report.py
```

### SSZ Implementation (Builder Pattern)

```python
from src.bal_builder import *
from src.BALs import *
from src.helpers import *

# Fetch block data
block_number = 22616000
trace_result = fetch_block_trace(block_number, RPC_URL)

# Create builder and process components
builder = BALBuilder()
touched_addresses = collect_touched_addresses(trace_result)
simple_transfers = identify_simple_eth_transfers(block_number, RPC_URL)

# Extract all components into the builder
process_storage_changes(trace_result, None, ignore_reads=True, builder=builder)
process_balance_changes(trace_result, builder, touched_addresses, simple_transfers)
process_code_changes(trace_result, builder)
process_nonce_changes(trace_result, builder)

# Build and encode BAL
block_obj = builder.build(ignore_reads=True)
block_obj_sorted = sort_block_access_list(block_obj)
encoded_bal = ssz.encode(block_obj_sorted, sedes=BlockAccessList)
```

### RLP Implementation (Builder Pattern)

```python
from src.bal_builder_rlp import *
from src.BALs_rlp import *
from src.helpers import *

# Fetch block data (identical process)
block_number = 22616000
trace_result = fetch_block_trace(block_number, RPC_URL)

# Create builder and process components
builder = BALBuilder()
touched_addresses = collect_touched_addresses(trace_result)
simple_transfers = identify_simple_eth_transfers(block_number, RPC_URL)

# Extract all components into the builder
process_storage_changes(trace_result, None, ignore_reads=True, builder=builder)
process_balance_changes(trace_result, builder, touched_addresses, simple_transfers)
process_code_changes(trace_result, builder)
process_nonce_changes(trace_result, builder)

# Build and encode BAL (RLP encoding)
block_obj = builder.build(ignore_reads=True)
block_obj_sorted = sort_block_access_list(block_obj)
encoded_bal = rlp.encode(block_obj_sorted)
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
- `src/BALs_rlp.py` - EIP-7928 data structures with RLP serialization
- `src/bal_builder.py` - SSZ BAL builder with optimized simple transfer detection
- `src/bal_builder_rlp.py` - RLP BAL builder with identical logic, different encoding
- `src/helpers.py` - RPC utilities, size analysis, and gas-based simple transfer detection
- `tests/` - Comprehensive test suite
- `reports/` - Analysis reports comparing encoding formats and read strategies
- `bal_raw/` - Generated BAL files and analysis data
  - `ssz/` - SSZ-encoded BALs and analysis results
  - `rlp/` - RLP-encoded BALs and analysis results

## License

MIT License - see [LICENSE](LICENSE) file.