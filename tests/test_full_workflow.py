#!/usr/bin/env python3
"""
Full Workflow Test Script

Tests the complete news analyst workflow by processing URLs from an input file
and generating a summary of the results.
"""

import os
import sys
import time
import logging
import argparse
import traceback
from datetime import datetime
from tabulate import tabulate
from typing import List, Dict, Any, Optional, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.config_manager import ConfigManager
from src.clients.claude_client import ClaudeClient, SecretConfig
from src.workflows.news_analyzer import NewsAnalysisWorkflow

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('tests/test_full_workflow.log')
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test the complete news analyst workflow")
    parser.add_argument(
        "--input-file", 
        default="tests/url_input.txt", 
        help="File containing URLs to test (one per line)"
    )
    parser.add_argument(
        "--config", 
        default="config.yaml", 
        help="Path to configuration file"
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=None,
        help="Maximum number of URLs to process (default: all)"
    )
    parser.add_argument(
        "--delay", 
        type=float, 
        default=2.0, 
        help="Delay between requests in seconds"
    )
    return parser.parse_args()

def read_urls(file_path: str, max_urls: Optional[int] = None) -> List[str]:
    """
    Read URLs from a file, one per line.
    
    Args:
        file_path: Path to the file containing URLs
        max_urls: Maximum number of URLs to return
        
    Returns:
        List of URLs
    """
    try:
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        if max_urls is not None and max_urls > 0:
            urls = urls[:max_urls]
            
        return urls
    except Exception as e:
        logger.error(f"Error reading URLs from {file_path}: {e}")
        return []

def initialize_claude_client(config: ConfigManager) -> Optional[ClaudeClient]:
    """
    Initialize the Claude client using the configuration.
    
    Args:
        config: Configuration manager
        
    Returns:
        Initialized Claude client or None if initialization fails
    """
    try:
        # Check for direct API key first
        api_key = config.get('api.claude.api_key')
        if api_key:
            logger.info("Using provided API key")
            return ClaudeClient(api_key=api_key)
        
        # Then check for 1Password integration
        elif config.get('api.claude.onepassword.enabled', False):
            logger.info("Using Claude API key from 1Password")
            op_config = SecretConfig(
                vault=config.get('api.claude.onepassword.vault'),
                item=config.get('api.claude.onepassword.item'),
                field=config.get('api.claude.onepassword.field')
            )
            return ClaudeClient(op_config=op_config)
        
        # Finally, fall back to environment variable
        else:
            env_var_name = config.get('api.claude.env_var_name')
            logger.info(f"Using API key from environment variable: {env_var_name}")
            return ClaudeClient(env_var_name=env_var_name)
            
    except Exception as e:
        logger.error(f"Failed to initialize Claude client: {e}")
        return None

def initialize_workflow(config: ConfigManager, claude_client: ClaudeClient) -> NewsAnalysisWorkflow:
    """
    Initialize the news analysis workflow.
    
    Args:
        config: Configuration manager
        claude_client: Initialized Claude client
        
    Returns:
        Initialized news analysis workflow
    """
    return NewsAnalysisWorkflow(
        claude_client=claude_client,
        system_prompt_file=config.get('prompts.system_prompt'),
        initial_prompt_file=config.get('prompts.initial_prompt'),
        follow_up_prompt_file=config.get('prompts.introspection_prompt'),
        output_format_prompt_file=config.get('prompts.output_format_prompt'),
        output_dir=config.get('output.directory'),
        model=config.get('model.name'),
        temperature=config.get('model.temperature'),
        max_tokens=config.get('model.max_tokens')
    )

