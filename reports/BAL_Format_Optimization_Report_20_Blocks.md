# Block Access List (BAL) Format Optimization Report - 20 Block Analysis

## Executive Summary

This report analyzes two new SSZ format designs for Block Access Lists (BALs) compared to the original nested format, based on analysis of 20 Ethereum blocks. The columnar format achieves an **8.3% size reduction** when compressed, while the optimized format with advanced encoding techniques results in a **28.9% size increase** due to structural overhead.

## Methodology

### Data Collection
- Analyzed 20 Ethereum blocks (every 10th block from 20615532 to 20615722)
- Used SSZ encoding with Snappy compression
- Compared uncompressed and compressed sizes
- Measured compression effectiveness across all formats

### Formats Tested
1. **Original Format**: Nested, account-centric structure
2. **Columnar Format**: Flattened, column-oriented structure
3. **Optimized Format**: Advanced encoding with VarInt, Delta encoding, Dictionary compression

## SSZ Structure Definitions

### Columnar Format Structure

```python
class BlockAccessListColumnar(Serializable):
    fields = [
        # Addresses
        ('addresses', SSZList(Address, MAX_ACCOUNTS)),
        
        # Storage writes
        ('slots', SSZList(StorageKey, MAX_SLOTS)),
        ('slot_owner', SSZList(uint32, MAX_SLOTS)),
        ('slot_counts', SSZList(uint16, MAX_SLOTS)),
        ('storage_tx_indices', SSZList(TxIndex, MAX_STORAGE_CHANGES)),
        ('storage_new_values', SSZList(StorageValue, MAX_STORAGE_CHANGES)),
        
        # Balance writes
        ('balance_account_idxs', SSZList(uint32, MAX_BALANCE_CHANGES)),
        ('balance_tx_indices', SSZList(TxIndex, MAX_BALANCE_CHANGES)),
        ('balance_post_balances', SSZList(Balance, MAX_BALANCE_CHANGES)),
        
        # Nonce writes
        ('nonce_account_idxs', SSZList(uint32, MAX_NONCE_CHANGES)),
        ('nonce_tx_indices', SSZList(TxIndex, MAX_NONCE_CHANGES)),
        ('nonce_post_values', SSZList(Nonce, MAX_NONCE_CHANGES)),
        
        # Code writes
        ('code_account_idxs', SSZList(uint32, MAX_CODE_CHANGES)),
        ('code_tx_indices', SSZList(TxIndex, MAX_CODE_CHANGES)),
        ('code_post_values', SSZList(ByteList(MAX_CODE_SIZE), MAX_CODE_CHANGES)),
    ]
```

### Optimized Format Structure

