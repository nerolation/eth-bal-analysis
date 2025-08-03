import pandas as pd
import json
from typing import Dict, List as PyList, Optional, Tuple
import rlp
from rlp.sedes import Serializable, big_endian_int, binary, CountableList

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

# Basic types for RLP
Address = binary  # 20 bytes
StorageKey = binary  # 32 bytes
StorageValue = binary  # 32 bytes
TxIndex = big_endian_int  # uint16
Balance = binary  # 16 bytes
Nonce = big_endian_int  # uint64
AccountIndex = big_endian_int  # uint32 for account indices

def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    return int(x, 16)


class BlockAccessListColumnarRLP(Serializable):
    """
    Columnar format for Block Access List using RLP encoding.
    Groups data by type rather than by account for better compression.
    """
    fields = [
        # 1️⃣ Accounts (sorted list of unique addresses)
        ('addresses', CountableList(Address)),
        
        # 2️⃣ Storage writes (columnar format)
        ('slots', CountableList(StorageKey)),  # unique slots
        ('slot_owner', CountableList(AccountIndex)),  # index into addresses
        ('slot_counts', CountableList(big_endian_int)),  # number of writes per slot
        ('storage_tx_indices', CountableList(TxIndex)),  # flattened tx indices
        ('storage_new_values', CountableList(StorageValue)),  # flattened new values

        # 3️⃣ Balance writes (columnar format)
        ('balance_account_idxs', CountableList(AccountIndex)),  # which account
        ('balance_tx_indices', CountableList(TxIndex)),
        ('balance_post_balances', CountableList(Balance)),

        # 4️⃣ Nonce writes (columnar format)
        ('nonce_account_idxs', CountableList(AccountIndex)),
        ('nonce_tx_indices', CountableList(TxIndex)),
        ('nonce_new_nonces', CountableList(Nonce)),

        # 5️⃣ Code writes (columnar format)
        ('code_account_idxs', CountableList(AccountIndex)),
        ('code_tx_indices', CountableList(TxIndex)),
        ('code_data_blob', binary),  # Concatenated code data
        ('code_offsets', CountableList(big_endian_int)),  # byte offset into blob
        ('code_lengths', CountableList(big_endian_int)),  # length of each code
    ]


