#!/usr/bin/env python3
"""
Test script for structured logging.
"""

import os
from src.utils.logging_utils import configure_logging, get_logger

def main():
    """Test structured logging functionality."""
    # Configure logging
    configure_logging(level="INFO")
    
    # Get a structured logger
    logger = get_logger("test_logging")
    
    # Log some test messages
    logger.info("Basic info message")
    logger.info("Message with context", url="https://example.com", status_code=200)
    logger.warning("Warning message with nested data", 
                  request={"url": "https://api.example.com", "method": "POST"},
                  response_time=1.23)
    
    # Test sensitive data redaction
    logger.info("Message with API key", api_key="sk_test_abcdefghijklmnopqrstuvwxyz")
    logger.error("Error with auth token", 
                token="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                ANTHROPIC_API_KEY="sk_ant_123456789")
    
    print("\nStructured logging test completed successfully!")

if __name__ == "__main__":
    main()
