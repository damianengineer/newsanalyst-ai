#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Article Extractor - Optimized for Claude 3.7

Extracts content and metadata from news articles and social media posts,
formats it as XML for processing with Claude 3.7, and saves to a file.
"""

import os
import re
import html
import json
import time
import logging
import argparse
import pathlib
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Set, Tuple
from urllib.parse import urljoin, urlparse
from logging.handlers import RotatingFileHandler
import concurrent.futures

# Third-party dependencies
import requests
from bs4 import BeautifulSoup
import trafilatura
from newspaper import Article

# ============================================================================
# GLOBAL CONFIGURATION - EDIT THESE SETTINGS AS NEEDED
# ============================================================================

CONFIG = {
    # File and directory settings
    "output_dir": "extracted_articles",  # Directory for extracted article files
    "log_file": "article_extractor.log", # Log file name
    "max_filename_length": 150,          # Maximum length for filenames
    
    # Network settings
    "request_timeout": 15,               # Timeout for HTTP requests in seconds
    "max_retries": 3,                    # Maximum number of retry attempts for network requests
    "backoff_factor": 0.5,               # Exponential backoff factor for retries
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    
    # Display settings
    "preview_length": 500,               # Length of preview in console
    
    # Logging settings
    "log_level": logging.INFO,           # Logging level (DEBUG, INFO, WARNING, ERROR)
    "log_max_size": 5 * 1024 * 1024,     # Maximum log file size (5MB)
    "log_backup_count": 3,               # Number of log backup files to keep
    
    # Content extraction settings
    "content_block_candidates": [        # HTML elements that likely contain main content
        'article', 'main', '.post-content', '.entry-content', 
        '.article-content', '#content', '.content', '.article-body'
    ],
    "ad_patterns": {                     # Class/ID patterns indicating advertisements
        'ad', 'ads', 'banner', 'promo', 'sponsor', 'advertisement',
        'sidebar', 'popup', 'social', 'share', 'menu', 'nav', 'related'
    },
    "cleanup_patterns": [                # Text patterns to remove from content
        r'Subscribe to our newsletter',
        r'Sign up for our daily newsletter',
        r'We use cookies',
        r'Accept cookies',
        r'Privacy Policy',
        r'Terms of Service',
        r'Share this article',
        r'Follow us on'
    ],
    "parallel_extraction": True,         # Use parallel extraction methods
}

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Link:
    """Represents a hyperlink with URL and display text."""
    url: str
    text: str

@dataclass
class ArticleData:
    """Structured container for extracted article data."""
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    source: Optional[str] = None
    date: Optional[Union[datetime, str]] = None
    author: Optional[str] = None
    hyperlinks: List[Link] = field(default_factory=list)
    error: Optional[str] = None
    
    def clean(self) -> 'ArticleData':
        """Clean the article data."""
        if self.content:
            self.content = clean_content(self.content)
        return self
    
    def is_valid(self) -> bool:
        """Check if the article data is valid."""
        return self.title is not None and self.content is not None
    
    def format_date(self) -> Optional[str]:
        """Format the date as a string if it's a datetime object."""
        if isinstance(self.date, datetime):
            return self.date.strftime('%Y-%m-%d %H:%M:%S')
        return self.date
    
    def extract_domain(self) -> None:
        """Extract domain from URL if source is not available."""
        if not self.source:
            source_match = re.search(r'https?://(?:www\.)?([^/]+)', self.url)
            if source_match:
                self.source = source_match.group(1)

# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure logging for the application with rotation and formatting."""
    # Create output directory if it doesn't exist for log file
    log_dir = os.path.dirname(CONFIG["log_file"])
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure root logger
    logging.basicConfig(
        level=CONFIG["log_level"],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                CONFIG["log_file"], 
                maxBytes=CONFIG["log_max_size"],
                backupCount=CONFIG["log_backup_count"]
            ),
            logging.StreamHandler()
        ]
    )
    
    # Suppress verbose logging from libraries
    for lib_logger in ["urllib3", "newspaper", "trafilatura", "requests", "bs4"]:
        logging.getLogger(lib_logger).setLevel(logging.WARNING)

    logger = logging.getLogger("article_extractor")
    logger.info("Logging initialized")
    return logger

