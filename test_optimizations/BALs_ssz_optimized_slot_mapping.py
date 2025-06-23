import os
import pandas as pd
import json
from collections import defaultdict
from typing import List as PyList, Optional, Dict

import ssz
from ssz import Serializable
from ssz.sedes import ByteVector, ByteList, uint16, uint64, List as SSZList, uint8, uint32
from eth_utils import to_canonical_address

# Constants; chosen to support a 630m block gas limit
MAX_TXS = 30_000
MAX_SLOTS = 300_000
MAX_ACCOUNTS = 300_000
MAX_CODE_SIZE = 24_576  # Maximum contract bytecode size in bytes
MAX_UNIQUE_SLOTS = 65_535  # Maximum number of unique storage slots per block
MAX_UNIQUE_ADDRESSES = 65_535  # Maximum number of unique addresses per block

# SSZ type aliases
Address = ByteVector(20)
StorageKey = ByteVector(32) 
StorageValue = ByteVector(32)
TxIndex = uint16
BalanceDelta = ByteVector(12)
Nonce = uint64
CodeData = ByteList(MAX_CODE_SIZE)
SlotIndex = uint16  # Index into the slot mapping table (0-65535)
AddressIndex = uint16  # Index into the address mapping table (0-65535)

def parse_hex_or_zero(x):
    if pd.isna(x) or x is None:
        return 0
    return int(x, 16)


# Address mapping structure - maps address indices to actual addresses
class AddressMapping(Serializable):
    fields = [
        ('addresses', SSZList(Address, MAX_UNIQUE_ADDRESSES)),  # Array of unique addresses
    ]

# Slot mapping structure - maps slot indices to actual storage keys
class SlotMapping(Serializable):
    fields = [
        ('slots', SSZList(StorageKey, MAX_UNIQUE_SLOTS)),  # Array of unique storage slots
    ]


# Storage Write structures (using slot indices instead of full keys)
class PerTxWriteIndexed(Serializable):
    fields = [
        ('tx_index', TxIndex),
        ('value_after', StorageValue),
    ]

class SlotWriteIndexed(Serializable):
    fields = [
        ('slot_index', SlotIndex),  # Index into the slot mapping
        ('writes', SSZList(PerTxWriteIndexed, MAX_TXS)),
    ]

class AccountWritesIndexed(Serializable):
    fields = [
        ('address_index', AddressIndex),  # Index into address mapping instead of full address
        ('slot_writes', SSZList(SlotWriteIndexed, MAX_SLOTS)),
    ]

AccountWritesIndexedList = SSZList(AccountWritesIndexed, MAX_ACCOUNTS)

# Storage Read structures (using slot indices)
class SlotReadIndexed(Serializable):
    fields = [
        ('slot_index', SlotIndex),  # Index into the slot mapping
    ]

class AccountReadsIndexed(Serializable):
    fields = [
        ('address_index', AddressIndex),  # Index into address mapping instead of full address
        ('slot_reads', SSZList(SlotReadIndexed, MAX_SLOTS)),
    ]

AccountReadsIndexedList = SSZList(AccountReadsIndexed, MAX_ACCOUNTS)

def estimate_size_bytes(obj):
    return len(json.dumps(obj).encode('utf-8'))


class SlotValue(Serializable):
    fields = [
        ('slot', StorageKey),
        ('value', StorageValue),
    ]

class AccountStorage(Serializable):
    fields = [
        ('address', Address),
        ('slots', SSZList(SlotValue, MAX_SLOTS)),
    ]

PostBlockStorage = SSZList(AccountStorage, MAX_ACCOUNTS)


# BALANCE DIFF (unchanged from original)

class BalanceChange(Serializable):
    fields = [
        ("tx_index", TxIndex),
        ("delta", BalanceDelta),
    ]

class AccountBalanceDiff(Serializable):
    fields = [
        ("address_index", AddressIndex),  # Index into address mapping instead of full address
        ("changes", SSZList(BalanceChange, MAX_TXS)),
    ]

BalanceDiffs = SSZList(AccountBalanceDiff, MAX_ACCOUNTS)

# NONCE DIFF (unchanged from original)
class TxNonceDiff(Serializable):
    fields = [
        ("tx_index", TxIndex),
        ("nonce_after", Nonce),  # nonce value after transaction execution
    ]

class AccountNonceDiff(Serializable):
    fields = [
        ("address_index", AddressIndex),  # Index into address mapping instead of full address
        ("changes", SSZList(TxNonceDiff, MAX_TXS)),
    ]

NonceDiffs = SSZList(AccountNonceDiff, MAX_TXS)


class CodeChange(Serializable):
    fields = [
        ('tx_index', TxIndex),
        ('new_code', CodeData),
    ]

class AccountCodeDiff(Serializable):
    fields = [
        ("address_index", AddressIndex),  # Index into address mapping instead of full address
        ("change", CodeChange),
    ]

CodeDiffs = SSZList(AccountCodeDiff, MAX_ACCOUNTS)


# Optimized BlockAccessList with both address and slot mapping
class BlockAccessListOptimizedMappings(Serializable):
    fields = [
        ('address_mapping', AddressMapping),  # Global address mapping for the block
        ('slot_mapping', SlotMapping),  # Global slot mapping for the block
        ('storage_writes', AccountWritesIndexedList),
        ('storage_reads', AccountReadsIndexedList),
        ('balance_diffs', BalanceDiffs),
        ('code_diffs', CodeDiffs),
        ('nonce_diffs', NonceDiffs),
    ]


