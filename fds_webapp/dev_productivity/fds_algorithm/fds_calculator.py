#!/usr/bin/env python3
"""
Final FDS Calculator for Fair Developer Contribution Algorithm

This module:
1. Combines effort and importance scores to calculate contributions
2. Aggregates contributions to compute Fair Developer Scores (FDS)
3. Provides comprehensive reporting and analysis
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Tuple
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))
from utils.mad_normalization import mad_z_score

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FDSCalculator:
    """Final calculator for Fair Developer Scores."""
    
    def __init__(self, config: dict = None):
        """
        Initialize with configuration parameters.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
    
    def _default_config(self) -> dict:
        """Default configuration for FDS calculation."""
        return {
            'time_window_days': 90,  # Rolling window for FDS aggregation
            'min_contributions': 1,  # Minimum contributions to be included
            'contribution_threshold': 0.01,  # Minimum meaningful contribution
        }
    
    def calculate_contributions(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate individual contributions.
        
        Formula: Contribution = Effort × Importance
        
        Args:
            df: DataFrame with effort and importance metrics
            
        Returns:
            DataFrame with contribution column added
        """
        df = df.copy()
        
        # Calculate raw contribution
        df['contribution'] = df['effort'] * df['batch_importance']
        
        # Apply minimum threshold
        df['contribution'] = df['contribution'].clip(lower=0)
        
        logger.info(f"Calculated {len(df)} individual contributions")
        return df
    
    def aggregate_contributions_by_author(self, df: pd.DataFrame, 
                                        time_window_days: int = None) -> pd.DataFrame:
        """
        Aggregate contributions by author within time windows.
        
        Args:
            df: DataFrame with contribution data
            time_window_days: Time window for aggregation (default from config)
            
        Returns:
            DataFrame with FDS scores by author
        """
        if time_window_days is None:
            time_window_days = self.config['time_window_days']
        
        # Convert timestamps to datetime (handle both Unix timestamps and ISO format)
        try:
            # First try as Unix timestamps
            df['commit_date'] = pd.to_datetime(df['commit_ts_utc'], unit='s')
        except (ValueError, OSError):
            # If that fails, try as ISO format strings
            df['commit_date'] = pd.to_datetime(df['commit_ts_utc'])
        
        # Define time window - for repository analysis, use adaptive window
        end_date = df['commit_date'].max()
        start_date = df['commit_date'].min()
        data_span_days = (end_date - start_date).days
        
        # Use adaptive time window: either specified window or full data span if data is historical
        if data_span_days <= time_window_days or time_window_days >= 365:
            # Use all data if span is small or window is large (full repo analysis)
            window_df = df.copy()
            actual_window_days = data_span_days
        else:
            # Use specified time window for recent data
            start_date = end_date - timedelta(days=time_window_days)
            window_df = df[df['commit_date'] >= start_date].copy()
            actual_window_days = time_window_days
        
        # Aggregate by author
        author_metrics = window_df.groupby('author_email').agg({
            'contribution': 'sum',
            'effort': 'mean',
            'batch_importance': 'mean',
            'effective_churn': 'sum',
            'files_changed': 'sum',
            'batch_id': 'nunique',
            'commit_date': ['min', 'max', 'count']
        }).round(4)
        
        # Flatten column names
        author_metrics.columns = [
            'fds', 'avg_effort', 'avg_importance', 'total_churn',
            'total_files', 'unique_batches', 'first_commit', 'last_commit', 'commit_count'
        ]
        
        # Add time window info
        author_metrics['window_start'] = window_df['commit_date'].min().date()
        author_metrics['window_end'] = window_df['commit_date'].max().date()
        author_metrics['window_days'] = actual_window_days
        
        # Filter by minimum contributions
        author_metrics = author_metrics[
            author_metrics['fds'] >= self.config['contribution_threshold']
        ].copy()
        
        # Sort by FDS score
        author_metrics = author_metrics.sort_values('fds', ascending=False)
        
        logger.info(f"Calculated FDS for {len(author_metrics)} authors in "
                   f"{actual_window_days}-day window ({window_df['commit_date'].min().date()} to {window_df['commit_date'].max().date()})")
        
        return author_metrics.reset_index()
    
    def calculate_detailed_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate detailed per-author metrics broken down by components.
        
        Args:
            df: DataFrame with all contribution data
            
        Returns:
            DataFrame with detailed author metrics
        """
        # Group by author and calculate all metrics
        author_details = df.groupby('author_email').agg({
            # Contribution metrics
            'contribution': ['sum', 'mean', 'std', 'count'],
            'effort': ['mean', 'std'],
            'batch_importance': ['mean', 'std'],
            
            # Effort components (if available)
            'share': 'mean',
            'scale_z': 'mean',
            'reach_z': 'mean',
            'centrality_z': 'mean',
            'dominance_z': 'mean',
            'novelty_z': 'mean',
            'speed_z': 'mean',
            
            # Basic metrics
            'effective_churn': 'sum',
            'files_changed': 'sum',
            'batch_id': 'nunique',
            'commit_ts_utc': ['min', 'max']
        }).round(4)
        
        # Flatten column names
        new_columns = []
        for col in author_details.columns:
            if isinstance(col, tuple):
                new_columns.append(f"{col[0]}_{col[1]}")
            else:
                new_columns.append(col)
        author_details.columns = new_columns
        
        # Rename key columns
        author_details = author_details.rename(columns={
            'contribution_sum': 'total_contribution',
            'contribution_mean': 'avg_contribution',
            'contribution_std': 'contribution_std',
            'contribution_count': 'total_commits',
            'batch_id_nunique': 'unique_batches',
            'commit_ts_utc_min': 'first_commit_ts',
            'commit_ts_utc_max': 'last_commit_ts'
        })
        
        # Convert timestamps to readable dates
        # Convert timestamps to dates (robust parsing)
        try:
            author_details['first_commit_date'] = pd.to_datetime(
                author_details['first_commit_ts'], unit='s'
            ).dt.date
            author_details['last_commit_date'] = pd.to_datetime(
                author_details['last_commit_ts'], unit='s'
            ).dt.date
        except (ValueError, OSError):
            author_details['first_commit_date'] = pd.to_datetime(
                author_details['first_commit_ts']
            ).dt.date
            author_details['last_commit_date'] = pd.to_datetime(
                author_details['last_commit_ts']
            ).dt.date
        
        # Calculate activity span
        author_details['activity_span_days'] = (
            (author_details['last_commit_ts'] - author_details['first_commit_ts']) / 86400
        ).round(1)
        
        return author_details.reset_index().sort_values('total_contribution', ascending=False)
    
    def generate_contribution_breakdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate per-batch contribution breakdown for analysis.
        
        Args:
            df: DataFrame with contribution data
            
        Returns:
            DataFrame with batch-level contribution summary
        """
        batch_summary = df.groupby('batch_id').agg({
            'author_email': 'nunique',
            'contribution': ['sum', 'mean', 'max'],
            'effort': 'mean',
            'batch_importance': 'first',  # Same for all commits in batch
            'effective_churn': 'sum',
            'files_changed': 'sum',
            'commit_ts_utc': ['min', 'max', 'count']
        }).round(4)
        
        # Flatten columns
        batch_summary.columns = [
            'unique_authors', 'total_contribution', 'avg_contribution', 'max_contribution',
            'avg_effort', 'importance', 'total_churn', 'total_files',
            'start_ts', 'end_ts', 'commit_count'
        ]
        
        # Add readable dates (robust parsing)
        try:
            batch_summary['start_date'] = pd.to_datetime(
                batch_summary['start_ts'], unit='s'
            ).dt.date
            batch_summary['end_date'] = pd.to_datetime(
                batch_summary['end_ts'], unit='s'
            ).dt.date
        except (ValueError, OSError):
            batch_summary['start_date'] = pd.to_datetime(
                batch_summary['start_ts']
            ).dt.date
            batch_summary['end_date'] = pd.to_datetime(
                batch_summary['end_ts']
            ).dt.date
        
        # Calculate batch duration
        batch_summary['duration_hours'] = (
            (batch_summary['end_ts'] - batch_summary['start_ts']) / 3600
        ).round(2)
        
        return batch_summary.reset_index().sort_values('total_contribution', ascending=False)
    
    def run_complete_analysis(self, input_file: str) -> Dict[str, pd.DataFrame]:
        """
        Run complete FDS analysis pipeline.
        
        Args:
            input_file: Path to input CSV with effort and importance data
            
        Returns:
            Dictionary containing all analysis results
        """
        logger.info(f"Loading data from {input_file}")
        df = pd.read_csv(input_file)
        
        # Step 1: Calculate contributions
        df = self.calculate_contributions(df)
        
        # Step 2: Calculate FDS scores
        fds_scores = self.aggregate_contributions_by_author(df)
        
        # Step 3: Calculate detailed metrics
        detailed_metrics = self.calculate_detailed_metrics(df)
        
        # Step 4: Generate batch breakdown
        batch_breakdown = self.generate_contribution_breakdown(df)
        
        results = {
            'contributions': df,
            'fds_scores': fds_scores,
            'detailed_metrics': detailed_metrics,
            'batch_breakdown': batch_breakdown
        }
        
        logger.info("Completed FDS analysis")
        return results
    
    def save_results(self, results: Dict[str, pd.DataFrame], output_dir: str):
        """
        Save all analysis results to CSV files.
        
        Args:
            results: Dictionary of analysis results
            output_dir: Directory to save files
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for name, df in results.items():
            if not df.empty:
                file_path = output_path / f"linux_kernel_{name}.csv"
                df.to_csv(file_path, index=False)
                logger.info(f"Saved {name} to {file_path}")
    
    def print_comprehensive_summary(self, results: Dict[str, pd.DataFrame]):
        """
        Print comprehensive summary of all FDS analysis results.
        
        Args:
            results: Dictionary of analysis results
        """
        print("\n" + "="*60)
        print("FAIR DEVELOPER SCORE (FDS) ANALYSIS SUMMARY")
        print("="*60)
        
        fds_scores = results['fds_scores']
        detailed_metrics = results['detailed_metrics']
        batch_breakdown = results['batch_breakdown']
        contributions = results['contributions']
        
        # Overall statistics
        print(f"\n📊 OVERALL STATISTICS")
        print(f"Total commits analyzed: {len(contributions):,}")
        print(f"Total batches: {contributions['batch_id'].nunique():,}")
        print(f"Total developers: {len(fds_scores):,}")
        print(f"Time period: {contributions['commit_ts_utc'].min()} to {contributions['commit_ts_utc'].max()}")
        print(f"Total contributions: {contributions['contribution'].sum():.3f}")
        
        # Top performers
        print(f"\n🏆 TOP 10 DEVELOPERS BY FDS SCORE")
        print("-" * 50)
        for i, (_, dev) in enumerate(fds_scores.head(10).iterrows()):
            print(f"{i+1:2d}. {dev['author_email']:<35} {dev['fds']:>8.3f}")
            print(f"     Effort: {dev['avg_effort']:>6.3f} | Importance: {dev['avg_importance']:>6.3f} | "
                  f"Batches: {dev['unique_batches']:>3.0f} | Commits: {dev['commit_count']:>3.0f}")
        
        # Effort component analysis
        if all(col in detailed_metrics.columns for col in ['share_mean', 'scale_z_mean', 'reach_z_mean']):
            print(f"\n🔍 EFFORT COMPONENT ANALYSIS (Top 5 Developers)")
            print("-" * 80)
            top_devs = detailed_metrics.head(5)
            print(f"{'Developer':<35} {'Share':<6} {'Scale':<6} {'Reach':<6} {'Central':<7} {'Domin':<6} {'Novel':<6}")
            print("-" * 80)
            for _, dev in top_devs.iterrows():
                print(f"{dev['author_email']:<35} "
                      f"{dev.get('share_mean', 0):<6.3f} "
                      f"{dev.get('scale_z_mean', 0):<6.3f} "
                      f"{dev.get('reach_z_mean', 0):<6.3f} "
                      f"{dev.get('centrality_z_mean', 0):<7.3f} "
                      f"{dev.get('dominance_z_mean', 0):<6.3f} "
                      f"{dev.get('novelty_z_mean', 0):<6.3f}")
        
        # Most important batches
        print(f"\n⭐ TOP 10 MOST IMPORTANT BATCHES")
        print("-" * 70)
        top_batches = batch_breakdown.head(10)
        for i, (_, batch) in enumerate(top_batches.iterrows()):
            print(f"{i+1:2d}. Batch {batch['batch_id']:<8} Contribution: {batch['total_contribution']:>8.3f} "
                  f"Importance: {batch['importance']:>6.3f} ({batch['commit_count']:>2.0f} commits)")
        
        # Distribution analysis
        print(f"\n📈 DISTRIBUTION ANALYSIS")
        print("-" * 30)
        print(f"FDS Score Statistics:")
        print(f"  Mean:   {fds_scores['fds'].mean():>8.3f}")
        print(f"  Median: {fds_scores['fds'].median():>8.3f}")
        print(f"  Std:    {fds_scores['fds'].std():>8.3f}")
        print(f"  Min:    {fds_scores['fds'].min():>8.3f}")
        print(f"  Max:    {fds_scores['fds'].max():>8.3f}")
        
        # Activity patterns
        print(f"\nActivity Patterns:")
        print(f"  Avg commits per developer: {fds_scores['commit_count'].mean():.1f}")
        print(f"  Avg batches per developer: {fds_scores['unique_batches'].mean():.1f}")
        print(f"  Avg files changed per dev: {fds_scores['total_files'].mean():.1f}")
        
        print("\n" + "="*60)
        print("Analysis complete! Check the saved CSV files for detailed data.")
        print("="*60)


if __name__ == "__main__":
    # Run the complete FDS analysis
    calculator = FDSCalculator()
    
    # Input file with effort and importance metrics
    input_file = "../../data/github_commit_data_test/linux_kernel_commits_with_importance.csv"
    output_dir = "../../data/github_commit_data_test/fds_results"
    
    try:
        # Run complete analysis
        results = calculator.run_complete_analysis(input_file)
        
        # Save results
        calculator.save_results(results, output_dir)
        
        # Print comprehensive summary
        calculator.print_comprehensive_summary(results)
        
    except FileNotFoundError:
        print(f"Input file not found: {input_file}")
        print("Please run the preprocessing and importance calculation steps first.")