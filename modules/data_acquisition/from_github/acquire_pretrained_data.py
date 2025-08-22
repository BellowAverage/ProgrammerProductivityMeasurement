#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# acquire_pretrained_data.py
#
# Extract raw features needed for clustering from GitHub repository using API,
# output as directly readable CSV.
# Dependencies: requests, python-dotenv
# ---------------------------------------------------------------------------

import csv
import os
import requests
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables from .env file
load_dotenv()

# ==============================================================================
# CONFIGURATION - Modify these settings as needed
# ==============================================================================

# GitHub repository to analyze (format: "owner/repo" or full GitHub URL)
REPO_URL = "torvalds/linux"  # Example: "torvalds/linux" or "https://github.com/torvalds/linux"

# Output file path
OUTPUT_FILE = "data/github_commit_data_test/linux_kernel_commits.csv"

# Limit number of commits to process (None for all commits, or set a number like 1000)
COMMIT_LIMIT = 300  # Set to None for all commits, or e.g., 1000 for testing

# GitHub API settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# ==============================================================================

# GitHub API setup
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
if not GITHUB_TOKEN:
    print("Warning: No GITHUB_TOKEN found in environment. API rate limits will be lower.")

headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}

if GITHUB_TOKEN:
    headers["Authorization"] = f"token {GITHUB_TOKEN}"


def extract_repo_name(repo_input: str) -> str:
    """
    Extract owner/repo format from various GitHub URL formats.
    
    Args:
        repo_input: GitHub URL or owner/repo string
        
    Returns:
        String in "owner/repo" format
    """
    if repo_input.startswith("http"):
        # Parse URL like https://github.com/torvalds/linux
        parsed = urlparse(repo_input)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            return f"{path_parts[0]}/{path_parts[1]}"
        else:
            raise ValueError(f"Invalid GitHub URL: {repo_input}")
    else:
        # Assume it's already in owner/repo format
        if "/" in repo_input:
            return repo_input
        else:
            raise ValueError(f"Invalid repository format: {repo_input}. Use 'owner/repo' or full GitHub URL.")


