import os
import sys
import subprocess
import threading
import time
import pandas as pd
from datetime import datetime, timezone
from django.utils import timezone as django_timezone
from .models import FDSAnalysis, DeveloperScore, BatchMetrics
import tempfile
import shutil
import requests
from pathlib import Path


class GitHubDataAcquisition:
    """Simplified GitHub data acquisition service"""
    
    def __init__(self, github_token):
        self.github_token = github_token
        self.headers = {
            'Authorization': f'token {github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def fetch_commits(self, owner, repo, limit=300):
        """Fetch commits with detailed stats (additions, deletions, files) from GitHub API"""
        commits: list[dict] = []
        page = 1
        per_page = min(100, limit)

        while len(commits) < limit:
            list_url = f"https://api.github.com/repos/{owner}/{repo}/commits"
            params = {'page': page, 'per_page': per_page}

            list_resp = requests.get(list_url, headers=self.headers, params=params)
            list_resp.raise_for_status()
            page_commits = list_resp.json()
            if not page_commits:
                break

            detailed_commits: list[dict] = []
            for item in page_commits:
                sha = item.get('sha')
                if not sha:
                    continue
                try:
                    detail_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
                    detail_resp = requests.get(detail_url, headers=self.headers)
                    detail_resp.raise_for_status()
                    detailed_commits.append(detail_resp.json())
                    # small delay to be gentle on rate limits
                    time.sleep(0.1)
                except Exception:
                    # fallback to list item if detailed fetch fails
                    detailed_commits.append(item)

            commits.extend(detailed_commits)
            page += 1

            if len(commits) >= limit:
                commits = commits[:limit]
                break

        return commits
    
    def process_commits_to_csv(self, commits, output_path):
        """Process GitHub API commits to CSV format compatible with FDS algorithm"""
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
                'dt_prev_author_sec': "",  # Simplified
                'files_changed': len(commit.get('files', [])),
                'insertions': stats.get('additions', 0),
                'deletions': stats.get('deletions', 0),
                'is_merge': len(commit.get('parents', [])) > 1,
                'dirs_touched': len(set([f['filename'].split('/')[0] for f in commit.get('files', []) if '/' in f['filename']])),
                'file_types': ','.join(set([f['filename'].split('.')[-1] for f in commit.get('files', []) if '.' in f['filename']])),
                'msg_subject': commit_data['message'].split('\n')[0][:100],
            }
            processed_commits.append(processed_commit)
        
        # Save to CSV
        df = pd.DataFrame(processed_commits)
        df.to_csv(output_path, index=False)
        return output_path


