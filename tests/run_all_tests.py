#!/usr/bin/env python3
"""
Comprehensive test runner for all BAL tests.
Runs all test suites and generates a summary report.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import importlib.util

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

def load_and_run_test_module(module_path: str, module_name: str) -> tuple[bool, dict]:
    """Load a test module and run its tests."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # Call main function
        if hasattr(module, 'main'):
            success = module.main()
            return success, {"success": success, "error": None}
        else:
            return False, {"success": False, "error": "No main() function found"}
            
    except Exception as e:
        return False, {"success": False, "error": str(e)}

def main():
    """Main test runner."""
    print("🧪 Comprehensive BAL Test Suite Runner")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Define test modules
    test_modules = [
        ("test_data_structure_integrity.py", "Data Structure Integrity"),
        ("test_builder_functionality.py", "Builder Functionality"), 
        ("test_ssz_encoding.py", "SSZ Encoding/Decoding"),
        ("test_real_world_integration.py", "Real-World Integration"),
    ]
    
    test_dir = Path(__file__).parent
    results = {}
    overall_success = True
    
    # Run each test module
    for test_file, test_name in test_modules:
        test_path = test_dir / test_file
        
        print(f"📋 Running {test_name}...")
        print("-" * 60)
        
        if not test_path.exists():
            print(f"❌ Test file not found: {test_file}")
            results[test_name] = {"success": False, "error": "File not found"}
            overall_success = False
            continue
        
        success, result = load_and_run_test_module(str(test_path), test_file[:-3])
        results[test_name] = result
        
        if not success:
            overall_success = False
        
        print()
    
    # Generate summary report
    print("📊 TEST SUMMARY REPORT")
    print("=" * 80)
    
    passed_tests = 0
    total_tests = len(test_modules)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result["success"] else "❌ FAILED"
        print(f"{status:<12} {test_name}")
        
        if not result["success"] and result["error"]:
            print(f"             Error: {result['error']}")
        
        if result["success"]:
            passed_tests += 1
    
    print("-" * 80)
    print(f"Overall Result: {passed_tests}/{total_tests} test suites passed")
    
    if overall_success:
        print("🎉 ALL TEST SUITES PASSED!")
        print()
        print("Your BAL implementation is working correctly with:")
        print("  ✅ Address uniqueness enforced")
        print("  ✅ Storage key uniqueness per address")
        print("  ✅ Proper sorting of all components")
        print("  ✅ Data structure integrity maintained")
        print("  ✅ Builder functionality working correctly")
        print("  ✅ SSZ encoding/decoding operational")
        print("  ✅ Real-world integration successful")
    else:
        print("⚠️  SOME TEST SUITES FAILED")
        print("Please review the failed tests above and fix any issues.")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)