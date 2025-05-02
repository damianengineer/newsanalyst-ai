#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Article Extractor Module

Extracts content and metadata from news articles, optimized for processing with Claude 3.7.
Based on the example web-extract.py script but simplified and modularized.
"""

import os
import re
import html
import logging
import datetime
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
import trafilatura
from newspaper import Article
import nltk

from .selenium_extractor import SeleniumExtractor

logger = logging.getLogger(__name__)

@dataclass
class Hyperlink:
    """Represents a hyperlink in an article."""
    url: str
    text: str
    
    def __post_init__(self):
        """Clean up URL and text after initialization."""
        self.url = self.url.strip() if self.url else ""
        self.text = self.text.strip() if self.text else ""

@dataclass
class ArticleData:
    """Represents extracted article data."""
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    date: Optional[Union[str, datetime.datetime]] = None
    author: Optional[str] = None
    domain: Optional[str] = None
    source: Optional[str] = None
    hyperlinks: List[Hyperlink] = field(default_factory=list)
    is_paywalled: bool = False
    extraction_limited: bool = False
    
    def clean(self) -> None:
        """Clean and validate article data."""
        # Ensure URL is valid
        self.url = self.url.strip() if self.url else ""
        
        # Clean title
        self.title = self.title.strip() if self.title else ""
        
        # Clean content
        self.content = self.content.strip() if self.content else ""
        
        # Format date as string if it's a datetime
        if isinstance(self.date, datetime.datetime):
            self.date = self.format_date(self.date)
        elif self.date is None:
            self.date = ""
        
        # Clean author
        self.author = self.author.strip() if self.author else ""
        
        # Extract domain from URL if not provided
        if not self.domain and self.url:
            try:
                parsed_url = urlparse(self.url)
                self.domain = parsed_url.netloc
            except Exception as e:
                logger.warning(f"Failed to extract domain from URL {self.url}: {e}")
                self.domain = ""
        
        # Set source to domain if not provided
        if not self.source:
            self.source = self.domain
    
    @staticmethod
    def format_date(date: datetime.datetime) -> str:
        """Format a datetime object as a string."""
        try:
            return date.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Failed to format date {date}: {e}")
            return ""

class ArticleExtractor:
    """Extracts article content and metadata from URLs."""
    
    def __init__(self, config=None):
        """
        Initialize the article extractor.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.user_agent = self._get_user_agent()
        self.timeout = self.config.get('timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.random_delay = self.config.get('random_delay', False)
        self.min_delay = self.config.get('min_delay', 1)
        self.max_delay = self.config.get('max_delay', 5)
        self.use_cookies = self.config.get('use_cookies', False)
        self.use_selenium = self.config.get('use_selenium', False)
        self.selenium_sites = self.config.get('selenium_sites', [])
        
        # Initialize Selenium extractor if enabled
        self.selenium_extractor = None
        if self.use_selenium:
            try:
                self.selenium_extractor = SeleniumExtractor(self.config)
                logger.info("Selenium extractor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Selenium extractor: {e}")
        
        # Known paywall domains
        self.paywall_domains = self.config.get('paywall_domains', [
            'nytimes.com', 'wsj.com', 'ft.com', 'bloomberg.com', 
            'economist.com', 'washingtonpost.com', 'newyorker.com',
            'thetimes.co.uk', 'telegraph.co.uk', 'theguardian.com',
            'latimes.com', 'theatlantic.com', 'wired.com', 'medium.com',
            'forbes.com', 'barrons.com', 'foreignpolicy.com',
            'hbr.org', 'technologyreview.com', 'foreignaffairs.com'
        ])
        
        # Common paywall phrases
        self.paywall_phrases = self.config.get('paywall_phrases', [
            'subscribe to continue', 'subscribe to read', 'subscribe for full access',
            'to continue reading', 'sign up to read', 'premium content',
            'premium article', 'subscribe now', 'subscription required',
            'paid subscription', 'register to continue', 'create an account',
            'log in to continue', 'sign in to continue', 'members only',
            'exclusive content', 'exclusive access', 'unlock this content',
            'unlock this article', 'for subscribers only', 'for members only'
        ])
        
        # Minimum content length for news articles (characters)
        self.min_content_length = self.config.get('min_content_length', 1000)
        
    def _get_user_agent(self):
        """
        Get a user agent string, either from config or from a list of common ones.
        
        Returns:
            User agent string
        """
        # If user agent is specified in config, use it
        if self.config and 'user_agent' in self.config:
            return self.config.get('user_agent')
            
        # Otherwise, use a random user agent from this list
        common_user_agents = [
            # Chrome on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
            # Chrome on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
            # Firefox on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
            # Firefox on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/113.0",
            # Safari on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15",
            # Edge on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36 Edg/113.0.1774.42",
            # Chrome on iOS
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/113.0.5672.109 Mobile/15E148 Safari/604.1",
        ]
        
        import random
        return random.choice(common_user_agents)
    
    def extract_from_url(self, url: str) -> Optional[ArticleData]:
        """
        Extract article data from a URL.
        
        Args:
            url: URL of the article
            
        Returns:
            ArticleData object or None if extraction failed
        """
        try:
            logger.info(f"Extracting article data from {url}")
            
            # Add random delay if enabled
            if self.random_delay:
                delay = random.uniform(self.min_delay, self.max_delay)
                logger.debug(f"Adding random delay of {delay:.2f} seconds")
                time.sleep(delay)
            
            # Check if we should use Selenium for this URL
            use_selenium_for_url = self._should_use_selenium(url)
            
            # Extract article information
            article_data = self._extract_article_info(url, use_selenium=use_selenium_for_url)
            
            if article_data:
                # Check for paywall
                is_paywalled, extraction_limited = self._detect_paywall(article_data)
                article_data.is_paywalled = is_paywalled
                article_data.extraction_limited = extraction_limited
                
                # Filter hyperlinks
                article_data.hyperlinks = self._filter_content_hyperlinks(article_data.hyperlinks)
                
                # Clean data
                article_data.clean()
                
                logger.info(f"Successfully extracted article data from {url}")
                return article_data
            else:
                logger.warning(f"Failed to extract article data from {url}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting article data from {url}: {e}", exc_info=True)
            return None
        
        finally:
            # Close Selenium if it was used
            if self.selenium_extractor and self.selenium_extractor.driver:
                self.selenium_extractor.close()
    
    def _should_use_selenium(self, url: str) -> bool:
        """
        Determine if Selenium should be used for this URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if Selenium should be used, False otherwise
        """
        if not self.use_selenium or not self.selenium_extractor:
            return False
            
        domain = urlparse(url).netloc
        
        # Check if domain matches any in selenium_sites list
        for site in self.selenium_sites:
            if site in domain:
                logger.info(f"Using Selenium for {url} (matched {site})")
                return True
                
        return False
    
    def _extract_article_info(self, url: str, use_selenium: bool = False) -> Optional[ArticleData]:
        """
        Extract article information using multiple methods.
        
        Args:
            url: URL of the article
            use_selenium: Whether to use Selenium for extraction
            
        Returns:
            ArticleData object or None if extraction failed
        """
        try:
            # Get HTML content
            if use_selenium and self.selenium_extractor:
                html_content = self.selenium_extractor.extract_html(url)
                logger.info(f"Extracted HTML content using Selenium for {url}")
            else:
                html_content = self._fetch_html(url)
                
            if not html_content:
                logger.warning(f"Failed to fetch HTML content from {url}")
                return None
            
            # Create BeautifulSoup object
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract with trafilatura
            traf_result = trafilatura.extract(html_content, include_links=True, output_format='xml')
            
            # Extract with newspaper3k
            article = Article(url)
            article.download(input_html=html_content)
            article.parse()
            
            # Create ArticleData object
            article_data = ArticleData(url=url)
            
            # Extract title (prioritize newspaper3k, fallback to meta tags)
            article_data.title = article.title
            if not article_data.title:
                article_data.title = self._extract_title_from_meta(soup)
            if not article_data.title:
                article_data.title = self._extract_title_from_url(url)
            
            # Extract content (prioritize trafilatura, fallback to newspaper3k)
            if traf_result:
                traf_soup = BeautifulSoup(traf_result, 'lxml')
                article_data.content = traf_soup.get_text(separator='\n\n', strip=True)
            
            if not article_data.content and article.text:
                article_data.content = article.text
                
            if not article_data.content:
                article_data.content = self._extract_content_from_html(soup)
            
            # Extract date (try multiple methods)
            article_data.date = self._extract_date_from_html(soup, url)
            if not article_data.date and article.publish_date:
                article_data.date = article.publish_date
            
            # Extract author
            article_data.author = article.authors[0] if article.authors else None
            if not article_data.author:
                article_data.author = self._extract_author_from_meta(soup)
            
            # Extract domain and source
            parsed_url = urlparse(url)
            article_data.domain = parsed_url.netloc
            article_data.source = article_data.domain
            
            # Extract hyperlinks
            article_data.hyperlinks = self._extract_hyperlinks_from_html(soup, url)
            
            # Ensure we have at least a title and some content
            if not article_data.title:
                article_data.title = self._extract_title_from_url(url)
                
            if not article_data.content:
                article_data.content = "Content extraction failed. The article may be behind a paywall or require JavaScript."
                article_data.extraction_limited = True
            
            return article_data
            
        except Exception as e:
            logger.error(f"Error in _extract_article_info for {url}: {e}", exc_info=True)
            return None
    
    def _fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content as string or None if failed
        """
        # Get headers from config or use defaults
        headers = self.config.get('headers', {})
        
        # Ensure user agent is set
        if 'User-Agent' not in headers:
            headers['User-Agent'] = self.user_agent
            
        # Add any missing standard headers
        if 'Accept' not in headers:
            headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        if 'Accept-Language' not in headers:
            headers['Accept-Language'] = 'en-US,en;q=0.5'
            
        logger.debug(f"Fetching URL: {url} with headers: {headers}")
        
        # Create a session if we're using cookies
        session = requests.Session() if self.use_cookies else None
        
        for attempt in range(self.max_retries):
            try:
                if session:
                    response = session.get(url, headers=headers, timeout=self.timeout)
                else:
                    response = requests.get(url, headers=headers, timeout=self.timeout)
                    
                response.raise_for_status()
                
                # Log response info
                logger.debug(f"Response status: {response.status_code}, Content-Type: {response.headers.get('Content-Type')}")
                
                return response.text
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt+1}/{self.max_retries} failed for {url}: {e}")
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to fetch HTML after {self.max_retries} attempts: {e}")
                    return None
                # Add exponential backoff
                import time
                time.sleep(2 ** attempt)
        
        return None
    
    def _extract_title_from_meta(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract title from meta tags.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Title as string or None if not found
        """
        # Try og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()
        
        # Try twitter:title
        twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
        if twitter_title and twitter_title.get('content'):
            return twitter_title['content'].strip()
        
        # Try title tag
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            return title_tag.string.strip()
        
        return None
    
    def _extract_title_from_url(self, url: str) -> str:
        """
        Extract a title from the URL path.
        
        Args:
            url: URL of the article
            
        Returns:
            Title derived from URL
        """
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path.strip('/')
            
            # If path is empty, use the domain
            if not path:
                return parsed_url.netloc
            
            # Get the last part of the path
            path_parts = path.split('/')
            last_part = path_parts[-1]
            
            # Remove file extension if present
            if '.' in last_part:
                last_part = last_part.rsplit('.', 1)[0]
            
            # Replace hyphens and underscores with spaces
            title = last_part.replace('-', ' ').replace('_', ' ')
            
            # Capitalize words
            title = ' '.join(word.capitalize() for word in title.split())
            
            return title
        except Exception as e:
            logger.warning(f"Failed to extract title from URL {url}: {e}")
            return "Untitled Article"
    
    def _extract_content_from_html(self, soup: BeautifulSoup) -> str:
        """
        Extract content from HTML using heuristics.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Content as string
        """
        # Look for common content containers
        content_containers = soup.select('article, .article, .content, .post, .entry, main')
        
        if content_containers:
            # Use the largest container by text length
            largest_container = max(content_containers, key=lambda x: len(x.get_text()))
            
            # Remove unwanted elements
            for unwanted in largest_container.select('script, style, nav, header, footer, .ad, .advertisement, .social, .comments, .related'):
                unwanted.decompose()
            
            return largest_container.get_text(separator='\n\n', strip=True)
        
        # Fallback to body text
        body = soup.find('body')
        if body:
            # Remove unwanted elements
            for unwanted in body.select('script, style, nav, header, footer, .ad, .advertisement, .social, .comments, .related'):
                unwanted.decompose()
            
            return body.get_text(separator='\n\n', strip=True)
        
        return ""
    
    def _extract_date_from_html(self, soup: BeautifulSoup, url: str) -> Optional[Union[str, datetime.datetime]]:
        """
        Extract publication date from HTML using multiple methods.
        
        Args:
            soup: BeautifulSoup object
            url: URL of the article
            
        Returns:
            Date as string or datetime, or None if not found
        """
        # Try common meta tags
        for meta_property in ['article:published_time', 'og:published_time', 'publication_date', 'publishedDate', 'date']:
            meta_tag = soup.find('meta', property=meta_property) or soup.find('meta', attrs={'name': meta_property})
            if meta_tag and meta_tag.get('content'):
                try:
                    date_str = meta_tag['content'].strip()
                    # Try to parse as ISO format
                    return datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    # Return as string if parsing fails
                    return date_str
        
        # Try LD+JSON
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict) and 'datePublished' in data:
                    date_str = data['datePublished']
                    try:
                        return datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        return date_str
            except Exception:
                pass
        
        # Try time tags with datetime attribute
        time_tag = soup.find('time')
        if time_tag and time_tag.get('datetime'):
            try:
                date_str = time_tag['datetime'].strip()
                return datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                return date_str
        
        # Try to find date patterns in text
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\w+ \d{1,2}, \d{4}',  # Month DD, YYYY
            r'\d{1,2} \w+ \d{4}'   # DD Month YYYY
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, soup.get_text())
            if matches:
                return matches[0]
        
        # Return current date as fallback
        return datetime.datetime.now()
    
    def _extract_author_from_meta(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract author from meta tags.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Author as string or None if not found
        """
        # Try common meta tags
        for meta_property in ['author', 'article:author', 'og:author', 'twitter:creator']:
            meta_tag = soup.find('meta', property=meta_property) or soup.find('meta', attrs={'name': meta_property})
            if meta_tag and meta_tag.get('content'):
                return meta_tag['content'].strip()
        
        # Try byline
        byline = soup.find(class_=re.compile(r'byline|author|writer', re.I))
        if byline:
            return byline.get_text().strip()
        
        return None
    
    def _extract_hyperlinks_from_html(self, soup: BeautifulSoup, base_url: str) -> List[Hyperlink]:
        """
        Extract hyperlinks from HTML.
        
        Args:
            soup: BeautifulSoup object
            base_url: Base URL for resolving relative links
            
        Returns:
            List of Hyperlink objects
        """
        hyperlinks = []
        
        try:
            # Find all links in the document
            for link in soup.find_all('a', href=True):
                href = link['href'].strip()
                
                # Skip empty, javascript, and anchor links
                if not href or href.startswith(('javascript:', '#', 'mailto:', 'tel:')):
                    continue
                
                # Resolve relative URLs
                full_url = urljoin(base_url, href)
                
                # Get link text
                text = link.get_text().strip()
                if not text:
                    # Use the URL as text if no text is available
                    text = full_url
                
                hyperlinks.append(Hyperlink(url=full_url, text=text))
                
        except Exception as e:
            logger.warning(f"Error extracting hyperlinks: {e}")
        
        return hyperlinks
    
    def _filter_content_hyperlinks(self, hyperlinks: List[Hyperlink]) -> List[Hyperlink]:
        """
        Filter and deduplicate hyperlinks.
        
        Args:
            hyperlinks: List of hyperlinks to filter
            
        Returns:
            Filtered list of hyperlinks
        """
        if not hyperlinks:
            return []
        
        # Keep track of unique URLs
        unique_urls = set()
        filtered_links = []
        
        for link in hyperlinks:
            # Skip links with empty URLs
            if not link.url:
                continue
                
            # Skip duplicate URLs - only keep the first occurrence
            if link.url in unique_urls:
                continue
                
            unique_urls.add(link.url)
            filtered_links.append(link)
        
        return filtered_links
    
    def _detect_paywall(self, article_data: ArticleData) -> tuple[bool, bool]:
        """
        Detect if an article is behind a paywall.
        
        Args:
            article_data: ArticleData object
            
        Returns:
            Tuple of (is_paywalled, extraction_limited)
        """
        is_paywalled = False
        extraction_limited = False
        
        # Check domain against known paywall sites
        if article_data.domain:
            for paywall_domain in self.paywall_domains:
                if paywall_domain in article_data.domain:
                    is_paywalled = True
                    break
        
        # Check content length for news sites
        if article_data.content and article_data.domain:
            # Only apply this heuristic to news domains
            if len(article_data.content) < self.min_content_length:
                extraction_limited = True
                
                # If it's a news site with very short content, it's likely paywalled
                if any(news_domain in article_data.domain for news_domain in self.paywall_domains):
                    is_paywalled = True
        
        # Check for paywall phrases in content
        if article_data.content:
            content_lower = article_data.content.lower()
            for phrase in self.paywall_phrases:
                if phrase in content_lower:
                    is_paywalled = True
                    extraction_limited = True
                    break
        
        if is_paywalled:
            logger.warning(f"Paywall detected for {article_data.url}")
        
        if extraction_limited:
            logger.warning(f"Content extraction appears to be limited for {article_data.url}")
        
        return is_paywalled, extraction_limited
    
    def format_article_as_xml(self, article_data: ArticleData) -> str:
        """
        Format article data as XML for Claude.
        
        Args:
            article_data: ArticleData object
            
        Returns:
            Article data formatted as XML
        """
        # Helper function to safely format text for XML
        def safe_xml_text(text):
            if text is None:
                return ""
            # Replace XML special characters
            return (str(text)
                    .replace('&', '&amp;')
                    .replace('<', '&lt;')
                    .replace('>', '&gt;')
                    .replace('"', '&quot;')
                    .replace("'", '&apos;'))
        
        # Start building XML
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<article>\n'
        
        # Add hyperlinks section first (least important for Claude's attention)
        xml += '  <hyperlinks>\n'
        if article_data.hyperlinks:
            for link in article_data.hyperlinks:
                xml += f'    <link url="{safe_xml_text(link.url)}">{safe_xml_text(link.text)}</link>\n'
        else:
            xml += '    <info>No hyperlinks found in the article.</info>\n'
        xml += '  </hyperlinks>\n'
        
        # Add metadata section second (medium importance)
        xml += '  <metadata>\n'
        xml += f'    <url>{safe_xml_text(article_data.url)}</url>\n'
        xml += f'    <title>{safe_xml_text(article_data.title)}</title>\n'
        xml += f'    <date>{safe_xml_text(article_data.date)}</date>\n'
        xml += f'    <author>{safe_xml_text(article_data.author)}</author>\n'
        xml += f'    <source>{safe_xml_text(article_data.source)}</source>\n'
        xml += f'    <domain>{safe_xml_text(article_data.domain)}</domain>\n'
        
        # Add paywall information
        if article_data.is_paywalled:
            xml += '    <paywall>true</paywall>\n'
            xml += '    <paywall_note>This article appears to be behind a paywall. Content extraction may be limited.</paywall_note>\n'
        else:
            xml += '    <paywall>false</paywall>\n'
        
        xml += '  </metadata>\n'
        
        # Add content section last (most important for Claude's attention)
        xml += '  <content>\n'
        
        # Add paywall warning to content if needed
        if article_data.is_paywalled:
            xml += '    <paywall_warning>\n'
            xml += '      WARNING: This article appears to be behind a paywall. The following content may be incomplete.\n'
            xml += '      Please note this limitation in your analysis.\n'
            xml += '    </paywall_warning>\n'
        
        # Add the main content
        xml += f'    {safe_xml_text(article_data.content)}\n'
        
        xml += '  </content>\n'
        xml += '</article>'
        
        return xml

def is_valid_url(url: str) -> bool:
    """
    Check if a URL is valid and has an appropriate scheme.
    
    Args:
        url: The URL to validate
        
    Returns:
        bool: True if the URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception as e:
        logger.warning(f"URL validation error: {e}")
        return False

def safe_request(url: str, max_retries: int = 3) -> requests.Response:
    """
    Make a safe HTTP request with proper headers, error handling, and retries.
    
    Args:
        url: The URL to request
        max_retries: Maximum number of retry attempts
        
    Returns:
        requests.Response: The HTTP response
        
    Raises:
        ValueError: If the URL is invalid
        requests.exceptions.RequestException: If the request fails after all retries
    """
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }
    
    retry_count = 0
    backoff_factor = 0.5
    timeout = 15
    
    while retry_count <= max_retries:
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            retry_count += 1
            if retry_count > max_retries:
                logger.error(f"Failed to fetch {url} after {max_retries} retries: {e}")
                raise
            
            # Exponential backoff
            wait_time = backoff_factor * (2 ** (retry_count - 1))
            logger.warning(f"Request failed, retrying in {wait_time:.2f}s: {e}")
            time.sleep(wait_time)

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
    
    # Unescape HTML entities
    text = html.unescape(text)
    
    # Remove common patterns from news sites
    cleanup_patterns = [
        r'Subscribe to our newsletter',
        r'Sign up for our daily newsletter',
        r'We use cookies',
        r'Accept cookies',
        r'Privacy Policy',
        r'Terms of Service',
        r'Share this article',
        r'Follow us on'
    ]
    
    for pattern in cleanup_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove duplicate paragraphs (common in some extractions)
    lines = text.split('\n')
    unique_lines = []
    for line in lines:
        line = line.strip()
        if line and line not in unique_lines:
            unique_lines.append(line)
    
    return '\n'.join(unique_lines)