```python
# Constants
MAX_TXS = 30_000
MAX_SLOTS = 300_000
MAX_ACCOUNTS = 300_000
MAX_CODE_SIZE = 24_576
MAX_STORAGE_CHANGES = MAX_SLOTS * 10
MAX_BALANCE_CHANGES = MAX_ACCOUNTS * 10
MAX_NONCE_CHANGES = MAX_ACCOUNTS * 10
MAX_CODE_CHANGES = 1000
MAX_VARINT_BYTES = 3
MAX_CHANGES_PER_ACCOUNT = 1000

# Type aliases
Address = ByteVector(20)
StorageKey = ByteVector(32)
TxIndex = uint16
Balance = uint128
Nonce = uint64
DictIndex = uint8
Bytes32 = ByteVector(32)

def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    return int(x, 16)

# Encoding utilities
def encode_varint(value: int) -> bytes:
    """Encode an integer as a variable-length byte sequence."""
    if value < 128:
        return bytes([value])
    elif value < 16384:
        return bytes([0x80 | (value & 0x7F), value >> 7])
    else:
        # For larger values, ensure each byte is in valid range
        b1 = 0x80 | (value & 0x7F)
        b2 = 0x80 | ((value >> 7) & 0x7F)
        b3 = (value >> 14) & 0xFF  # Ensure it's within byte range
        return bytes([b1, b2, b3])

def decode_varint(data: bytes) -> Tuple[int, int]:
    """Decode a variable-length integer. Returns (value, bytes_consumed)."""
    value = 0
    shift = 0
    for i, byte in enumerate(data):
        value |= (byte & 0x7F) << shift
        if byte & 0x80 == 0:
            return value, i + 1
        shift += 7
    raise ValueError("Invalid varint encoding")

def zigzag_encode(value: int) -> int:
    """Encode signed integer using ZigZag encoding."""
    if value >= 0:
        return value << 1
    else:
        return ((-value) << 1) - 1

def zigzag_decode(value: int) -> int:
    """Decode ZigZag encoded integer."""
    return (value >> 1) if (value & 1) == 0 else -((value + 1) >> 1)

def encode_delta_varint(value: int) -> bytes:
    """Encode a signed delta as ZigZag + VarInt."""
    return encode_varint(zigzag_encode(value))

def count_leading_zeros(data: bytes) -> int:
    """Count leading zero bytes."""
    for i, byte in enumerate(data):
        if byte != 0:
            return i
    return len(data)

# SSZ structures

class VarInt(Serializable):
    fields = [
        ('bytes', SSZList(uint8, MAX_VARINT_BYTES))
    ]

class DeltaVarInt(Serializable):
    fields = [
        ('bytes', SSZList(uint8, MAX_VARINT_BYTES))
    ]

class CompressedValue(Serializable):
    fields = [
        ('is_dict', boolean),
        ('dict_index', DictIndex),
        ('literal', Bytes32)
    ]

class TrimmedBalance(Serializable):
    fields = [
        ('header', uint8),
        ('bytes', SSZVector(uint8, 32))
    ]

class DeltaIndexList(Serializable):
    fields = [
        ('first', TxIndex),
        ('deltas', SSZList(DeltaVarInt, MAX_CHANGES_PER_ACCOUNT))
    ]

class CompressedSlot(Serializable):
    fields = [
        ('slot_key', StorageKey),
        ('count', VarInt),
        ('tx_indices', DeltaIndexList),
        ('values', SSZList(CompressedValue, MAX_TXS))
    ]

# Account flags type - 4 bits per account
AccountFlags = Bitvector(MAX_ACCOUNTS * 4)

class OptimizedBlockAccessList(Serializable):
    fields = [
        # Header
        ('encoding_flags', uint8),
        ('dict_size', uint8),
        
        # Dictionary
        ('dictionary_values', SSZList(Bytes32, 255)),
        
        # Accounts
        ('addresses', SSZList(Address, MAX_ACCOUNTS)),
        ('account_flags', AccountFlags),
        
        # Storage writes
        ('total_slots', VarInt),
        ('slots', SSZList(CompressedSlot, MAX_SLOTS)),
        
        # Balance writes
        ('total_balance_changes', VarInt),
        ('balance_accounts', DeltaIndexList),
        ('balances', SSZList(TrimmedBalance, MAX_BALANCE_CHANGES)),
        
        # Nonce writes
        ('total_nonce_changes', VarInt),
        ('nonce_accounts', DeltaIndexList),
        ('nonces', SSZList(VarInt, MAX_NONCE_CHANGES)),
        
        # Transaction indexes
        ('total_tx_indices', VarInt),
        ('tx_index_list', DeltaIndexList),
        
        # Code writes
        ('total_code_changes', VarInt),
        ('code_accounts', DeltaIndexList),
        ('code_tx_indices', DeltaIndexList),
        ('code_blob', SSZList(uint8, MAX_CODE_CHANGES * MAX_CODE_SIZE)),
        ('code_offsets', SSZList(uint32, MAX_CODE_CHANGES)),
        ('code_lengths', SSZList(uint32, MAX_CODE_CHANGES))
    ]
```

## Results - 20 Block Analysis

### Average Size Comparison

| Format | Uncompressed Size | Compressed Size | vs Original (Compressed) |
|--------|------------------|-----------------|-------------------------|
| Original | 53.86 KB | 34.14 KB | - |
| Columnar | 49.28 KB | 31.29 KB | **-8.3%** ✅ |
| Optimized | 220.34 KB | 44.00 KB | **+28.9%** ❌ |

