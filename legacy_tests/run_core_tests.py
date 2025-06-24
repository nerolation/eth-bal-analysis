#!/usr/bin/env python3
"""
Comprehensive test runner for core BAL implementations.
Runs all tests for RLP vs SSZ core implementations and generates a summary report.
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add src directory to path
project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

def run_import_tests():
    """Test that all core modules can be imported."""
    print("🔍 Running Import Tests...")
    print("-" * 40)
    
    tests_passed = 0
    tests_total = 6
    
    # Test SSZ imports
    try:
        from BALs import *
        print("  ✅ BALs.py (SSZ structures)")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ BALs.py failed: {e}")
    
    try:
        from bal_builder import *
        print("  ✅ bal_builder.py (SSZ builder)")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ bal_builder.py failed: {e}")
    
    # Test RLP imports
    try:
        from BALs_rlp import *
        print("  ✅ BALs_rlp.py (RLP structures)")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ BALs_rlp.py failed: {e}")
    
    try:
        from bal_builder_rlp import *
        print("  ✅ bal_builder_rlp.py (RLP builder)")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ bal_builder_rlp.py failed: {e}")
    
    # Test helpers
    try:
        from helpers import *
        print("  ✅ helpers.py")
        tests_passed += 1
    except Exception as e:
        print(f"  ❌ helpers.py failed: {e}")
    
    # Test existence of __init__.py
    init_file = os.path.join(src_dir, "__init__.py")
    if os.path.exists(init_file):
        print("  ✅ __init__.py exists")
        tests_passed += 1
    else:
        print("  ❌ __init__.py missing")
    
    print(f"\nImport Tests: {tests_passed}/{tests_total} passed")
    return tests_passed, tests_total

def run_structure_tests():
    """Run structure creation and validation tests."""
    print("\n🔍 Running Structure Tests...")
    print("-" * 40)
    
    try:
        # Import and run the structure tests
        from test_core_implementations import test_ssz_structures, test_rlp_structures, test_helper_functions
        
        tests_passed = 0
        tests_total = 3
        
        if test_ssz_structures():
            tests_passed += 1
        
        if test_rlp_structures():
            tests_passed += 1
            
        if test_helper_functions():
            tests_passed += 1
        
        print(f"\nStructure Tests: {tests_passed}/{tests_total} passed")
        return tests_passed, tests_total
        
    except Exception as e:
        print(f"❌ Structure tests failed to run: {e}")
        return 0, 3

def run_builder_tests():
    """Run builder functionality tests."""
    print("\n🔍 Running Builder Tests...")
    print("-" * 40)
    
    try:
        from test_core_builders import run_builder_tests
        
        passed_tests, total_tests, edge_passed, edge_failed = run_builder_tests()
        
        print(f"\nBuilder Tests: {passed_tests}/{total_tests} main tests passed")
        print(f"Edge Cases: {edge_passed} passed, {edge_failed} failed")
        
        return passed_tests, total_tests, edge_passed, edge_failed
        
    except Exception as e:
        print(f"❌ Builder tests failed to run: {e}")
        return 0, 4, 0, 2

def run_performance_tests():
    """Run performance comparison tests."""
    print("\n🔍 Running Performance Tests...")
    print("-" * 40)
    
    try:
        from test_core_performance import run_performance_tests
        
        results = run_performance_tests()
        
        # Count successful performance tests
        successful_comparisons = sum(1 for r in results.values() if r['ssz'] and r['rlp'])
        total_scenarios = len(results)
        
        print(f"\nPerformance Tests: {successful_comparisons}/{total_scenarios} scenarios completed")
        
        return successful_comparisons, total_scenarios, results
        
    except Exception as e:
        print(f"❌ Performance tests failed to run: {e}")
        return 0, 3, {}

def check_file_organization():
    """Check that files are properly organized."""
    print("\n🔍 Checking File Organization...")
    print("-" * 40)
    
    checks_passed = 0
    checks_total = 6
    
    # Check core files exist in src/
    core_files = [
        "BALs.py",
        "BALs_rlp.py", 
        "bal_builder.py",
        "bal_builder_rlp.py",
        "helpers.py"
    ]
    
    for filename in core_files:
        filepath = os.path.join(src_dir, filename)
        if os.path.exists(filepath):
            print(f"  ✅ {filename} in src/")
            checks_passed += 1
        else:
            print(f"  ❌ {filename} missing from src/")
    
    # Check test_optimizations directory exists
    test_opt_dir = os.path.join(project_root, "test_optimizations")
    if os.path.exists(test_opt_dir):
        print(f"  ✅ test_optimizations/ directory exists")
        checks_passed += 1
    else:
        print(f"  ❌ test_optimizations/ directory missing")
    
    print(f"\nFile Organization: {checks_passed}/{checks_total} checks passed")
    return checks_passed, checks_total

def generate_test_report(results):
    """Generate a comprehensive test report."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "test_summary": results,
        "recommendations": []
    }
    
    # Calculate overall success rate
    total_passed = sum(r.get('passed', 0) for r in results.values())
    total_tests = sum(r.get('total', 0) for r in results.values())
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    
    report["overall_success_rate"] = success_rate
    
    # Add recommendations based on results
    if success_rate >= 90:
        report["recommendations"].append("✅ All core systems functioning well")
    elif success_rate >= 70:
        report["recommendations"].append("⚠️ Some issues detected - review failed tests")
    else:
        report["recommendations"].append("❌ Significant issues detected - requires attention")
    
    # Check specific issues
    if results.get('imports', {}).get('passed', 0) < results.get('imports', {}).get('total', 1):
        report["recommendations"].append("🔧 Fix import issues before proceeding")
    
    if results.get('structures', {}).get('passed', 0) < results.get('structures', {}).get('total', 1):
        report["recommendations"].append("🏗️ Structure definitions need attention")
    
    if results.get('builders', {}).get('passed', 0) < results.get('builders', {}).get('total', 1):
        report["recommendations"].append("⚙️ Builder implementations need fixes")
    
    return report