def filter_content_hyperlinks(hyperlinks: List[Hyperlink], content: str) -> List[Hyperlink]:
    """
    Filter hyperlinks to only include those relevant to the article content.
    Removes duplicates, keeping only the first occurrence of each unique URL.
    
    Args:
        hyperlinks: List of all extracted hyperlinks
        content: The article content text
        
    Returns:
        List[Hyperlink]: Filtered list of hyperlinks that are relevant to the content
    """
    if not hyperlinks or not content:
        return []
    
    # Convert content to lowercase for case-insensitive matching
    content_lower = content.lower()
    
    # Filter criteria:
    filtered_links = []
    seen_urls = set()  # Track URLs we've already processed
    
    for link in hyperlinks:
        # Skip empty links
        if not link.url or not link.text:
            continue
            
        # Skip duplicate URLs - only keep the first occurrence
        if link.url in seen_urls:
            continue
        
        # Skip links with very short text (likely icons or navigation)
        if len(link.text.strip()) < 3:
            continue
            
        # Skip common navigation/footer links
        nav_patterns = ['home', 'about', 'contact', 'privacy', 'terms', 'login', 
                        'sign in', 'subscribe', 'menu', 'search', 'share', 
                        'facebook', 'twitter', 'instagram', 'linkedin']
        
        if any(pattern in link.text.lower() for pattern in nav_patterns):
            continue
            
        # Skip links that don't have their text in the content
        # This helps identify links that are in the main article vs. navigation
        link_text_lower = link.text.lower()
        if len(link_text_lower) > 5 and link_text_lower in content_lower:
            filtered_links.append(link)
            seen_urls.add(link.url)  # Mark this URL as seen
            continue
            
        # Include links that have URLs referenced in the content
        if link.url and link.url in content:
            filtered_links.append(link)
            seen_urls.add(link.url)  # Mark this URL as seen
            continue
    
    return filtered_links

