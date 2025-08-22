#!/usr/bin/env python3
"""
Batch Importance Calculator for FDS Algorithm

This module calculates the 6 dimensions of batch importance:
1. Scale - total code change volume
2. Scope - breadth of impact (files, directories)
3. Centrality - architectural importance of touched areas
4. Complexity - technical difficulty estimation
5. Type - priority based on commit message classification
6. Release - proximity to release events
"""

import pandas as pd
import numpy as np
import re
import logging
from typing import Dict, List, Tuple
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.mad_normalization import mad_z_score, entropy, safe_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BatchImportanceCalculator:
    """Calculator for batch importance metrics."""
    
    def __init__(self, config: dict = None):
        """
        Initialize with configuration parameters.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._default_config()
        self.importance_weights = {
            'scale': 0.30,
            'scope': 0.20,
            'centrality': 0.15,
            'complexity': 0.15,
            'type': 0.10,
            'release': 0.10
        }
        self.commit_type_patterns = self._get_commit_type_patterns()
        self.commit_type_priorities = self._get_commit_type_priorities()
    
    def _default_config(self) -> dict:
        """Default configuration for importance calculation."""
        return {
            'release_proximity_days': 30,  # Days around release for proximity bonus
            'complexity_scale_factor': 1.0,
            'min_batch_churn': 1,  # Minimum churn for valid batch
        }
    
    def _get_commit_type_patterns(self) -> Dict[str, List[re.Pattern]]:
        """Regular expressions to classify commit types."""
        patterns = {
            'security': [
                re.compile(r'\b(security|cve|vuln|exploit|attack|breach)\b', re.I),
                re.compile(r'\b(xss|csrf|injection|overflow|privilege)\b', re.I),
            ],
            'hotfix': [
                re.compile(r'\b(hotfix|urgent|critical|emergency)\b', re.I),
                re.compile(r'\b(fix.*critical|critical.*fix)\b', re.I),
            ],
            'feature': [
                re.compile(r'\b(feature|add|new|implement|introduce)\b', re.I),
                re.compile(r'\b(support|enable|enhance)\b', re.I),
            ],
            'perf': [
                re.compile(r'\b(perf|performance|optimiz|faster|speed)\b', re.I),
                re.compile(r'\b(cache|memory|cpu|latency)\b', re.I),
            ],
            'bugfix': [
                re.compile(r'\b(fix|bug|issue|problem|error)\b', re.I),
                re.compile(r'\b(correct|resolve|address)\b', re.I),
            ],
            'refactor': [
                re.compile(r'\b(refactor|restructure|reorganize|cleanup)\b', re.I),
                re.compile(r'\b(simplify|extract|rename)\b', re.I),
            ],
            'doc': [
                re.compile(r'\b(doc|documentation|readme|comment)\b', re.I),
                re.compile(r'\b(manual|guide|tutorial)\b', re.I),
            ],
        }
        return patterns
    
    def _get_commit_type_priorities(self) -> Dict[str, float]:
        """Priority multipliers for different commit types."""
        return {
            'security': 1.20,
            'hotfix': 1.15,
            'feature': 1.10,
            'perf': 1.05,
            'bugfix': 1.00,
            'refactor': 0.90,
            'doc': 0.60,
            'other': 0.80
        }
    
    def classify_commit_type(self, msg_subject: str) -> str:
        """
        Classify commit type based on message subject.
        
        Args:
            msg_subject: Commit message subject line
            
        Returns:
            Commit type string
        """
        if pd.isna(msg_subject):
            return 'other'
        
        msg_subject = str(msg_subject).lower()
        
        # Check patterns in priority order
        for commit_type, patterns in self.commit_type_patterns.items():
            for pattern in patterns:
                if pattern.search(msg_subject):
                    return commit_type
        
        return 'other'
    
    def calculate_batch_scale(self, batch_df: pd.DataFrame) -> float:
        """
        Calculate batch scale based on total code change.
        
        Formula: log(1 + total_churn_batch)
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            Scale score for the batch
        """
        total_churn = batch_df['effective_churn'].sum()
        return safe_log(total_churn)
    
    def calculate_batch_scope(self, batch_df: pd.DataFrame) -> float:
        """
        Calculate batch scope based on breadth of impact.
        
        Formula: 0.5*files_changed + 0.3*H_dir + 0.2*unique_dirs
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            Scope score for the batch
        """
        # Files changed component
        total_files = batch_df['files_changed'].sum()
        
        # Directory entropy component
        all_dirs = []
        dir_churn = {}
        
        for _, commit in batch_df.iterrows():
            dirs_touched = str(commit.get('dirs_touched', ''))
            if not dirs_touched or pd.isna(dirs_touched):
                continue
                
            dirs = [d.strip() for d in dirs_touched.split(';') if d.strip()]
            commit_churn = commit.get('effective_churn', 0)
            
            for dir_name in dirs:
                all_dirs.append(dir_name)
                dir_churn[dir_name] = dir_churn.get(dir_name, 0) + commit_churn
        
        # Calculate directory entropy
        if dir_churn:
            churn_values = np.array(list(dir_churn.values()))
            h_dir = entropy(churn_values, base=2)
            unique_dirs = len(dir_churn)
        else:
            h_dir = 0.0
            unique_dirs = 0
        
        # Combine scope components
        scope = 0.5 * total_files + 0.3 * h_dir + 0.2 * unique_dirs
        return scope
    
    def calculate_batch_centrality(self, batch_df: pd.DataFrame) -> float:
        """
        Calculate batch centrality based on directory importance.
        
        Formula: Mean centrality of all directories in batch
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            Centrality score for the batch
        """
        centrality_scores = []
        
        for _, commit in batch_df.iterrows():
            dir_centrality = commit.get('directory_centrality', 0)
            if not pd.isna(dir_centrality):
                centrality_scores.append(dir_centrality)
        
        return np.mean(centrality_scores) if centrality_scores else 0.0
    
    def calculate_batch_complexity(self, batch_df: pd.DataFrame) -> float:
        """
        Calculate batch complexity based on diversity and scale.
        
        Formula: sqrt(unique_dirs × log(1 + total_churn))
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            Complexity score for the batch
        """
        # Count unique directories
        all_dirs = set()
        for _, commit in batch_df.iterrows():
            dirs_touched = str(commit.get('dirs_touched', ''))
            if not dirs_touched or pd.isna(dirs_touched):
                continue
                
            dirs = [d.strip() for d in dirs_touched.split(';') if d.strip()]
            all_dirs.update(dirs)
        
        unique_dirs = len(all_dirs)
        total_churn = batch_df['effective_churn'].sum()
        
        complexity = np.sqrt(unique_dirs * safe_log(total_churn))
        return complexity * self.config['complexity_scale_factor']
    
    def calculate_batch_type_priority(self, batch_df: pd.DataFrame) -> float:
        """
        Calculate batch type priority based on commit classifications.
        
        Args:
            batch_df: DataFrame with commits from a single batch
            
        Returns:
            Type priority score for the batch
        """
        # Classify all commits in the batch
        commit_types = []
        for _, commit in batch_df.iterrows():
            msg_subject = commit.get('msg_subject', '')
            commit_type = self.classify_commit_type(msg_subject)
            commit_types.append(commit_type)
        
        # Use the highest priority type in the batch
        if commit_types:
            type_priorities = [self.commit_type_priorities[t] for t in commit_types]
            return max(type_priorities)
        else:
            return self.commit_type_priorities['other']
    
    def calculate_batch_release_proximity(self, batch_df: pd.DataFrame, 
                                        release_dates: List[datetime] = None) -> float:
        """
        Calculate batch release proximity.
        
        Formula: exp(-days_to_nearest_release / 30)
        
        Args:
            batch_df: DataFrame with commits from a single batch
            release_dates: List of release dates (if available)
            
        Returns:
            Release proximity score for the batch
        """
        if not release_dates:
            # Without release data, use a default moderate score
            return 0.5
        
        # Get batch timestamp (use first commit)
        batch_ts = batch_df['commit_ts_utc'].min()
        batch_date = datetime.fromtimestamp(batch_ts)
        
        # Find nearest release
        min_days_to_release = float('inf')
        for release_date in release_dates:
            days_diff = abs((batch_date - release_date).days)
            min_days_to_release = min(min_days_to_release, days_diff)
        
        # Calculate proximity score
        if min_days_to_release == float('inf'):
            return 0.5
        else:
            return np.exp(-min_days_to_release / self.config['release_proximity_days'])
    
    def calculate_batch_importance_metrics(self, batch_df: pd.DataFrame,
                                         release_dates: List[datetime] = None) -> Dict[str, float]:
        """
        Calculate all raw importance metrics for a batch.
        
        Args:
            batch_df: DataFrame with commits from a single batch
            release_dates: List of release dates for proximity calculation
            
        Returns:
            Dictionary with raw importance metrics
        """
        return {
            'scale_raw': self.calculate_batch_scale(batch_df),
            'scope_raw': self.calculate_batch_scope(batch_df),
            'centrality_raw': self.calculate_batch_centrality(batch_df),
            'complexity_raw': self.calculate_batch_complexity(batch_df),
            'type_raw': self.calculate_batch_type_priority(batch_df),
            'release_raw': self.calculate_batch_release_proximity(batch_df, release_dates)
        }
    
    def normalize_importance_metrics(self, batch_metrics: pd.DataFrame) -> pd.DataFrame:
        """
        Apply MAD-Z normalization to importance metrics.
        
        Args:
            batch_metrics: DataFrame with raw importance metrics
            
        Returns:
            DataFrame with normalized importance metrics
        """
        batch_metrics = batch_metrics.copy()
        
        raw_columns = [
            'scale_raw', 'scope_raw', 'centrality_raw',
            'complexity_raw', 'type_raw', 'release_raw'
        ]
        
        for col in raw_columns:
            if col in batch_metrics.columns:
                z_col = col.replace('_raw', '_z')
                batch_metrics[z_col] = mad_z_score(batch_metrics[col])
        
        return batch_metrics
    
    def calculate_final_importance(self, batch_metrics: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate final importance scores using weighted combination.
        
        Args:
            batch_metrics: DataFrame with normalized importance metrics
            
        Returns:
            DataFrame with importance column added
        """
        batch_metrics = batch_metrics.copy()
        
        # Calculate weighted importance score
        batch_metrics['importance'] = (
            self.importance_weights['scale'] * batch_metrics['scale_z'] +
            self.importance_weights['scope'] * batch_metrics['scope_z'] +
            self.importance_weights['centrality'] * batch_metrics['centrality_z'] +
            self.importance_weights['complexity'] * batch_metrics['complexity_z'] +
            self.importance_weights['type'] * batch_metrics['type_z'] +
            self.importance_weights['release'] * batch_metrics['release_z']
        )
        
        return batch_metrics
    
    def process_all_batches(self, df: pd.DataFrame, 
                          release_dates: List[datetime] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Process all batches to calculate importance metrics.
        
        Args:
            df: DataFrame with all commits and batches
            release_dates: List of release dates for proximity calculation
            
        Returns:
            Tuple of (updated_commits_df, batch_importance_df)
        """
        logger.info("Calculating batch importance metrics...")
        
        batch_metrics_list = []
        
        for batch_id in df['batch_id'].unique():
            batch_df = df[df['batch_id'] == batch_id].copy()
            
            min_batch_churn = self.config.get('min_batch_churn', 1)
            if len(batch_df) >= 1 and batch_df['effective_churn'].sum() >= min_batch_churn:
                metrics = self.calculate_batch_importance_metrics(batch_df, release_dates)
                metrics['batch_id'] = batch_id
                metrics['batch_start_ts'] = batch_df['commit_ts_utc'].min()
                metrics['batch_end_ts'] = batch_df['commit_ts_utc'].max()
                metrics['batch_commit_count'] = len(batch_df)
                metrics['batch_total_churn'] = batch_df['effective_churn'].sum()
                
                batch_metrics_list.append(metrics)
        
        # Create batch metrics DataFrame
        if batch_metrics_list:
            batch_metrics_df = pd.DataFrame(batch_metrics_list)
            
            # Apply normalization
            batch_metrics_df = self.normalize_importance_metrics(batch_metrics_df)
            
            # Calculate final importance scores
            batch_metrics_df = self.calculate_final_importance(batch_metrics_df)
            
            # Add importance scores back to original DataFrame
            batch_importance_map = dict(zip(batch_metrics_df['batch_id'], 
                                          batch_metrics_df['importance']))
            df['batch_importance'] = df['batch_id'].map(batch_importance_map).fillna(0.0)
        else:
            batch_metrics_df = pd.DataFrame()
            df['batch_importance'] = 0.0
        
        logger.info(f"Calculated importance for {len(batch_metrics_df)} batches")
        return df, batch_metrics_df
    
    def print_importance_summary(self, batch_metrics_df: pd.DataFrame):
        """Print summary of importance calculation results."""
        if batch_metrics_df.empty:
            print("No batch importance metrics calculated.")
            return
        
        print(f"\n=== Batch Importance Summary ===")
        print(f"Total batches processed: {len(batch_metrics_df)}")
        print(f"Average importance score: {batch_metrics_df['importance'].mean():.3f}")
        print(f"Importance range: [{batch_metrics_df['importance'].min():.3f}, "
              f"{batch_metrics_df['importance'].max():.3f}]")
        
        # Top batches by importance
        top_batches = batch_metrics_df.nlargest(5, 'importance')
        print(f"\nTop 5 batches by importance:")
        for i, (_, batch) in enumerate(top_batches.iterrows()):
            print(f"  {i+1}. Batch {batch['batch_id']}: {batch['importance']:.3f} "
                  f"({batch['batch_commit_count']} commits)")
        
        # Importance component analysis
        print(f"\nAverage importance components:")
        if 'scale_z' in batch_metrics_df.columns:
            print(f"  Scale (Z): {batch_metrics_df['scale_z'].mean():.3f}")
            print(f"  Scope (Z): {batch_metrics_df['scope_z'].mean():.3f}")
            print(f"  Centrality (Z): {batch_metrics_df['centrality_z'].mean():.3f}")
            print(f"  Complexity (Z): {batch_metrics_df['complexity_z'].mean():.3f}")
            print(f"  Type (Z): {batch_metrics_df['type_z'].mean():.3f}")
            print(f"  Release (Z): {batch_metrics_df['release_z'].mean():.3f}")
        
        # Commit type distribution
        if hasattr(self, '_type_counts'):
            print(f"\nCommit type distribution:")
            for commit_type, count in self._type_counts.items():
                print(f"  {commit_type}: {count}")


if __name__ == "__main__":
    # Test the importance calculator
    calculator = BatchImportanceCalculator()
    
    # Load preprocessed data with effort metrics
    input_file = "../../../data/github_commit_data_test/linux_kernel_commits_with_effort.csv"
    
    try:
        df = pd.read_csv(input_file)
        
        # Process batches
        updated_df, batch_metrics_df = calculator.process_all_batches(df)
        calculator.print_importance_summary(batch_metrics_df)
        
        # Save results
        output_file = "../../../data/github_commit_data_test/linux_kernel_commits_with_importance.csv"
        batch_output_file = "../../../data/github_commit_data_test/linux_kernel_batch_importance.csv"
        
        updated_df.to_csv(output_file, index=False)
        batch_metrics_df.to_csv(batch_output_file, index=False)
        
        print(f"\nSaved importance metrics to {output_file}")
        print(f"Saved batch metrics to {batch_output_file}")
        
    except FileNotFoundError:
        print(f"Input file not found: {input_file}")
        print("Please run the effort calculation step first.")