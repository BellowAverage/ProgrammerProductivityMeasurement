#!/usr/bin/env python3
"""
MAD-Z Normalization and Statistical Utilities for FDS Algorithm

This module implements robust statistical normalization using Median Absolute Deviation (MAD)
which is more resistant to outliers than standard z-scores.
"""

import numpy as np
import pandas as pd
from typing import Union, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def mad_z_score(values: Union[np.ndarray, pd.Series], 
                median: Optional[float] = None,
                mad: Optional[float] = None,
                clip_range: tuple = (-3, 3)) -> np.ndarray:
    """
    Calculate MAD-Z scores for robust normalization.
    
    Formula: z = clip((x - median) / (1.4826 * MAD), -3, +3)
    
    Args:
        values: Input values to normalize
        median: Pre-computed median (if None, will compute)
        mad: Pre-computed MAD (if None, will compute)
        clip_range: Range to clip outliers (-3, 3) by default
        
    Returns:
        Array of MAD-Z scores
    """
    values = np.array(values)
    
    if median is None:
        median = np.median(values)
    
    if mad is None:
        mad = np.median(np.abs(values - median))
    
    # Handle zero MAD (all values are identical)
    if mad == 0:
        return np.zeros_like(values)
    
    # Calculate MAD-Z score with scaling factor 1.4826 for normal distribution equivalence
    z_scores = (values - median) / (1.4826 * mad)
    
    # Clip to range to handle extreme outliers
    z_scores = np.clip(z_scores, clip_range[0], clip_range[1])
    
    return z_scores


def compute_mad_stats(df: pd.DataFrame, 
                     column: str,
                     group_by: Optional[list] = None) -> pd.DataFrame:
    """
    Compute MAD statistics for a column, optionally grouped.
    
    Args:
        df: Input DataFrame
        column: Column to compute stats for
        group_by: Columns to group by (e.g., ['repo', 'quarter'])
        
    Returns:
        DataFrame with median and MAD values
    """
    if group_by is None:
        median_val = df[column].median()
        mad_val = df[column].mad()
        return pd.DataFrame({
            'median': [median_val],
            'mad': [mad_val]
        })
    else:
        return df.groupby(group_by)[column].agg([
            ('median', 'median'),
            ('mad', lambda x: np.median(np.abs(x - x.median())))
        ]).reset_index()


def normalize_column_by_group(df: pd.DataFrame,
                             column: str,
                             group_by: Optional[list] = None,
                             suffix: str = '_z') -> pd.DataFrame:
    """
    Add MAD-Z normalized column to DataFrame, optionally grouped.
    
    Args:
        df: Input DataFrame
        column: Column to normalize
        group_by: Columns to group by for normalization
        suffix: Suffix for the new normalized column
        
    Returns:
        DataFrame with added normalized column
    """
    df = df.copy()
    new_column = f"{column}{suffix}"
    
    if group_by is None:
        # Global normalization
        df[new_column] = mad_z_score(df[column])
    else:
        # Group-wise normalization
        def normalize_group(group):
            group = group.copy()
            group[new_column] = mad_z_score(group[column])
            return group
        
        df = df.groupby(group_by, group_keys=False).apply(normalize_group)
    
    logger.info(f"Normalized column '{column}' -> '{new_column}' (groups: {group_by})")
    return df


def entropy(values: np.ndarray, base: int = 2) -> float:
    """
    Calculate Shannon entropy of a distribution.
    
    Args:
        values: Array of values representing a distribution
        base: Logarithm base (2 for bits, e for nats)
        
    Returns:
        Entropy value
    """
    # Remove zeros and normalize to probabilities
    values = values[values > 0]
    if len(values) == 0:
        return 0.0
    
    probabilities = values / np.sum(values)
    
    if base == 2:
        return -np.sum(probabilities * np.log2(probabilities))
    else:
        return -np.sum(probabilities * np.log(probabilities))


def directory_entropy(dirs_touched: str, churn_by_dir: dict) -> float:
    """
    Calculate directory entropy based on code churn distribution.
    
    Args:
        dirs_touched: Semicolon-separated directory names
        churn_by_dir: Dictionary mapping directory -> churn amount
        
    Returns:
        Directory entropy value
    """
    if not dirs_touched or pd.isna(dirs_touched):
        return 0.0
    
    dirs = [d.strip() for d in str(dirs_touched).split(';') if d.strip()]
    if not dirs:
        return 0.0
    
    # Get churn values for touched directories
    churn_values = np.array([churn_by_dir.get(d, 1) for d in dirs])
    
    return entropy(churn_values)


def safe_log(x: Union[float, np.ndarray], base: float = np.e) -> Union[float, np.ndarray]:
    """
    Safe logarithm that handles zero and negative values.
    
    Args:
        x: Input value(s)
        base: Logarithm base
        
    Returns:
        log(1 + max(0, x))
    """
    x = np.maximum(0, x)
    if base == np.e:
        return np.log1p(x)
    else:
        return np.log1p(x) / np.log(base)


def print_normalization_summary(df: pd.DataFrame, columns: list):
    """
    Print summary statistics for normalized columns.
    
    Args:
        df: DataFrame with normalized columns
        columns: List of column names to summarize
    """
    print("\n=== MAD-Z Normalization Summary ===")
    for col in columns:
        if col in df.columns:
            stats = df[col].describe()
            print(f"\n{col}:")
            print(f"  Count: {stats['count']:.0f}")
            print(f"  Mean:  {stats['mean']:.3f}")
            print(f"  Std:   {stats['std']:.3f}")
            print(f"  Min:   {stats['min']:.3f}")
            print(f"  Max:   {stats['max']:.3f}")
        else:
            print(f"\nColumn '{col}' not found in DataFrame")


if __name__ == "__main__":
    # Test the normalization functions
    test_data = np.random.exponential(2, 1000)  # Skewed distribution
    
    print("Testing MAD-Z normalization...")
    z_scores = mad_z_score(test_data)
    
    print(f"Original data: mean={np.mean(test_data):.3f}, std={np.std(test_data):.3f}")
    print(f"MAD-Z scores: mean={np.mean(z_scores):.3f}, std={np.std(z_scores):.3f}")
    print(f"Range: [{np.min(z_scores):.3f}, {np.max(z_scores):.3f}]")