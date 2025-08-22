#!/usr/bin/env python3
"""
Test script to verify the FDS Calculator method fix
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
project_root = Path(__file__).parent
sys.path.append(str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fds_webapp.settings')
django.setup()

def test_fds_calculator_methods():
    """Test that FDSCalculator has the correct methods"""
    print("🧪 Testing FDS Calculator Methods")
    print("=" * 50)
    
    try:
        # Import the FDS algorithm modules
        sys.path.append(str(project_root / "dev_productivity"))
        from fds_algorithm.fds_calculator import FDSCalculator
        
        print("✅ FDSCalculator imported successfully")
        
        # Create calculator instance
        calculator = FDSCalculator()
        print("✅ FDSCalculator instance created")
        
        # Check for correct methods
        expected_methods = [
            'calculate_contributions',
            'aggregate_contributions_by_author', 
            'calculate_detailed_metrics',
            'run_complete_analysis'
        ]
        
        missing_methods = []
        for method in expected_methods:
            if hasattr(calculator, method):
                print(f"✅ FDSCalculator.{method} exists")
            else:
                print(f"❌ FDSCalculator.{method} NOT found")
                missing_methods.append(method)
        
        # Check that incorrect methods don't exist
        incorrect_methods = [
            'calculate_individual_contributions',
            'calculate_final_scores'
        ]
        
        for method in incorrect_methods:
            if hasattr(calculator, method):
                print(f"⚠️  FDSCalculator.{method} still exists (should be removed/renamed)")
            else:
                print(f"✅ FDSCalculator.{method} correctly not found")
        
        if not missing_methods:
            print("\n🎉 All required FDS Calculator methods are available!")
            return True
        else:
            print(f"\n❌ Missing methods: {missing_methods}")
            return False
            
    except Exception as e:
        print(f"❌ FDSCalculator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_services_import():
    """Test that the services module can import FDS components correctly"""
    print("\n🧪 Testing Services Import")
    print("=" * 50)
    
    try:
        from dev_productivity.services import FDSAnalysisService
        print("✅ FDSAnalysisService imported successfully")
        
        # Try to create a service instance
        service = FDSAnalysisService()
        print("✅ FDSAnalysisService instance created")
        
        # Check if the service has the expected method
        if hasattr(service, '_run_fds_analysis'):
            print("✅ FDSAnalysisService._run_fds_analysis method exists")
        else:
            print("❌ FDSAnalysisService._run_fds_analysis method NOT found")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Services import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 Starting FDS Calculator Fix Tests")
    print("=" * 50)
    
    tests = [
        ("FDS Calculator Methods", test_fds_calculator_methods),
        ("Services Import", test_services_import),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🧪 FDS CALCULATOR FIX TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL FDS CALCULATOR TESTS PASSED! The fix is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)