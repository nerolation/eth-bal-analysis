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

from BALs import *


def convert_ssz_to_dict(obj) -> Any:
    """Convert SSZ objects to plain Python dictionaries/lists for RLP encoding."""
    if hasattr(obj, '_asdict'):
        # Handle SSZ Container objects
        result = {}
        for field_name, _ in obj.__class__.fields:
            field_value = getattr(obj, field_name)
            result[field_name] = convert_ssz_to_dict(field_value)
        return result
    elif isinstance(obj, list):
        # Handle SSZ Lists
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


def load_and_convert_bal(file_path: str) -> tuple[bytes, bytes, int, int]:
    """Load BAL from SSZ format and convert to RLP format.
    
    Returns:
        (ssz_encoded, rlp_encoded, ssz_size, rlp_size)
    """
    print(f"Processing {file_path}...")
    
    # Read the SSZ-encoded hex data
    with open(file_path, 'r') as f:
        ssz_hex = f.read().strip()
    
    # Convert hex to bytes
    ssz_data = bytes.fromhex(ssz_hex)
    
    # Decode SSZ to get the BlockAccessList object
    block_access_list = ssz.decode(ssz_data, sedes=BlockAccessList)
    
    # Convert SSZ object to plain Python data structure
    dict_data = convert_ssz_to_dict(block_access_list)
    
    # Convert to RLP-compatible list format
    rlp_data = dict_to_rlp_list(dict_data)
    
    # Encode with RLP
    rlp_encoded = rlp.encode(rlp_data)
    
    return ssz_data, rlp_encoded, len(ssz_data), len(rlp_encoded)


def main():
    parser = argparse.ArgumentParser(description='Convert BALs from SSZ to RLP format for size comparison')
    parser.add_argument('--input-dir', default=os.path.join(project_root, 'bal_raw'),
                        help='Directory containing SSZ BAL files (default: ../bal_raw)')
    parser.add_argument('--output-dir', default=os.path.join(project_root, 'bal_rlp'),
                        help='Directory to save RLP BAL files (default: ../bal_rlp)')
    parser.add_argument('--pattern', default='*_block_access_list_*.txt',
                        help='File pattern to match (default: *_block_access_list_*.txt)')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Find all BAL files
    pattern = os.path.join(args.input_dir, args.pattern)
    bal_files = glob.glob(pattern)
    
    if not bal_files:
        print(f"No BAL files found matching pattern: {pattern}")
        return
    
    print(f"Found {len(bal_files)} BAL files to process")
    
    # Process each file and collect size statistics
    results = []
    total_ssz_size = 0
    total_rlp_size = 0
    
    for file_path in sorted(bal_files):
        try:
            ssz_data, rlp_data, ssz_size, rlp_size = load_and_convert_bal(file_path)
            
            # Create output filename
            filename = os.path.basename(file_path)
            rlp_filename = filename.replace('.txt', '_rlp.txt')
            rlp_path = os.path.join(args.output_dir, rlp_filename)
            
            # Save RLP-encoded data
            with open(rlp_path, 'w') as f:
                f.write(rlp_data.hex())
            
            # Collect statistics
            compression_ratio = rlp_size / ssz_size if ssz_size > 0 else 0
            results.append({
                'file': filename,
                'ssz_size': ssz_size,
                'rlp_size': rlp_size,
                'compression_ratio': compression_ratio,
                'size_diff': rlp_size - ssz_size
            })
            
            total_ssz_size += ssz_size
            total_rlp_size += rlp_size
            
            print(f"  {filename}: SSZ={ssz_size}B, RLP={rlp_size}B, ratio={compression_ratio:.3f}")
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue
    
    # Print summary statistics
    print(f"\n=== Summary ===")
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
    
    # Save detailed results to JSON
    results_file = os.path.join(args.output_dir, 'size_comparison.json')
    with open(results_file, 'w') as f:
        json.dump({
            'summary': {
                'files_processed': len(results),
                'total_ssz_size': total_ssz_size,
                'total_rlp_size': total_rlp_size,
                'overall_ratio': total_rlp_size/total_ssz_size if total_ssz_size > 0 else 0,
                'size_difference': total_rlp_size - total_ssz_size
            },
            'per_file_results': results
        }, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")
    print(f"RLP files saved to: {args.output_dir}")


if __name__ == "__main__":
    main()