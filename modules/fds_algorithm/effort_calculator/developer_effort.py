#!/usr/bin/env python3
"""
Developer Effort Calculator for FDS Algorithm

This module calculates the 6 dimensions of developer effort:
1. Share - portion of batch work done by developer
2. Scale - amount of code changed (logarithmic)
3. Reach - directory diversity (entropy-based)
4. Centrality - importance of touched directories
5. Dominance - leadership in the batch
6. Novelty - new files and key infrastructure work
7. Speed - iteration speed (optional)
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Tuple
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.mad_normalization import mad_z_score, entropy, safe_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeveloperEffortCalculator:
    """Calculator for developer effort metrics."""
    
    def __init__(self, config: dict = None):
        """
        Initialize with configuration parameters.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
        self.effort_weights = {
            'share': 0.25,
            'scale': 0.15,
            'reach': 0.20,
            'centrality': 0.20,
            'dominance': 0.15,
            'novelty': 0.05,
            'speed': 0.05  # Optional
        }
    
    def _default_config(self) -> dict:
        """Default configuration for effort calculation."""
        return {
            'speed_half_life_hours': 24,  # Hours for speed decay
            'novelty_cap': 2.0,          # Maximum novelty score
            'min_batch_size': 1,         # Minimum commits for valid batch
        }
    
    def calculate_share(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate each developer's share of work in the batch.
        
        Formula: author_effective_churn / batch_effective_churn
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with share column added
        """
        batch_df = batch_df.copy()
        
        # Calculate total batch churn
        batch_total_churn = batch_df['effective_churn'].sum()
        
        if batch_total_churn == 0:
            batch_df['share'] = 0.0
        else:
            # Calculate each author's share
            author_churn = batch_df.groupby('author_email')['effective_churn'].sum()
            batch_df['share'] = batch_df['author_email'].map(
                lambda email: author_churn[email] / batch_total_churn
            )
        
        return batch_df
    
    def calculate_scale(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate scale metric based on code change volume.
        
        Formula: log(1 + author_churn_in_batch)
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with scale_raw column added
        """
        batch_df = batch_df.copy()
        
        # Calculate total churn per author in this batch
        author_churn = batch_df.groupby('author_email')['effective_churn'].sum()
        
        batch_df['scale_raw'] = batch_df['author_email'].map(
            lambda email: safe_log(author_churn[email])
        )
        
        return batch_df
    
    def calculate_reach(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate reach metric based on directory diversity.
        
        Formula: H = -Σ p_i log2 p_i where p_i = churn_in_dir_i / total_author_churn
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with reach_raw column added
        """
        batch_df = batch_df.copy()
        batch_df['reach_raw'] = 0.0
        
        for author_email in batch_df['author_email'].unique():
            author_commits = batch_df[batch_df['author_email'] == author_email]
            
            # Build directory -> churn mapping for this author
            dir_churn = {}
            total_author_churn = 0
            
            for _, commit in author_commits.iterrows():
                dirs_touched = str(commit.get('dirs_touched', ''))
                if not dirs_touched or pd.isna(dirs_touched):
                    continue
                
                dirs = [d.strip() for d in dirs_touched.split(';') if d.strip()]
                commit_churn = commit.get('effective_churn', 0)
                
                # Distribute churn equally among directories
                churn_per_dir = commit_churn / len(dirs) if dirs else 0
                
                for dir_name in dirs:
                    dir_churn[dir_name] = dir_churn.get(dir_name, 0) + churn_per_dir
                    total_author_churn += churn_per_dir
            
            # Calculate entropy
            if total_author_churn > 0 and dir_churn:
                probabilities = np.array(list(dir_churn.values())) / total_author_churn
                reach_score = entropy(probabilities, base=2)
            else:
                reach_score = 0.0
            
            # Update all commits for this author
            batch_df.loc[batch_df['author_email'] == author_email, 'reach_raw'] = reach_score
        
        return batch_df
    
    def calculate_centrality(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate centrality metric based on directory importance.
        
        Formula: Mean centrality of directories touched by author
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with centrality_raw column added
        """
        batch_df = batch_df.copy()
        
        # Use the directory_centrality column from preprocessing
        batch_df['centrality_raw'] = batch_df['directory_centrality']
        
        return batch_df
    
    def calculate_dominance(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate dominance metric based on batch leadership.
        
        Formula: 0.3*is_first_commit + 0.3*is_last_commit + 0.4*commit_count_share
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with dominance_raw column added
        """
        batch_df = batch_df.copy()
        batch_df = batch_df.sort_values('commit_ts_utc')
        
        total_commits = len(batch_df)
        
        for author_email in batch_df['author_email'].unique():
            author_mask = batch_df['author_email'] == author_email
            author_commits = batch_df[author_mask]
            
            # Check if author has first/last commit
            is_first = batch_df.iloc[0]['author_email'] == author_email
            is_last = batch_df.iloc[-1]['author_email'] == author_email
            
            # Calculate commit count share
            commit_count_share = len(author_commits) / total_commits
            
            # Combine dominance factors
            dominance = (
                0.3 * (1.0 if is_first else 0.0) +
                0.3 * (1.0 if is_last else 0.0) +
                0.4 * commit_count_share
            )
            
            batch_df.loc[author_mask, 'dominance_raw'] = dominance
        
        return batch_df
    
    def calculate_novelty(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate novelty metric based on new files and key paths.
        
        Formula: (new_file_lines + key_path_lines) / author_churn, capped at 2.0
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with novelty_raw column added
        """
        batch_df = batch_df.copy()
        
        for author_email in batch_df['author_email'].unique():
            author_mask = batch_df['author_email'] == author_email
            author_commits = batch_df[author_mask]
            
            # Sum novelty indicators for this author
            total_new_file_lines = author_commits['new_file_lines'].sum()
            total_key_path_lines = author_commits['key_path_lines'].sum()
            total_author_churn = author_commits['effective_churn'].sum()
            
            if total_author_churn > 0:
                novelty = (total_new_file_lines + total_key_path_lines) / total_author_churn
                novelty = min(novelty, self.config['novelty_cap'])  # Cap at 2.0
            else:
                novelty = 0.0
            
            batch_df.loc[author_mask, 'novelty_raw'] = novelty
        
        return batch_df
    
    def calculate_speed(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate speed metric based on iteration frequency.
        
        Formula: exp(-hours_since_prev_author_commit / 24)
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with speed_raw column added
        """
        batch_df = batch_df.copy()
        
        for _, commit in batch_df.iterrows():
            dt_prev_author = commit.get('dt_prev_author_sec', np.nan)
            
            if pd.isna(dt_prev_author) or dt_prev_author == '':
                speed = 0.0  # No previous commit
            else:
                hours_since_prev = float(dt_prev_author) / 3600  # Convert to hours
                speed = np.exp(-hours_since_prev / self.config['speed_half_life_hours'])
            
            batch_df.loc[batch_df['hash'] == commit['hash'], 'speed_raw'] = speed
        
        return batch_df
    
    def calculate_batch_effort_metrics(self, batch_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all raw effort metrics for a batch.
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            DataFrame with all raw effort metrics added
        """
        batch_df = self.calculate_share(batch_df)
        batch_df = self.calculate_scale(batch_df)
        batch_df = self.calculate_reach(batch_df)
        batch_df = self.calculate_centrality(batch_df)
        batch_df = self.calculate_dominance(batch_df)
        batch_df = self.calculate_novelty(batch_df)
        batch_df = self.calculate_speed(batch_df)
        
        return batch_df
    
    def normalize_effort_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply MAD-Z normalization to effort metrics.
        
        Args:
            df: DataFrame with raw effort metrics
            
        Returns:
            DataFrame with normalized effort metrics
        """
        df = df.copy()
        
        # Columns to normalize (exclude 'share' as it's already a proportion)
        metrics_to_normalize = [
            'scale_raw', 'reach_raw', 'centrality_raw', 
            'dominance_raw', 'novelty_raw', 'speed_raw'
        ]
        
        for metric in metrics_to_normalize:
            if metric in df.columns:
                z_column = metric.replace('_raw', '_z')
                df[z_column] = mad_z_score(df[metric])
        
        return df
    
    def calculate_final_effort(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate final effort scores using weighted combination.
        
        Args:
            df: DataFrame with normalized effort metrics
            
        Returns:
            DataFrame with effort column added
        """
        df = df.copy()
        
        # Calculate weighted effort score
        df['effort'] = (
            self.effort_weights['share'] * df['share'] +
            self.effort_weights['scale'] * df['scale_z'] +
            self.effort_weights['reach'] * df['reach_z'] +
            self.effort_weights['centrality'] * df['centrality_z'] +
            self.effort_weights['dominance'] * df['dominance_z'] +
            self.effort_weights['novelty'] * df['novelty_z'] +
            self.effort_weights['speed'] * df['speed_z']
        )
        
        return df
    
    def process_all_batches(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process all batches to calculate effort metrics.
        
        Args:
            df: DataFrame with all commits and batches
            
        Returns:
            DataFrame with effort metrics for all commits
        """
        logger.info("Calculating developer effort metrics for all batches...")
        
        # Process each batch separately
        batch_results = []
        
        for batch_id in df['batch_id'].unique():
            batch_df = df[df['batch_id'] == batch_id].copy()
            
            min_batch_size = self.config.get('min_batch_size', 1)
            if len(batch_df) >= min_batch_size:
                batch_df = self.calculate_batch_effort_metrics(batch_df)
                batch_results.append(batch_df)
        
        # Combine all batches
        if batch_results:
            combined_df = pd.concat(batch_results, ignore_index=True)
            
            # Apply normalization across all data
            combined_df = self.normalize_effort_metrics(combined_df)
            
            # Calculate final effort scores
            combined_df = self.calculate_final_effort(combined_df)
        else:
            combined_df = df.copy()
            combined_df['effort'] = 0.0
        
        logger.info(f"Calculated effort metrics for {len(combined_df)} commits")
        return combined_df
    
    def print_effort_summary(self, df: pd.DataFrame):
        """Print summary of effort calculation results."""
        if 'effort' not in df.columns:
            print("No effort metrics calculated yet.")
            return
        
        print(f"\n=== Developer Effort Summary ===")
        print(f"Total commits processed: {len(df)}")
        print(f"Average effort score: {df['effort'].mean():.3f}")
        print(f"Effort score range: [{df['effort'].min():.3f}, {df['effort'].max():.3f}]")
        
        # Top contributors by effort
        author_effort = df.groupby('author_email')['effort'].sum().sort_values(ascending=False)
        print(f"\nTop 5 contributors by total effort:")
        for i, (author, total_effort) in enumerate(author_effort.head().items()):
            print(f"  {i+1}. {author}: {total_effort:.3f}")
        
        # Effort component analysis
        if all(col in df.columns for col in ['share', 'scale_z', 'reach_z', 'centrality_z', 'dominance_z', 'novelty_z']):
            print(f"\nAverage effort components:")
            print(f"  Share: {df['share'].mean():.3f}")
            print(f"  Scale (Z): {df['scale_z'].mean():.3f}")
            print(f"  Reach (Z): {df['reach_z'].mean():.3f}")
            print(f"  Centrality (Z): {df['centrality_z'].mean():.3f}")
            print(f"  Dominance (Z): {df['dominance_z'].mean():.3f}")
            print(f"  Novelty (Z): {df['novelty_z'].mean():.3f}")


if __name__ == "__main__":
    # Test the effort calculator
    calculator = DeveloperEffortCalculator()
    
    # Load preprocessed data
    input_file = "../../../data/github_commit_data_test/linux_kernel_commits_processed.csv"
    
    try:
        df = pd.read_csv(input_file)
        result_df = calculator.process_all_batches(df)
        calculator.print_effort_summary(result_df)
        
        # Save results
        output_file = "../../../data/github_commit_data_test/linux_kernel_commits_with_effort.csv"
        result_df.to_csv(output_file, index=False)
        print(f"\nSaved effort metrics to {output_file}")
        
    except FileNotFoundError:
        print(f"Input file not found: {input_file}")
        print("Please run the preprocessing step first.")