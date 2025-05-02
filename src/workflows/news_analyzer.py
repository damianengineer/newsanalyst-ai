#!/usr/bin/env python3
"""
News Analyzer Workflow

Orchestrates the process of analyzing news articles using Claude.
"""

import os
import json
import logging
import datetime
from typing import Dict, Any, Optional, List, Union
from slugify import slugify

from src.clients.claude_client import ClaudeClient
from src.extractors.article_extractor import ArticleExtractor, ArticleData
from src.utils.file_utils import read_file, ensure_directory_exists

logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""
    
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()
        return super().default(obj)

class NewsAnalysisWorkflow:
    """Orchestrates the news analysis workflow."""
    
    def __init__(
        self,
        claude_client: ClaudeClient,
        system_prompt_file: str,
        initial_prompt_file: str,
        follow_up_prompt_file: str,
        output_format_prompt_file: str,
        output_dir: str = "output",
        model: str = "claude-3-7-sonnet-20250219",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        request_timeout: Optional[int] = None
    ):
        """
        Initialize the news analysis workflow.
        
        Args:
            claude_client: Initialized Claude client
            system_prompt_file: Path to system prompt file
            initial_prompt_file: Path to initial prompt file
            follow_up_prompt_file: Path to follow-up prompt file
            output_format_prompt_file: Path to output format prompt file
            output_dir: Directory to save output files
            model: Claude model to use
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            request_timeout: Timeout for Claude API requests in seconds
        """
        self.claude_client = claude_client
        self.article_extractor = ArticleExtractor()
        
        # Load prompts
        self.system_prompt = read_file(system_prompt_file)
        self.initial_prompt = read_file(initial_prompt_file)
        self.follow_up_prompt = read_file(follow_up_prompt_file)
        self.output_format_prompt = read_file(output_format_prompt_file)
        
        # Configuration
        self.output_dir = output_dir
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.request_timeout = request_timeout
        
        # Create output directory if it doesn't exist
        ensure_directory_exists(output_dir)
        
        logger.info(f"Initialized NewsAnalysisWorkflow with model {model}")
        
    def analyze_url(self, url: str) -> Dict[str, Any]:
        """
        Analyze a news article from a URL.
        
        Args:
            url: URL of the news article
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing URL: {url}")
        
        # Initialize token usage tracking
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        }
        
        # Extract article information
        article_data = self.article_extractor.extract_from_url(url)
        
        if not article_data:
            error_msg = f"Failed to extract article data from {url}"
            logger.error(error_msg)
            return {"error": error_msg, "url": url}
        
        # Check for paywall
        if article_data.is_paywalled:
            logger.warning(f"⚠️ Paywall detected for {url}. Analysis may be limited.")
            print(f"⚠️ Paywall detected. Analysis may be limited.")
        
        # Format article as XML
        article_xml = self.article_extractor.format_article_as_xml(article_data)
        
        # Run the three-step analysis process
        try:
            # Step 1: Initial analysis
            initial_analysis = self._run_initial_analysis(article_xml)
            
            # Step 2: Introspection
            introspection_analysis = self._run_introspection(article_xml, initial_analysis)
            
            # Step 3: Output formatting
            formatted_output = self._run_output_formatting(
                article_xml, 
                initial_analysis, 
                introspection_analysis
            )
            
            # Save results
            result = self._save_results(article_data, formatted_output)
            
            # Add token usage to result
            result["token_usage"] = self.token_usage
            
            # Print total token usage
            print(f"📊 Total token usage: {self.token_usage['input_tokens']} input + {self.token_usage['output_tokens']} output = {self.token_usage['total_tokens']} total tokens")
            logger.info(f"Total token usage: {self.token_usage['input_tokens']} input + {self.token_usage['output_tokens']} output = {self.token_usage['total_tokens']} total tokens")
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing {url}: {e}", exc_info=True)
            return {"error": str(e), "url": url}
    
    def _run_initial_analysis(self, article_xml: str) -> str:
        """
        Run the initial analysis with Claude.
        
        Args:
            article_xml: Article content formatted as XML
            
        Returns:
            Claude's initial analysis
        """
        logger.info("Running initial analysis")
        
        # Create prompt with article content
        prompt = f"{self.initial_prompt}\n\n{article_xml}"
        
        # Get completion from Claude
        response = self.claude_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self.system_prompt,
            request_timeout=self.request_timeout
        )
        
        # Log token usage if available
        self._log_token_usage("Initial analysis", response)
        
        # Extract and return the response text
        try:
            content = response.get("content", [{}])[0].get("text", "")
            logger.info("Initial analysis completed")
            return content
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting response from Claude: {e}")
            logger.debug(f"Claude response: {response}")
            raise ValueError("Failed to extract response from Claude")
    
    def _run_introspection(self, article_xml: str, initial_analysis: str) -> str:
        """
        Run the introspection analysis with Claude.
        
        Args:
            article_xml: Article content formatted as XML
            initial_analysis: Claude's initial analysis
            
        Returns:
            Claude's introspection analysis
        """
        logger.info("Running introspection analysis")
        
        # Create prompt with article content and initial analysis
        prompt = f"{self.follow_up_prompt}\n\n{article_xml}\n\nYour initial analysis:\n\n{initial_analysis}"
        
        # Get completion from Claude
        response = self.claude_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self.system_prompt,
            request_timeout=self.request_timeout
        )
        
        # Log token usage if available
        self._log_token_usage("Introspection analysis", response)
        
        # Extract and return the response text
        try:
            content = response.get("content", [{}])[0].get("text", "")
            logger.info("Introspection analysis completed")
            return content
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting response from Claude: {e}")
            logger.debug(f"Claude response: {response}")
            raise ValueError("Failed to extract response from Claude")
    
    def _run_output_formatting(
        self, 
        article_xml: str, 
        initial_analysis: str, 
        introspection_analysis: str
    ) -> str:
        """
        Run the output formatting with Claude.
        
        Args:
            article_xml: Article content formatted as XML
            initial_analysis: Claude's initial analysis
            introspection_analysis: Claude's introspection analysis
            
        Returns:
            Claude's formatted output
        """
        logger.info("Running output formatting")
        
        # Create prompt with article content, initial analysis, and introspection
        prompt = (
            f"{self.output_format_prompt}\n\n"
            f"{article_xml}\n\n"
            f"Your initial analysis:\n\n{initial_analysis}\n\n"
            f"Your introspection analysis:\n\n{introspection_analysis}"
        )
        
        # Get completion from Claude
        response = self.claude_client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=self.system_prompt,
            request_timeout=self.request_timeout
        )
        
        # Log token usage if available
        self._log_token_usage("Output formatting", response)
        
        # Extract and return the response text
        try:
            content = response.get("content", [{}])[0].get("text", "")
            logger.info("Output formatting completed")
            return content
        except (KeyError, IndexError) as e:
            logger.error(f"Error extracting response from Claude: {e}")
            logger.debug(f"Claude response: {response}")
            raise ValueError("Failed to extract response from Claude")
            
    def _log_token_usage(self, step_name: str, response: Dict[str, Any]) -> None:
        """
        Log token usage information from Claude API response and update the total usage.
        
        Args:
            step_name: Name of the analysis step
            response: Claude API response
        """
        # Check if usage information is available
        if "usage" in response:
            usage = response["usage"]
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            total_tokens = input_tokens + output_tokens
            
            # Update the token usage tracking
            self.token_usage["input_tokens"] += input_tokens
            self.token_usage["output_tokens"] += output_tokens
            self.token_usage["total_tokens"] += total_tokens
            
            # Log to console and file
            usage_msg = f"{step_name} token usage: {input_tokens} input + {output_tokens} output = {total_tokens} total tokens"
            logger.info(usage_msg)
            print(f"📊 {usage_msg}")
    
    def _save_results(self, article_data: ArticleData, formatted_output: str) -> Dict[str, Any]:
        """
        Save analysis results to files.
        
        Args:
            article_data: Extracted article data
            formatted_output: Formatted output from Claude
            
        Returns:
            Dictionary with result information
        """
        # Generate a slug for the filename
        title = article_data.title or "untitled"
        try:
            slug = slugify(title)
        except Exception as e:
            logger.warning(f"Error slugifying title '{title}': {e}")
            # Fallback to a simple slug
            slug = "article-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Create output paths
        output_path = os.path.join(self.output_dir, f"{slug}.md")
        json_path = os.path.join(self.output_dir, f"{slug}.json")
        content_path = os.path.join(self.output_dir, f"{slug}_content.txt")
        
        # Add source information and paywall warning to the formatted output
        source_info = (
            f"\n\n---\n\n"
            f"**Source Information**\n\n"
            f"- **URL**: {article_data.url}\n"
            f"- **Title**: {article_data.title}\n"
            f"- **Date**: {article_data.date}\n"
            f"- **Author**: {article_data.author or 'Unknown'}\n"
        )
        
        if article_data.is_paywalled:
            paywall_warning = (
                f"\n\n⚠️ **Paywall Warning**: This article appears to be behind a paywall. "
                f"The analysis may be based on limited content and might not reflect the full article.\n"
            )
            source_info += paywall_warning
        
        final_output = formatted_output + source_info
        
        # Save markdown output
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_output)
        
        # Save raw content to a separate file
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(f"# {article_data.title}\n\n")
            f.write(f"Source: {article_data.domain}\n")
            f.write(f"Date: {article_data.date}\n")
            f.write(f"Author: {article_data.author or 'Unknown'}\n")
            f.write(f"URL: {article_data.url}\n\n")
            
            # Add paywall warning if applicable
            if article_data.is_paywalled:
                f.write("\n## ⚠️ Paywall Warning\n")
                f.write("Content extraction was limited due to a paywall or access restrictions. ")
                f.write("The analysis may be based on incomplete information.\n\n")
            
            f.write("## Article Content\n\n")
            f.write(f"{article_data.content}\n\n")
            
            # Add hyperlinks section
            f.write("## Hyperlinks\n\n")
            if article_data.hyperlinks:
                for i, link in enumerate(article_data.hyperlinks, 1):
                    f.write(f"{i}. [{link.text}]({link.url})\n")
            else:
                f.write("No hyperlinks found in the article.\n")
            
        # Save JSON output
        result_data = {
            "url": article_data.url,
            "title": article_data.title,
            "date": article_data.date,
            "author": article_data.author,
            "domain": article_data.domain,
            "is_paywalled": article_data.is_paywalled,
            "extraction_limited": article_data.extraction_limited,
            "analysis_timestamp": datetime.datetime.now().isoformat(),
            "output_path": output_path,
            "content_path": content_path
        }
        
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2, cls=DateTimeEncoder)
            
        logger.info(f"Saved results to {output_path}, {json_path}, and {content_path}")
        
        return result_data
