#!/usr/bin/env python3
"""
Debug helpers and a synchronous runner to reproduce the pipeline outside of views.
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

from dev_productivity.models import FDSAnalysis, DeveloperScore, BatchMetrics
from dev_productivity.services import GitHubDataAcquisition, FDSAnalysisService

def debug_analysis_21():
    """Debug analysis ID 21 from the screenshot"""
    print("🔍 DEBUGGING FDS ANALYSIS ID 21")
    print("=" * 60)
    
    try:
        # Get the analysis
        analysis = FDSAnalysis.objects.get(id=21)
        print(f"✅ Found analysis: {analysis.repo_url}")
        print(f"   Status: {analysis.status}")
        print(f"   Total Commits: {analysis.total_commits}")
        print(f"   Total Developers: {analysis.total_developers}")
        print(f"   Total Batches: {analysis.total_batches}")
        print(f"   Created: {analysis.created_at}")
        
        # Check developer scores
        developer_scores = DeveloperScore.objects.filter(analysis=analysis)
        print(f"\n📊 Developer Scores in Database: {developer_scores.count()}")
        
        if developer_scores.count() > 0:
            print("✅ Developer scores exist! Showing top 5:")
            for i, score in enumerate(developer_scores.order_by('-fds_score')[:5]):
                print(f"   {i+1}. {score.author_email}: FDS = {score.fds_score:.3f}")
        else:
            print("❌ No developer scores found in database!")
            
        # Check batch metrics
        batch_metrics = BatchMetrics.objects.filter(analysis=analysis)
        print(f"\n📊 Batch Metrics in Database: {batch_metrics.count()}")
        
        if batch_metrics.count() > 0:
            print("✅ Batch metrics exist! Showing first 3:")
            for i, batch in enumerate(batch_metrics[:3]):
                print(f"   Batch {batch.batch_id}: {batch.commit_count} commits, importance = {batch.importance:.3f}")
        else:
            print("❌ No batch metrics found in database!")
            
        return analysis
        
    except FDSAnalysis.DoesNotExist:
        print("❌ Analysis ID 21 not found in database!")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def debug_fds_calculation():
    """Test FDS calculation with minimal data to identify the issue"""
    print("\n🧪 TESTING FDS CALCULATION PIPELINE")
    print("=" * 60)
    
    try:
        sys.path.append(str(project_root / "dev_productivity"))
        from fds_algorithm.fds_calculator import FDSCalculator
        import pandas as pd
        from datetime import datetime, timedelta
        
        # Create simple test data that should definitely work
        base_time = datetime.now() - timedelta(days=30)  # Recent data
        test_data = []
        
        for i in range(3):
            test_data.append({
                'commit_ts_utc': int((base_time + timedelta(days=i)).timestamp()),
                'author_email': f'developer{i % 2 + 1}@test.com',
                'contribution': 1.5 + i,  # Clear non-zero contributions
                'effort': 0.8 + (i * 0.1),
                'batch_importance': 0.7 + (i * 0.1),
                'effective_churn': 100 + (i * 20),
                'files_changed': 3 + i,
                'batch_id': 1  # Single batch
            })
        
        df = pd.DataFrame(test_data)
        print(f"📊 Test data: {len(df)} commits, {df['author_email'].nunique()} developers")
        print(f"   Contributions: {df['contribution'].tolist()}")
        print(f"   Date range: recent (last 30 days)")
        
        # Test with very low threshold
        calculator = FDSCalculator({
            'time_window_days': 365,
            'min_contributions': 1,
            'contribution_threshold': 0.001  # Very low threshold
        })
        
        fds_scores = calculator.aggregate_contributions_by_author(df)
        print(f"\n✅ FDS Calculation Result: {len(fds_scores)} developers found")
        
        if len(fds_scores) > 0:
            print("📊 FDS Scores:")
            for _, row in fds_scores.iterrows():
                print(f"   {row['author_email']}: FDS = {row['fds']:.3f}")
            return True
        else:
            print("❌ Still no developers found! Issue with FDS calculation logic.")
            return False
            
    except Exception as e:
        print(f"❌ FDS Calculation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_all_analyses():
    """Check all analyses to see if any have developer scores"""
    print("\n📋 CHECKING ALL ANALYSES")
    print("=" * 60)
    
    analyses = FDSAnalysis.objects.all().order_by('-id')
    print(f"Total analyses in database: {analyses.count()}")
    
    for analysis in analyses[:5]:  # Check last 5
        dev_count = DeveloperScore.objects.filter(analysis=analysis).count()
        batch_count = BatchMetrics.objects.filter(analysis=analysis).count()
        print(f"Analysis {analysis.id}: {dev_count} developers, {batch_count} batches ({analysis.status})")

def main():
    """Run all debugging tests"""
    analysis = debug_analysis_21()
    
    if analysis and analysis.status == 'completed':
        dev_scores = DeveloperScore.objects.filter(analysis=analysis).count()
        if dev_scores == 0:
            print("\n🔍 ISSUE IDENTIFIED: Analysis completed but no developer scores saved!")
            print("   This suggests an issue in the _save_results_to_db method.")
            
    check_all_analyses()
    
    # Test FDS calculation independently
    calculation_works = debug_fds_calculation()
    
    print("\n" + "=" * 60)
    print("🔍 DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    if calculation_works:
        print("✅ FDS calculation logic works correctly")
        print("❌ Issue is likely in the data pipeline or database saving")
        print("🔧 SOLUTION: Fix the _save_results_to_db method or data flow")
    else:
        print("❌ FDS calculation logic has issues")
        print("🔧 SOLUTION: Fix the contribution threshold or calculation logic")

    # Provide a synchronous runner for targeted repo/token
    print("\n🧪 Running synchronous pipeline for quick verification...")
    try:
        repo_url = os.environ.get('FDS_DEBUG_REPO')
        token = os.environ.get('FDS_DEBUG_TOKEN')
        limit = int(os.environ.get('FDS_DEBUG_LIMIT', '50'))
        if repo_url and token:
            owner, repo = repo_url.rstrip('/').split('/')[-2:]
            gh = GitHubDataAcquisition(token)
            commits = gh.fetch_commits(owner, repo, limit)
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as td:
                tmp = Path(td)
                csv_path = tmp / 'commits.csv'
                gh.process_commits_to_csv(commits, csv_path)
                service = FDSAnalysisService()
                clustered = service._run_torque_clustering(csv_path, tmp)
                results = service._run_fds_analysis(clustered, tmp)
                print({k: results[k] for k in ['total_commits','total_batches','total_developers']})
                print(results['fds_scores'].head())
        else:
            print("Set FDS_DEBUG_REPO and FDS_DEBUG_TOKEN to use the synchronous runner.")
    except Exception as e:
        print(f"Synchronous runner failed: {e}")

if __name__ == "__main__":
    main()