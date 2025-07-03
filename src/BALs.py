import pandas as pd
import json
from typing import Dict, List as PyList, Optional, Tuple

from ssz import Serializable
from ssz.sedes import ByteVector, ByteList, uint16, uint32, uint64, uint128, List as SSZList

# Constants; chosen to support a 630m block gas limit
MAX_TXS = 30_000
MAX_SLOTS = 300_000
MAX_ACCOUNTS = 300_000
MAX_CODE_SIZE = 24_576  # Maximum contract bytecode size in bytes

# SSZ type aliases per latest EIP-7928
Address = ByteVector(20)  # Bytes20
StorageKey = ByteVector(32)  # Bytes32
StorageValue = ByteVector(32)  # Bytes32
TxIndex = uint16
Balance = ByteVector(16)  # bytes16 for balance differences
Nonce = uint64
CodeData = ByteList(MAX_CODE_SIZE)  # List[byte, MAX_CODE_SIZE]

def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    return int(x, 16)

# =============================================================================
# CORE CHANGE STRUCTURES (latest EIP-7928 format)
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
        ('post_balance', Balance),  # Now uint128
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
# STORAGE ACCESS TRACKING (simplified per latest EIP-7928)
# =============================================================================

class StorageAccess(Serializable):
    """Storage access for a single slot with all changes"""
    fields = [
        ('slot', StorageKey),
        ('changes', SSZList(StorageChange, MAX_TXS)),
    ]

# StorageRead class removed - we now use StorageKey directly in storage_reads list

# =============================================================================
# ACCOUNT-LEVEL STRUCTURE (simplified per latest EIP-7928)
# =============================================================================

class AccountChanges(Serializable):
    """
    All changes for a single account per latest EIP-7928.
    More direct structure without nested containers.
    """
    fields = [
        ('address', Address),
        ('storage_writes', SSZList(StorageAccess, MAX_SLOTS)),
        ('storage_reads', SSZList(StorageKey, MAX_SLOTS)),
        ('balance_changes', SSZList(BalanceChange, MAX_TXS)),
        ('nonce_changes', SSZList(NonceChange, MAX_TXS)),
        ('code_changes', SSZList(CodeChange, MAX_TXS)),
    ]

# =============================================================================
# BLOCK-LEVEL STRUCTURE
# =============================================================================

class BlockAccessList(Serializable):
    """
    Block Access List structure for latest EIP-7928.
    """
    fields = [
        ('account_changes', SSZList(AccountChanges, MAX_ACCOUNTS)),
    ]

# =============================================================================
# BUILDER FOR EFFICIENT CONSTRUCTION
# =============================================================================

class BALBuilder:
    """
    Builder for constructing BlockAccessList efficiently.
    Updated for latest EIP-7928 format.
    """
    
    def __init__(self):
        # address -> field_type -> changes
        self.accounts: Dict[bytes, Dict[str, PyList]] = {}
        
    def _ensure_account(self, address: bytes):
        """Ensure account exists in builder."""
        if address not in self.accounts:
            self.accounts[address] = {
                'storage_writes': {},  # slot -> [StorageChange]
                'storage_reads': set(), # set of slots  
                'balance_changes': [],  # [BalanceChange]
                'nonce_changes': [],    # [NonceChange]
                'code_changes': [],     # [CodeChange]
            }
    
    def add_storage_write(self, address: bytes, slot: bytes, tx_index: int, new_value: bytes):
        """Add storage write: address -> slot -> tx_index -> new_value"""
        self._ensure_account(address)
        
        if slot not in self.accounts[address]['storage_writes']:
            self.accounts[address]['storage_writes'][slot] = []
            
        change = StorageChange(tx_index=tx_index, new_value=new_value)
        self.accounts[address]['storage_writes'][slot].append(change)
    
    def add_storage_read(self, address: bytes, slot: bytes):
        """Add storage read: address -> slot (read-only)"""
        self._ensure_account(address)
        self.accounts[address]['storage_reads'].add(slot)
    
    def add_balance_change(self, address: bytes, tx_index: int, post_balance: bytes):
        """Add balance change: address -> balance -> tx_index -> post_balance (as bytes16)"""
        self._ensure_account(address)
        
        # Ensure balance is exactly 16 bytes
        if len(post_balance) != 16:
            raise ValueError(f"Balance must be exactly 16 bytes, got {len(post_balance)}")
            
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
        """Add an account that was touched but not changed"""
        self._ensure_account(address)
    
    def build(self, ignore_reads: bool = False) -> BlockAccessList:
        """Build the final BlockAccessList."""
        account_changes_list = []
        
        for address, changes in self.accounts.items():
            # Build storage writes
            storage_writes = []
            for slot, slot_changes in changes['storage_writes'].items():
                # Sort changes by tx_index for deterministic encoding
                sorted_changes = sorted(slot_changes, key=lambda x: x.tx_index)
                storage_writes.append(StorageAccess(slot=slot, changes=sorted_changes))
            
            # Build storage reads (only if not ignoring reads)
            storage_reads = []
            if not ignore_reads:
                for slot in changes['storage_reads']:
                    # Only include reads for slots that weren't written to
                    if slot not in changes['storage_writes']:
                        storage_reads.append(slot)
            
            # Sort all changes by tx_index for deterministic encoding
            balance_changes = sorted(changes['balance_changes'], key=lambda x: x.tx_index)
            nonce_changes = sorted(changes['nonce_changes'], key=lambda x: x.tx_index)
            code_changes = sorted(changes['code_changes'], key=lambda x: x.tx_index)
            
            # Create account changes object
            account_change = AccountChanges(
                address=address,
                storage_writes=storage_writes,
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
        if account.storage_writes:
            stats['accounts_with_storage_writes'] += 1
            for storage_access in account.storage_writes:
                stats['total_storage_writes'] += len(storage_access.changes)
        
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