#!/usr/bin/env python3
"""
Local FDS Analyzer - Standalone version for testing and analysis
Run this script to analyze any GitHub repository locally without the web interface.
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import shutil
import logging

# Setup paths
script_dir = Path(__file__).parent
sys.path.append(str(script_dir / "dev_productivity"))

def setup_logging():
    """Setup logging for the analysis"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('fds_analysis.log')
        ]
    )
    return logging.getLogger(__name__)

def get_user_input():
    """Get input from user for analysis parameters"""
    print("\nLOCAL FDS ANALYZER")
    print("=" * 60)
    print("This tool will analyze developer contributions for any GitHub repository.")
    print("Results will be saved to a local folder for your review.")
    print()
    
    # Use hardcoded values for testing
    token = os.getenv("GITHUB_TOKEN", "YOUR_GITHUB_TOKEN_HERE")
    repo_url = "https://github.com/facebook/react"
    commit_limit = 100
    
    print(f"Using repository: {repo_url}")
    print(f"Commit limit: {commit_limit}")
    print(f"GitHub token: {token[:10]}...")
    print()
    
    # Create output directory
    repo_name = repo_url.rstrip('/').split('/')[-1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(f"fds_results_{repo_name}_{timestamp}")
    output_dir.mkdir(exist_ok=True)
    
    return {
        'token': token,
        'repo_url': repo_url,
        'commit_limit': commit_limit,
        'output_dir': output_dir,
        'repo_name': repo_name
    }

def run_data_acquisition(params, logger):
    """Run GitHub data acquisition"""
    logger.info("Step 1: Acquiring commit data from GitHub...")
    
    try:
        from data_acquisition.from_github.acquire_pretrained_data import GitHubDataAcquisition
        
        # Create temporary file for commit data
        temp_file = params['output_dir'] / 'raw_commits.csv'
        
        # Initialize data acquisition
        acquisition = GitHubDataAcquisition(
            github_token=params['token'],
            output_file=str(temp_file),
            commit_limit=params['commit_limit']
        )
        
        # Extract repo owner and name from URL
        url_parts = params['repo_url'].rstrip('/').split('/')
        repo_owner = url_parts[-2]
        repo_name = url_parts[-1]
        
        logger.info(f"   Repository: {repo_owner}/{repo_name}")
        logger.info(f"   Commit limit: {params['commit_limit']}")
        
        # Fetch commit data
        commits_data = acquisition.fetch_commits(repo_owner, repo_name)
        
        if not commits_data:
            logger.error("No commit data retrieved!")
            return None
        
        logger.info(f"Retrieved {len(commits_data)} commits")
        
        # Convert to DataFrame and save
        df = pd.DataFrame(commits_data)
        df.to_csv(temp_file, index=False)
        
        return str(temp_file)
        
    except Exception as e:
        logger.error(f"Data acquisition failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_torque_clustering(commit_file, output_dir, logger):
    """Run TORQUE clustering on commit data"""
    logger.info("Step 2: Running TORQUE clustering...")
    
    try:
        from torque_clustering.run_torque import run_torque_clustering
        
        # Output file for clustered data
        clustered_file = output_dir / 'commits_clustered.csv'
        summary_file = output_dir / 'clustering_summary.txt'
        
        # Run clustering
        result = run_torque_clustering(
            input_file=commit_file,
            output_file=str(clustered_file),
            summary_file=str(summary_file)
        )
        
        if result:
            logger.info("TORQUE clustering completed")
            
            # Read summary
            if summary_file.exists():
                with open(summary_file, 'r') as f:
                    summary = f.read()
                logger.info(f"Clustering Summary:\n{summary}")
            
            return str(clustered_file)
        else:
            logger.error("TORQUE clustering failed!")
            return None
            
    except Exception as e:
        logger.error(f"TORQUE clustering failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def run_fds_analysis(clustered_file, output_dir, logger):
    """Run FDS analysis on clustered data"""
    logger.info("Step 3: Running FDS analysis...")
    
    try:
        # Import FDS components
        from fds_algorithm.preprocessing.data_processor import DataProcessor
        from fds_algorithm.effort_calculator.developer_effort import DeveloperEffortCalculator
        from fds_algorithm.importance_calculator.batch_importance import BatchImportanceCalculator
        from fds_algorithm.fds_calculator import FDSCalculator
        
        # Configuration
        config = {
            'whitespace_noise_factor': 0.3,
            'pagerank_iterations': 100,
            'key_file_extensions': ['.py', '.js', '.java', '.cpp', '.c', '.h'],
            'min_batch_size': 1,
            'min_batch_churn': 1,
            'novelty_cap': 10.0,
            'speed_half_life_hours': 24.0,
            'release_proximity_days': 30.0,
            'complexity_scale_factor': 1.0,
            'time_window_days': 365,  # Use full year for repository analysis
            'min_contributions': 1,
            'contribution_threshold': 0.001  # Very low threshold
        }
        
        # Step 3a: Data preprocessing
        logger.info("   - Preprocessing data...")
        processor = DataProcessor(config)
        processed_df = processor.process_data(clustered_file)
        
        processed_file = output_dir / 'processed_data.csv'
        processed_df.to_csv(processed_file, index=False)
        logger.info(f"   - Processed {len(processed_df)} commits")
        
        # Step 3b: Calculate developer effort
        logger.info("   - Calculating developer effort...")
        effort_calc = DeveloperEffortCalculator(config)
        effort_df = effort_calc.process_all_batches(processed_df)
        
        effort_file = output_dir / 'developer_effort.csv'
        effort_df.to_csv(effort_file, index=False)
        logger.info(f"   - Calculated effort for {len(effort_df)} commits")
        
        # Step 3c: Calculate batch importance
        logger.info("   - Calculating batch importance...")
        importance_calc = BatchImportanceCalculator(config)
        commits_with_importance, importance_df = importance_calc.process_all_batches(processed_df)
        
        importance_file = output_dir / 'batch_importance.csv'
        importance_df.to_csv(importance_file, index=False)
        
        # Safe logging for batch count
        if len(importance_df) > 0 and 'batch_id' in importance_df.columns:
            unique_batches = importance_df['batch_id'].nunique()
        else:
            unique_batches = 0
        logger.info(f"   - Calculated importance for {unique_batches} batches")
        
        # Step 3d: Merge and calculate final FDS scores
        logger.info("   - Calculating final FDS scores...")
        
        # Merge effort and importance data - handle cases where importance data might be empty
        if len(commits_with_importance) > 0:
            merged_df = effort_df.merge(
                commits_with_importance,
                on=['hash', 'batch_id'],
                suffixes=('_effort', '_importance')
            )
            
            # Clean up column names by removing suffixes from essential columns
            essential_columns = [
                'hash', 'author_name', 'author_email', 'commit_ts_utc', 'batch_id',
                'effective_churn', 'files_changed', 'insertions', 'deletions',
                'dirs_touched', 'contribution'
            ]
            for col in essential_columns:
                if f'{col}_effort' in merged_df.columns:
                    merged_df[col] = merged_df[f'{col}_effort']
                elif f'{col}_importance' in merged_df.columns:
                    merged_df[col] = merged_df[f'{col}_importance']
            
            # Ensure we have the batch importance column
            if 'batch_importance' in merged_df.columns:
                merged_df['importance'] = merged_df['batch_importance']
            else:
                merged_df['importance'] = 1.0
        else:
            # If no importance data, use effort data only and add default importance
            merged_df = effort_df.copy()
            merged_df['importance'] = 1.0  # Default importance for all commits
        
        merged_file = output_dir / 'merged_data.csv'
        merged_df.to_csv(merged_file, index=False)
        
        # Debug: Print column information
        logger.info(f"   - Merged dataframe columns: {list(merged_df.columns)}")
        logger.info(f"   - Merged dataframe shape: {merged_df.shape}")
        
        # Calculate FDS
        fds_calc = FDSCalculator(config)
        individual_contributions = fds_calc.calculate_contributions(merged_df)
        fds_scores = fds_calc.aggregate_contributions_by_author(individual_contributions)
        detailed_metrics = fds_calc.calculate_detailed_metrics(individual_contributions)
        
        # Save results
        contributions_file = output_dir / 'individual_contributions.csv'
        individual_contributions.to_csv(contributions_file, index=False)
        
        fds_scores_file = output_dir / 'fds_scores.csv'
        fds_scores.to_csv(fds_scores_file, index=False)
        
        detailed_file = output_dir / 'detailed_metrics.csv'
        detailed_metrics.to_csv(detailed_file, index=False)
        
        logger.info(f"FDS analysis completed for {len(fds_scores)} developers")
        
        return {
            'fds_scores': fds_scores,
            'detailed_metrics': detailed_metrics,
            'individual_contributions': individual_contributions,
            'processed_df': processed_df
        }
        
    except Exception as e:
        logger.error(f"FDS analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_summary_report(results, params, logger):
    """Generate a human-readable summary report"""
    logger.info("Step 4: Generating summary report...")
    
    try:
        fds_scores = results['fds_scores']
        detailed_metrics = results['detailed_metrics']
        processed_df = results['processed_df']
        
        report_file = params['output_dir'] / 'FDS_Analysis_Report.txt'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("FDS ANALYSIS REPORT\n")
            f.write("=" * 80 + "\n")
            f.write(f"Repository: {params['repo_url']}\n")
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Commits Analyzed: {len(processed_df)}\n")
            f.write(f"Developers Found: {len(fds_scores)}\n")
            f.write(f"Unique Batches: {processed_df['batch_id'].nunique()}\n")
            f.write("\n")
            
            if len(fds_scores) > 0:
                f.write("TOP DEVELOPERS BY FDS SCORE\n")
                f.write("-" * 40 + "\n")
                
                # Sort by FDS score
                top_developers = fds_scores.sort_values('fds', ascending=False).head(10)
                
                for i, (_, dev) in enumerate(top_developers.iterrows(), 1):
                    f.write(f"{i:2d}. {dev['author_email']}\n")
                    f.write(f"     FDS Score: {dev['fds']:.3f}\n")
                    f.write(f"     Total Churn: {dev['total_churn']}\n")
                    f.write(f"     Commits: {dev['commit_count']}\n")
                    f.write(f"     Active Days: {dev['active_days']}\n")
                    f.write("\n")
                
                f.write("\nDETAILED METRICS SUMMARY\n")
                f.write("-" * 40 + "\n")
                f.write(f"Average FDS Score: {fds_scores['fds'].mean():.3f}\n")
                f.write(f"Median FDS Score: {fds_scores['fds'].median():.3f}\n")
                f.write(f"Max FDS Score: {fds_scores['fds'].max():.3f}\n")
                f.write(f"Min FDS Score: {fds_scores['fds'].min():.3f}\n")
                
            else:
                f.write("WARNING: NO DEVELOPERS FOUND!\n")
                f.write("This might indicate an issue with the analysis parameters\n")
                f.write("or the data processing pipeline.\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("FILES GENERATED:\n")
            f.write("- raw_commits.csv: Original GitHub commit data\n")
            f.write("- commits_clustered.csv: TORQUE clustered batches\n")
            f.write("- processed_data.csv: Preprocessed data with features\n")
            f.write("- developer_effort.csv: Developer effort calculations\n")
            f.write("- batch_importance.csv: Batch importance calculations\n")
            f.write("- individual_contributions.csv: Per-commit contributions\n")
            f.write("- fds_scores.csv: Final FDS scores per developer\n")
            f.write("- detailed_metrics.csv: Detailed developer metrics\n")
            f.write("- FDS_Analysis_Report.txt: This summary report\n")
            f.write("- fds_analysis.log: Detailed execution log\n")
        
        logger.info(f"Summary report generated: {report_file}")
        return report_file
        
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return None

def print_results_summary(results, params):
    """Print a quick summary to console"""
    if not results:
        print("\nAnalysis failed - no results to display")
        return
    
    fds_scores = results['fds_scores']
    
    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print(f"Repository: {params['repo_name']}")
    print(f"Total Developers: {len(fds_scores)}")
    print(f"Results saved to: {params['output_dir']}")
    print()
    
    if len(fds_scores) > 0:
        print("TOP 5 DEVELOPERS:")
        top_5 = fds_scores.sort_values('fds', ascending=False).head(5)
        
        for i, (_, dev) in enumerate(top_5.iterrows(), 1):
            print(f"   {i}. {dev['author_email']}")
            print(f"      FDS Score: {dev['fds']:.3f}")
            print(f"      Total Churn: {dev['total_churn']}")
            print()
    else:
        print("WARNING: NO DEVELOPERS FOUND!")
        print("   Check the analysis log for debugging information.")
    
    print(f"Open folder: {params['output_dir'].absolute()}")
    print(f"Read report: {params['output_dir'] / 'FDS_Analysis_Report.txt'}")

def main():
    """Main execution function"""
    # Setup
    logger = setup_logging()
    
    try:
        # Get user input
        params = get_user_input()
        if not params:
            return
        
        logger.info(f"Starting FDS analysis for {params['repo_url']}")
        
        # Step 1: Data acquisition
        commit_file = run_data_acquisition(params, logger)
        if not commit_file:
            print("Data acquisition failed! Check the log for details.")
            return
        
        # Step 2: TORQUE clustering
        clustered_file = run_torque_clustering(commit_file, params['output_dir'], logger)
        if not clustered_file:
            print("TORQUE clustering failed! Check the log for details.")
            return
        
        # Step 3: FDS analysis
        results = run_fds_analysis(clustered_file, params['output_dir'], logger)
        if not results:
            print("FDS analysis failed! Check the log for details.")
            return
        
        # Step 4: Generate report
        report_file = generate_summary_report(results, params, logger)
        
        # Print summary
        print_results_summary(results, params)
        
        logger.info("Analysis completed successfully!")
        
    except KeyboardInterrupt:
        print("\nAnalysis interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()