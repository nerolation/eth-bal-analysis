import os
import pandas as pd
import json
from collections import defaultdict
from typing import List as PyList, Optional

import ssz
from ssz import Serializable
from ssz.sedes import ByteVector, ByteList, uint16, uint64, List as SSZList, uint8
from eth_utils import to_canonical_address

# Constants; chosen to support a 630m block gas limit
MAX_TXS = 30_000
MAX_SLOTS = 300_000
MAX_ACCOUNTS = 300_000
MAX_CODE_SIZE = 24_576  # Maximum contract bytecode size in bytes

# SSZ type aliases
Address = ByteVector(20)
StorageKey = ByteVector(32)
StorageValue = ByteVector(32)
TxIndex = uint16
BalanceDelta = ByteVector(12)
Nonce = uint64
CodeData = ByteList(MAX_CODE_SIZE)

def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    return int(x, 16)


class PerTxAccess(Serializable):
    fields = [
        ('tx_index', TxIndex),
        ('value_after', StorageValue),
    ]


class SlotAccess(Serializable):
    fields = [
        ('slot', StorageKey),
        ('accesses', SSZList(PerTxAccess, MAX_TXS)),
    ]


class AccountAccess(Serializable):
    fields = [
        ('address', Address),
        ('accesses', SSZList(SlotAccess, MAX_SLOTS)),
    ]

AccountAccessList = SSZList(AccountAccess, MAX_ACCOUNTS)

def estimate_size_bytes(obj):
    return len(json.dumps(obj).encode('utf-8'))

# BALANCE DIFF

class BalanceChange(Serializable):
    fields = [
        ("tx_index", TxIndex),
        ("delta", BalanceDelta),
    ]

class AccountBalanceDiff(Serializable):
    fields = [
        ("address", Address),
        ("changes", SSZList(BalanceChange, MAX_TXS)),
    ]

BalanceDiffs = SSZList(AccountBalanceDiff, MAX_ACCOUNTS)

# NONCE DIFF
class TxNonceDiff(Serializable):
    fields = [
        ("tx_index", TxIndex),
        ("nonce_after", Nonce),  # nonce value after transaction execution
    ]

class AccountNonceDiff(Serializable):
    fields = [
        ("address", Address),
        ("changes", SSZList(TxNonceDiff, MAX_TXS)),
    ]

NonceDiffs = SSZList(AccountNonceDiff, MAX_ACCOUNTS)


class CodeChange(Serializable):
    fields = [
        ('tx_index', TxIndex),
        ('new_code', CodeData),
    ]

class AccountCodeDiff(Serializable):
    fields = [
        ("address", Address),
        ("change", CodeChange),
    ]

CodeDiffs = SSZList(AccountCodeDiff, MAX_ACCOUNTS)


class BlockAccessList(Serializable):
    fields = [
        ('account_accesses', AccountAccessList),
        ('balance_diffs',     BalanceDiffs),
        ('code_diffs',        CodeDiffs),
        ('nonce_diffs',       NonceDiffs),
    ]