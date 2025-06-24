import pandas as pd
import json
from typing import Dict, List as PyList, Optional, Tuple

from ssz import Serializable
from ssz.sedes import ByteVector, ByteList, uint16, uint32, uint64, List as SSZList

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

# =============================================================================
# CORE CHANGE STRUCTURES (no redundant keys)
# =============================================================================

class StorageChange(Serializable):
    """Single storage write: tx_index -> new_value"""
    fields = [
        ('tx_index', TxIndex),
        ('new_value', StorageValue),
    ]

class BalanceChange(Serializable):
    """Single balance change: tx_index -> delta"""
    fields = [
        ('tx_index', TxIndex),
        ('delta', BalanceDelta),
    ]

class NonceChange(Serializable):
    """Single nonce change: tx_index -> new_nonce"""
    fields = [
        ('tx_index', TxIndex),
        ('new_nonce', Nonce),
    ]

class CodeChange(Serializable):
    """Single code change: tx_index -> new_code"""
    fields = [
        ('tx_index', TxIndex),
        ('new_code', CodeData),
    ]

# =============================================================================
# SLOT-LEVEL MAPPING (eliminates slot key redundancy)
# =============================================================================

class SlotChanges(Serializable):
    """All changes to a single storage slot"""
    fields = [
        ('slot', StorageKey),
        ('changes', SSZList(StorageChange, MAX_TXS)),  # Only changes, no redundant slot
    ]

class SlotRead(Serializable):
    """Read-only access to a storage slot (no changes)"""
    fields = [
        ('slot', StorageKey),
    ]

# =============================================================================
# ACCOUNT-LEVEL MAPPING (groups all account changes)
# =============================================================================

class AccountChanges(Serializable):
    """
    All changes for a single account, grouped by field type.
    This eliminates address redundancy across different change types.
    """
    fields = [
        ('address', Address),
        
        # Storage changes (slot -> [tx_index -> new_value])
        ('storage_changes', SSZList(SlotChanges, MAX_SLOTS)),
        ('storage_reads', SSZList(SlotRead, MAX_SLOTS)),
        
        # Balance changes ([tx_index -> delta])
        ('balance_changes', SSZList(BalanceChange, MAX_TXS)),
        
        # Nonce changes ([tx_index -> new_nonce])
        ('nonce_changes', SSZList(NonceChange, MAX_TXS)),
        
        # Code changes ([tx_index -> new_code]) - typically 0 or 1
        ('code_changes', SSZList(CodeChange, MAX_TXS)),
    ]

# =============================================================================
# BLOCK-LEVEL STRUCTURE (simple list of account changes)
# =============================================================================

class MappedBlockAccessList(Serializable):
    """
    Efficient Block Access List using mapping approach.
    
    Benefits:
    1. Single list of accounts (no separate diffs)
    2. All changes for an account grouped together
    3. Keys implicit in structure (no redundant storage)
    4. Direct address->field->tx lookups
    5. Eliminates cross-referencing between different change types
    """
    fields = [
        ('account_changes', SSZList(AccountChanges, MAX_ACCOUNTS)),
    ]

# =============================================================================
# BUILDER FOR EFFICIENT CONSTRUCTION
# =============================================================================

class MappedBALBuilder:
    """
    Builder for constructing MappedBlockAccessList efficiently.
    
    Follows the natural transaction pattern:
    address -> field -> tx_index -> change
    """
    
    def __init__(self):
        # address -> field_type -> changes
        self.accounts: Dict[bytes, Dict[str, PyList]] = {}
        
    def _ensure_account(self, address: bytes):
        """Ensure account exists in builder."""
        if address not in self.accounts:
            self.accounts[address] = {
                'storage_changes': {},  # slot -> [StorageChange]
                'storage_reads': set(), # set of slots  
                'balance_changes': [],  # [BalanceChange]
                'nonce_changes': [],    # [NonceChange]
                'code_changes': [],     # [CodeChange]
            }
    
    def add_storage_write(self, address: bytes, slot: bytes, tx_index: int, new_value: bytes):
        """Add storage write: address -> slot -> tx_index -> new_value"""
        self._ensure_account(address)
        
        if slot not in self.accounts[address]['storage_changes']:
            self.accounts[address]['storage_changes'][slot] = []
            
        change = StorageChange(tx_index=tx_index, new_value=new_value)
        self.accounts[address]['storage_changes'][slot].append(change)
    
    def add_storage_read(self, address: bytes, slot: bytes):
        """Add storage read: address -> slot (read-only)"""
        self._ensure_account(address)
        self.accounts[address]['storage_reads'].add(slot)
    
    def add_balance_change(self, address: bytes, tx_index: int, delta: bytes):
        """Add balance change: address -> balance -> tx_index -> delta"""
        self._ensure_account(address)
        
        change = BalanceChange(tx_index=tx_index, delta=delta)
        self.accounts[address]['balance_changes'].append(change)
    
    def add_nonce_change(self, address: bytes, tx_index: int, new_nonce: int):
        """Add nonce change: address -> nonce -> tx_index -> new_nonce"""
        self._ensure_account(address)
        
        change = NonceChange(tx_index=tx_index, new_nonce=new_nonce)
        self.accounts[address]['nonce_changes'].append(change)
    
    def add_code_change(self, address: bytes, tx_index: int, new_code: bytes):
        """Add code change: address -> code -> tx_index -> new_code"""
        self._ensure_account(address)
        
        change = CodeChange(tx_index=tx_index, new_code=new_code)
        self.accounts[address]['code_changes'].append(change)
    
    def build(self, ignore_reads: bool = False) -> MappedBlockAccessList:
        """Build the final MappedBlockAccessList."""
        account_changes_list = []
        
        for address, changes in self.accounts.items():
            # Build storage changes
            storage_changes = []
            for slot, slot_changes in changes['storage_changes'].items():
                # Sort changes by tx_index for deterministic encoding
                sorted_changes = sorted(slot_changes, key=lambda x: x.tx_index)
                storage_changes.append(SlotChanges(slot=slot, changes=sorted_changes))
            
            # Build storage reads (only if not ignoring reads)
            storage_reads = []
            if not ignore_reads:
                for slot in changes['storage_reads']:
                    # Only include reads for slots that weren't written to
                    if slot not in changes['storage_changes']:
                        storage_reads.append(SlotRead(slot=slot))
            
            # Sort all changes by tx_index for deterministic encoding
            balance_changes = sorted(changes['balance_changes'], key=lambda x: x.tx_index)
            nonce_changes = sorted(changes['nonce_changes'], key=lambda x: x.tx_index)
            code_changes = sorted(changes['code_changes'], key=lambda x: x.tx_index)
            
            # Create account changes object
            account_change = AccountChanges(
                address=address,
                storage_changes=storage_changes,
                storage_reads=storage_reads,
                balance_changes=balance_changes,
                nonce_changes=nonce_changes,
                code_changes=code_changes
            )
            
            account_changes_list.append(account_change)
        
        # Sort accounts by address for deterministic encoding
        account_changes_list.sort(key=lambda x: bytes(x.address))
        
        return MappedBlockAccessList(account_changes=account_changes_list)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def estimate_size_bytes(obj):
    """Estimate size in bytes for debugging."""
    return len(json.dumps(obj).encode('utf-8'))