def process_url(
    workflow: NewsAnalysisWorkflow, 
    url: str, 
    index: int, 
    total: int
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Process a single URL through the news analysis workflow.
    
    Args:
        workflow: News analysis workflow
        url: URL to process
        index: Current URL index
        total: Total number of URLs
        
    Returns:
        Tuple of (result dictionary, error message or None)
    """
    logger.info(f"Processing URL {index}/{total}: {url}")
    print(f"Processing URL {index}/{total}: {url}")
    
    start_time = time.time()
    
    try:
        # Analyze the URL
        result = workflow.analyze_url(url)
        processing_time = time.time() - start_time
        
        # Add processing time to result
        result['processing_time'] = processing_time
        
        logger.info(f"Successfully analyzed: {result['title']}")
        print(f"✅ Analyzed: {result['title']}")
        print(f"   Output: {os.path.abspath(result.get('output_path', ''))}")
        print(f"   Time: {processing_time:.2f}s")
        
        return result, None
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = str(e)
        logger.error(f"Error processing {url}: {error_msg}")
        logger.debug(traceback.format_exc())
        print(f"❌ Error processing {url}: {error_msg}")
        
        # Return minimal result with error
        return {
            'url': url,
            'title': None,
            'processing_time': processing_time,
            'error': error_msg
        }, error_msg

def print_results_table(results: List[Dict[str, Any]]):
    """
    Print a table summarizing the processing results.
    
    Args:
        results: List of result dictionaries
    """
    # Prepare table data
    table_data = []
    for r in results:
        # Truncate title if it's too long
        title = r.get('title')
        if title:
            title = (title[:50] + '...') if len(title) > 50 else title
            
        table_data.append([
            r.get('url', 'N/A'),
            title or 'N/A',
            r.get('source', 'N/A'),
            f"{r.get('processing_time', 0):.2f}s",
            '❌' if r.get('error') else '✅',
            r.get('error', '')[:50] + ('...' if r.get('error', '') and len(r.get('error', '')) > 50 else '')
        ])
    
    # Print table
    headers = ["URL", "Title", "Source", "Time", "Status", "Error"]
    print("\nProcessing Results:")
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Print summary
    success_count = sum(1 for r in results if not r.get('error'))
    fail_count = len(results) - success_count
    print(f"\nSummary: {success_count}/{len(results)} successful analyses, {fail_count} failed")
    
    # Calculate average processing time for successful analyses
    successful_times = [r.get('processing_time', 0) for r in results if not r.get('error')]
    if successful_times:
        avg_time = sum(successful_times) / len(successful_times)
        print(f"Average processing time: {avg_time:.2f}s")

def save_summary_report(results: List[Dict[str, Any]], output_dir: str):
    """
    Save a summary report of the processing results.
    
    Args:
        results: List of result dictionaries
        output_dir: Directory to save the report
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate report filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(output_dir, f"workflow_test_report_{timestamp}.txt")
    
    with open(report_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write("News Analyst Workflow Test Report\n")
        f.write("================================\n\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Write summary
        success_count = sum(1 for r in results if not r.get('error'))
        fail_count = len(results) - success_count
        f.write(f"Total URLs processed: {len(results)}\n")
        f.write(f"Successful: {success_count}\n")
        f.write(f"Failed: {fail_count}\n\n")
        
        # Calculate average processing time for successful analyses
        successful_times = [r.get('processing_time', 0) for r in results if not r.get('error')]
        if successful_times:
            avg_time = sum(successful_times) / len(successful_times)
            f.write(f"Average processing time: {avg_time:.2f}s\n\n")
        
        # Write detailed results
        f.write("Detailed Results\n")
        f.write("---------------\n\n")
        
        for i, r in enumerate(results, 1):
            f.write(f"URL {i}: {r.get('url', 'N/A')}\n")
            f.write(f"Title: {r.get('title', 'N/A')}\n")
            f.write(f"Source: {r.get('source', 'N/A')}\n")
            f.write(f"Processing time: {r.get('processing_time', 0):.2f}s\n")
            f.write(f"Status: {'Success' if not r.get('error') else 'Failed'}\n")
            
            if r.get('error'):
                f.write(f"Error: {r.get('error')}\n")
                
            if not r.get('error'):
                f.write(f"Output file: {os.path.abspath(r.get('output_path', 'N/A'))}\n")
                
            f.write("\n")
    
    logger.info(f"Summary report saved to {report_file}")
    print(f"\nSummary report saved to {report_file}")
    
    return report_file

def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Load configuration
    config = ConfigManager(args.config)
    
    # Read URLs from input file
    urls = read_urls(args.input_file, args.max_urls)
    if not urls:
        logger.error("No URLs to process")
        print("❌ Error: No URLs to process")
        return 1
    
    print(f"Testing full workflow for {len(urls)} URLs...")
    
    # Initialize Claude client
    claude_client = initialize_claude_client(config)
    if not claude_client:
        logger.error("Failed to initialize Claude client")
        print("❌ Error: Failed to initialize Claude client")
        return 1
    
    # Initialize workflow
    workflow = initialize_workflow(config, claude_client)
    
    # Process URLs
    results = []
    for i, url in enumerate(urls, 1):
        result, error = process_url(workflow, url, i, len(urls))
        results.append(result)
        
        # Add delay between requests
        if i < len(urls):
            time.sleep(args.delay)
    
    # Print results table
    print_results_table(results)
    
    # Save summary report
    output_dir = config.get('output.directory')
    save_summary_report(results, output_dir)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