# Initialize logger
logger = logging.getLogger("article_extractor")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid and has an appropriate scheme.
    
    Args:
        url: The URL to validate
        
    Returns:
        bool: True if the URL is valid, False otherwise
    
    Example:
        >>> is_valid_url("https://example.com")
        True
        >>> is_valid_url("not-a-url")
        False
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception as e:
        logger.warning(f"URL validation error: {e}")
        return False

def safe_request(url: str, max_retries: Optional[int] = None) -> requests.Response:
    """
    Make a safe HTTP request with proper headers, error handling, and retries.
    
    Args:
        url: The URL to request
        max_retries: Maximum number of retry attempts (defaults to CONFIG["max_retries"])
        
    Returns:
        requests.Response: The HTTP response
        
    Raises:
        ValueError: If the URL is invalid
        requests.exceptions.RequestException: If the request fails after all retries
    """
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL: {url}")
    
    if max_retries is None:
        max_retries = CONFIG["max_retries"]
        
    headers = {
        'User-Agent': CONFIG["user_agent"],
        'Accept': 'text/html,application/xhtml+xml,application/xml',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.google.com/',
        'DNT': '1',  # Do Not Track
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
    }
    
    retry_count = 0
    backoff_factor = CONFIG["backoff_factor"]
    
    while retry_count < max_retries:
        try:
            response = requests.get(
                url, 
                headers=headers, 
                timeout=CONFIG["request_timeout"],
                allow_redirects=True
            )
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if hasattr(e, 'response') else "unknown"
            logger.error(f"HTTP Error: {e} (Status code: {status_code})")
            # Don't retry for client errors (4xx)
            if status_code < 500:
                raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection Error: {e}")
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout Error: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Error: {e}")
        
        # Wait before retrying with exponential backoff
        retry_count += 1
        if retry_count < max_retries:
            wait_time = backoff_factor * (2 ** (retry_count - 1))
            logger.info(f"Retrying in {wait_time:.1f} seconds... (Attempt {retry_count+1}/{max_retries})")
            time.sleep(wait_time)
    
    # If we get here, all retries failed
    raise requests.exceptions.RequestException(f"Failed to fetch {url} after {max_retries} attempts")

def safe_xml_text(text: Optional[Any]) -> str:
    """
    Safely convert any input to a string and escape XML entities.
    
    Args:
        text: The text to convert and escape
        
    Returns:
        str: The escaped XML-safe text
    """
    if text is None:
        return "Unknown"
    return html.escape(str(text))

def safe_path(base_dir: str, filename: str) -> str:
    """
    Ensure file path is safely within the base directory.
    
    Args:
        base_dir: Base directory
        filename: Filename to append to base directory
        
    Returns:
        str: Safe absolute path
        
    Raises:
        ValueError: If the resulting path is outside the base directory
    """
    # Use pathlib for more robust path handling
    base_path = pathlib.Path(base_dir).resolve()
    full_path = (base_path / filename).resolve()
    
    # Verify the path is within the base directory
    if not str(full_path).startswith(str(base_path)):
        raise ValueError(f"Path {full_path} is outside of base directory {base_path}")
    
    return str(full_path)

def generate_safe_filename(url: str) -> str:
    """
    Generate a safe filename from a URL.
    
    Args:
        url: The URL to generate a filename from
        
    Returns:
        str: A safe filename
    """
    # Get the domain and path parts
    parsed_url = urlparse(url)
    domain = parsed_url.netloc
    path = parsed_url.path.replace('/', '_')
    
    # Remove unsafe characters and create a base filename
    base = re.sub(r'[^\w]', '_', f"{domain}{path}")
    base = re.sub(r'_{2,}', '_', base)  # Replace multiple underscores
    
    # Truncate if too long while keeping domain intact
    max_len = CONFIG["max_filename_length"]
    if len(base) > max_len:
        # Keep domain part and truncate the rest
        domain_part = re.sub(r'[^\w]', '_', domain)
        available_len = max_len - len(domain_part) - 1  # -1 for the separator
        if available_len > 10:  # Ensure we have enough space for a meaningful path
            return f"{domain_part}_{base[-available_len:]}"
        else:
            return domain_part[:max_len]
    
    return base

# ============================================================================
# DATE EXTRACTION
# ============================================================================

