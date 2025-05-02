#!/usr/bin/env python3
"""
Selenium Extractor

Uses Selenium WebDriver to extract content from websites with strong anti-scraping measures.
"""

import os
import time
import random
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

class SeleniumExtractor:
    """Uses Selenium WebDriver to extract content from websites with strong anti-scraping measures."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Selenium extractor.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.driver = None
        self.user_agent = self._get_user_agent()
        
    def _get_user_agent(self) -> str:
        """
        Get a user agent string, either from config or using fake-useragent.
        
        Returns:
            User agent string
        """
        if self.config and 'user_agent' in self.config:
            return self.config.get('user_agent')
        
        try:
            ua = UserAgent()
            return ua.chrome
        except Exception as e:
            logger.warning(f"Failed to get user agent from fake-useragent: {e}")
            # Fallback to a common Chrome user agent
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    
    def _initialize_driver(self) -> None:
        """Initialize the Selenium WebDriver."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument(f"user-agent={self.user_agent}")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # Add additional arguments from config
            extra_args = self.config.get('selenium_args', [])
            for arg in extra_args:
                chrome_options.add_argument(arg)
            
            # Set window size to mimic a desktop browser
            chrome_options.add_argument("--window-size=1920,1080")
            
            # Disable images for faster loading
            chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            
            # Add experimental options to avoid detection
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)
            
            # Initialize the WebDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Set additional properties to avoid detection
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            logger.info("Selenium WebDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Selenium WebDriver: {e}")
            raise
    
    def extract_html(self, url: str) -> Optional[str]:
        """
        Extract HTML content from a URL using Selenium.
        
        Args:
            url: URL to extract content from
            
        Returns:
            HTML content as string or None if extraction failed
        """
        if self.driver is None:
            try:
                self._initialize_driver()
            except Exception as e:
                logger.error(f"Failed to initialize WebDriver: {e}")
                return None
        
        try:
            logger.info(f"Extracting content from {url} using Selenium")
            
            # Navigate to the URL
            self.driver.get(url)
            
            # Add random delay to mimic human behavior
            random_delay = random.uniform(
                self.config.get('min_delay', 2),
                self.config.get('max_delay', 5)
            )
            time.sleep(random_delay)
            
            # Wait for the page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Scroll down to load lazy content
            self._scroll_page()
            
            # Get the page source
            html_content = self.driver.page_source
            
            # Check if we need to handle cookies or paywalls
            if self._is_cookie_banner_present():
                self._handle_cookie_banner()
                # Reload the page source after handling cookies
                html_content = self.driver.page_source
            
            if self._is_paywall_present(url):
                logger.warning(f"Paywall detected for {url}")
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error extracting content from {url} using Selenium: {e}")
            return None
            
        finally:
            # Don't close the driver after each extraction to reuse it
            pass
    
    def _scroll_page(self) -> None:
        """Scroll down the page to load lazy content."""
        try:
            # Get scroll height
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # Scroll down in steps
            for i in range(3):  # Scroll in 3 steps
                # Scroll down to a portion of the page
                scroll_position = (i + 1) * last_height // 3
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                
                # Add random delay between scrolls
                time.sleep(random.uniform(0.5, 1.5))
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            
        except Exception as e:
            logger.warning(f"Error scrolling page: {e}")
    
    def _is_cookie_banner_present(self) -> bool:
        """Check if a cookie consent banner is present on the page."""
        try:
            # Common cookie banner selectors
            selectors = [
                "div[class*='cookie']",
                "div[id*='cookie']",
                "div[class*='consent']",
                "div[id*='consent']",
                "div[class*='gdpr']",
                "div[id*='gdpr']"
            ]
            
            for selector in selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements and any(el.is_displayed() for el in elements):
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking for cookie banner: {e}")
            return False
    
    def _handle_cookie_banner(self) -> None:
        """Handle cookie consent banners by clicking accept buttons."""
        try:
            # Common accept button selectors
            button_selectors = [
                "button[id*='accept']",
                "button[class*='accept']",
                "a[id*='accept']",
                "a[class*='accept']",
                "button[id*='agree']",
                "button[class*='agree']",
                "button[id*='consent']",
                "button[class*='consent']",
                "button:contains('Accept')",
                "button:contains('Agree')",
                "button:contains('OK')"
            ]
            
            for selector in button_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in buttons:
                        if button.is_displayed():
                            button.click()
                            logger.info("Clicked cookie consent button")
                            time.sleep(1)  # Wait for banner to disappear
                            return
                except Exception:
                    continue
            
            logger.warning("Could not find cookie consent button to click")
            
        except Exception as e:
            logger.warning(f"Error handling cookie banner: {e}")
    
    def _is_paywall_present(self, url: str) -> bool:
        """
        Check if a paywall is present on the page.
        
        Args:
            url: URL of the page
            
        Returns:
            True if a paywall is detected, False otherwise
        """
        try:
            # Check domain against known paywall sites
            domain = urlparse(url).netloc
            paywall_domains = self.config.get('paywall_domains', [])
            
            if any(pd in domain for pd in paywall_domains):
                # Check for common paywall selectors
                paywall_selectors = [
                    "div[class*='paywall']",
                    "div[id*='paywall']",
                    "div[class*='subscribe']",
                    "div[id*='subscribe']",
                    "div[class*='premium']",
                    "div[id*='premium']"
                ]
                
                for selector in paywall_selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and any(el.is_displayed() for el in elements):
                        return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Error checking for paywall: {e}")
            return False
    
    def close(self) -> None:
        """Close the WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("Selenium WebDriver closed")
            except Exception as e:
                logger.warning(f"Error closing Selenium WebDriver: {e}")
