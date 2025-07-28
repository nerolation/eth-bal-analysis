import pandas as pd
import json
from typing import Dict, List as PyList
from ssz import Serializable
from ssz.sedes import (
    ByteVector, ByteList, uint8, uint16, uint32, uint64, 
    List as SSZList, Vector as SSZVector
)

if not hasattr(ByteList, 'length'):
    ByteList.length = property(lambda self: self.max_length)

# Constants matching the original
MAX_TXS = 30_000
MAX_SLOTS = 300_000
MAX_ACCOUNTS = 300_000
MAX_CODE_SIZE = 24_576
MAX_STORAGE_CHANGES = MAX_SLOTS * 10  # Assuming max 10 changes per slot
MAX_BALANCE_CHANGES = MAX_ACCOUNTS * 10  # Assuming max 10 balance changes per account
MAX_NONCE_CHANGES = MAX_ACCOUNTS * 10  # Assuming max 10 nonce changes per account
MAX_CODE_CHANGES = 1000  # Assuming max 1000 code deployments per block
MAX_CODE_BLOB_SIZE = MAX_CODE_CHANGES * MAX_CODE_SIZE

# Basic types
Address = ByteVector(20)
StorageKey = ByteVector(32)
StorageValue = ByteVector(32)
TxIndex = uint16
Balance = ByteVector(16)
Nonce = uint64

def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    return int(x, 16)


class BlockAccessListColumnar(Serializable):
    fields = [
        # 1️⃣ Accounts
        ('addresses', SSZList(Address, MAX_ACCOUNTS)),  # sorted
        
        # 2️⃣ Storage writes
        ('slots', SSZList(StorageKey, MAX_SLOTS)),  # unique slots
        ('slot_owner', SSZList(uint32, MAX_SLOTS)),  # index into addresses
        ('slot_counts', SSZList(uint32, MAX_SLOTS)),  # # writes per slot
        ('storage_tx_indices', SSZList(TxIndex, MAX_STORAGE_CHANGES)),  # flattened tx indices
        ('storage_new_values', SSZList(StorageValue, MAX_STORAGE_CHANGES)),  # flattened new values

        # 3️⃣ Balance writes
        ('balance_account_idxs', SSZList(uint32, MAX_BALANCE_CHANGES)),  # which account
        ('balance_tx_indices', SSZList(TxIndex, MAX_BALANCE_CHANGES)),
        ('balance_post_balances', SSZList(Balance, MAX_BALANCE_CHANGES)),

        # 4️⃣ Nonce writes
        ('nonce_account_idxs', SSZList(uint32, MAX_NONCE_CHANGES)),
        ('nonce_tx_indices', SSZList(TxIndex, MAX_NONCE_CHANGES)),
        ('nonce_new_nonces', SSZList(Nonce, MAX_NONCE_CHANGES)),

        # 5️⃣ Code writes
        ('code_account_idxs', SSZList(uint32, MAX_CODE_CHANGES)),
        ('code_tx_indices', SSZList(TxIndex, MAX_CODE_CHANGES)),
        ('code_data_blob', ByteList(MAX_CODE_BLOB_SIZE)),  # Variable size blob
        ('code_offsets', SSZList(uint32, MAX_CODE_CHANGES)),  # byte‐offset into blob
        ('code_lengths', SSZList(uint32, MAX_CODE_CHANGES)),
    ]