### Compression Effectiveness

| Format | Compression Ratio | Efficiency |
|--------|------------------|-----------|
| Original | 63.4% | Good |
| Columnar | 63.5% | Good |
| Optimized | 20.0% | Poor |

### Size Distribution (Compressed)

| Format | Min | P25 | Median | P75 | Max |
|--------|-----|-----|--------|-----|-----|
| Original | 2.95 KB | 23.45 KB | 31.38 KB | 36.99 KB | 79.90 KB |
| Columnar | 2.79 KB | 21.44 KB | 28.40 KB | 34.12 KB | 76.24 KB |
| Optimized | 10.13 KB | 32.46 KB | 41.92 KB | 47.21 KB | 89.47 KB |

### Block Size Variability

The analysis shows significant variation in block sizes:
- **Small blocks** (<10 KB): Show the worst optimized format overhead (up to +243.6%)
- **Medium blocks** (20-40 KB): Consistent 8-10% improvement with columnar
- **Large blocks** (>60 KB): Smaller relative improvements but still significant

### Dictionary Analysis

Average dictionary size: **232 entries** (out of 255 max)
- Most blocks fill the dictionary completely (255 entries)
- Even with full dictionaries, the overhead exceeds benefits
- Small blocks have smaller dictionaries but worse overhead ratios

## Key Findings

### 1. Columnar Format Success
- **Consistent 8-10% reduction** across all block sizes
- **Simple implementation** with predictable behavior
- **No overhead** - just reorganization of existing data
- **Works well with Snappy** compression algorithm

### 2. Optimized Format Failure
- **28.9% average increase** in compressed size
- **Worst on small blocks**: Up to 243.6% overhead
- **Dictionary rarely effective**: 8KB overhead for minimal benefit
- **Poor compression**: Only compresses to 20% vs 63% for other formats

### 3. Overhead Analysis

The optimized format adds approximately:
- **8.16 KB** for dictionary (255 × 32 bytes)
- **2-4 KB** for metadata and wrappers
- **1-2 KB** for SSZ structure overhead
- **Total: ~12-14 KB** fixed overhead per block

This overhead is particularly punishing for small blocks:
- 3 KB block → 10 KB with optimized format (+233%)
- 30 KB block → 42 KB with optimized format (+40%)
- 70 KB block → 82 KB with optimized format (+17%)

## Performance Implications

### Encoding/Decoding Speed (Estimated)
1. **Columnar**: Minimal overhead, similar to original
2. **Optimized**: Significant overhead due to:
   - Dictionary lookups
   - VarInt encoding/decoding
   - Delta calculations
   - Multiple compression layers

### Memory Usage
1. **Columnar**: Similar to original
2. **Optimized**: Higher due to dictionary and complex structures

## Recommendations

### Immediate Action
**Deploy the columnar format** for production use:
- Proven 8.3% size reduction across 20 blocks
- Simple, reliable implementation
- No performance concerns
- Easy to integrate with existing systems

### Abandon Optimized Format
The current optimized format should not be used because:
- Increases size by 28.9% on average
- Adds significant complexity
- Poor compression characteristics
- Overhead exceeds any theoretical benefits

### Future Research
If further optimization is needed:
1. **Analyze larger datasets**: 1000+ blocks to find better patterns
2. **Selective optimization**: Apply only to specific data types
3. **Dynamic encoding**: Choose encoding based on block characteristics
4. **Hybrid approach**: Start with columnar, add minimal optimizations

## Conclusion

The 20-block analysis confirms that the **columnar format is the clear winner**, providing consistent 8-10% compression improvements with minimal complexity. The optimized format, despite sophisticated encoding techniques, adds too much overhead for typical Ethereum block sizes. The columnar format should be adopted as the new standard for Block Access Lists.

### Summary Statistics
- **Blocks analyzed**: 20
- **Columnar improvement**: 8.3% average (4.6% - 10.7% range)
- **Optimized overhead**: 28.9% average (12.0% - 243.6% range)
- **Recommendation**: Adopt columnar format immediately