def extract_with_trafilatura(url: str) -> Dict[str, Any]:
    """
    Extract article data using trafilatura.
    
    Args:
        url: URL of the article
        
    Returns:
        Dict[str, Any]: Extracted data
    """
    try:
        logger.info(f"Extracting with trafilatura: {url}")
        response = safe_request(url)
        
        # Extract with trafilatura
        extracted = trafilatura.extract(
            response.text,
            output_format='xml',
            include_links=True,
            include_images=False,
            include_tables=False,
            include_formatting=False,
            date_extraction_params={"extensive_search": True}
        )
        
        if not extracted:
            return {"error": "Trafilatura extraction failed"}
        
        # Parse the XML output
        soup = BeautifulSoup(extracted, 'lxml-xml')
        
        # Extract data from XML
        title = soup.find('title')
        title = title.text if title else None
        
        content = soup.find('text')
        content = content.text if content else None
        
        author = soup.find('author')
        author = author.text if author else None
        
        date = soup.find('date')
        date = date.text if date else None
        
        # Extract hyperlinks
        hyperlinks = []
        for link in soup.find_all('ref'):
            if link.get('target') and link.text:
                hyperlinks.append(Hyperlink(url=link.get('target'), text=link.text))
        
        return {
            "title": title,
            "content": content,
            "author": author,
            "date": date,
            "hyperlinks": hyperlinks
        }
    
    except Exception as e:
        logger.error(f"Trafilatura extraction error: {e}")
        return {"error": f"Trafilatura extraction error: {e}"}

