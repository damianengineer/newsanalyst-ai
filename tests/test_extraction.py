#!/usr/bin/env python3
"""
Article Extraction Test Script

Tests the article extraction functionality by processing URLs from an input file
and generating a summary table of the results.
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime
from tabulate import tabulate
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extractors.article_extractor import ArticleExtractor
from src.utils.config_manager import ConfigManager

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Test article extraction functionality")
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
        "--output-dir", 
        default="tests/output", 
        help="Directory to save detailed extraction results"
    )
    parser.add_argument(
        "--delay", 
        type=float, 
        default=1.0, 
        help="Delay between requests in seconds"
    )
    return parser.parse_args()

def read_urls(file_path: str) -> List[str]:
    """Read URLs from a file, one per line."""
    try:
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        return urls
    except Exception as e:
        print(f"Error reading URLs from {file_path}: {e}")
        return []

def test_extraction(
    urls: List[str], 
    config_path: str, 
    output_dir: str, 
    delay: float
) -> List[Dict[str, Any]]:
    """
    Test article extraction for a list of URLs.
    
    Args:
        urls: List of URLs to test
        config_path: Path to configuration file
        output_dir: Directory to save detailed results
        delay: Delay between requests in seconds
        
    Returns:
        List of dictionaries with extraction results
    """
    # Load configuration
    config = ConfigManager(config_path)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize article extractor
    extractor = ArticleExtractor(config.get('extraction', {}))
    
    results = []
    
    for i, url in enumerate(urls):
        print(f"Processing URL {i+1}/{len(urls)}: {url}")
        
        try:
            # Extract article data
            start_time = time.time()
            article_data = extractor.extract_from_url(url)
            extraction_time = time.time() - start_time
            
            if article_data:
                # Save detailed results
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                domain = article_data.domain or "unknown"
                detail_file = os.path.join(output_dir, f"{timestamp}_{domain}_details.txt")
                
                with open(detail_file, 'w', encoding='utf-8') as f:
                    f.write(f"URL: {url}\n")
                    f.write(f"Title: {article_data.title}\n")
                    f.write(f"Source: {article_data.source}\n")
                    f.write(f"Date: {article_data.date}\n")
                    f.write(f"Author: {article_data.author}\n")
                    f.write(f"Domain: {article_data.domain}\n")
                    f.write(f"Is Paywalled: {article_data.is_paywalled}\n")
                    f.write(f"Extraction Limited: {article_data.extraction_limited}\n")
                    f.write(f"Content Length: {len(article_data.content) if article_data.content else 0}\n")
                    f.write(f"Hyperlinks Count: {len(article_data.hyperlinks)}\n")
                    f.write(f"Extraction Time: {extraction_time:.2f} seconds\n\n")
                    f.write("Content Preview:\n")
                    f.write("-" * 80 + "\n")
                    if article_data.content:
                        f.write(article_data.content[:500] + "...\n")
                    else:
                        f.write("No content extracted\n")
                
                # Add to results
                results.append({
                    "url": url,
                    "title": article_data.title,
                    "source": article_data.source,
                    "date": article_data.date,
                    "author": article_data.author,
                    "is_paywalled": article_data.is_paywalled,
                    "extraction_limited": article_data.extraction_limited,
                    "content_length": len(article_data.content) if article_data.content else 0,
                    "hyperlinks_count": len(article_data.hyperlinks),
                    "extraction_time": f"{extraction_time:.2f}s",
                    "error": None
                })
            else:
                results.append({
                    "url": url,
                    "title": None,
                    "source": None,
                    "date": None,
                    "author": None,
                    "is_paywalled": None,
                    "extraction_limited": None,
                    "content_length": 0,
                    "hyperlinks_count": 0,
                    "extraction_time": f"{extraction_time:.2f}s",
                    "error": "Failed to extract article data"
                })
                
        except Exception as e:
            results.append({
                "url": url,
                "title": None,
                "source": None,
                "date": None,
                "author": None,
                "is_paywalled": None,
                "extraction_limited": None,
                "content_length": 0,
                "hyperlinks_count": 0,
                "extraction_time": "N/A",
                "error": str(e)
            })
        
        # Add delay between requests
        if i < len(urls) - 1:
            time.sleep(delay)
    
    return results

def print_results_table(results: List[Dict[str, Any]]):
    """Print a table of extraction results."""
    # Prepare table data
    table_data = []
    for r in results:
        table_data.append([
            r["url"],
            r["source"],
            r["date"],
            r["author"],
            "✅" if not r["error"] else "❌",
            "Yes" if r["is_paywalled"] else "No" if r["is_paywalled"] is not None else "N/A",
            r["content_length"],
            r["extraction_time"],
            r["error"] or ""
        ])
    
    # Print table
    headers = ["URL", "Source", "Date", "Author", "Success", "Paywalled", "Content Length", "Time", "Error"]
    print("\nExtraction Results:")
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Print summary
    success_count = sum(1 for r in results if not r["error"])
    paywall_count = sum(1 for r in results if r["is_paywalled"])
    print(f"\nSummary: {success_count}/{len(results)} successful extractions, {paywall_count} paywalled articles")

def main():
    """Main entry point."""
    args = parse_args()
    
    # Read URLs from input file
    urls = read_urls(args.input_file)
    if not urls:
        print(f"No URLs found in {args.input_file}")
        return 1
    
    print(f"Testing extraction for {len(urls)} URLs...")
    
    # Run extraction tests
    results = test_extraction(urls, args.config, args.output_dir, args.delay)
    
    # Print results table
    print_results_table(results)
    
    # Save results to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = os.path.join(args.output_dir, f"{timestamp}_extraction_results.csv")
    
    try:
        import csv
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved to {csv_file}")
    except Exception as e:
        print(f"Error saving results to CSV: {e}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
