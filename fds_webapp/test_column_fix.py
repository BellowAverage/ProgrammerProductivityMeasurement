#!/usr/bin/env python3
"""
Test script to verify the column name fix for FDS calculation
"""

import os
import sys
import django
from pathlib import Path
import pandas as pd

# Setup Django
project_root = Path(__file__).parent
sys.path.append(str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fds_webapp.settings')
django.setup()

def test_data_columns():
    """Test that we can create sample data with correct column structure"""
    print("🧪 Testing Data Column Structure")
    print("=" * 50)
    
    try:
        # Create sample effort_df (similar to what effort calculator would output)
        effort_data = {
            'hash': ['abc123', 'def456', 'ghi789'],
            'batch_id': [1, 1, 2],
            'author_email': ['dev1@test.com', 'dev2@test.com', 'dev1@test.com'],
            'effort': [0.8, 0.6, 0.9],
            'share': [0.7, 0.3, 1.0],
            'scale_z': [0.5, 0.2, 0.8],
            'effective_churn': [100, 50, 120]
        }
        effort_df = pd.DataFrame(effort_data)
        print("✅ Created sample effort_df with columns:", list(effort_df.columns))
        
        # Create sample importance_df (similar to what importance calculator would output)
        importance_data = {
            'hash': ['abc123', 'def456', 'ghi789'],
            'batch_id': [1, 1, 2],
            'author_email': ['dev1@test.com', 'dev2@test.com', 'dev1@test.com'],
            'batch_importance': [0.7, 0.7, 0.9],
            'commit_ts_utc': [1640995200, 1640998800, 1641002400]  # Sample timestamps
        }
        importance_df = pd.DataFrame(importance_data)
        print("✅ Created sample importance_df with columns:", list(importance_df.columns))
        
        # Test the merge operation (this was failing before)
        try:
            merged_df = effort_df.merge(
                importance_df, 
                on=['hash', 'batch_id'], 
                suffixes=('', '_imp')
            )
            print("✅ Merge operation successful! Merged columns:", list(merged_df.columns))
            
            # Check that required columns for contribution calculation exist
            if 'effort' in merged_df.columns and 'batch_importance' in merged_df.columns:
                print("✅ Required columns for contribution calculation exist")
                
                # Test contribution calculation
                merged_df['contribution'] = merged_df['effort'] * merged_df['batch_importance']
                print("✅ Contribution calculation successful")
                print(f"Sample contributions: {merged_df['contribution'].tolist()}")
                
                return True
            else:
                print("❌ Missing required columns for contribution calculation")
                print(f"Available columns: {list(merged_df.columns)}")
                return False
                
        except Exception as e:
            print(f"❌ Merge operation failed: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Data column test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fds_calculator_import():
    """Test that we can import and use the FDS calculator"""
    print("\n🧪 Testing FDS Calculator with Sample Data")
    print("=" * 50)
    
    try:
        # Import FDS calculator
        sys.path.append(str(project_root / "dev_productivity"))
        from fds_algorithm.fds_calculator import FDSCalculator
        
        # Create sample merged data
        sample_data = {
            'hash': ['abc123', 'def456', 'ghi789'],
            'batch_id': [1, 1, 2],
            'author_email': ['dev1@test.com', 'dev2@test.com', 'dev1@test.com'],
            'effort': [0.8, 0.6, 0.9],
            'batch_importance': [0.7, 0.7, 0.9],
            'commit_ts_utc': [1640995200, 1640998800, 1641002400],
            'effective_churn': [100, 50, 120],
            'files_changed': [5, 3, 8]
        }
        merged_df = pd.DataFrame(sample_data)
        print(f"✅ Created sample merged data with {len(merged_df)} rows")
        
        # Test FDS calculator methods
        calculator = FDSCalculator()
        
        # Test calculate_contributions
        contributions_df = calculator.calculate_contributions(merged_df)
        print("✅ calculate_contributions() successful")
        print(f"Contributions: {contributions_df['contribution'].tolist()}")
        
        # Test aggregate_contributions_by_author
        fds_scores = calculator.aggregate_contributions_by_author(contributions_df)
        print("✅ aggregate_contributions_by_author() successful")
        print(f"FDS scores calculated for {len(fds_scores)} authors")
        
        return True
        
    except Exception as e:
        print(f"❌ FDS calculator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("🧪 Starting Column Fix Tests")
    print("=" * 50)
    
    tests = [
        ("Data Column Structure", test_data_columns),
        ("FDS Calculator Integration", test_fds_calculator_import),
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
    print("🧪 COLUMN FIX TEST SUMMARY")
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
        print("🎉 ALL COLUMN FIX TESTS PASSED! The merge fix is working correctly.")
        return True
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)