def main():
    """Run all core tests and generate summary."""
    print("🚀 CORE BAL IMPLEMENTATION TEST SUITE")
    print("=" * 80)
    print(f"Testing core RLP vs SSZ implementations in src/")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    results = {}
    
    # Run all test suites
    import_passed, import_total = run_import_tests()
    results['imports'] = {'passed': import_passed, 'total': import_total}
    
    structure_passed, structure_total = run_structure_tests()
    results['structures'] = {'passed': structure_passed, 'total': structure_total}
    
    builder_passed, builder_total, edge_passed, edge_failed = run_builder_tests()
    results['builders'] = {
        'passed': builder_passed, 
        'total': builder_total,
        'edge_passed': edge_passed,
        'edge_failed': edge_failed
    }
    
    perf_passed, perf_total, perf_results = run_performance_tests()
    results['performance'] = {
        'passed': perf_passed, 
        'total': perf_total,
        'results': perf_results
    }
    
    org_passed, org_total = check_file_organization()
    results['organization'] = {'passed': org_passed, 'total': org_total}
    
    # Generate final report
    print("\n" + "=" * 80)
    print("📊 FINAL TEST SUMMARY")
    print("=" * 80)
    
    total_passed = 0
    total_tests = 0
    
    for test_category, test_results in results.items():
        if test_category == 'performance':
            continue  # Handle performance separately
            
        passed = test_results['passed']
        total = test_results['total']
        percentage = (passed / total * 100) if total > 0 else 0
        
        total_passed += passed
        total_tests += total
        
        status = "✅" if percentage >= 80 else "⚠️" if percentage >= 60 else "❌"
        print(f"{status} {test_category.title():15}: {passed:2d}/{total:2d} ({percentage:5.1f}%)")
    
    # Handle performance separately
    perf = results['performance']
    perf_percentage = (perf['passed'] / perf['total'] * 100) if perf['total'] > 0 else 0
    perf_status = "✅" if perf_percentage >= 80 else "⚠️" if perf_percentage >= 60 else "❌"
    print(f"{perf_status} Performance     : {perf['passed']:2d}/{perf['total']:2d} ({perf_percentage:5.1f}%)")
    
    overall_percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
    overall_status = "✅" if overall_percentage >= 80 else "⚠️" if overall_percentage >= 60 else "❌"
    
    print("-" * 50)
    print(f"{overall_status} Overall         : {total_passed:2d}/{total_tests:2d} ({overall_percentage:5.1f}%)")
    
    # Key findings
    print(f"\n🔍 Key Findings:")
    
    if results['imports']['passed'] == results['imports']['total']:
        print("  ✅ All core modules import successfully")
    else:
        print("  ❌ Some core modules have import issues")
    
    if results['builders']['passed'] >= 2:  # At least SSZ and RLP builders work
        print("  ✅ Both RLP and SSZ builders are functional")
    else:
        print("  ❌ Builder implementations have issues")
    
    if perf['passed'] > 0:
        print("  ✅ Performance comparison tests completed")
        
        # Analyze performance results if available
        if perf['results']:
            successful_scenarios = [r for r in perf['results'].values() if r['ssz'] and r['rlp']]
            if successful_scenarios:
                avg_ssz_size = sum(r['ssz']['total_size'] for r in successful_scenarios) / len(successful_scenarios)
                avg_rlp_size = sum(r['rlp']['total_size'] for r in successful_scenarios) / len(successful_scenarios)
                ratio = avg_ssz_size / avg_rlp_size
                
                if ratio > 1:
                    print(f"  📈 SSZ is {((ratio - 1) * 100):.1f}% larger than RLP on average")
                else:
                    print(f"  📉 RLP is {((1 - ratio) * 100):.1f}% larger than SSZ on average")
    else:
        print("  ❌ Performance comparison tests failed")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    
    if overall_percentage >= 90:
        print("  🎉 Excellent! Core implementations are working well.")
        print("  ➡️  Ready for production testing with real blockchain data.")
    elif overall_percentage >= 70:
        print("  ⚠️  Core implementations mostly working but need attention.")
        print("  ➡️  Fix failing tests before deploying to production.")
    else:
        print("  🚨 Significant issues detected in core implementations.")
        print("  ➡️  Review and fix critical issues before proceeding.")
    
    if results['organization']['passed'] == results['organization']['total']:
        print("  ✅ File organization is correct - core files in src/, optimizations moved.")
    
    # Save report to file
    report = generate_test_report(results)
    report_filename = f"core_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    try:
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Detailed report saved to: {report_filename}")
    except Exception as e:
        print(f"\n❌ Failed to save report: {e}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    main()