def get_mapped_account_stats(mapped_bal: MappedBlockAccessList) -> Dict[str, int]:
    """Get statistics about the mapped BAL structure."""
    stats = {
        'total_accounts': len(mapped_bal.account_changes),
        'accounts_with_storage_writes': 0,
        'accounts_with_storage_reads': 0,
        'accounts_with_balance_changes': 0,
        'accounts_with_nonce_changes': 0,
        'accounts_with_code_changes': 0,
        'total_storage_writes': 0,
        'total_storage_reads': 0,
        'total_balance_changes': 0,
        'total_nonce_changes': 0,
        'total_code_changes': 0,
    }
    
    for account in mapped_bal.account_changes:
        if account.storage_changes:
            stats['accounts_with_storage_writes'] += 1
            for slot_changes in account.storage_changes:
                stats['total_storage_writes'] += len(slot_changes.changes)
        
        if account.storage_reads:
            stats['accounts_with_storage_reads'] += 1
            stats['total_storage_reads'] += len(account.storage_reads)
            
        if account.balance_changes:
            stats['accounts_with_balance_changes'] += 1
            stats['total_balance_changes'] += len(account.balance_changes)
            
        if account.nonce_changes:
            stats['accounts_with_nonce_changes'] += 1
            stats['total_nonce_changes'] += len(account.nonce_changes)
            
        if account.code_changes:
            stats['accounts_with_code_changes'] += 1
            stats['total_code_changes'] += len(account.code_changes)
    
    return stats

# =============================================================================
# LEGACY CONVERSION FUNCTIONS
# =============================================================================

def convert_legacy_to_mapped(legacy_bal, ignore_reads: bool = False) -> MappedBlockAccessList:
    """Convert legacy BlockAccessList to MappedBlockAccessList."""
    builder = MappedBALBuilder()
    
    # Convert storage access
    for account_access in legacy_bal.account_accesses:
        address = bytes(account_access.address)
        
        for slot_access in account_access.accesses:
            slot = bytes(slot_access.slot)
            
            if slot_access.accesses:  # Has write operations
                for per_tx_access in slot_access.accesses:
                    builder.add_storage_write(
                        address=address,
                        slot=slot,
                        tx_index=per_tx_access.tx_index,
                        new_value=bytes(per_tx_access.value_after)
                    )
            elif not ignore_reads:  # Read-only operation
                builder.add_storage_read(address=address, slot=slot)
    
    # Convert balance changes
    for account_balance_diff in legacy_bal.balance_diffs:
        address = bytes(account_balance_diff.address)
        
        for balance_change in account_balance_diff.changes:
            builder.add_balance_change(
                address=address,
                tx_index=balance_change.tx_index,
                delta=bytes(balance_change.delta)
            )
    
    # Convert nonce changes
    for account_nonce_diff in legacy_bal.nonce_diffs:
        address = bytes(account_nonce_diff.address)
        
        for nonce_change in account_nonce_diff.changes:
            builder.add_nonce_change(
                address=address,
                tx_index=nonce_change.tx_index,
                new_nonce=nonce_change.nonce_after
            )
    
    # Convert code changes
    for account_code_diff in legacy_bal.code_diffs:
        address = bytes(account_code_diff.address)
        code_change = account_code_diff.change
        
        builder.add_code_change(
            address=address,
            tx_index=code_change.tx_index,
            new_code=bytes(code_change.new_code)
        )
    
    return builder.build(ignore_reads=ignore_reads)