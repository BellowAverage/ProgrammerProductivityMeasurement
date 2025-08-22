#!/usr/bin/env python3
"""
Synchronous runner for the Django FDS pipeline.

Usage:
  set GITHUB_TOKEN=... && python run_django_pipeline_cli.py --repo https://github.com/torvalds/linux --limit 50
"""

import os
import sys
from pathlib import Path
from argparse import ArgumentParser

# Ensure project on sys.path
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fds_webapp.settings')
django.setup()

from dev_productivity.services import GitHubDataAcquisition, FDSAnalysisService


def run(repo_url: str, token: str, limit: int) -> int:
    owner, repo = repo_url.rstrip('/').split('/')[-2:]
    gh = GitHubDataAcquisition(token)

    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as td:
        tmp = Path(td)
        print(f"Fetching {limit} commits from {owner}/{repo}...")
        commits = gh.fetch_commits(owner, repo, limit)
        csv_path = tmp / 'commits.csv'
        gh.process_commits_to_csv(commits, csv_path)

        service = FDSAnalysisService()
        print("Running TORQUE clustering...")
        clustered = service._run_torque_clustering(csv_path, tmp)
        print("Running FDS analysis...")
        results = service._run_fds_analysis(clustered, tmp)

        print("\nSummary:")
        print(f"  Total commits:    {results['total_commits']}")
        print(f"  Total batches:    {results['total_batches']}")
        print(f"  Total developers: {results['total_developers']}")
        top = results['fds_scores'].sort_values('fds', ascending=False).head(5)
        print("\nTop developers:")
        for i, (_, row) in enumerate(top.iterrows(), 1):
            print(f"  {i}. {row['author_email']}  FDS={row['fds']:.3f}  commits={row['commit_count']}  batches={row['unique_batches']}")

    return 0


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--repo', required=True, help='GitHub repo URL')
    parser.add_argument('--limit', type=int, default=50, help='Number of commits to analyze')
    args = parser.parse_args()

    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print('Error: set GITHUB_TOKEN environment variable.')
        sys.exit(2)

    sys.exit(run(args.repo, token, args.limit))