def make_github_request(url: str, params: dict = None) -> dict:
    """
    Make a GitHub API request with error handling and rate limiting.
    
    Args:
        url: API endpoint URL
        params: Query parameters
        
    Returns:
        JSON response data
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            # Check rate limit
            if response.status_code == 403 and "rate limit exceeded" in response.text.lower():
                reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                current_time = int(time.time())
                wait_time = max(reset_time - current_time, 60)
                print(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                print(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                raise


def get_commits_from_api(repo_name: str, limit: int = None):
    """
    Fetch commits from GitHub API.
    
    Args:
        repo_name: Repository in "owner/repo" format
        limit: Maximum number of commits to fetch
        
    Yields:
        Commit data from GitHub API
    """
    url = f"https://api.github.com/repos/{repo_name}/commits"
    page = 1
    per_page = 100
    total_fetched = 0
    
    print(f"[+] Fetching commits from {repo_name}...")
    
    while True:
        params = {
            "page": page,
            "per_page": per_page
        }
        
        try:
            commits = make_github_request(url, params)
            
            if not commits:  # No more commits
                break
                
            for commit in commits:
                if limit and total_fetched >= limit:
                    return
                    
                yield commit
                total_fetched += 1
                
                if total_fetched % 100 == 0:
                    print(f"[+] Fetched {total_fetched} commits...")
            
            page += 1
            
            # Small delay to be nice to the API
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Error fetching commits on page {page}: {e}")
            break


def extract_features_from_api(repo_name: str, limit: int = None):
    """
    Extract commit-level features from GitHub API data.
    
    Args:
        repo_name: Repository in "owner/repo" format
        limit: Maximum number of commits to process
        
    Yields:
        Dictionary containing commit features
    """
    prev_ts_repo = None
    last_ts_by_author: dict[str, float] = {}
    commits_data = []
    
    # First, collect all commit data
    for commit_data in get_commits_from_api(repo_name, limit):
        commits_data.append(commit_data)
    
    # Reverse to process chronologically (oldest first)
    commits_data.reverse()
    
    print(f"[+] Processing {len(commits_data)} commits for feature extraction...")
    
    for i, commit_data in enumerate(commits_data):
        try:
            commit = commit_data["commit"]
            
            # Parse timestamp
            commit_date = datetime.fromisoformat(commit["committer"]["date"].replace("Z", "+00:00"))
            committed_ts = commit_date.timestamp()
            
            # Get author info
            author_info = commit_data.get("author") or {}
            author_name = commit["author"]["name"]
            author_email = commit["author"]["email"].lower()
            
            # Time delta features
            dt_prev_repo = (
                None if prev_ts_repo is None else committed_ts - prev_ts_repo
            )
            prev_ts_repo = committed_ts
            
            dt_prev_author = (
                None
                if author_email not in last_ts_by_author
                else committed_ts - last_ts_by_author[author_email]
            )
            last_ts_by_author[author_email] = committed_ts
            
            # Get additional commit details (files changed, stats)
            commit_url = f"https://api.github.com/repos/{repo_name}/commits/{commit_data['sha']}"
            commit_details = make_github_request(commit_url)
            
            # Extract file and directory information
            files = commit_details.get("files", [])
            files_changed = len(files)
            
            dirs_touched = set()
            file_types = set()
            insertions = 0
            deletions = 0
            
            for file_info in files:
                filename = file_info["filename"]
                
                # Directory information
                path_parts = Path(filename).parts
                if path_parts:
                    dirs_touched.add(path_parts[0])
                
                # File type information
                file_ext = Path(filename).suffix.lstrip(".").lower() or "noext"
                file_types.add(file_ext)
                
                # Stats
                insertions += file_info.get("additions", 0)
                deletions += file_info.get("deletions", 0)
            
            # Check if it's a merge commit
            is_merge = len(commit_data.get("parents", [])) > 1
            
            # Message
            message_lines = commit["message"].splitlines()
            msg_subject = message_lines[0][:120] if message_lines else ""
            
            yield {
                "hash": commit_data["sha"],
                "author_name": author_name,
                "author_email": author_email,
                "commit_ts_utc": int(committed_ts),
                "dt_prev_commit_sec": int(dt_prev_repo) if dt_prev_repo is not None else "",
                "dt_prev_author_sec": int(dt_prev_author) if dt_prev_author is not None else "",
                "files_changed": files_changed,
                "insertions": insertions,
                "deletions": deletions,
                "is_merge": int(is_merge),
                "dirs_touched": ";".join(sorted(dirs_touched)),
                "file_types": ";".join(sorted(file_types)),
                "msg_subject": msg_subject,
            }
            
            if (i + 1) % 50 == 0:
                print(f"[+] Processed {i + 1} commits...")
                
        except Exception as e:
            print(f"Error processing commit {commit_data.get('sha', 'unknown')}: {e}")
            continue


def main() -> None:
    """Main function to extract commit features and save to CSV."""
    
    try:
        # Extract repository name
        repo_name = extract_repo_name(REPO_URL)
        print(f"[+] Analyzing repository: {repo_name}")
        
        if COMMIT_LIMIT:
            print(f"[+] Processing last {COMMIT_LIMIT} commits only")
        else:
            print(f"[+] Processing all available commits")
        
        # Check if repo exists
        repo_url = f"https://api.github.com/repos/{repo_name}"
        repo_info = make_github_request(repo_url)
        print(f"[+] Repository found: {repo_info['full_name']} ({repo_info.get('stargazers_count', 0)} stars)")
        
        # Extract features
        rows = extract_features_from_api(repo_name, COMMIT_LIMIT)

        fieldnames = [
            "hash",
            "author_name",
            "author_email",
            "commit_ts_utc",
            "dt_prev_commit_sec",
            "dt_prev_author_sec",
            "files_changed",
            "insertions",
            "deletions",
            "is_merge",
            "dirs_touched",
            "file_types",
            "msg_subject",
        ]

        # Create output directory if it doesn't exist
        output_dir = Path(OUTPUT_FILE).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            count = 0
            for row in rows:
                writer.writerow(row)
                count += 1

        print(f"[+] CSV written to {OUTPUT_FILE}")
        print(f"[+] Total commits processed: {count}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
