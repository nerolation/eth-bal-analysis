import os
import sys
import glob
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

import ssz
import rlp
from rlp.sedes import Serializable, big_endian_int, binary

# Add project paths
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

# Fix for SSZ ByteList compatibility issue
from ssz.sedes.byte_list import ByteList
def fixed_get_sedes_id(self):
    """Fixed version that uses max_length instead of length"""
    return f"{self.__class__.__name__}{self.max_length}"

# Monkey patch the ByteList class
ByteList.get_sedes_id = fixed_get_sedes_id

from BALs_ssz_optimized_reads import *


def convert_ssz_to_dict(obj) -> Any:
    """Convert SSZ objects to plain Python dictionaries/lists for RLP encoding."""
    # Handle SSZ Container objects (like BlockAccessList, AccountWrites, etc.)
    if hasattr(obj, '__class__') and hasattr(obj.__class__, 'fields'):
        result = {}
        for field_name, _ in obj.__class__.fields:
            field_value = getattr(obj, field_name)
            result[field_name] = convert_ssz_to_dict(field_value)
        return result
    # Handle SSZ Lists (both List and ByteList)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        return [convert_ssz_to_dict(item) for item in obj]
    elif isinstance(obj, bytes):
        # Keep bytes as-is for RLP
        return obj
    elif isinstance(obj, int):
        # Keep integers as-is
        return obj
    else:
        # For primitive types, return as-is
        return obj


def dict_to_rlp_list(data: Dict[str, Any]) -> List[Any]:
    """Convert dictionary to list format for RLP encoding.
    
    Order matters for RLP, so we need consistent field ordering.
    """
    if isinstance(data, dict):
        # Convert dict to list based on field order
        return [dict_to_rlp_list(value) for value in data.values()]
    elif isinstance(data, list):
        return [dict_to_rlp_list(item) for item in data]
    else:
        return data


