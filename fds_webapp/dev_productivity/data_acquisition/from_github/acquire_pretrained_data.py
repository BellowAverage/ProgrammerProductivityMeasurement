#!/usr/bin/env python3
"""
Standalone GitHub Data Acquisition for Local FDS Analyzer
"""

import requests
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GitHubDataAcquisition:
    """Simplified GitHub data acquisition service for local analysis"""
    
    def __init__(self, github_token, output_file=None, commit_limit=300):
        self.github_token = github_token
        self.output_file = output_file
        self.commit_limit = commit_limit
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def fetch_commits(self, owner, repo):
        """Fetch commits from GitHub API and return processed data"""
        logger.info(f"Fetching commits from {owner}/{repo}")
        
        commits = []
        page = 1
        per_page = min(100, self.commit_limit)  # GitHub API max is 100 per page
        
        while len(commits) < self.commit_limit:
            url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {
                'page': page,
                'per_page': per_page,
            }
            
            logger.info(f"Fetching page {page}...")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            page_commits = response.json()
            if not page_commits:
                break
                
            # Fetch detailed stats for each commit
            detailed_commits = []
            for commit in page_commits:
                try:
                    # Get detailed commit info including stats
                    detail_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit['sha']}"
                    detail_response = requests.get(detail_url, headers=self.headers)
                    detail_response.raise_for_status()
                    detailed_commit = detail_response.json()
                    detailed_commits.append(detailed_commit)
                    
                    # Small delay to avoid rate limiting
                    import time
                    time.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Failed to get details for commit {commit['sha']}: {e}")
                    detailed_commits.append(commit)  # Use basic commit if detail fetch fails
                
            commits.extend(detailed_commits)
            page += 1
            
            if len(commits) >= self.commit_limit:
                commits = commits[:self.commit_limit]
            break

        logger.info(f"Retrieved {len(commits)} commits")
        
        # Process commits to the required format
        processed_commits = self._process_commits(commits)
        return processed_commits
    
    def _process_commits(self, commits):
        """Process GitHub API commits to the format expected by FDS algorithm"""
        processed_commits = []
        
        for i, commit in enumerate(commits):
            commit_data = commit['commit']
            stats = commit.get('stats', {})
            
            # Calculate time difference from previous commit
            dt_prev_commit_sec = ""
            if i > 0:
                current_time = datetime.fromisoformat(commit_data['author']['date'].replace('Z', '+00:00'))
                prev_time = datetime.fromisoformat(commits[i-1]['commit']['author']['date'].replace('Z', '+00:00'))
                dt_prev_commit_sec = (current_time - prev_time).total_seconds()
            
            # Convert ISO timestamp to Unix timestamp
            commit_timestamp = datetime.fromisoformat(commit_data['author']['date'].replace('Z', '+00:00'))
            commit_ts_utc = int(commit_timestamp.timestamp())
            
            processed_commit = {
                'hash': commit['sha'],
                'author_name': commit_data['author']['name'],
                'author_email': commit_data['author']['email'],
                'commit_ts_utc': commit_ts_utc,
                'dt_prev_commit_sec': dt_prev_commit_sec,
                'dt_prev_author_sec': "",  # Simplified for local analysis
                'files_changed': len(commit.get('files', [])),
                'insertions': stats.get('additions', 0),
                'deletions': stats.get('deletions', 0),
                'is_merge': len(commit.get('parents', [])) > 1,
                'dirs_touched': len(set([f['filename'].split('/')[0] for f in commit.get('files', []) if '/' in f['filename']])),
                'file_types': ','.join(set([f['filename'].split('.')[-1] for f in commit.get('files', []) if '.' in f['filename']])),
                'msg_subject': commit_data['message'].split('\n')[0][:100],
            }
            processed_commits.append(processed_commit)
        
        return processed_commits

def main():
    """Test function for standalone usage"""
    # This would be used if running the file directly
    import os
    token = os.getenv('GITHUB_TOKEN')
    if not token:
        print("Please set GITHUB_TOKEN environment variable")
        return
    
    acquisition = GitHubDataAcquisition(token, commit_limit=10)
    commits = acquisition.fetch_commits('torvalds', 'linux')
    
    print(f"Retrieved {len(commits)} commits")
    for commit in commits[:3]:
        print(f"- {commit['hash'][:8]}: {commit['msg_subject']}")

if __name__ == "__main__":
    main()