class BALColumnarBuilder:
    """Builder for constructing BlockAccessListColumnar efficiently."""
    
    def __init__(self):
        # Account tracking
        self.addresses: PyList[bytes] = []
        self.address_to_idx: Dict[bytes, int] = {}
        
        # Storage writes tracking
        self.storage_writes: Dict[tuple[bytes, bytes], PyList[tuple[int, bytes]]] = {}
        
        # Balance changes tracking
        self.balance_changes: PyList[tuple[bytes, int, bytes]] = []
        
        # Nonce changes tracking
        self.nonce_changes: PyList[tuple[bytes, int, int]] = []
        
        # Code changes tracking
        self.code_changes: PyList[tuple[bytes, int, bytes]] = []
        
        # Storage reads tracking (for future use if needed)
        self.storage_reads: Dict[bytes, set[bytes]] = {}
    
    def _ensure_account(self, address: bytes) -> int:
        """Ensure account exists and return its index."""
        if address not in self.address_to_idx:
            idx = len(self.addresses)
            self.addresses.append(address)
            self.address_to_idx[address] = idx
        return self.address_to_idx[address]
    
    def add_storage_write(self, address: bytes, slot: bytes, tx_index: int, new_value: bytes):
        account_idx = self._ensure_account(address)
        key = (address, slot)
        if key not in self.storage_writes:
            self.storage_writes[key] = []
        self.storage_writes[key].append((tx_index, new_value))
    
    def add_storage_read(self, address: bytes, slot: bytes):
        """Track storage reads (not included in columnar format but kept for compatibility)."""
        if address not in self.storage_reads:
            self.storage_reads[address] = set()
        self.storage_reads[address].add(slot)
    
    def add_balance_change(self, address: bytes, tx_index: int, post_balance: bytes):
        if len(post_balance) != 16:
            raise ValueError(f"Balance must be exactly 16 bytes, got {len(post_balance)}")
        account_idx = self._ensure_account(address)
        self.balance_changes.append((address, tx_index, post_balance))
    
    def add_nonce_change(self, address: bytes, tx_index: int, new_nonce: int):
        account_idx = self._ensure_account(address)
        self.nonce_changes.append((address, tx_index, new_nonce))
    
    def add_code_change(self, address: bytes, tx_index: int, new_code: bytes):
        if len(new_code) > MAX_CODE_SIZE:
            raise ValueError(f"Code size {len(new_code)} exceeds maximum {MAX_CODE_SIZE}")
        account_idx = self._ensure_account(address)
        self.code_changes.append((address, tx_index, new_code))
    
    def add_touched_account(self, address: bytes):
        """Ensure account exists in the address list."""
        self._ensure_account(address)
    
    def build(self, ignore_reads: bool = False) -> BlockAccessListColumnar:
        # Sort addresses for consistent ordering
        sorted_addresses = sorted(self.addresses)
        address_to_sorted_idx = {addr: i for i, addr in enumerate(sorted_addresses)}
        
        # Build storage write arrays
        slots = []
        slot_owner = []
        slot_counts = []
        storage_tx_indices = []
        storage_new_values = []
        
        # Sort storage writes by (address_idx, slot)
        sorted_storage_writes = sorted(
            self.storage_writes.items(),
            key=lambda x: (address_to_sorted_idx[x[0][0]], x[0][1])
        )
        
        for (address, slot), changes in sorted_storage_writes:
            slots.append(slot)
            slot_owner.append(address_to_sorted_idx[address])
            slot_counts.append(len(changes))
            
            # Sort changes by tx_index and flatten
            sorted_changes = sorted(changes, key=lambda x: x[0])
            for tx_idx, new_value in sorted_changes:
                storage_tx_indices.append(tx_idx)
                storage_new_values.append(new_value)
        
        # Build balance change arrays
        balance_account_idxs = []
        balance_tx_indices = []
        balance_post_balances = []
        
        # Sort balance changes by (account_idx, tx_index)
        sorted_balance_changes = sorted(
            self.balance_changes,
            key=lambda x: (address_to_sorted_idx[x[0]], x[1])
        )
        
        for address, tx_idx, post_balance in sorted_balance_changes:
            balance_account_idxs.append(address_to_sorted_idx[address])
            balance_tx_indices.append(tx_idx)
            balance_post_balances.append(post_balance)
        
        # Build nonce change arrays
        nonce_account_idxs = []
        nonce_tx_indices = []
        nonce_new_nonces = []
        
        # Sort nonce changes by (account_idx, tx_index)
        sorted_nonce_changes = sorted(
            self.nonce_changes,
            key=lambda x: (address_to_sorted_idx[x[0]], x[1])
        )
        
        for address, tx_idx, new_nonce in sorted_nonce_changes:
            nonce_account_idxs.append(address_to_sorted_idx[address])
            nonce_tx_indices.append(tx_idx)
            nonce_new_nonces.append(new_nonce)
        
        # Build code change arrays
        code_account_idxs = []
        code_tx_indices = []
        code_data_blob = bytearray()
        code_offsets = []
        code_lengths = []
        
        # Sort code changes by (account_idx, tx_index)
        sorted_code_changes = sorted(
            self.code_changes,
            key=lambda x: (address_to_sorted_idx[x[0]], x[1])
        )
        
        current_offset = 0
        for address, tx_idx, code in sorted_code_changes:
            code_account_idxs.append(address_to_sorted_idx[address])
            code_tx_indices.append(tx_idx)
            code_offsets.append(current_offset)
            code_lengths.append(len(code))
            code_data_blob.extend(code)
            current_offset += len(code)
        
        # No padding needed for ByteList
        
        return BlockAccessListColumnar(
            addresses=sorted_addresses,
            slots=slots,
            slot_owner=slot_owner,
            slot_counts=slot_counts,
            storage_tx_indices=storage_tx_indices,
            storage_new_values=storage_new_values,
            balance_account_idxs=balance_account_idxs,
            balance_tx_indices=balance_tx_indices,
            balance_post_balances=balance_post_balances,
            nonce_account_idxs=nonce_account_idxs,
            nonce_tx_indices=nonce_tx_indices,
            nonce_new_nonces=nonce_new_nonces,
            code_account_idxs=code_account_idxs,
            code_tx_indices=code_tx_indices,
            code_data_blob=bytes(code_data_blob),
            code_offsets=code_offsets,
            code_lengths=code_lengths
        )


def get_account_stats_columnar(bal: BlockAccessListColumnar) -> Dict[str, int]:
    """Get statistics about a columnar BAL."""
    stats = {
        'total_accounts': len(bal.addresses),
        'accounts_with_storage_writes': len(set(bal.slot_owner)),
        'accounts_with_storage_reads': 0,  # Not tracked in columnar format
        'accounts_with_balance_changes': len(set(bal.balance_account_idxs)),
        'accounts_with_nonce_changes': len(set(bal.nonce_account_idxs)),
        'accounts_with_code_changes': len(set(bal.code_account_idxs)),
        'total_storage_writes': len(bal.storage_tx_indices),
        'total_storage_reads': 0,  # Not tracked in columnar format
        'total_balance_changes': len(bal.balance_tx_indices),
        'total_nonce_changes': len(bal.nonce_tx_indices),
        'total_code_changes': len(bal.code_tx_indices),
        'total_storage_slots': len(bal.slots),
    }
    return stats