def load_and_convert_bal_optimized(file_path: str) -> tuple[bytes, bytes, int, int]:
    """Load optimized BAL from SSZ format and convert to RLP format.
    
    Returns:
        (ssz_encoded, rlp_encoded, ssz_size, rlp_size)
    """
    print(f"Processing {file_path}...")
    
    try:
        # Read the SSZ-encoded hex data
        with open(file_path, 'r') as f:
            ssz_hex = f.read().strip()
        
        # Convert hex to bytes
        ssz_data = bytes.fromhex(ssz_hex)
        
        # Decode SSZ to get the optimized BlockAccessList object
        block_access_list = ssz.decode(ssz_data, sedes=BlockAccessList)
        
        # Convert SSZ object to plain Python data structure
        dict_data = convert_ssz_to_dict(block_access_list)
        
        # Convert to RLP-compatible list format
        rlp_data = dict_to_rlp_list(dict_data)
        
        # Encode with RLP
        rlp_encoded = rlp.encode(rlp_data)
        
        return ssz_data, rlp_encoded, len(ssz_data), len(rlp_encoded)
        
    except Exception as e:
        print(f"Debug info for {file_path}:")
        print(f"  Error: {e}")
        print(f"  Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        raise


def analyze_optimized_structure(file_path: str) -> Dict[str, Any]:
    """Analyze the optimized BAL structure to understand size breakdown."""
    try:
        # Read the SSZ-encoded hex data
        with open(file_path, 'r') as f:
            ssz_hex = f.read().strip()
        
        # Convert hex to bytes
        ssz_data = bytes.fromhex(ssz_hex)
        
        # Decode SSZ to get the optimized BlockAccessList object
        block_access_list = ssz.decode(ssz_data, sedes=BlockAccessList)
        
        # Analyze component sizes
        storage_writes_encoded = ssz.encode(block_access_list.storage_writes, sedes=AccountWritesList)
        storage_reads_encoded = ssz.encode(block_access_list.storage_reads, sedes=AccountReadsList)
        balance_diffs_encoded = ssz.encode(block_access_list.balance_diffs, sedes=BalanceDiffs)
        code_diffs_encoded = ssz.encode(block_access_list.code_diffs, sedes=CodeDiffs)
        nonce_diffs_encoded = ssz.encode(block_access_list.nonce_diffs, sedes=NonceDiffs)
        
        # Count elements
        num_write_accounts = len(block_access_list.storage_writes)
        num_read_accounts = len(block_access_list.storage_reads)
        num_balance_accounts = len(block_access_list.balance_diffs)
        num_code_accounts = len(block_access_list.code_diffs)
        num_nonce_accounts = len(block_access_list.nonce_diffs)
        
        # Count total slots
        total_write_slots = sum(len(acc.slot_writes) for acc in block_access_list.storage_writes)
        total_read_slots = sum(len(acc.slot_reads) for acc in block_access_list.storage_reads)
        
        return {
            'total_size': len(ssz_data),
            'component_sizes': {
                'storage_writes': len(storage_writes_encoded),
                'storage_reads': len(storage_reads_encoded),
                'balance_diffs': len(balance_diffs_encoded),
                'code_diffs': len(code_diffs_encoded),
                'nonce_diffs': len(nonce_diffs_encoded)
            },
            'counts': {
                'write_accounts': num_write_accounts,
                'read_accounts': num_read_accounts,
                'balance_accounts': num_balance_accounts,
                'code_accounts': num_code_accounts,
                'nonce_accounts': num_nonce_accounts,
                'total_write_slots': total_write_slots,
                'total_read_slots': total_read_slots
            }
        }
        
    except Exception as e:
        print(f"Error analyzing {file_path}: {e}")
        return {}


def main():
    parser = argparse.ArgumentParser(description='Convert optimized BALs from SSZ to RLP format for size comparison')
    parser.add_argument('--input-dir', default=os.path.join(project_root, 'bal_raw'),
                        help='Directory containing SSZ BAL files (default: ../bal_raw)')
    parser.add_argument('--output-dir', default=os.path.join(project_root, 'bal_rlp_optimized'),
                        help='Directory to save RLP BAL files (default: ../bal_rlp_optimized)')
    parser.add_argument('--pattern', default='*_block_access_list_optimized_*.txt',
                        help='File pattern to match (default: *_block_access_list_optimized_*.txt)')
    parser.add_argument('--analyze', action='store_true',
                        help='Perform detailed analysis of optimized structure')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Find all optimized BAL files
    pattern = os.path.join(args.input_dir, args.pattern)
    bal_files = glob.glob(pattern)
    
    if not bal_files:
        print(f"No optimized BAL files found matching pattern: {pattern}")
        return
    
    print(f"Found {len(bal_files)} optimized BAL files to process")
    
    # Process each file and collect size statistics
    results = []
    analysis_results = []
    total_ssz_size = 0
    total_rlp_size = 0
    
    for file_path in sorted(bal_files):
        try:
            ssz_data, rlp_data, ssz_size, rlp_size = load_and_convert_bal_optimized(file_path)
            
            # Create output filename
            filename = os.path.basename(file_path)
            rlp_filename = filename.replace('.txt', '_rlp.txt')
            rlp_path = os.path.join(args.output_dir, rlp_filename)
            
            # Save RLP-encoded data
            with open(rlp_path, 'w') as f:
                f.write(rlp_data.hex())
            
            # Collect statistics
            compression_ratio = rlp_size / ssz_size if ssz_size > 0 else 0
            result = {
                'file': filename,
                'ssz_size': ssz_size,
                'rlp_size': rlp_size,
                'compression_ratio': compression_ratio,
                'size_diff': rlp_size - ssz_size
            }
            
            # Perform detailed analysis if requested
            if args.analyze:
                analysis = analyze_optimized_structure(file_path)
                if analysis:
                    result['analysis'] = analysis
                    analysis_results.append({
                        'file': filename,
                        **analysis
                    })
            
            results.append(result)
            
            total_ssz_size += ssz_size
            total_rlp_size += rlp_size
            
            print(f"  {filename}: SSZ={ssz_size}B, RLP={rlp_size}B, ratio={compression_ratio:.3f}")
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    # Print summary statistics
    print(f"\n=== Optimized BAL Summary ===")
    print(f"Files processed: {len(results)}")
    print(f"Total SSZ size: {total_ssz_size:,} bytes")
    print(f"Total RLP size: {total_rlp_size:,} bytes")
    print(f"Overall RLP/SSZ ratio: {total_rlp_size/total_ssz_size:.3f}")
    print(f"Size difference: {total_rlp_size - total_ssz_size:+,} bytes")
    
    if total_rlp_size < total_ssz_size:
        savings = total_ssz_size - total_rlp_size
        print(f"RLP saves {savings:,} bytes ({savings/total_ssz_size*100:.1f}%)")
    else:
        overhead = total_rlp_size - total_ssz_size
        print(f"RLP adds {overhead:,} bytes overhead ({overhead/total_ssz_size*100:.1f}%)")
    
    # Print analysis summary if available
    if analysis_results:
        print(f"\n=== Structure Analysis ===")
        avg_write_accounts = sum(a['counts']['write_accounts'] for a in analysis_results) / len(analysis_results)
        avg_read_accounts = sum(a['counts']['read_accounts'] for a in analysis_results) / len(analysis_results)
        avg_write_slots = sum(a['counts']['total_write_slots'] for a in analysis_results) / len(analysis_results)
        avg_read_slots = sum(a['counts']['total_read_slots'] for a in analysis_results) / len(analysis_results)
        
        print(f"Average write accounts per block: {avg_write_accounts:.1f}")
        print(f"Average read accounts per block: {avg_read_accounts:.1f}")
        print(f"Average write slots per block: {avg_write_slots:.1f}")
        print(f"Average read slots per block: {avg_read_slots:.1f}")
        
        # Component size breakdown
        total_components = {}
        for analysis in analysis_results:
            for component, size in analysis['component_sizes'].items():
                total_components[component] = total_components.get(component, 0) + size
        
        print(f"\n=== Component Size Breakdown ===")
        for component, total_size in total_components.items():
            percentage = (total_size / total_ssz_size) * 100
            print(f"{component}: {total_size:,} bytes ({percentage:.1f}%)")
    
    # Save detailed results to JSON
    results_file = os.path.join(args.output_dir, 'size_comparison_optimized.json')
    output_data = {
        'summary': {
            'files_processed': len(results),
            'total_ssz_size': total_ssz_size,
            'total_rlp_size': total_rlp_size,
            'overall_ratio': total_rlp_size/total_ssz_size if total_ssz_size > 0 else 0,
            'size_difference': total_rlp_size - total_ssz_size
        },
        'per_file_results': results
    }
    
    if analysis_results:
        output_data['structure_analysis'] = analysis_results
        output_data['summary']['component_totals'] = total_components
    
    with open(results_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    print(f"RLP files saved to: {args.output_dir}")


if __name__ == "__main__":
    main()