#!/usr/bin/env python3
"""
CLI Utilities

Command-line interface utilities for the NewsAnalyst application.
"""

import os
import argparse
import logging
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid.
    
    Args:
        url: URL to validate
        
    Returns:
        True if the URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception as e:
        logger.warning(f"URL validation error: {e}")
        return False

def read_urls_from_file(file_path: str) -> List[str]:
    """
    Read URLs from a file, one per line.
    
    Args:
        file_path: Path to the file containing URLs
        
    Returns:
        List of valid URLs
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return []
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
            
        # Filter out invalid URLs
        valid_urls = []
        for url in urls:
            if is_valid_url(url):
                valid_urls.append(url)
            else:
                logger.warning(f"Invalid URL in file: {url}")
                
        logger.info(f"Read {len(valid_urls)} valid URLs from {file_path}")
        return valid_urls
    except Exception as e:
        logger.error(f"Error reading URLs from file: {e}")
        return []

def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="News Analyst - Analyze news articles with Claude 3.7")
    
    # URL input options (mutually exclusive)
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument("-u", "--url", help="URL of the news article to analyze")
    url_group.add_argument("-f", "--file", help="File containing URLs to analyze (one per line)")
    
    # Configuration
    parser.add_argument("--config", help="Path to configuration file", default="config.yaml")
    
    # API configuration overrides
    api_group = parser.add_argument_group("API Configuration")
    api_group.add_argument("--api-key", help="Claude API key (overrides config)")
    api_group.add_argument("--op-vault", help="1Password vault name (overrides config)")
    api_group.add_argument("--op-item", help="1Password item name (overrides config)")
    api_group.add_argument("--op-field", help="1Password field name (overrides config)")
    
    # Model configuration overrides
    model_group = parser.add_argument_group("Model Configuration")
    model_group.add_argument("--model", help="Claude model to use (overrides config)")
    model_group.add_argument("--temperature", type=float, help="Temperature for Claude responses (0.0-1.0) (overrides config)")
    model_group.add_argument("--max-tokens", type=int, help="Maximum tokens for Claude responses (overrides config)")
    
    # Prompt configuration overrides
    prompt_group = parser.add_argument_group("Prompt Configuration")
    prompt_group.add_argument("--system-prompt", help="Path to system prompt file (overrides config)")
    prompt_group.add_argument("--initial-prompt", help="Path to initial prompt file (overrides config)")
    prompt_group.add_argument("--introspection-prompt", help="Path to introspection prompt file (overrides config)")
    prompt_group.add_argument("--output-format-prompt", help="Path to output format prompt file (overrides config)")
    
    # Output configuration overrides
    output_group = parser.add_argument_group("Output Configuration")
    output_group.add_argument("--output-dir", "-o", help="Directory to save output files (overrides config)")
    
    return parser.parse_args()
