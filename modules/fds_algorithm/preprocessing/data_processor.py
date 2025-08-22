#!/usr/bin/env python3
"""
Data Preprocessing Module for FDS Algorithm

This module handles:
1. Noise filtering (vendor files, whitespace changes, etc.)
2. Directory co-change graph construction and PageRank
3. Key meta-flags (new files, key paths)
4. Time window preparation
"""

import pandas as pd
import numpy as np
import networkx as nx
from pathlib import Path
import re
import logging
from typing import Dict, List, Tuple, Set
from collections import defaultdict, Counter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataProcessor:
    """Main preprocessing class for FDS algorithm."""
    
    def __init__(self, config: dict = None):
        """
        Initialize with configuration parameters.
        
        Args:
            config: Configuration dictionary with preprocessing parameters
        """
        self.config = config or self._default_config()
        self.directory_graph = nx.Graph()
        self.directory_centrality = {}
        self.known_vendor_patterns = self._get_vendor_patterns()
        self.known_key_directories = self._get_key_directories()
    
    def _default_config(self) -> dict:
        """Default configuration for preprocessing."""
        return {
            'noise_threshold': 0.1,  # Below this ratio, consider as noise
            'pagerank_damping': 0.85,
            'pagerank_iterations': 100,
            'min_churn_for_edge': 2,  # Minimum co-change to create directory edge
            'key_file_extensions': {'.c', '.h', '.py', '.js', '.java', '.cpp', '.hpp'},
            'vendor_noise_factor': 0.1,  # Down-weight vendor files
            'whitespace_noise_factor': 0.3,  # Down-weight whitespace changes
        }
    
    def _get_vendor_patterns(self) -> List[re.Pattern]:
        """Patterns to identify vendor/generated files."""
        patterns = [
            r'vendor/',
            r'third_party/',
            r'node_modules/',
            r'\.min\.',
            r'generated/',
            r'build/',
            r'dist/',
            r'\.lock$',
            r'package-lock\.json$',
            r'yarn\.lock$',
            r'Cargo\.lock$',
        ]
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def _get_key_directories(self) -> Set[str]:
        """Directories that are considered architecturally important."""
        return {
            'kernel', 'core', 'src', 'lib', 'include', 'drivers', 'arch',
            'fs', 'net', 'security', 'crypto', 'mm', 'ipc', 'init',
            'api', 'engine', 'framework', 'service', 'controller',
            'model', 'database', 'config', 'auth', 'middleware'
        }
    
    def detect_noise(self, row: pd.Series) -> float:
        """
        Detect and quantify noise in a commit.
        
        Args:
            row: Commit row from DataFrame
            
        Returns:
            Noise factor (0.0 = no noise, 1.0 = pure noise)
        """
        noise_factors = []
        
        # Check for vendor files
        dirs_touched = str(row.get('dirs_touched', ''))
        file_types = str(row.get('file_types', ''))
        msg_subject = str(row.get('msg_subject', ''))
        
        # Vendor file detection
        vendor_score = 0
        for pattern in self.known_vendor_patterns:
            if pattern.search(dirs_touched) or pattern.search(file_types):
                vendor_score = 1
                break
        
        if vendor_score > 0:
            noise_factors.append(self.config['vendor_noise_factor'])
        
        # Whitespace/formatting detection
        whitespace_indicators = [
            'format', 'style', 'indent', 'whitespace', 'spacing',
            'trailing', 'cleanup', 'lint', 'prettier', 'clang-format'
        ]
        
        if any(indicator in msg_subject.lower() for indicator in whitespace_indicators):
            # High insertions + deletions but low net change suggests formatting
            insertions = row.get('insertions', 0)
            deletions = row.get('deletions', 0)
            if insertions + deletions > 50 and abs(insertions - deletions) < 10:
                noise_factors.append(self.config['whitespace_noise_factor'])
        
        # Return worst (highest) noise factor
        return max(noise_factors) if noise_factors else 1.0
    
    def compute_effective_churn(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute effective churn with noise reduction.
        
        Args:
            df: DataFrame with commit data
            
        Returns:
            DataFrame with effective_churn column added
        """
        df = df.copy()
        
        # Apply noise detection
        df['noise_factor'] = df.apply(self.detect_noise, axis=1)
        
        # Calculate effective churn
        df['raw_churn'] = df['insertions'] + df['deletions']
        df['effective_churn'] = df['raw_churn'] * df['noise_factor']
        
        logger.info(f"Applied noise filtering. Avg noise factor: {df['noise_factor'].mean():.3f}")
        return df
    
    def build_directory_graph(self, df: pd.DataFrame) -> nx.Graph:
        """
        Build directory co-change graph and compute centrality.
        
        Args:
            df: DataFrame with commit data
            
        Returns:
            NetworkX graph of directory relationships
        """
        # Track co-changes between directories
        cochange_count = defaultdict(int)
        
        for _, row in df.iterrows():
            dirs_touched = str(row.get('dirs_touched', ''))
            if not dirs_touched or pd.isna(dirs_touched):
                continue
            
            dirs = [d.strip() for d in dirs_touched.split(';') if d.strip()]
            churn = row.get('effective_churn', 0)
            
            # Add edges for all directory pairs in this commit
            for i, dir1 in enumerate(dirs):
                for dir2 in dirs[i+1:]:
                    if dir1 != dir2:
                        edge = tuple(sorted([dir1, dir2]))
                        cochange_count[edge] += churn
        
        # Build graph with weighted edges
        self.directory_graph = nx.Graph()
        for (dir1, dir2), weight in cochange_count.items():
            if weight >= self.config['min_churn_for_edge']:
                self.directory_graph.add_edge(dir1, dir2, weight=weight)
        
        # Compute PageRank centrality
        if len(self.directory_graph.nodes()) > 0:
            self.directory_centrality = nx.pagerank(
                self.directory_graph,
                weight='weight',
                alpha=self.config['pagerank_damping'],
                max_iter=self.config['pagerank_iterations']
            )
        else:
            self.directory_centrality = {}
        
        logger.info(f"Built directory graph: {len(self.directory_graph.nodes())} nodes, "
                   f"{len(self.directory_graph.edges())} edges")
        
        return self.directory_graph
    
    def compute_directory_centrality(self, dirs_touched: str) -> float:
        """
        Compute average centrality for directories touched in a commit.
        
        Args:
            dirs_touched: Semicolon-separated directory names
            
        Returns:
            Average PageRank centrality
        """
        if not dirs_touched or pd.isna(dirs_touched):
            return 0.0
        
        dirs = [d.strip() for d in str(dirs_touched).split(';') if d.strip()]
        if not dirs:
            return 0.0
        
        centralities = [self.directory_centrality.get(d, 0.0) for d in dirs]
        return np.mean(centralities) if centralities else 0.0
    
    def detect_key_paths(self, row: pd.Series) -> int:
        """
        Detect if commit touches key architectural paths.
        
        Args:
            row: Commit row from DataFrame
            
        Returns:
            Number of lines touching key paths
        """
        dirs_touched = str(row.get('dirs_touched', ''))
        if not dirs_touched or pd.isna(dirs_touched):
            return 0
        
        dirs = [d.strip() for d in dirs_touched.split(';') if d.strip()]
        
        # Check if any directory is in our key directories set
        key_dirs = [d for d in dirs if d.lower() in self.known_key_directories]
        
        if key_dirs:
            # Estimate proportion of churn in key directories
            key_proportion = len(key_dirs) / len(dirs)
            total_churn = row.get('effective_churn', 0)
            return int(total_churn * key_proportion)
        
        return 0
    
    def detect_new_files(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect new file creation based on commit history.
        
        Args:
            df: DataFrame with commit data (sorted by timestamp)
            
        Returns:
            DataFrame with new_file_lines column added
        """
        df = df.copy()
        
        # Simple heuristic: if a commit has high insertions and low deletions,
        # and mentions "add", "new", "create" in message, likely new files
        df['new_file_indicator'] = df.apply(
            lambda row: (
                'add' in str(row.get('msg_subject', '')).lower() or
                'new' in str(row.get('msg_subject', '')).lower() or
                'create' in str(row.get('msg_subject', '')).lower()
            ) and (
                row.get('insertions', 0) > 2 * row.get('deletions', 0)
            ),
            axis=1
        )
        
        # Estimate new file lines
        df['new_file_lines'] = df.apply(
            lambda row: int(row.get('insertions', 0) * 0.8) if row['new_file_indicator'] else 0,
            axis=1
        )
        
        logger.info(f"Detected {df['new_file_indicator'].sum()} potential new file commits")
        return df
    
    def add_metadata_flags(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add all metadata flags to the DataFrame.
        
        Args:
            df: DataFrame with commit data
            
        Returns:
            DataFrame with metadata columns added
        """
        df = df.copy()
        
        # Effective churn with noise reduction
        df = self.compute_effective_churn(df)
        
        # Build directory graph
        self.build_directory_graph(df)
        
        # Add centrality scores
        df['directory_centrality'] = df['dirs_touched'].apply(self.compute_directory_centrality)
        
        # Add key path detection
        df['key_path_lines'] = df.apply(self.detect_key_paths, axis=1)
        
        # Add new file detection
        df = self.detect_new_files(df)
        
        logger.info("Added all metadata flags to DataFrame")
        return df
    
    def process_data(self, input_file: str, output_file: str = None) -> pd.DataFrame:
        """
        Main processing pipeline.
        
        Args:
            input_file: Path to clustered commit data CSV
            output_file: Path to save processed data (optional)
            
        Returns:
            Processed DataFrame
        """
        logger.info(f"Loading data from {input_file}")
        df = pd.read_csv(input_file)
        
        # Ensure data is sorted by timestamp
        df = df.sort_values('commit_ts_utc').reset_index(drop=True)
        
        # Add all preprocessing features
        df = self.add_metadata_flags(df)
        
        if output_file:
            df.to_csv(output_file, index=False)
            logger.info(f"Saved processed data to {output_file}")
        
        # Print summary statistics
        self._print_processing_summary(df)
        
        return df
    
    def _print_processing_summary(self, df: pd.DataFrame):
        """Print summary of preprocessing results."""
        print(f"\n=== Data Processing Summary ===")
        print(f"Total commits: {len(df)}")
        print(f"Unique authors: {df['author_email'].nunique()}")
        print(f"Unique batches: {df['batch_id'].nunique()}")
        print(f"Average effective churn: {df['effective_churn'].mean():.1f}")
        print(f"Directory graph nodes: {len(self.directory_graph.nodes())}")
        print(f"Directory graph edges: {len(self.directory_graph.edges())}")
        print(f"Commits with new files: {df['new_file_indicator'].sum()}")
        print(f"Commits touching key paths: {(df['key_path_lines'] > 0).sum()}")
        
        # Top directories by centrality
        if self.directory_centrality:
            top_dirs = sorted(self.directory_centrality.items(), 
                            key=lambda x: x[1], reverse=True)[:5]
            print(f"\nTop directories by centrality:")
            for dir_name, centrality in top_dirs:
                print(f"  {dir_name}: {centrality:.4f}")


if __name__ == "__main__":
    # Test the preprocessing pipeline
    processor = DataProcessor()
    
    # Process the clustered data
    input_file = "../../data/github_commit_data_test/linux_kernel_commits_clustered.csv"
    output_file = "../../data/github_commit_data_test/linux_kernel_commits_processed.csv"
    
    df = processor.process_data(input_file, output_file)
    print(f"\nProcessed {len(df)} commits with {df['batch_id'].nunique()} batches")