class AddressIndexManager:
    """
    Manages the mapping between addresses and their indices.
    Provides efficient lookups and ensures unique address assignment.
    """
    
    def __init__(self):
        self.address_to_index: Dict[str, int] = {}  # address_hex -> index
        self.index_to_address: Dict[int, str] = {}  # index -> address_hex
        self.next_index = 0
    
    def get_or_create_index(self, address_hex: str) -> int:
        """
        Get the index for an address, creating a new one if needed.
        
        Args:
            address_hex: Address as hex string (with or without 0x prefix)
        
        Returns:
            The index for this address
        """
        # Normalize the address hex (ensure lowercase, with 0x prefix)
        if not address_hex.startswith('0x'):
            address_hex = '0x' + address_hex
        address_hex = address_hex.lower()
        
        if address_hex in self.address_to_index:
            return self.address_to_index[address_hex]
        
        if self.next_index >= MAX_UNIQUE_ADDRESSES:
            raise ValueError(f"Too many unique addresses in block: {self.next_index} >= {MAX_UNIQUE_ADDRESSES}")
        
        index = self.next_index
        self.address_to_index[address_hex] = index
        self.index_to_address[index] = address_hex
        self.next_index += 1
        
        return index
    
    def get_index(self, address_hex: str) -> Optional[int]:
        """Get the index for an address if it exists, None otherwise."""
        if not address_hex.startswith('0x'):
            address_hex = '0x' + address_hex
        address_hex = address_hex.lower()
        return self.address_to_index.get(address_hex)
    
    def get_address(self, index: int) -> Optional[str]:
        """Get the address hex for an index if it exists, None otherwise."""
        return self.index_to_address.get(index)
    
    def get_address_mapping(self) -> AddressMapping:
        """Create the SSZ AddressMapping structure."""
        addresses = []
        for i in range(self.next_index):
            address_hex = self.index_to_address[i]
            # Convert hex string to 20-byte address
            address_bytes = bytes.fromhex(address_hex[2:].zfill(40))  # Remove 0x and pad to 40 chars
            addresses.append(address_bytes)
        
        return AddressMapping(addresses=addresses)
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about address usage."""
        return {
            'unique_addresses': self.next_index,
            'bytes_saved_per_reference': 20 - 2,  # 20 bytes address -> 2 bytes index
            'total_references_needed': len(self.address_to_index),  # This would be calculated by the caller
        }


class SlotIndexManager:
    """
    Manages the mapping between storage slots and their indices.
    Provides efficient lookups and ensures unique slot assignment.
    """
    
    def __init__(self):
        self.slot_to_index: Dict[str, int] = {}  # slot_hex -> index
        self.index_to_slot: Dict[int, str] = {}  # index -> slot_hex
        self.next_index = 0
    
    def get_or_create_index(self, slot_hex: str) -> int:
        """
        Get the index for a storage slot, creating a new one if needed.
        
        Args:
            slot_hex: Storage slot as hex string (with or without 0x prefix)
        
        Returns:
            The index for this slot
        """
        # Normalize the slot hex (ensure lowercase, with 0x prefix)
        if not slot_hex.startswith('0x'):
            slot_hex = '0x' + slot_hex
        slot_hex = slot_hex.lower()
        
        if slot_hex in self.slot_to_index:
            return self.slot_to_index[slot_hex]
        
        if self.next_index >= MAX_UNIQUE_SLOTS:
            raise ValueError(f"Too many unique slots in block: {self.next_index} >= {MAX_UNIQUE_SLOTS}")
        
        index = self.next_index
        self.slot_to_index[slot_hex] = index
        self.index_to_slot[index] = slot_hex
        self.next_index += 1
        
        return index
    
    def get_index(self, slot_hex: str) -> Optional[int]:
        """Get the index for a slot if it exists, None otherwise."""
        if not slot_hex.startswith('0x'):
            slot_hex = '0x' + slot_hex
        slot_hex = slot_hex.lower()
        return self.slot_to_index.get(slot_hex)
    
    def get_slot(self, index: int) -> Optional[str]:
        """Get the slot hex for an index if it exists, None otherwise."""
        return self.index_to_slot.get(index)
    
    def get_slot_mapping(self) -> SlotMapping:
        """Create the SSZ SlotMapping structure."""
        slots = []
        for i in range(self.next_index):
            slot_hex = self.index_to_slot[i]
            # Convert hex string to 32-byte storage key
            slot_bytes = bytes.fromhex(slot_hex[2:].zfill(64))  # Remove 0x and pad to 64 chars
            slots.append(slot_bytes)
        
        return SlotMapping(slots=slots)
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about slot usage."""
        return {
            'unique_slots': self.next_index,
            'bytes_saved_per_reference': 32 - 2,  # 32 bytes slot -> 2 bytes index
            'total_references_needed': len(self.slot_to_index),  # This would be calculated by the caller
        }


def hex_to_bytes32(hex_str: str) -> bytes:
    """Convert a hex string to 32-byte storage key."""
    if hex_str.startswith('0x'):
        hex_str = hex_str[2:]
    return bytes.fromhex(hex_str.zfill(64))