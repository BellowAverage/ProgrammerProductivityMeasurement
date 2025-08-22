#!/usr/bin/env python3
"""
Test script to verify the time window fix for historical repository analysis
"""

import os
import sys
import django
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta

# Setup Django
project_root = Path(__file__).parent
sys.path.append(str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fds_webapp.settings')
django.setup()

def test_time_window_fix():
    """Test that historical commits are now included in FDS calculation"""
    print("🧪 Testing Time Window Fix for Historical Data")
    print("=" * 60)
    
    try:
        sys.path.append(str(project_root / "dev_productivity"))
        from fds_algorithm.fds_calculator import FDSCalculator
        
        # Create test data with historical commits (from 2023, not recent)
        base_time = datetime(2023, 6, 1)  # June 2023 - historical data
        historical_data = []
        
        for i in range(5):
            commit_time = base_time + timedelta(days=i*7)  # Weekly commits
            historical_data.append({
                'commit_ts_utc': int(commit_time.timestamp()),
                'author_email': f'dev{i % 2 + 1}@test.com',  # 2 developers
                'contribution': 1.0 + (i * 0.2),
                'effort': 0.5 + (i * 0.1),
                'batch_importance': 0.6 + (i * 0.1),
                'effective_churn': 50 + (i * 10),
                'files_changed': 3 + i,
                'batch_id': (i // 2) + 1  # 3 batches
            })
        
        df = pd.DataFrame(historical_data)
        
        print(f"📊 Test data: {len(df)} commits from 2023")
        print(f"   Date range: {datetime.fromtimestamp(df['commit_ts_utc'].min()).date()} to {datetime.fromtimestamp(df['commit_ts_utc'].max()).date()}")
        print(f"   Developers: {df['author_email'].nunique()}")
        
        # Test with old 90-day window (should find fewer/no developers)
        print("\n📋 Test 1: 90-day window (restrictive)")
        calculator_90 = FDSCalculator({
            'time_window_days': 90,
            'min_contributions': 1,
            'contribution_threshold': 0.01
        })
        
        fds_scores_90 = calculator_90.aggregate_contributions_by_author(df)
        print(f"   Result: {len(fds_scores_90)} developers found with 90-day window")
        
        # Test with new 365-day window (should find all developers)
        print("\n📋 Test 2: 365-day window (inclusive)")
        calculator_365 = FDSCalculator({
            'time_window_days': 365,
            'min_contributions': 1,
            'contribution_threshold': 0.01
        })
        
        fds_scores_365 = calculator_365.aggregate_contributions_by_author(df)
        print(f"   Result: {len(fds_scores_365)} developers found with 365-day window")
        
        # Test with adaptive window logic (should include all historical data)
        print("\n📋 Test 3: Very large window (adaptive - should use all data)")
        calculator_adaptive = FDSCalculator({
            'time_window_days': 1000,  # Very large window
            'min_contributions': 1,
            'contribution_threshold': 0.01
        })
        
        fds_scores_adaptive = calculator_adaptive.aggregate_contributions_by_author(df)
        print(f"   Result: {len(fds_scores_adaptive)} developers found with adaptive window")
        
        # Show actual FDS scores
        if len(fds_scores_365) > 0:
            print("\n📊 FDS Scores with 365-day window:")
            for _, row in fds_scores_365.iterrows():
                print(f"   {row['author_email']}: FDS = {row['fds']:.3f}")
        
        # Verify the fix worked
        if len(fds_scores_365) >= 2:
            print("\n✅ SUCCESS: Time window fix working correctly!")
            print("   - Historical commits are now included in FDS calculation")
            print("   - Repository analysis will show developer scores")
            return True
        else:
            print("\n❌ ISSUE: Still not finding enough developers")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_time_window_fix()
    sys.exit(0 if success else 1)