def extract_date(soup: BeautifulSoup, url: str) -> Optional[datetime]:
    """
    Extract publication date using multiple strategies.
    
    Args:
        soup: BeautifulSoup object of the page
        url: URL of the page
        
    Returns:
        Optional[datetime]: Publication date if found, None otherwise
    """
    # Strategy 1: Look for schema.org metadata
    schema = soup.find('script', type='application/ld+json')
    if schema:
        try:
            data = json.loads(schema.string)
            # Handle both single items and lists of items
            if isinstance(data, list):
                data = data[0]
            if 'datePublished' in data:
                return datetime.fromisoformat(data['datePublished'].replace('Z', '+00:00'))
            elif '@graph' in data:
                for item in data['@graph']:
                    if 'datePublished' in item:
                        return datetime.fromisoformat(item['datePublished'].replace('Z', '+00:00'))
        except (json.JSONDecodeError, ValueError, AttributeError, KeyError) as e:
            logger.debug(f"Error parsing schema.org JSON: {e}")
    
    # Strategy 2: Check common meta tags
    meta_tags = [
        ('property', 'article:published_time'),
        ('property', 'og:published_time'),
        ('name', 'pubdate'),
        ('name', 'publishdate'),
        ('name', 'timestamp'),
        ('name', 'date'),
        ('itemprop', 'datePublished')
    ]
    
    for attr, value in meta_tags:
        meta = soup.find('meta', {attr: value})
        if meta and meta.get('content'):
            try:
                # Handle various date formats
                date_str = meta.get('content')
                # Try ISO format first
                try:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    # Try other common formats
                    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
            except Exception as e:
                logger.debug(f"Error parsing date from meta tag {attr}={value}: {e}")
    
    # Strategy 3: Look for dates in URL
    url_date_patterns = [
        r'/(\d{4})/(\d{1,2})/(\d{1,2})/',  # /yyyy/mm/dd/
        r'/(\d{4})-(\d{1,2})-(\d{1,2})/',  # /yyyy-mm-dd/
    ]
    
    for pattern in url_date_patterns:
        match = re.search(pattern, url)
        if match:
            try:
                year, month, day = map(int, match.groups())
                return datetime(year, month, day)
            except (ValueError, TypeError) as e:
                logger.debug(f"Error parsing date from URL: {e}")
    
    return None

# ============================================================================
# AUTHOR EXTRACTION
# ============================================================================