def extract_with_newspaper(url: str) -> Dict[str, Any]:
    """
    Extract article data using newspaper3k.
    
    Args:
        url: URL of the article
        
    Returns:
        Dict[str, Any]: Extracted data
    """
    try:
        # Configure newspaper
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
        article = Article(url, browser_user_agent=user_agent)
        
        # Download and parse
        article.download()
        article.parse()
        
        # Extract data
        title = article.title
        content = article.text
        
        # Extract and normalize date
        date = None
        if article.publish_date:
            date = article.publish_date
        else:
            # Try to find date in meta tags or other sources
            date = extract_date_from_html(article.html)
        
        # Extract author
        author = None
        if article.authors:
            author = ', '.join(article.authors)
            
        # Extract hyperlinks
        hyperlinks = []
        if article.html:
            hyperlinks = extract_hyperlinks_from_html(article.html, url)
            
        return {
            "title": title,
            "content": content,
            "date": date,
            "author": author,
            "hyperlinks": hyperlinks,
            "html": article.html
        }
    except Exception as e:
        logger.error(f"Error extracting with newspaper3k: {e}")
        return {"error": str(e)}

def extract_date_from_html(html_content: str) -> Optional[str]:
    """
    Extract publication date from HTML using various patterns.
    
    Args:
        html_content: HTML content of the article
        
    Returns:
        Optional[str]: Extracted date as string or None if not found
    """
    if not html_content:
        return None
        
    try:
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Common meta tags for dates
        date_meta_tags = [
            'article:published_time', 'datePublished', 'date', 'pubdate',
            'publishdate', 'og:published_time', 'publication_date'
        ]
        
        # Check meta tags
        for tag_name in date_meta_tags:
            meta_tag = soup.find('meta', {'property': tag_name}) or soup.find('meta', {'name': tag_name})
            if meta_tag and meta_tag.get('content'):
                return meta_tag['content']
        
        # Look for time tags
        time_tags = soup.find_all('time')
        for time_tag in time_tags:
            if time_tag.get('datetime'):
                return time_tag['datetime']
            elif time_tag.text and len(time_tag.text.strip()) > 5:  # Avoid empty or too short text
                return time_tag.text.strip()
        
        # Look for common date patterns in text
        date_patterns = [
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',
            r'\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}',
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{1,2}\.\d{1,2}\.\d{4}'
        ]
        
        for pattern in date_patterns:
            for text in soup.stripped_strings:
                match = re.search(pattern, text)
                if match:
                    return match.group(0)
                    
        # If nothing found, return current date as fallback
        return None
    except Exception as e:
        logger.warning(f"Error extracting date from HTML: {e}")
        return None

