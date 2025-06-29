import pandas as pd
import json
from typing import Dict, List as PyList, Optional, Tuple
import rlp
from rlp.sedes import Serializable, big_endian_int, binary, CountableList

# Constants; chosen to support a 630m block gas limit
MAX_TXS = 30_000
MAX_SLOTS = 300_000
MAX_ACCOUNTS = 300_000
MAX_CODE_SIZE = 24_576  # Maximum contract bytecode size in bytes

# RLP type aliases
Address = binary  # 20 bytes
StorageKey = binary  # 32 bytes
StorageValue = binary  # 32 bytes
TxIndex = big_endian_int  # uint16 equivalent
Balance = binary  # 12 bytes for post balance value
Nonce = big_endian_int  # uint64 equivalent
CodeData = binary  # Variable length bytecode

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
    """Single balance change: tx_index -> post_balance"""
    fields = [
        ('tx_index', TxIndex),
        ('post_balance', Balance),
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
        ('changes', CountableList(StorageChange)),  # Only changes, no redundant slot
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
        ('storage_changes', CountableList(SlotChanges)),
        ('storage_reads', CountableList(SlotRead)),
        
        # Balance changes ([tx_index -> post_balance])
        ('balance_changes', CountableList(BalanceChange)),
        
        # Nonce changes ([tx_index -> new_nonce])
        ('nonce_changes', CountableList(NonceChange)),
        
        # Code changes ([tx_index -> new_code]) - typically 0 or 1
        ('code_changes', CountableList(CodeChange)),
    ]

# =============================================================================
# BLOCK-LEVEL STRUCTURE (simple list of account changes)
# =============================================================================

class BlockAccessList(Serializable):
    """
    Block Access List structure for EIP-7928.
    
    Account-centric design that groups all changes by address,
    eliminating redundancy and providing optimal encoding efficiency.
    """
    fields = [
        ('account_changes', CountableList(AccountChanges)),
    ]

# =============================================================================
# BUILDER FOR EFFICIENT CONSTRUCTION
# =============================================================================

class BALBuilder:
    """
    Builder for constructing BlockAccessList efficiently.
    
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
    
    def add_balance_change(self, address: bytes, tx_index: int, post_balance: bytes):
        """Add balance change: address -> balance -> tx_index -> post_balance"""
        self._ensure_account(address)
        
        change = BalanceChange(tx_index=tx_index, post_balance=post_balance)
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
    
    def add_touched_account(self, address: bytes):
        """Add an account that was touched but not changed (e.g., for EXTCODEHASH, BALANCE checks)"""
        self._ensure_account(address)
    
    def build(self, ignore_reads: bool = False) -> BlockAccessList:
        """Build the final BlockAccessList."""
        account_changes_list = []
        
        for address, changes in self.accounts.items():
            if (
                not changes['storage_changes']
                and not changes['storage_reads']
                and not changes['balance_changes']
                and not changes['nonce_changes']
                and not changes['code_changes']
            ):
                continue

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
        
        return BlockAccessList(account_changes=account_changes_list)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def estimate_size_bytes(obj):
    """Estimate size in bytes for debugging."""
    return len(json.dumps(obj).encode('utf-8'))

def get_account_stats(bal: BlockAccessList) -> Dict[str, int]:
    """Get statistics about the BAL structure."""
    stats = {
        'total_accounts': len(bal.account_changes),
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
    
    for account in bal.account_changes:
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
