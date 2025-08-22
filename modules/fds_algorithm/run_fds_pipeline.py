#!/usr/bin/env python3
"""
Complete FDS Pipeline Runner

This script runs the complete Fair Developer Score algorithm pipeline:
1. Data preprocessing (noise filtering, directory graph, metadata)
2. Developer effort calculation (6 dimensions)
3. Batch importance calculation (6 dimensions)
4. Final FDS calculation and reporting
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
import sys
import time
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fds_pipeline.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import our modules
sys.path.append(str(Path(__file__).parent))
from preprocessing.data_processor import DataProcessor
from effort_calculator.developer_effort import DeveloperEffortCalculator
from importance_calculator.batch_importance import BatchImportanceCalculator
from fds_calculator import FDSCalculator


class FDSPipeline:
    """Complete FDS analysis pipeline."""
    
    def __init__(self, config: dict = None):
        """
        Initialize the FDS pipeline.
        
        Args:
            config: Configuration dictionary for all components
        """
        self.config = config or self._default_config()
        
        # Initialize all components
        self.preprocessor = DataProcessor(self.config.get('preprocessing', {}))
        self.effort_calculator = DeveloperEffortCalculator(self.config.get('effort', {}))
        self.importance_calculator = BatchImportanceCalculator(self.config.get('importance', {}))
        self.fds_calculator = FDSCalculator(self.config.get('fds', {}))
        
        self.results = {}
    
    def _default_config(self) -> dict:
        """Default configuration for the entire pipeline."""
        return {
            'preprocessing': {
                'noise_threshold': 0.1,
                'pagerank_damping': 0.85,
                'pagerank_iterations': 100,
                'min_churn_for_edge': 2,
                'vendor_noise_factor': 0.1,
                'whitespace_noise_factor': 0.3,
                'key_file_extensions': {'.c', '.h', '.py', '.js', '.java', '.cpp', '.hpp'},
            },
            'effort': {
                'speed_half_life_hours': 24,
                'novelty_cap': 2.0,
                'min_batch_size': 1,
            },
            'importance': {
                'release_proximity_days': 30,
                'complexity_scale_factor': 1.0,
                'min_batch_churn': 1,
            },
            'fds': {
                'time_window_days': 90,
                'min_contributions': 1,
                'contribution_threshold': 0.01,
            }
        }
    
    def run_preprocessing(self, input_file: str, output_file: str = None) -> pd.DataFrame:
        """
        Step 1: Run data preprocessing.
        
        Args:
            input_file: Path to clustered commit data
            output_file: Path to save processed data
            
        Returns:
            Processed DataFrame
        """
        logger.info("="*60)
        logger.info("STEP 1: DATA PREPROCESSING")
        logger.info("="*60)
        
        start_time = time.time()
        
        try:
            df = self.preprocessor.process_data(input_file, output_file)
            self.results['preprocessed_data'] = df
            
            elapsed = time.time() - start_time
            logger.info(f"Preprocessing completed in {elapsed:.2f} seconds")
            logger.info(f"   Processed {len(df)} commits with {df['batch_id'].nunique()} batches")
            
            return df
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {str(e)}")
            raise
    
    def run_effort_calculation(self, df: pd.DataFrame, output_file: str = None) -> pd.DataFrame:
        """
        Step 2: Calculate developer effort metrics.
        
        Args:
            df: Preprocessed DataFrame
            output_file: Path to save effort data
            
        Returns:
            DataFrame with effort metrics
        """
        logger.info("="*60)
        logger.info("STEP 2: DEVELOPER EFFORT CALCULATION")
        logger.info("="*60)
        
        start_time = time.time()
        
        try:
            df_with_effort = self.effort_calculator.process_all_batches(df)
            self.effort_calculator.print_effort_summary(df_with_effort)
            
            if output_file:
                df_with_effort.to_csv(output_file, index=False)
                logger.info(f"Saved effort data to {output_file}")
            
            self.results['effort_data'] = df_with_effort
            
            elapsed = time.time() - start_time
            logger.info(f"Effort calculation completed in {elapsed:.2f} seconds")
            
            return df_with_effort
            
        except Exception as e:
            logger.error(f"Effort calculation failed: {str(e)}")
            raise
    
    def run_importance_calculation(self, df: pd.DataFrame, 
                                 output_file: str = None,
                                 batch_output_file: str = None) -> tuple:
        """
        Step 3: Calculate batch importance metrics.
        
        Args:
            df: DataFrame with effort metrics
            output_file: Path to save importance data
            batch_output_file: Path to save batch metrics
            
        Returns:
            Tuple of (df_with_importance, batch_metrics_df)
        """
        logger.info("="*60)
        logger.info("STEP 3: BATCH IMPORTANCE CALCULATION")
        logger.info("="*60)
        
        start_time = time.time()
        
        try:
            df_with_importance, batch_metrics = self.importance_calculator.process_all_batches(df)
            self.importance_calculator.print_importance_summary(batch_metrics)
            
            if output_file:
                df_with_importance.to_csv(output_file, index=False)
                logger.info(f"Saved importance data to {output_file}")
            
            if batch_output_file and not batch_metrics.empty:
                batch_metrics.to_csv(batch_output_file, index=False)
                logger.info(f"Saved batch metrics to {batch_output_file}")
            
            self.results['importance_data'] = df_with_importance
            self.results['batch_metrics'] = batch_metrics
            
            elapsed = time.time() - start_time
            logger.info(f"Importance calculation completed in {elapsed:.2f} seconds")
            
            return df_with_importance, batch_metrics
            
        except Exception as e:
            logger.error(f"Importance calculation failed: {str(e)}")
            raise
    
    def run_fds_calculation(self, df: pd.DataFrame, output_dir: str = None) -> dict:
        """
        Step 4: Calculate final FDS scores.
        
        Args:
            df: DataFrame with effort and importance metrics
            output_dir: Directory to save all FDS results
            
        Returns:
            Dictionary with all FDS analysis results
        """
        logger.info("="*60)
        logger.info("STEP 4: FINAL FDS CALCULATION")
        logger.info("="*60)
        
        start_time = time.time()
        
        try:
            # Calculate contributions
            df_with_contributions = self.fds_calculator.calculate_contributions(df)
            
            # Generate all analysis results
            fds_scores = self.fds_calculator.aggregate_contributions_by_author(df_with_contributions)
            detailed_metrics = self.fds_calculator.calculate_detailed_metrics(df_with_contributions)
            batch_breakdown = self.fds_calculator.generate_contribution_breakdown(df_with_contributions)
            
            results = {
                'contributions': df_with_contributions,
                'fds_scores': fds_scores,
                'detailed_metrics': detailed_metrics,
                'batch_breakdown': batch_breakdown
            }
            
            # Save results
            if output_dir:
                self.fds_calculator.save_results(results, output_dir)
            
            # Print comprehensive summary
            self.fds_calculator.print_comprehensive_summary(results)
            
            self.results.update(results)
            
            elapsed = time.time() - start_time
            logger.info(f"FDS calculation completed in {elapsed:.2f} seconds")
            
            return results
            
        except Exception as e:
            logger.error(f"FDS calculation failed: {str(e)}")
            raise
    
    def run_complete_pipeline(self, input_file: str, output_dir: str = None) -> dict:
        """
        Run the complete FDS analysis pipeline.
        
        Args:
            input_file: Path to clustered commit data CSV
            output_dir: Directory to save all outputs
            
        Returns:
            Dictionary with all analysis results
        """
        pipeline_start = time.time()
        
        logger.info("STARTING COMPLETE FDS ANALYSIS PIPELINE")
        logger.info(f"Input file: {input_file}")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Prepare output paths
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                
                processed_file = output_path / "linux_kernel_commits_processed.csv"
                effort_file = output_path / "linux_kernel_commits_with_effort.csv"
                importance_file = output_path / "linux_kernel_commits_with_importance.csv"
                batch_file = output_path / "linux_kernel_batch_metrics.csv"
                fds_output_dir = output_path / "fds_results"
            else:
                processed_file = effort_file = importance_file = batch_file = fds_output_dir = None
            
            # Step 1: Preprocessing
            df = self.run_preprocessing(input_file, processed_file)
            
            # Step 2: Effort calculation
            df = self.run_effort_calculation(df, effort_file)
            
            # Step 3: Importance calculation
            df, batch_metrics = self.run_importance_calculation(df, importance_file, batch_file)
            
            # Step 4: FDS calculation
            fds_results = self.run_fds_calculation(df, fds_output_dir)
            
            # Final summary
            total_elapsed = time.time() - pipeline_start
            logger.info("="*60)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY!")
            logger.info("="*60)
            logger.info(f"Total execution time: {total_elapsed:.2f} seconds")
            logger.info(f"Analyzed {len(df)} commits from {df['author_email'].nunique()} developers")
            logger.info(f"Generated FDS scores for {len(fds_results['fds_scores'])} active contributors")
            logger.info(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            return self.results
            
        except Exception as e:
            logger.error(f"PIPELINE FAILED: {str(e)}")
            raise


def main():
    """Main entry point for the FDS pipeline."""
    
    # Configuration
    config = {
        'preprocessing': {
            'noise_threshold': 0.1,
            'pagerank_damping': 0.85,
            'pagerank_iterations': 100,
            'min_churn_for_edge': 2,
            'vendor_noise_factor': 0.1,
            'whitespace_noise_factor': 0.3,
            'key_file_extensions': {'.c', '.h', '.py', '.js', '.java', '.cpp', '.hpp'},
        },
        'effort': {
            'speed_half_life_hours': 24,
            'novelty_cap': 2.0,
        },
        'importance': {
            'release_proximity_days': 30,
            'complexity_scale_factor': 1.0,
        },
        'fds': {
            'time_window_days': 90,
            'contribution_threshold': 0.01,
        }
    }
    
    # File paths
    input_file = "../../data/github_commit_data_test/linux_kernel_commits_clustered.csv"
    output_dir = "../../data/github_commit_data_test/fds_analysis"
    
    # Run pipeline
    pipeline = FDSPipeline(config)
    results = pipeline.run_complete_pipeline(input_file, output_dir)
    
    return results


if __name__ == "__main__":
    results = main()