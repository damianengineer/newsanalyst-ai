#!/usr/bin/env python3
"""
News Analyst

A modular workflow for analyzing news articles using Claude 3.7.

Usage:
    python newsanalyst.py                      # Analyze URLs from url_input.txt (default)
    python newsanalyst.py -u <url>             # Analyze a single URL
    python newsanalyst.py -f <file_with_urls>  # Analyze URLs from a specified file
"""

import os
import sys
import logging
import argparse
import nltk
from typing import List, Optional

from src.utils.config_manager import ConfigManager
from src.utils.logging_utils import configure_logging, get_logger
from src.clients.claude_client import ClaudeClient, SecretConfig
from src.workflows.news_analyzer import NewsAnalysisWorkflow

# Use structured logging
logger = get_logger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="News Analyst - Analyze news articles with Claude 3.7")
    
    # URL input options (mutually exclusive and optional)
    url_group = parser.add_mutually_exclusive_group(required=False)
    url_group.add_argument("-u", "--url", help="URL of the news article to analyze")
    url_group.add_argument("-f", "--file", help="File containing URLs to analyze (one per line)")
    
    # Configuration
    parser.add_argument("--config", help="Path to configuration file", default="config.yaml")
    
    # Override options (these will override the config file settings)
    parser.add_argument("--output-dir", "-o", help="Output directory (overrides config)")
    
    return parser.parse_args()

def get_urls_from_file(file_path: str) -> List[str]:
    """
    Read URLs from a file, one per line.
    
    Args:
        file_path: Path to the file containing URLs
        
    Returns:
        List of URLs
    """
    try:
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        return urls
    except Exception as e:
        logger.error("Error reading URLs from file", file_path=file_path, error=str(e))
        return []

def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_args()
    
    # Load configuration
    config = ConfigManager(args.config)
    
    # Update config with command line arguments
    config_overrides = {k: v for k, v in vars(args).items() if v is not None}
    config.update_from_args(config_overrides)
    
    # Configure logging
    log_level = config.get('logging.level', 'INFO')
    log_file = config.get('logging.file', 'logs/newsanalyst.log')
    module_levels = config.get('logging.modules', {})
    configure_logging(log_level, log_file, module_levels)
    
    logger.info("News Analyst starting")
    
    # Ensure NLTK data is available
    logger.info("Ensuring NLTK data is available...")
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt')
    logger.info("NLTK data check completed")
    
    # Initialize Claude client
    claude_client = None
    try:
        # Check for 1Password integration
        if config.get('api.claude.onepassword.enabled', False):
            logger.info("Using Claude API key from 1Password")
            op_config = SecretConfig(
                vault=config.get('api.claude.onepassword.vault'),
                item=config.get('api.claude.onepassword.item'),
                field=config.get('api.claude.onepassword.field')
            )
            claude_client = ClaudeClient(op_config=op_config)
        # Fall back to environment variable
        else:
            logger.info("Using API key from environment variable", env_var=config.get('api.claude.env_var_name'))
            claude_client = ClaudeClient(env_var_name=config.get('api.claude.env_var_name'))
    except Exception as e:
        logger.error("Failed to initialize Claude client", error=str(e))
        print(f"❌ Error: {e}")
        return 1
    
    # Initialize workflow
    workflow = NewsAnalysisWorkflow(
        claude_client=claude_client,
        system_prompt_file=config.get('prompts.system_prompt'),
        initial_prompt_file=config.get('prompts.initial_prompt'),
        follow_up_prompt_file=config.get('prompts.introspection_prompt'),
        output_format_prompt_file=config.get('prompts.output_format_prompt'),
        output_dir=config.get('output.directory'),
        model=config.get('model.name'),
        temperature=config.get('model.temperature'),
        max_tokens=config.get('model.max_tokens'),
        request_timeout=config.get('api.claude.request_timeout')
    )
    
    # Get URLs to analyze
    urls = []
    if args.url:
        urls = [args.url]
    elif args.file:
        urls = get_urls_from_file(args.file)
    else:
        # Default: use url_input.txt in the root directory
        default_input_file = "url_input.txt"
        if os.path.exists(default_input_file):
            logger.info("No URL specified, using default input file", file=default_input_file)
            print(f"No URL specified, using default input file: {default_input_file}")
            urls = get_urls_from_file(default_input_file)
        else:
            logger.error("No URL specified and default input file not found", file=default_input_file)
            print(f"❌ Error: No URL specified and default input file not found: {default_input_file}")
            print("Please specify a URL with -u or a file with -f, or create a url_input.txt file.")
            return 1
        
    if not urls:
        logger.error("No URLs to analyze")
        print("❌ Error: No URLs to analyze")
        return 1
        
    # Process URLs
    logger.info("Processing URLs", count=len(urls))
    print(f"Processing {len(urls)} URL(s)...")
    
    success_count = 0
    fail_count = 0
    
    for i, url in enumerate(urls, 1):
        logger.info("Processing URL", index=f"{i}/{len(urls)}", url=url)
        print(f"Processing URL {i}/{len(urls)}: {url}")
        
        try:
            result = workflow.analyze_url(url)
            print(f"✅ Analyzed: {result['title']}")
            print(f"   Output: {os.path.join(config.get('output.directory'), os.path.basename(result.get('output_path', '')))}")
            success_count += 1
        except Exception as e:
            logger.error("Error processing URL", url=url, error=str(e))
            print(f"❌ Error processing {url}: {e}")
            fail_count += 1
            
    print(f"\nProcessed {len(urls)} URLs: {success_count} successful, {fail_count} failed")
    print(f"Results saved to: {os.path.abspath(config.get('output.directory'))}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