def extract_author(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract author information using multiple strategies.
    
    Args:
        soup: BeautifulSoup object of the page
        
    Returns:
        Optional[str]: Author name(s) if found, None otherwise
    """
    # Strategy 1: Check schema.org metadata
    schema = soup.find('script', type='application/ld+json')
    if schema:
        try:
            data = json.loads(schema.string)
            # Handle both single items and lists of items
            if isinstance(data, list):
                data = data[0]
            
            # Check for author field
            if 'author' in data:
                author = data['author']
                if isinstance(author, dict):
                    return author.get('name')
                elif isinstance(author, list) and len(author) > 0:
                    names = []
                    for a in author:
                        if isinstance(a, dict) and 'name' in a:
                            names.append(a['name'])
                    if names:
                        return ', '.join(names)
                elif isinstance(author, str):
                    return author
        except (json.JSONDecodeError, ValueError, AttributeError) as e:
            logger.debug(f"Error parsing schema.org JSON for author: {e}")
    
    # Strategy 2: Check meta tags
    meta_tags = [
        ('name', 'author'),
        ('property', 'article:author'),
        ('property', 'og:author'),
        ('name', 'byl'),  # Common in some CMS
    ]
    
    for attr, value in meta_tags:
        meta = soup.find('meta', {attr: value})
        if meta and meta.get('content'):
            return meta.get('content')
    
    # Strategy 3: Look for author in common HTML patterns
    author_classes = [
        'author', 'byline', 'by-line', 'article-author', 
        'entry-author', 'story-author', 'writer'
    ]
    
    for cls in author_classes:
        author_elem = soup.find(class_=cls)
        if author_elem:
            text = author_elem.get_text().strip()
            # Clean up common prefixes
            text = re.sub(r'^(by|written by|posted by|author)[:\s]+', '', text, flags=re.IGNORECASE)
            if text:
                return text
    
    # Strategy 4: Look for rel="author" links
    author_link = soup.find('a', rel='author')
    if author_link:
        return author_link.get_text().strip()
    
    return None

# ============================================================================
# EXTRACTION FUNCTIONS
# ============================================================================

def extract_with_trafilatura(url: str) -> Dict[str, Any]:
    """
    Extract article data using trafilatura.
    
    Args:
        url: URL of the article
        
    Returns:
        Dict[str, Any]: Extracted data
    """
    logger.debug(f"Extracting with trafilatura: {url}")
    result = {
        'title': None,
        'content': None,
        'date': None,
        'author': None
    }
    
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            traf_result = trafilatura.extract(
                downloaded, 
                include_links=True, 
                include_images=False, 
                include_comments=False,
                output_format='json'
            )
            
            if traf_result:
                traf_data = json.loads(traf_result)
                result['title'] = traf_data.get('title')
                result['content'] = traf_data.get('text')
                result['date'] = traf_data.get('date')
                result['author'] = traf_data.get('author')
                logger.debug("Successfully extracted content with trafilatura")
            else:
                logger.debug("Trafilatura extraction returned no data")
    except Exception as e:
        logger.warning(f"Trafilatura extraction error: {e}")
    
    return result

def extract_with_newspaper(url: str) -> Dict[str, Any]:
    """
    Extract article data using newspaper3k.
    
    Args:
        url: URL of the article
        
    Returns:
        Dict[str, Any]: Extracted data
    """
    logger.debug(f"Extracting with newspaper3k: {url}")
    result = {
        'title': None,
        'content': None,
        'date': None,
        'author': None,
        'source_url': None
    }
    
    try:
        article = Article(url)
        article.download()
        article.parse()
        
        result['title'] = article.title
        result['content'] = article.text
        result['date'] = article.publish_date
        result['author'] = ', '.join(article.authors) if article.authors else None
        result['source_url'] = article.source_url
        
        logger.debug("Successfully extracted content with newspaper3k")
    except Exception as e:
        logger.warning(f"Newspaper extraction error: {e}")
    
    return result

def identify_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Identify the main content container in the HTML.
    
    Args:
        soup: BeautifulSoup object
        
    Returns:
        BeautifulSoup: The element containing the main content
    """
    main_content = None
    
    # Try to find the main content using our candidate selectors
    for candidate in CONFIG["content_block_candidates"]:
        if candidate.startswith(('.', '#')):
            found = soup.select(candidate)
        else:
            found = soup.find_all(candidate)
        
        if found:
            main_content = found[0]
            logger.debug(f"Found main content using selector: {candidate}")
            break
    
    # If we couldn't find a clear content area, use the whole body but filter out noise
    if not main_content:
        logger.debug("No specific content container found, using filtered body")
        main_content = soup
        
        # Remove obvious navigation and advertisement sections
        for div in soup.find_all(['nav', 'header', 'footer', 'aside']):
            div.decompose()
            
        # Remove elements with ad-related class names
        for div in soup.find_all(class_=lambda c: c and any(ad in c.lower() for ad in CONFIG["ad_patterns"])):
            div.decompose()
            
        # Remove elements with ad-related id attributes
        for div in soup.find_all(id=lambda i: i and any(ad in i.lower() for ad in CONFIG["ad_patterns"])):
            div.decompose()
    
    return main_content

def extract_links_and_metadata(soup: BeautifulSoup, url: str) -> Dict[str, Any]:
    """
    Extract hyperlinks and additional metadata from BeautifulSoup object.
    
    Args:
        soup: BeautifulSoup object
        url: URL of the page
        
    Returns:
        Dict[str, Any]: Extracted links and metadata
    """
    logger.debug("Extracting links and metadata from HTML")
    result = {
        'source': None,
        'date': None,
        'author': None,
        'hyperlinks': []
    }
    
    # Try to find the main content container
    main_content = identify_main_content(soup)
    
    # Extract links from the main content area
    links = []
    for link in main_content.find_all('a', href=True):
        href = link.get('href')
        if not href or href.startswith(('javascript:', 'mailto:', '#')):
            continue
            
        # Convert relative URLs to absolute
        abs_url = urljoin(url, href)
        
        # Get display text
        display_text = link.get_text().strip()
        if not display_text and link.find('img'):
            display_text = link.find('img').get('alt', '[Image]')
        if not display_text:
            display_text = abs_url
            
        links.append(Link(url=abs_url, text=display_text))
        
    result['hyperlinks'] = links
    
    # Extract source
    og_site = soup.find('meta', property='og:site_name')
    if og_site:
        result['source'] = og_site.get('content')
    
    # Extract date using enhanced date extraction
    date_result = extract_date(soup, url)
    if date_result:
        result['date'] = date_result
    
    # Extract author using enhanced author extraction
    author_result = extract_author(soup)
    if author_result:
        result['author'] = author_result
    
    return result

def assess_content_quality(content: Optional[str]) -> float:
    """
    Assess the quality of extracted content.
    
    Args:
        content: The content to assess
        
    Returns:
        float: Quality score (0-1) where higher is better
    """
    if not content:
        return 0.0
    
    score = 0.0
    
    # Length contributes to score (longer is usually more complete)
    length = len(content)
    if length > 1000:
        score += 0.3
    elif length > 500:
        score += 0.2
    elif length > 100:
        score += 0.1
    
    # Presence of paragraphs suggests structured content
    paragraphs = content.count('\n\n')
    if paragraphs > 5:
        score += 0.3
    elif paragraphs > 2:
        score += 0.2
    elif paragraphs > 0:
        score += 0.1
    
    # Absence of typical "junk" patterns (navs, ads, etc.)
    junk_patterns = [
        r'share this', r'subscribe', r'newsletter', r'sign up',
        r'click here', r'comment', r'copyright', r'all rights reserved'
    ]
    
    junk_count = sum(1 for pattern in junk_patterns if re.search(pattern, content, re.IGNORECASE))
    if junk_count == 0:
        score += 0.2
    elif junk_count <= 2:
        score += 0.1
    
    # Text-to-HTML ratio proxy: check for HTML remnants
    html_pattern = r'</?[a-z][a-z0-9]*[^<>]*>|<!--.*?-->'
    html_matches = len(re.findall(html_pattern, content))
    if html_matches == 0:
        score += 0.2
    elif html_matches <= 3:
        score += 0.1
    
    return min(1.0, score)

def clean_content(text: Optional[str]) -> Optional[str]:
    """
    Clean extracted content by removing extra whitespace and unwanted patterns.
    
    Args:
        text: The text to clean
        
    Returns:
        Optional[str]: Cleaned text, or None if input was None
    """
    if not text:
        return None
    
    logger.debug("Cleaning extracted content")
    
    # Remove excessive newlines and whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove common newsletter and cookie notice patterns
    for pattern in CONFIG["cleanup_patterns"]:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Fix a few common encoding issues
    text = text.replace('â€™', "'")
    text = text.replace('â€œ', '"')
    text = text.replace('â€', '"')
    text = text.replace('&amp;', '&')
    
    return text.strip()

# ============================================================================
# PARALLEL EXTRACTION
# ============================================================================

def extract_all_parallel(url: str) -> ArticleData:
    """
    Extract article content and metadata using multiple methods in parallel.
    
    Args:
        url: URL of the article
        
    Returns:
        ArticleData: Combined extracted data
    """
    result = ArticleData(url=url)
    
    try:
        # Create a thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # Submit extraction tasks
            traf_future = executor.submit(extract_with_trafilatura, url)
            news_future = executor.submit(extract_with_newspaper, url)
            
            # Get HTML for direct parsing
            try:
                response = safe_request(url)
                soup = BeautifulSoup(response.content, 'html.parser')
                html_future = executor.submit(extract_links_and_metadata, soup, url)
            except Exception as e:
                logger.error(f"Error fetching HTML: {e}")
                html_future = None
            
            # Get results
            traf_result = traf_future.result()
            news_result = news_future.result()
            html_result = html_future.result() if html_future else {}
            
            # Assess content quality for each extractor
            traf_score = assess_content_quality(traf_result.get('content'))
            news_score = assess_content_quality(news_result.get('content'))
            
            logger.debug(f"Content quality scores - Trafilatura: {traf_score:.2f}, Newspaper: {news_score:.2f}")
            
            # Choose the best content based on quality score
            if traf_score > news_score:
                result.content = traf_result.get('content')
                logger.debug("Using Trafilatura content (higher quality)")
            else:
                result.content = news_result.get('content')
                logger.debug("Using Newspaper content (higher quality)")
            
            # Combine other metadata, prefer Trafilatura for title
            result.title = traf_result.get('title') or news_result.get('title')
            result.date = traf_result.get('date') or news_result.get('date') or html_result.get('date')
            result.author = traf_result.get('author') or news_result.get('author') or html_result.get('author')
            result.source = news_result.get('source_url') or html_result.get('source')
            result.hyperlinks = html_result.get('hyperlinks', [])
            
            # Clean the content
            result.clean()
            
            # If source still not found, extract domain from URL
            result.extract_domain()
            
    except Exception as e:
        error_msg = f"Parallel extraction error: {str(e)}"
        logger.error(error_msg)
        result.error = error_msg
        
    return result

def extract_all_sequential(url: str) -> ArticleData:
    """
    Extract article content and metadata using multiple methods sequentially.
    
    Args:
        url: URL of the article
        
    Returns:
        ArticleData: Combined extracted data
    """
    result = ArticleData(url=url)
    
    try:
        # Strategy 1: Trafilatura extraction
        traf_result = extract_with_trafilatura(url)
        
        # Strategy 2: Newspaper3k extraction
        news_result = extract_with_newspaper(url)
        
        # Strategy 3: Direct HTML parsing for hyperlinks and additional metadata
        try:
            response = safe_request(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            html_result = extract_links_and_metadata(soup, url)
        except Exception as e:
            logger.error(f"Error fetching HTML: {e}")
            html_result = {}
        
        # Assess content quality for each extractor
        traf_score = assess_content_quality(traf_result.get('content'))
        news_score = assess_content_quality(news_result.get('content'))
        
        logger.debug(f"Content quality scores - Trafilatura: {traf_score:.2f}, Newspaper: {news_score:.2f}")
        
        # Choose the best content based on quality score
        if traf_score > news_score:
            result.content = traf_result.get('content')
            logger.debug("Using Trafilatura content (higher quality)")
        else:
            result.content = news_result.get('content')
            logger.debug("Using Newspaper content (higher quality)")
        
        # Combine other metadata, prefer Trafilatura for title
        result.title = traf_result.get('title') or news_result.get('title')
        result.date = traf_result.get('date') or news_result.get('date') or html_result.get('date')
        result.author = traf_result.get('author') or news_result.get('author') or html_result.get('author')
        result.source = news_result.get('source_url') or html_result.get('source')
        result.hyperlinks = html_result.get('hyperlinks', [])
        
        # Clean the content
        result.clean()
        
        # If source still not found, extract domain from URL
        result.extract_domain()
            
    except Exception as e:
        error_msg = f"Sequential extraction error: {str(e)}"
        logger.error(error_msg)
        result.error = error_msg
        
    return result

# ============================================================================
# MAIN EXTRACTION FUNCTION
# ============================================================================

def extract_article_info(url: str) -> ArticleData:
    """
    Extract article content and metadata from a URL using multiple strategies.
    
    Args:
        url (str): URL of the news article or social media post
        
    Returns:
        ArticleData: Object containing extracted information
    """
    logger.info(f"Extracting article information from: {url}")
    
    try:
        # Choose parallel or sequential extraction based on config
        if CONFIG["parallel_extraction"]:
            result = extract_all_parallel(url)
        else:
            result = extract_all_sequential(url)
            
        if result.is_valid():
            logger.info(f"Extraction successful. Title: {result.title}")
        else:
            if not result.error:
                result.error = "Extraction completed but no valid content was found"
            logger.warning(f"Extraction yielded no valid content: {result.error}")
            
    except Exception as e:
        error_msg = f"Extraction error: {str(e)}"
        logger.error(error_msg)
        result = ArticleData(url=url, error=error_msg)
        
    return result

# ============================================================================
# OUTPUT FUNCTIONS
# ============================================================================

def format_article_as_xml(article_data: ArticleData) -> str:
    """
    Format the extracted article data as XML.
    
    Args:
        article_data: The article data to format
        
    Returns:
        str: XML representation of the article
    """
    logger.debug("Formatting article as XML")
    
    xml_output = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<article>\n"
    
    # 1. Links section (least important, goes first for possible truncation)
    xml_output += "  <links>\n"
    if article_data.hyperlinks:
        for link in article_data.hyperlinks:
            xml_output += f'    <link url="{safe_xml_text(link.url)}" text="{safe_xml_text(link.text)}" />\n'
    else:
        xml_output += "    <!-- No hyperlinks found -->\n"
    xml_output += "  </links>\n\n"
    
    # 2. Metadata section
    xml_output += "  <metadata>\n"
    xml_output += f"    <title>{safe_xml_text(article_data.title)}</title>\n"
    xml_output += f"    <source>{safe_xml_text(article_data.source)}</source>\n"
    xml_output += f"    <author>{safe_xml_text(article_data.author)}</author>\n"
    xml_output += f"    <publication_date>{safe_xml_text(article_data.format_date())}</publication_date>\n"
    xml_output += f"    <url>{safe_xml_text(article_data.url)}</url>\n"
    xml_output += "  </metadata>\n\n"
    
    # 3. Content section (most important, goes last to ensure inclusion)
    xml_output += "  <content>\n"
    if article_data.content:
        # Split content into paragraphs and format each one
        paragraphs = article_data.content.split('\n\n')
        for paragraph in paragraphs:
            if paragraph.strip():
                xml_output += f"    <p>{safe_xml_text(paragraph.strip())}</p>\n"
    else:
        xml_output += "    <!-- No content extracted -->\n"
    xml_output += "  </content>\n"
    
    xml_output += "</article>"
    
    return xml_output

def save_to_file(xml_content: str, url: str, output_dir: Optional[str] = None) -> str:
    """
    Save the XML content to a file.
    
    Args:
        xml_content: The XML content to save
        url: The source URL used to generate the filename
        output_dir: Directory to save the file (defaults to CONFIG["output_dir"])
        
    Returns:
        str: Path to the saved file
    """
    if output_dir is None:
        output_dir = CONFIG["output_dir"]
        
    # Create output directory if it doesn't exist
    output_path = pathlib.Path(output_dir)
    if not output_path.exists():
        logger.debug(f"Creating output directory: {output_dir}")
        output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate a filename based on the URL
    filename = generate_safe_filename(url)
    filepath = safe_path(output_dir, f"{filename}.xml")
    
    logger.info(f"Saving article to: {filepath}")
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        logger.debug("File saved successfully")
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        raise
    
    return filepath

# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main function to run the article extractor."""
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Extract article content and metadata from a URL.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--url', type=str, help='URL of the article to extract')
    parser.add_argument('--output-dir', type=str, help=f'Directory to save extracted articles (default: {CONFIG["output_dir"]})')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--timeout', type=int, help=f'Request timeout in seconds (default: {CONFIG["request_timeout"]})')
    parser.add_argument('--sequential', action='store_true', help='Use sequential extraction instead of parallel')
    args = parser.parse_args()
    
    # Update config if arguments provided
    if args.output_dir:
        CONFIG['output_dir'] = args.output_dir
    
    if args.debug:
        CONFIG['log_level'] = logging.DEBUG
    
    if args.timeout:
        CONFIG['request_timeout'] = args.timeout
        
    if args.sequential:
        CONFIG['parallel_extraction'] = False
    
    # Setup logging
    global logger
    logger = setup_logging()
    
    # Get URL from command line or prompt
    url = args.url
    if not url:
        url = input("Enter the URL of the news article or social media post: ")
    
    if not is_valid_url(url):
        logger.error(f"Invalid URL: {url}")
        print(f"Error: Invalid URL {url}")
        return 1
    
    logger.info(f"Starting extraction for URL: {url}")
    print(f"Extracting information from: {url}")
    
    try:
        # Extract the article information
        result = extract_article_info(url)
        
        if result.error:
            logger.error(f"Extraction error: {result.error}")
            print(f"Error: {result.error}")
            return 1
        
        # Format as XML
        xml_content = format_article_as_xml(result)
        
        # Save to file
        filepath = save_to_file(xml_content, url)
        
        print(f"\nArticle extracted and saved to: {filepath}")
        
        # Display a preview
        print("\n--- XML PREVIEW ---")
        preview_length = min(CONFIG["preview_length"], len(xml_content))
        print(xml_content[:preview_length] + "..." if len(xml_content) > preview_length else xml_content)
        
        # Also show metadata summary
        print("\n--- EXTRACTION SUMMARY ---")
        print(f"Title: {result.title}")
        print(f"Source: {result.source}")
        print(f"Date: {result.format_date()}")
        print(f"Author: {result.author}")
        print(f"Content Length: {len(result.content) if result.content else 0} characters")
        print(f"Links Found: {len(result.hyperlinks)}")
        
        logger.info(f"Extraction complete. Saved to {filepath}")
        return 0
        
    except Exception as e:
        logger.exception("Unexpected error in main execution")
        print(f"An unexpected error occurred: {str(e)}")
        return 1

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)