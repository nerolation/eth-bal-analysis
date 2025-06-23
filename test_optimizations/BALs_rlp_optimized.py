import os
import pandas as pd
import json
from collections import defaultdict
from typing import List as PyList, Optional

import rlp
from rlp.sedes import Serializable, big_endian_int, binary, CountableList
from eth_utils import to_canonical_address

# Constants; chosen to support a 630m block gas limit
MAX_TXS = 30_000
MAX_SLOTS = 300_000
MAX_ACCOUNTS = 300_000
MAX_CODE_SIZE = 24_576  # Maximum contract bytecode size in bytes

def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    return int(x, 16)


# Storage Write structures (only for slots that are written to)
class PerTxWriteRLP(Serializable):
    fields = [
        ('tx_index', big_endian_int),      # uint16 equivalent
        ('value_after', binary),           # 32-byte storage value
    ]

class SlotWriteRLP(Serializable):
    fields = [
        ('slot', binary),                  # 32-byte storage key
        ('writes', CountableList(PerTxWriteRLP)),
    ]

class AccountWritesRLP(Serializable):
    fields = [
        ('address', binary),               # 20-byte address
        ('slot_writes', CountableList(SlotWriteRLP)),
    ]

# Storage Read structures (read-only slots - much more compact)
class SlotReadRLP(Serializable):
    fields = [
        ('slot', binary),                  # 32-byte storage key
    ]

class AccountReadsRLP(Serializable):
    fields = [
        ('address', binary),               # 20-byte address
        ('slot_reads', CountableList(SlotReadRLP)),
    ]

def estimate_size_bytes(obj):
    return len(json.dumps(obj).encode('utf-8'))

# BALANCE DIFF

class BalanceChangeRLP(Serializable):
    fields = [
        ("tx_index", big_endian_int),      # uint16 equivalent
        ("delta", binary),                 # 12-byte signed balance delta
    ]

class AccountBalanceDiffRLP(Serializable):
    fields = [
        ("address", binary),               # 20-byte address
        ("changes", CountableList(BalanceChangeRLP)),
    ]

# NONCE DIFF
class TxNonceDiffRLP(Serializable):
    fields = [
        ("tx_index", big_endian_int),      # uint16 equivalent
        ("nonce_after", big_endian_int),   # uint64 equivalent - nonce value after transaction execution
    ]

class AccountNonceDiffRLP(Serializable):
    fields = [
        ("address", binary),               # 20-byte address
        ("changes", CountableList(TxNonceDiffRLP)),
    ]


class CodeChangeRLP(Serializable):
    fields = [
        ('tx_index', big_endian_int),      # uint16 equivalent
        ('new_code', binary),              # variable-length bytecode
    ]

class AccountCodeDiffRLP(Serializable):
    fields = [
        ("address", binary),               # 20-byte address
        ("change", CodeChangeRLP),
    ]


# Optimized BlockAccessList that separates reads from writes  
class BlockAccessListRLP(Serializable):
    fields = [
        ('storage_writes', CountableList(AccountWritesRLP)),
        ('storage_reads', CountableList(AccountReadsRLP)),
        ('balance_diffs', CountableList(AccountBalanceDiffRLP)),
        ('code_diffs', CountableList(AccountCodeDiffRLP)),
        ('nonce_diffs', CountableList(AccountNonceDiffRLP)),
    ]


# Helper functions for conversion between SSZ and RLP formats

def encode_balance_delta(delta_int):
    """Convert integer balance delta to 12-byte signed representation"""
    if delta_int >= 0:
        return delta_int.to_bytes(12, byteorder='big', signed=False)
    else:
        return delta_int.to_bytes(12, byteorder='big', signed=True)

def decode_balance_delta(delta_bytes):
    """Convert 12-byte signed representation back to integer"""
    return int.from_bytes(delta_bytes, byteorder='big', signed=True)

def encode_storage_key(key_hex):
    """Convert hex storage key to 32-byte binary"""
    if isinstance(key_hex, str):
        key_int = int(key_hex, 16) if key_hex else 0
    else:
        key_int = key_hex
    return key_int.to_bytes(32, byteorder='big')

def encode_storage_value(value_hex):
    """Convert hex storage value to 32-byte binary"""
    if isinstance(value_hex, str):
        value_int = int(value_hex, 16) if value_hex else 0
    else:
        value_int = value_hex
    return value_int.to_bytes(32, byteorder='big')

def encode_address(addr_hex):
    """Convert hex address to 20-byte binary"""
    if isinstance(addr_hex, str):
        return to_canonical_address(addr_hex)
    return addr_hex