def extract_article_info(url: str) -> ArticleData:
    """
    Extract article content and metadata from a URL using multiple strategies.
    
    Args:
        url (str): URL of the news article
        
    Returns:
        ArticleData: Object containing extracted information
    """
    logger.info(f"Extracting article info from: {url}")
    
    # Initialize with default values
    article_data = ArticleData(url=url)
    
    # Try trafilatura first
    try:
        logger.info(f"Extracting with trafilatura: {url}")
        trafilatura_result = extract_with_trafilatura(url)
        
        if trafilatura_result and trafilatura_result.get("content"):
            logger.info("Trafilatura extraction successful")
            article_data.title = trafilatura_result.get("title")
            article_data.content = trafilatura_result.get("content")
            article_data.author = trafilatura_result.get("author")
            article_data.date = trafilatura_result.get("date")
            article_data.hyperlinks = trafilatura_result.get("hyperlinks", [])
            
            # Extract and filter hyperlinks from HTML
            if "html" in trafilatura_result:
                hyperlinks = extract_hyperlinks_from_html(trafilatura_result["html"], url)
                filtered_links = filter_content_hyperlinks(hyperlinks, article_data.content)
                article_data.hyperlinks = filtered_links
                
            # Ensure we have a title
            if not article_data.title:
                article_data.title = extract_title_from_url(url)
                
            return article_data
        else:
            logger.warning("Trafilatura returned empty content")
            
    except Exception as e:
        logger.error(f"Trafilatura extraction error: {str(e)}")
    
    # Fall back to newspaper3k
    try:
        logger.info(f"Extracting with newspaper3k: {url}")
        newspaper_result = extract_with_newspaper(url)
        
        if newspaper_result and newspaper_result.get("content"):
            logger.info("Newspaper3k extraction successful")
            article_data.title = article_data.title or newspaper_result.get("title")
            article_data.content = article_data.content or newspaper_result.get("content")
            article_data.author = article_data.author or newspaper_result.get("author")
            article_data.date = newspaper_result.get("date")
            
            # Check for limited content that might indicate a paywall
            is_limited = detect_paywall(article_data.content, url)
            if is_limited:
                article_data.is_paywalled = True
                article_data.extraction_limited = True
                logger.warning(f"Paywall detected at {url} - content extraction may be limited")
                
                # Add a note about the paywall to the content
                paywall_note = "\n\n**NOTE: Content extraction was limited due to a paywall or access restrictions. The analysis below may be based on incomplete information.**\n\n"
                article_data.content = article_data.content + paywall_note
            
            # Ensure we have a title
            if not article_data.title:
                article_data.title = extract_title_from_url(url)
                
            return article_data
        else:
            logger.warning("Newspaper3k returned empty content")
    except Exception as e:
        logger.error(f"Error extracting with newspaper3k: {str(e)}")
        
        # If both methods failed with exceptions, check if it might be due to a paywall
        if "403" in str(e) or "forbidden" in str(e).lower() or "paywall" in str(e).lower():
            article_data.is_paywalled = True
            article_data.extraction_limited = True
            logger.warning(f"Paywall likely detected at {url} - content extraction was limited")
            
            # Add a note about the paywall to the content
            paywall_note = "\n\n**NOTE: Content extraction was limited due to a paywall or access restrictions. The analysis below may be based on incomplete information.**\n\n"
            article_data.content = article_data.content + paywall_note
    
    # If we got here, both extraction methods failed
    if not article_data.content:
        logger.error(f"Failed to extract content from {url}")
        article_data.extraction_limited = True
        article_data.content = "Content extraction failed. This may be due to a paywall or access restrictions."
    
    # Ensure we have a title
    if not article_data.title:
        article_data.title = extract_title_from_url(url)
        
    # Final validation - ensure we have at least minimal content
    article_data.title = article_data.title or "Untitled Article"
    article_data.content = article_data.content or "Content extraction failed."
    article_data.date = article_data.date or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    return article_data