class FDSAnalysisService:
    """Service to run FDS analysis in background"""
    
    def start_analysis(self, analysis_id):
        """Start analysis in background thread"""
        thread = threading.Thread(target=self._run_analysis, args=(analysis_id,))
        thread.daemon = True
        thread.start()
    
    def _run_analysis(self, analysis_id):
        """Run the complete FDS analysis pipeline"""
        try:
            analysis = FDSAnalysis.objects.get(id=analysis_id)
            analysis.status = 'running'
            analysis.started_at = django_timezone.now()
            analysis.save()
            
            start_time = time.time()
            
            # Create temporary directory for analysis
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Step 1: Data Acquisition
                self._update_status(analysis, "Fetching commit data from GitHub...")
                
                # Extract owner/repo from URL
                repo_parts = analysis.repo_url.rstrip('/').split('/')
                owner, repo = repo_parts[-2], repo_parts[-1]
                
                # Fetch commits
                github_service = GitHubDataAcquisition(analysis.access_token)
                commits = github_service.fetch_commits(owner, repo, analysis.commit_limit)
                
                # Process to CSV
                commits_csv = temp_path / "commits.csv"
                github_service.process_commits_to_csv(commits, commits_csv)
                
                # Step 2: TORQUE Clustering
                self._update_status(analysis, "Running TORQUE clustering...")
                clustered_csv, summary_file = self._run_torque_clustering(commits_csv, temp_path)
                
                # Step 3: FDS Analysis
                self._update_status(analysis, "Calculating Fair Developer Scores...")
                results = self._run_fds_analysis(
                    clustered_csv,
                    temp_path,
                    raw_commits_path=commits_csv,
                    clustering_summary_path=summary_file,
                )
                
                # Step 4: Save Results to Database
                self._update_status(analysis, "Saving results...")
                self._save_results_to_db(analysis, results)
                
                # Complete analysis
                execution_time = time.time() - start_time
                analysis.status = 'completed'
                analysis.completed_at = django_timezone.now()
                analysis.execution_time = execution_time
                analysis.save()
                
        except Exception as e:
            analysis.status = 'failed'
            analysis.error_message = str(e)
            analysis.save()
    
    def _update_status(self, analysis, message):
        """Update analysis status with message"""
        # In a real implementation, you might want to log this or store progress
        pass
    
    def _run_torque_clustering(self, input_csv, temp_path):
        """Run TORQUE clustering on commits and write a summary file."""
        # Import the torque clustering module
        sys.path.append(str(Path(__file__).parent))
        from torque_clustering.run_torque import torque_cluster

        # Load data
        df = pd.read_csv(input_csv)

        # Clustering parameters (keep in sync with dashboard display)
        alpha = 0.001
        beta = 0.1
        gap = 30.0
        break_on_merge = True
        break_on_author = False

        # Run TORQUE clustering with collaborative settings
        df["batch_id"] = torque_cluster(
            df,
            α=alpha,
            β=beta,
            gap=gap,
            break_on_merge=break_on_merge,
            break_on_author=break_on_author,
        )

        # Save clustered data
        clustered_csv = temp_path / "commits_clustered.csv"
        df.to_csv(clustered_csv, index=False)

        # Write clustering summary (ASCII only for Windows consoles)
        summary_file = temp_path / "clustering_summary.txt"
        try:
            total_commits = int(len(df))
            total_batches = int(df["batch_id"].nunique()) if not df.empty else 0
            avg_per_batch = (total_commits / max(1, total_batches)) if total_commits else 0.0
            with open(summary_file, "w", encoding="utf-8") as f:
                f.write("TORQUE Clustering Summary\n")
                f.write("========================\n\n")
                f.write("Parameters:\n")
                f.write(f"  alpha: {alpha}\n")
                f.write(f"  beta: {beta}\n")
                f.write(f"  Gap threshold: {gap}\n")
                f.write(f"  Break on merge: {break_on_merge}\n")
                f.write(f"  Break on author: {break_on_author}\n\n")
                f.write("Results:\n")
                f.write(f"  Total commits: {total_commits}\n")
                f.write(f"  Total batches: {total_batches}\n")
                f.write(f"  Average commits per batch: {avg_per_batch:.2f}\n")
        except Exception:
            # Non-fatal; continue without summary
            pass

        return clustered_csv, summary_file
    
    def _run_fds_analysis(self, clustered_csv, temp_path, raw_commits_path=None, clustering_summary_path=None):
        """Run FDS analysis on clustered commits and persist intermediates in temp_path."""
        # Import FDS modules
        sys.path.append(str(Path(__file__).parent))
        
        from fds_algorithm.preprocessing.data_processor import DataProcessor
        from fds_algorithm.effort_calculator.developer_effort import DeveloperEffortCalculator
        from fds_algorithm.importance_calculator.batch_importance import BatchImportanceCalculator
        from fds_algorithm.fds_calculator import FDSCalculator
        
        # Configuration
        config = {
            'noise_factor_threshold': 0.1,
            'whitespace_noise_factor': 0.99,
            'key_file_extensions': ['.py', '.js', '.java', '.cpp', '.c', '.h'],
            'pagerank_iterations': 100,
            'min_batch_size': 1,  # build size minimum (kept key for code compatibility)
            'min_batch_churn': 1,  # build churn minimum
            'time_window_days': 365,  # Use 1 year window for repository analysis
            'min_contributions': 1,
            'contribution_threshold': 0.01,
            # Effort/importance specific params expected by calculators
            'novelty_cap': 2.0,
            'speed_half_life_hours': 72,
            'release_proximity_days': 7,
            'complexity_scale_factor': 1.0,
        }
        
        # Step 1: Preprocessing
        processor = DataProcessor(config)
        processed_df = processor.process_data(str(clustered_csv))
        # Persist processed data
        processed_csv = temp_path / "processed_data.csv"
        try:
            processed_df.to_csv(processed_csv, index=False)
        except Exception:
            pass
        
        # Step 2: Developer Effort
        effort_calc = DeveloperEffortCalculator(config)
        effort_df = effort_calc.process_all_batches(processed_df)
        effort_csv = temp_path / "developer_effort.csv"
        try:
            effort_df.to_csv(effort_csv, index=False)
        except Exception:
            pass
        
        # Step 3: Batch Importance
        importance_calc = BatchImportanceCalculator(config)
        importance_df, batch_metrics_df = importance_calc.process_all_batches(processed_df)
        importance_csv = temp_path / "batch_importance.csv"
        try:
            importance_df.to_csv(importance_csv, index=False)
        except Exception:
            pass
        
        # Step 4: Final FDS Calculation
        fds_calc = FDSCalculator(config)
        
        # Merge effort and importance data
        # Merge on hash (commit identifier) and batch_id to combine effort and importance
        merged_df = effort_df.merge(
            importance_df, 
            on=['hash', 'batch_id'], 
            suffixes=('', '_imp')
        )
        merged_csv = temp_path / "merged_data.csv"
        try:
            merged_df.to_csv(merged_csv, index=False)
        except Exception:
            pass
        
        # Calculate individual contributions
        individual_contributions = fds_calc.calculate_contributions(merged_df)
        
        # Calculate final FDS scores by aggregating contributions
        fds_scores = fds_calc.aggregate_contributions_by_author(individual_contributions)
        
        # Calculate detailed metrics
        detailed_metrics = fds_calc.calculate_detailed_metrics(individual_contributions)
        
        # Generate batch-level breakdown derived from contributions (ensures required columns exist)
        batch_breakdown = fds_calc.generate_contribution_breakdown(individual_contributions)
        
        return {
            'fds_scores': fds_scores,
            'detailed_metrics': detailed_metrics,
            'batch_metrics': batch_breakdown,
            'individual_contributions': individual_contributions,
            'total_commits': len(processed_df),
            'total_batches': processed_df['batch_id'].nunique(),
            'total_developers': processed_df['author_email'].nunique(),
            'processed_df': processed_df,
            # Intermediate artifacts and their file paths for persistence
            'effort_df': effort_df,
            'importance_df': importance_df,
            'merged_df': merged_df,
            'raw_commits_path': Path(raw_commits_path) if raw_commits_path else None,
            'clustered_csv_path': Path(clustered_csv) if clustered_csv else None,
            'clustering_summary_path': Path(clustering_summary_path) if clustering_summary_path else None,
            'processed_csv_path': processed_csv,
            'effort_csv_path': effort_csv,
            'importance_csv_path': importance_csv,
            'merged_csv_path': merged_csv,
        }
    
    def _save_results_to_db(self, analysis, results):
        """Save FDS results to database"""
        def _to_datetime_utc(value):
            """Coerce various timestamp/date representations to timezone-aware datetime (UTC)."""
            try:
                import pandas as _pd
            except Exception:
                _pd = None

            # pandas Timestamp
            if _pd is not None and isinstance(value, getattr(_pd, 'Timestamp', tuple())):
                dt = value.to_pydatetime()
            # datetime already
            elif isinstance(value, datetime):
                dt = value
            # epoch seconds
            elif isinstance(value, (int, float)):
                return datetime.fromtimestamp(value, tz=timezone.utc)
            else:
                # string or other
                try:
                    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
                except Exception:
                    if _pd is not None:
                        dt = _pd.to_datetime(value).to_pydatetime()
                    else:
                        dt = datetime.utcnow()

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        # Update analysis summary
        analysis.total_commits = results['total_commits']
        analysis.total_batches = results['total_batches']
        analysis.total_developers = results['total_developers']
        analysis.save()
        
        # Save artifacts into organized folder under fds_webapp/
        try:
            base_dir = Path(__file__).resolve().parents[1]
            repo_sanitized = (analysis.repo_url or 'repo').rstrip('/').split('/')[-2:]  # owner/repo
            repo_sanitized = '_'.join(repo_sanitized)
            folder = base_dir / 'fds_results' / f"analysis_{analysis.id}_{repo_sanitized}"
            folder.mkdir(parents=True, exist_ok=True)

            # Persist CSVs for this analysis (full detailed set)
            indiv = results.get('individual_contributions')
            detailed = results.get('detailed_metrics')
            fds_scores_df = results.get('fds_scores')
            batch_df = results.get('batch_metrics')
            processed_df = results.get('processed_df')
            effort_df = results.get('effort_df')
            importance_df = results.get('importance_df')
            merged_df = results.get('merged_df')

            # Raw/clustered inputs
            raw_commits_path = results.get('raw_commits_path')
            clustered_csv_path = results.get('clustered_csv_path')
            clustering_summary_path = results.get('clustering_summary_path')

            # Copy raw and clustered files if available
            try:
                if raw_commits_path and Path(raw_commits_path).exists():
                    shutil.copyfile(raw_commits_path, folder / 'raw_commits.csv')
            except Exception:
                pass
            try:
                if clustered_csv_path and Path(clustered_csv_path).exists():
                    shutil.copyfile(clustered_csv_path, folder / 'commits_clustered.csv')
            except Exception:
                pass
            try:
                if clustering_summary_path and Path(clustering_summary_path).exists():
                    shutil.copyfile(clustering_summary_path, folder / 'clustering_summary.txt')
            except Exception:
                pass

            # Intermediate dataframes
            if processed_df is not None:
                processed_df.to_csv(folder / 'processed_data.csv', index=False)
            if effort_df is not None:
                effort_df.to_csv(folder / 'developer_effort.csv', index=False)
            if importance_df is not None:
                importance_df.to_csv(folder / 'batch_importance.csv', index=False)
            if merged_df is not None:
                merged_df.to_csv(folder / 'merged_data.csv', index=False)

            if fds_scores_df is not None:
                fds_scores_df.to_csv(folder / 'fds_scores.csv', index=False)
            if detailed is not None:
                detailed.to_csv(folder / 'detailed_metrics.csv', index=False)
            if batch_df is not None:
                batch_df.to_csv(folder / 'batch_breakdown.csv', index=False)
            if indiv is not None:
                # Align name with local tool expectation
                indiv.to_csv(folder / 'individual_contributions.csv', index=False)
        except Exception:
            # Non-fatal; DB remains source of truth
            pass

        # Save developer scores
        fds_scores = results['fds_scores']
        detailed_metrics = results['detailed_metrics']
        
        for _, row in fds_scores.iterrows():
            email = row['author_email']
            detailed_row = detailed_metrics[detailed_metrics['author_email'] == email].iloc[0]
            
            DeveloperScore.objects.create(
                analysis=analysis,
                author_email=email,
                fds_score=row['fds'],
                avg_effort=row['avg_effort'],
                avg_importance=row['avg_importance'],
                total_commits=row['commit_count'],
                unique_batches=row['unique_batches'],
                total_churn=row['total_churn'],
                total_files=row['total_files'],
                share_mean=detailed_row['share_mean'],
                scale_z_mean=detailed_row['scale_z_mean'],
                reach_z_mean=detailed_row['reach_z_mean'],
                centrality_z_mean=detailed_row['centrality_z_mean'],
                dominance_z_mean=detailed_row['dominance_z_mean'],
                novelty_z_mean=detailed_row['novelty_z_mean'],
                speed_z_mean=detailed_row.get('speed_z_mean', 0),
                first_commit_date=_to_datetime_utc(row['first_commit']),
                last_commit_date=_to_datetime_utc(row['last_commit']),
                activity_span_days=detailed_row['activity_span_days'],
            )
        
        # Save batch metrics
        batch_metrics = results['batch_metrics']
        for _, row in batch_metrics.iterrows():
            BatchMetrics.objects.create(
                analysis=analysis,
                batch_id=int(row['batch_id']),
                unique_authors=row['unique_authors'],
                total_contribution=row['total_contribution'],
                avg_contribution=row['avg_contribution'],
                max_contribution=row['max_contribution'],
                avg_effort=row['avg_effort'],
                importance=row['importance'],
                total_churn=row['total_churn'],
                total_files=row['total_files'],
                commit_count=row['commit_count'],
                start_date=datetime.fromtimestamp(row['start_ts'], tz=timezone.utc),
                end_date=datetime.fromtimestamp(row['end_ts'], tz=timezone.utc),
                duration_hours=row['duration_hours'],
            )