class BALColumnarRLPBuilder:
    """Builder for constructing BlockAccessListColumnarRLP efficiently."""
    
    def __init__(self):
        # Account tracking
        self.addresses: PyList[bytes] = []
        self.address_to_idx: Dict[bytes, int] = {}
        
        # Storage writes tracking
        self.storage_writes: Dict[Tuple[bytes, bytes], PyList[Tuple[int, bytes]]] = {}
        
        # Balance changes tracking
        self.balance_changes: PyList[Tuple[bytes, int, bytes]] = []
        
        # Nonce changes tracking
        self.nonce_changes: PyList[Tuple[bytes, int, int]] = []
        
        # Code changes tracking
        self.code_changes: PyList[Tuple[bytes, int, bytes]] = []
        
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
        """Add a storage write."""
        self._ensure_account(address)
        key = (address, slot)
        
        if key not in self.storage_writes:
            self.storage_writes[key] = []
        
        self.storage_writes[key].append((tx_index, new_value))
    
    def add_storage_read(self, address: bytes, slot: bytes):
        """Add a storage read (not included in RLP format currently)."""
        self._ensure_account(address)
        
        if address not in self.storage_reads:
            self.storage_reads[address] = set()
        
        self.storage_reads[address].add(slot)
    
    def add_balance_change(self, address: bytes, tx_index: int, post_balance: bytes):
        """Add a balance change."""
        self._ensure_account(address)
        
        # Ensure balance is 16 bytes
        if len(post_balance) != 16:
            raise ValueError(f"Balance must be exactly 16 bytes, got {len(post_balance)}")
        
        self.balance_changes.append((address, tx_index, post_balance))
    
    def add_nonce_change(self, address: bytes, tx_index: int, new_nonce: int):
        """Add a nonce change."""
        self._ensure_account(address)
        self.nonce_changes.append((address, tx_index, new_nonce))
    
    def add_code_change(self, address: bytes, tx_index: int, new_code: bytes):
        """Add a code change."""
        self._ensure_account(address)
        self.code_changes.append((address, tx_index, new_code))
    
    def add_touched_account(self, address: bytes):
        """Add a touched account (ensures it's in the address list)."""
        self._ensure_account(address)
    
    def build(self, ignore_reads: bool = False) -> BlockAccessListColumnarRLP:
        """Build the final columnar RLP structure."""
        # Sort addresses for consistent ordering
        sorted_addresses = sorted(self.addresses)
        address_to_sorted_idx = {addr: idx for idx, addr in enumerate(sorted_addresses)}
        
        # Process storage writes
        slots = []
        slot_owner = []
        slot_counts = []
        storage_tx_indices = []
        storage_new_values = []
        
        # Sort storage writes by (address_idx, slot)
        sorted_storage = sorted(
            self.storage_writes.items(),
            key=lambda x: (address_to_sorted_idx[x[0][0]], x[0][1])
        )
        
        for (address, slot), changes in sorted_storage:
            slots.append(slot)
            slot_owner.append(address_to_sorted_idx[address])
            slot_counts.append(len(changes))
            
            # Sort changes by tx_index
            sorted_changes = sorted(changes, key=lambda x: x[0])
            for tx_idx, new_value in sorted_changes:
                storage_tx_indices.append(tx_idx)
                storage_new_values.append(new_value)
        
        # Process balance changes
        balance_account_idxs = []
        balance_tx_indices = []
        balance_post_balances = []
        
        # Sort by (address_idx, tx_index)
        sorted_balance_changes = sorted(
            self.balance_changes,
            key=lambda x: (address_to_sorted_idx[x[0]], x[1])
        )
        
        for address, tx_idx, post_balance in sorted_balance_changes:
            balance_account_idxs.append(address_to_sorted_idx[address])
            balance_tx_indices.append(tx_idx)
            balance_post_balances.append(post_balance)
        
        # Process nonce changes
        nonce_account_idxs = []
        nonce_tx_indices = []
        nonce_new_nonces = []
        
        # Sort by (address_idx, tx_index)
        sorted_nonce_changes = sorted(
            self.nonce_changes,
            key=lambda x: (address_to_sorted_idx[x[0]], x[1])
        )
        
        for address, tx_idx, new_nonce in sorted_nonce_changes:
            nonce_account_idxs.append(address_to_sorted_idx[address])
            nonce_tx_indices.append(tx_idx)
            nonce_new_nonces.append(new_nonce)
        
        # Process code changes
        code_account_idxs = []
        code_tx_indices = []
        code_data_blob = b''
        code_offsets = []
        code_lengths = []
        
        # Sort by (address_idx, tx_index)
        sorted_code_changes = sorted(
            self.code_changes,
            key=lambda x: (address_to_sorted_idx[x[0]], x[1])
        )
        
        current_offset = 0
        for address, tx_idx, new_code in sorted_code_changes:
            code_account_idxs.append(address_to_sorted_idx[address])
            code_tx_indices.append(tx_idx)
            code_offsets.append(current_offset)
            code_lengths.append(len(new_code))
            code_data_blob += new_code
            current_offset += len(new_code)
        
        return BlockAccessListColumnarRLP(
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
            code_data_blob=code_data_blob,
            code_offsets=code_offsets,
            code_lengths=code_lengths
        )


def get_account_stats_columnar_rlp(bal: BlockAccessListColumnarRLP) -> Dict[str, int]:
    """Get statistics about a columnar RLP BAL."""
    return {
        'total_accounts': len(bal.addresses),
        'total_storage_writes': len(bal.storage_tx_indices),
        'total_storage_reads': 0,  # Not tracked in columnar format
        'total_balance_changes': len(bal.balance_tx_indices),
        'total_nonce_changes': len(bal.nonce_tx_indices),
        'total_code_changes': len(bal.code_tx_indices),
        'unique_slots': len(bal.slots),
        'code_blob_size': len(bal.code_data_blob)
    }