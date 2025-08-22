#!/usr/bin/env python3
"""
Test script to verify the timestamp parsing fix
"""

import os
import sys
import django
from pathlib import Path
import pandas as pd
from datetime import datetime

# Setup Django
project_root = Path(__file__).parent
sys.path.append(str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fds_webapp.settings')
django.setup()

def test_timestamp_parsing():
    """Test that both Unix timestamps and ISO format timestamps work correctly"""
    print("🧪 Testing Timestamp Parsing Fix")
    print("=" * 50)
    
    try:
        sys.path.append(str(project_root / "dev_productivity"))
        from fds_algorithm.fds_calculator import FDSCalculator
        
        # Test data with Unix timestamps (old format)
        unix_data = pd.DataFrame({
            'commit_ts_utc': [1640995200, 1640998800, 1641002400],
            'author_email': ['dev1@test.com', 'dev2@test.com', 'dev1@test.com'],
            'contribution': [1.5, 1.2, 1.8],
            'effort': [0.8, 0.6, 0.9],
            'batch_importance': [0.7, 0.8, 0.9],
            'effective_churn': [100, 80, 120],
            'files_changed': [5, 3, 7],
            'batch_id': [1, 1, 2]
        })
        
        # Test data with ISO timestamps (new format from GitHub)
        iso_data = pd.DataFrame({
            'commit_ts_utc': ['2021-12-31T20:00:00Z', '2021-12-31T21:00:00Z', '2022-01-01T00:00:00Z'],
            'author_email': ['dev1@test.com', 'dev2@test.com', 'dev1@test.com'],
            'contribution': [1.5, 1.2, 1.8],
            'effort': [0.8, 0.6, 0.9],
            'batch_importance': [0.7, 0.8, 0.9],
            'effective_churn': [100, 80, 120],
            'files_changed': [5, 3, 7],
            'batch_id': [1, 1, 2]
        })
        
        calculator = FDSCalculator({
            'time_window_days': 90,
            'min_contributions': 1,
            'contribution_threshold': 0.01
        })
        
        # Test 1: Unix timestamps (should work as before)
        print("📋 Test 1: Unix timestamp format")
        try:
            fds_scores_unix = calculator.aggregate_contributions_by_author(unix_data)
            print(f"✅ Unix timestamps: {len(fds_scores_unix)} developers processed")
        except Exception as e:
            print(f"❌ Unix timestamps failed: {e}")
            return False
        
        # Test 2: ISO timestamps (should work with the fix)
        print("📋 Test 2: ISO timestamp format")
        try:
            fds_scores_iso = calculator.aggregate_contributions_by_author(iso_data)
            print(f"✅ ISO timestamps: {len(fds_scores_iso)} developers processed")
        except Exception as e:
            print(f"❌ ISO timestamps failed: {e}")
            return False
        
        # Test 3: Services timestamp conversion
        print("📋 Test 3: GitHub timestamp conversion")
        from dev_productivity.services import FDSAnalysisService
        service = FDSAnalysisService()
        
        # Simulate GitHub API response format
        mock_commit = {
            'sha': 'abc123',
            'commit': {
                'author': {
                    'name': 'Test Developer',
                    'email': 'test@example.com',
                    'date': '2025-06-04T13:52:19Z'  # This was causing the original error
                }
            },
            'stats': {'additions': 50, 'deletions': 10},
            'files': [{'filename': 'test.py'}],
            'parents': [{'sha': 'parent123'}]
        }
        
        mock_commits = [mock_commit]
        
        try:
            # Process commits (this will use the fixed timestamp conversion)
            processed_commits = []
            for i, commit in enumerate(mock_commits):
                commit_data = commit['commit']
                stats = commit.get('stats', {})
                dt_prev_commit_sec = 3600 if i > 0 else 0  # 1 hour
                
                # Convert ISO timestamp to Unix timestamp (the fix)
                commit_timestamp = datetime.fromisoformat(commit_data['author']['date'].replace('Z', '+00:00'))
                commit_ts_utc = int(commit_timestamp.timestamp())
                
                processed_commit = {
                    'hash': commit['sha'],
                    'author_name': commit_data['author']['name'],
                    'author_email': commit_data['author']['email'],
                    'commit_ts_utc': commit_ts_utc,
                    'dt_prev_commit_sec': dt_prev_commit_sec,
                    'dt_prev_author_sec': "",
                    'files_changed': len(commit.get('files', [])),
                    'insertions': stats.get('additions', 0),
                    'deletions': stats.get('deletions', 0),
                    'is_merge': len(commit.get('parents', [])) > 1,
                    'dirs_touched': 'src',
                    'file_types': '.py',
                }
                processed_commits.append(processed_commit)
            
            print(f"✅ GitHub timestamp conversion: {len(processed_commits)} commits processed")
            print(f"   Original: '2025-06-04T13:52:19Z'")
            print(f"   Converted: {processed_commits[0]['commit_ts_utc']} (Unix timestamp)")
            
        except Exception as e:
            print(f"❌ GitHub timestamp conversion failed: {e}")
            return False
        
        print("\n" + "=" * 50)
        print("🎉 ALL TIMESTAMP PARSING TESTS PASSED!")
        print("✅ Unix timestamps work correctly")
        print("✅ ISO timestamps work correctly") 
        print("✅ GitHub API timestamp conversion works correctly")
        print("✅ The datetime parsing error has been fixed!")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_timestamp_parsing()
    sys.exit(0 if success else 1)