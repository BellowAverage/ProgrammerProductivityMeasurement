#!/usr/bin/env python3
"""
Test script to verify the fixes for DataProcessor and imports
"""

import os
import sys
import django
from pathlib import Path

# Add the Django project to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fds_webapp.settings')
django.setup()

def test_imports():
    """Test that all required modules can be imported"""
    print("🔍 Testing imports...")
    
    try:
        from dev_productivity.models import FDSAnalysis
        print("✅ Models import successful")
    except Exception as e:
        print(f"❌ Models import failed: {e}")
        return False
    
    try:
        from dev_productivity.views import delete_analysis
        print("✅ Views import successful")
    except Exception as e:
        print(f"❌ Views import failed: {e}")
        return False
    
    try:
        sys.path.append(str(project_root / "dev_productivity"))
        from fds_algorithm.preprocessing.data_processor import DataProcessor
        print("✅ DataProcessor import successful")
    except Exception as e:
        print(f"❌ DataProcessor import failed: {e}")
        return False
    
    try:
        from torque_clustering.run_torque import torque_cluster
        print("✅ TORQUE clustering import successful")
    except Exception as e:
        print(f"❌ TORQUE clustering import failed: {e}")
        return False
    
    return True

def test_dataprocessor_methods():
    """Test that DataProcessor has the correct method names"""
    print("\n🔍 Testing DataProcessor methods...")
    
    try:
        sys.path.append(str(project_root / "dev_productivity"))
        from fds_algorithm.preprocessing.data_processor import DataProcessor
        
        processor = DataProcessor()
        
        # Check if process_data method exists (the correct one)
        if hasattr(processor, 'process_data'):
            print("✅ DataProcessor.process_data method exists")
        else:
            print("❌ DataProcessor.process_data method NOT found")
            return False
        
        # Check that the old incorrect method name doesn't exist
        if hasattr(processor, 'process_commits'):
            print("⚠️  DataProcessor.process_commits method still exists (should be removed)")
        else:
            print("✅ DataProcessor.process_commits method correctly removed")
        
        return True
        
    except Exception as e:
        print(f"❌ DataProcessor method test failed: {e}")
        return False

def test_database_models():
    """Test that database models work correctly"""
    print("\n🔍 Testing database models...")
    
    try:
        from dev_productivity.models import FDSAnalysis, DeveloperScore, BatchMetrics
        
        # Test model creation (without saving to avoid conflicts)
        analysis = FDSAnalysis(
            repo_url="https://github.com/test/repo",
            access_token="test_token",
            commit_limit=100
        )
        
        print("✅ FDSAnalysis model creation successful")
        
        # Test that the model has the expected fields
        expected_fields = ['repo_url', 'access_token', 'commit_limit', 'status']
        for field in expected_fields:
            if hasattr(analysis, field):
                print(f"✅ FDSAnalysis.{field} field exists")
            else:
                print(f"❌ FDSAnalysis.{field} field missing")
                return False
        
        return True
        
    except Exception as e:
        print(f"❌ Database model test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Starting FDS Web Application Fix Tests")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("DataProcessor Method Tests", test_dataprocessor_methods),
        ("Database Model Tests", test_database_models),
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
    print("🧪 TEST SUMMARY")
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
        print("🎉 ALL TESTS PASSED! The fixes are working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)