def extract_title_from_url(url: str) -> str:
    """
    Extract a title from the URL when other extraction methods fail.
    
    Args:
        url: The URL to extract title from
        
    Returns:
        str: Extracted title or fallback
    """
    try:
        # Parse the URL
        parsed_url = urlparse(url)
        
        # Extract the last part of the path
        path = parsed_url.path.strip('/')
        segments = path.split('/')
        
        # Use the last segment if available
        if segments:
            last_segment = segments[-1]
            
            # Clean up common URL patterns
            last_segment = re.sub(r'\.(html|php|aspx)$', '', last_segment)
            
            # Replace hyphens, underscores with spaces and capitalize words
            title = last_segment.replace('-', ' ').replace('_', ' ').replace('.', ' ')
            title = ' '.join(word.capitalize() for word in title.split())
            
            return title
    except Exception as e:
        logger.warning(f"Failed to extract title from URL: {e}")
    
    # Fallback
    return "Untitled Article"

def detect_paywall(content: str, url: str) -> bool:
    """
    Detect if content extraction was likely limited by a paywall.
    
    Args:
        content: The extracted content
        url: The source URL
        
    Returns:
        bool: True if paywall likely detected
    """
    # Check content length - very short content from news sites is suspicious
    if len(content.strip()) < 1000:
        # Known paywall domains
        paywall_domains = [
            "nytimes.com", "wsj.com", "ft.com", "economist.com", 
            "washingtonpost.com", "newyorker.com", "bloomberg.com",
            "thetimes.co.uk", "telegraph.co.uk", "latimes.com"
        ]
        
        # Check if URL is from a known paywalled site
        if any(domain in url.lower() for domain in paywall_domains):
            return True
            
    # Check for common paywall phrases in the content
    paywall_phrases = [
        "subscribe to continue", "subscribe to read", "subscription required",
        "to continue reading", "create an account", "sign up to read",
        "premium content", "premium article", "members only", "subscribe now",
        "register to continue", "paid subscribers only", "sign in to read"
    ]
    
    content_lower = content.lower()
    if any(phrase in content_lower for phrase in paywall_phrases):
        return True
        
    return False

