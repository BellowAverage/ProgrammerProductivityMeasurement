#!/usr/bin/env python3
"""
Test script to verify the delete analysis functionality
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
from django.test import Client
from django.urls import reverse

def test_delete_functionality():
    """Test the delete analysis functionality"""
    print("🧪 Testing Delete Analysis Functionality")
    print("=" * 50)
    
    # Create a test analysis
    print("📝 Creating test analysis...")
    test_analysis = FDSAnalysis.objects.create(
        repo_url="https://github.com/test/delete-test",
        access_token="test_token_for_delete",
        commit_limit=50,
        status='completed',
        total_commits=10,
        total_developers=3,
        total_batches=5
    )
    print(f"✅ Created test analysis with ID: {test_analysis.id}")
    
    # Create related test data
    print("📝 Creating related test data...")
    test_developer = DeveloperScore.objects.create(
        analysis=test_analysis,
        author_email="test@example.com",
        fds_score=1.5,
        avg_effort=0.8,
        avg_importance=0.7,
        total_commits=3,
        unique_batches=2,
        total_churn=100.0,
        total_files=10,
        share_mean=0.9,
        scale_z_mean=0.5,
        reach_z_mean=0.3,
        centrality_z_mean=0.2,
        dominance_z_mean=0.1,
        novelty_z_mean=0.4,
        speed_z_mean=0.6,
        first_commit_date="2025-01-01",
        last_commit_date="2025-01-02",
        activity_span_days=1.0
    )
    
    test_batch = BatchMetrics.objects.create(
        analysis=test_analysis,
        batch_id=1,
        unique_authors=2,
        total_contribution=2.5,
        avg_contribution=1.25,
        max_contribution=1.5,
        avg_effort=0.8,
        importance=0.9,
        total_churn=150.0,
        total_files=15,
        commit_count=3,
        start_date="2025-01-01",
        end_date="2025-01-01",
        duration_hours=2.0
    )
    print("✅ Created related DeveloperScore and BatchMetrics")
    
    # Verify data exists
    print("🔍 Verifying test data exists...")
    assert FDSAnalysis.objects.filter(id=test_analysis.id).exists()
    assert DeveloperScore.objects.filter(analysis=test_analysis).exists()
    assert BatchMetrics.objects.filter(analysis=test_analysis).exists()
    print("✅ Test data verified")
    
    # Test the delete functionality
    print("🗑️ Testing delete functionality...")
    
    # Get initial counts
    initial_analysis_count = FDSAnalysis.objects.count()
    initial_dev_count = DeveloperScore.objects.count()
    initial_batch_count = BatchMetrics.objects.count()
    
    print(f"📊 Initial counts: {initial_analysis_count} analyses, {initial_dev_count} developers, {initial_batch_count} batches")
    
    # Simulate the delete request using Django test client
    client = Client()
    delete_url = reverse('delete_analysis', args=[test_analysis.id])
    print(f"🌐 Testing DELETE request to: {delete_url}")
    
    response = client.post(delete_url)
    
    # Check response
    if response.status_code == 302:  # Redirect after successful delete
        print("✅ Delete request returned redirect (expected)")
    else:
        print(f"❌ Delete request returned status {response.status_code}")
        return False
    
    # Verify deletion
    print("🔍 Verifying deletion...")
    
    # Check that the analysis is deleted
    if not FDSAnalysis.objects.filter(id=test_analysis.id).exists():
        print("✅ Analysis successfully deleted")
    else:
        print("❌ Analysis still exists after delete")
        return False
    
    # Check that related data is also deleted (cascade)
    if not DeveloperScore.objects.filter(analysis_id=test_analysis.id).exists():
        print("✅ Related DeveloperScore records successfully deleted")
    else:
        print("❌ Related DeveloperScore records still exist")
        return False
    
    if not BatchMetrics.objects.filter(analysis_id=test_analysis.id).exists():
        print("✅ Related BatchMetrics records successfully deleted")
    else:
        print("❌ Related BatchMetrics records still exist")
        return False
    
    # Check final counts
    final_analysis_count = FDSAnalysis.objects.count()
    final_dev_count = DeveloperScore.objects.count()
    final_batch_count = BatchMetrics.objects.count()
    
    print(f"📊 Final counts: {final_analysis_count} analyses, {final_dev_count} developers, {final_batch_count} batches")
    
    # Verify counts decreased correctly
    if (final_analysis_count == initial_analysis_count - 1 and
        final_dev_count == initial_dev_count - 1 and
        final_batch_count == initial_batch_count - 1):
        print("✅ All record counts decreased correctly")
        return True
    else:
        print("❌ Record counts did not decrease as expected")
        return False

def test_delete_nonexistent():
    """Test deleting a non-existent analysis"""
    print("\n🧪 Testing Delete Non-existent Analysis")
    print("=" * 50)
    
    # Try to delete an analysis that doesn't exist
    client = Client()
    fake_id = 99999
    delete_url = reverse('delete_analysis', args=[fake_id])
    
    print(f"🌐 Testing DELETE request for non-existent ID: {fake_id}")
    response = client.post(delete_url)
    
    if response.status_code == 404:
        print("✅ Correctly returned 404 for non-existent analysis")
        return True
    else:
        print(f"❌ Expected 404 but got {response.status_code}")
        return False

def main():
    """Run all delete tests"""
    print("🧪 Starting Delete Analysis Feature Tests")
    print("=" * 50)
    
    tests = [
        ("Delete Functionality Test", test_delete_functionality),
        ("Delete Non-existent Test", test_delete_nonexistent),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("🧪 DELETE FEATURE TEST SUMMARY")
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
        print("🎉 ALL DELETE TESTS PASSED! Delete functionality works correctly.")
        return True
    else:
        print("⚠️  Some delete tests failed. Check the output above for details.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)