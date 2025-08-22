#!/usr/bin/env python3
"""
Queue multiple large FDS analyses via the Django models/service.

Usage:
  set GITHUB_TOKEN=... && python run_bulk_analyses.py
"""

import os
import sys
from pathlib import Path

# Ensure project on sys.path and Django loaded
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fds_webapp.settings')
django.setup()

from dev_productivity.models import FDSAnalysis
from dev_productivity.services import FDSAnalysisService


REPOS = [
    'https://github.com/facebook/react',
    'https://github.com/apache/kafka',
    'https://github.com/vercel/next.js',
    'https://github.com/pytorch/pytorch',
    'https://github.com/pandas-dev/pandas',
]

COMMITS = 1200


def main() -> int:
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print('Error: set GITHUB_TOKEN environment variable before running.')
        return 2

    service = FDSAnalysisService()
    for idx, repo_url in enumerate(REPOS, start=1):
        analysis = FDSAnalysis.objects.create(
            repo_url=repo_url,
            access_token=token,
            commit_limit=COMMITS,
            status='pending',
        )
        print(f"[{idx}/{len(REPOS)}] Running analysis {analysis.id} for {repo_url} ({COMMITS} commits)...")
        # Run synchronously to avoid daemon thread exit when script ends
        service._run_analysis(analysis.id)
        print(f"[OK] Completed analysis {analysis.id} for {repo_url}")

    print('All analyses completed. Open the dashboard to review results.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())