def format_article_as_xml(article_data: ArticleData) -> str:
    """
    Format the extracted article data as XML for Claude processing.
    
    Args:
        article_data: The article data to format
        
    Returns:
        str: XML representation of the article
    """
    def safe_xml_text(text):
        """Make text safe for XML by escaping special characters."""
        if text is None:
            return ""
        return (str(text)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&apos;"))
    
    xml = '<article>\n'
    
    # 1. References and URLs (least important)
    xml += f'  <hyperlinks>\n'
    if article_data.hyperlinks:
        for link in article_data.hyperlinks:
            xml += f'    <link url="{safe_xml_text(link.url)}">{safe_xml_text(link.text)}</link>\n'
    else:
        xml += f'    <info>No hyperlinks found in the article</info>\n'
    xml += f'  </hyperlinks>\n'
    
    # Add paywall information
    xml += f'  <paywall>\n'
    xml += f'    <is_paywalled>{str(article_data.is_paywalled).lower()}</is_paywalled>\n'
    xml += f'    <extraction_limited>{str(article_data.extraction_limited).lower()}</extraction_limited>\n'
    xml += f'  </paywall>\n'
    
    # 2. Metadata (medium importance)
    xml += f'  <metadata>\n'
    xml += f'    <url>{safe_xml_text(article_data.url)}</url>\n'
    xml += f'    <source>{safe_xml_text(article_data.source)}</source>\n'
    xml += f'    <date>{safe_xml_text(article_data.date)}</date>\n'
    xml += f'    <author>{safe_xml_text(article_data.author)}</author>\n'
    xml += f'    <title>{safe_xml_text(article_data.title)}</title>\n'
    xml += f'  </metadata>\n'
    
    # 3. Content (most important)
    xml += f'  <content>\n'
    xml += f'    {safe_xml_text(article_data.content)}\n'
    xml += f'  </content>\n'
    
    xml += '</article>'
    return xml

def extract_hyperlinks_from_html(html_content: str, base_url: str) -> List[Hyperlink]:
    """
    Extract hyperlinks from HTML content.
    
    Args:
        html_content: HTML content to extract links from
        base_url: Base URL for resolving relative links
        
    Returns:
        List[Hyperlink]: List of extracted hyperlinks
    """
    if not html_content:
        return []
        
    try:
        hyperlinks = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().strip()
            
            # Skip empty links or javascript
            if not href or href.startswith('javascript:') or href == '#':
                continue
                
            # Resolve relative URLs
            if not href.startswith(('http://', 'https://')):
                # Handle different types of relative URLs
                if href.startswith('/'):
                    # Absolute path
                    base_parts = urlparse(base_url)
                    href = f"{base_parts.scheme}://{base_parts.netloc}{href}"
                else:
                    # Relative path - more complex, simplified for now
                    base_parts = urlparse(base_url)
                    base_path = os.path.dirname(base_parts.path)
                    if not base_path.endswith('/'):
                        base_path += '/'
                    href = f"{base_parts.scheme}://{base_parts.netloc}{base_path}{href}"
            
            # Add to list if it has text
            if text:
                hyperlinks.append(Hyperlink(url=href, text=text))
                
        return hyperlinks
    except Exception as e:
        logger.error(f"Error extracting hyperlinks from HTML: {e}")
        return []
