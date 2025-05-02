#!/usr/bin/env python3
"""
Logging Utilities

Configure logging for the NewsAnalyst application.
"""

import os
import logging
import re
import sys
import structlog
from typing import Optional, Dict, Any, List

# Define a filter to redact sensitive information
class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive information from log records."""
    
    def __init__(self, patterns: List[Dict[str, Any]] = None):
        """
        Initialize the filter with patterns to redact.
        
        Args:
            patterns: List of dictionaries with 'pattern' (regex) and 'replacement' keys
        """
        super().__init__()
        self.patterns = patterns or [
            {
                'pattern': re.compile(r'("x-api-key"|"Authorization"|api_key)(\s*:\s*)("[^"]+"|[^",\s}]+)', re.IGNORECASE),
                'replacement': r'\1\2"[REDACTED]"'
            },
            {
                'pattern': re.compile(r'(password|secret|token|key)(\s*=\s*)("[^"]+"|[^",\s)]+)', re.IGNORECASE),
                'replacement': r'\1\2"[REDACTED]"'
            },
            {
                'pattern': re.compile(r'(ANTHROPIC_API_KEY|OPENAI_API_KEY)([=:])([^&\s,)]+)', re.IGNORECASE),
                'replacement': r'\1\2[REDACTED]'
            }
        ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log records by redacting sensitive information.
        
        Args:
            record: Log record to filter
            
        Returns:
            True (always allow the record, but modify it first)
        """
        if isinstance(record.msg, str):
            for pattern_dict in self.patterns:
                record.msg = pattern_dict['pattern'].sub(pattern_dict['replacement'], record.msg)
                
        # Also check args if they are strings
        if record.args:
            args_list = list(record.args)
            for i, arg in enumerate(args_list):
                if isinstance(arg, str):
                    for pattern_dict in self.patterns:
                        args_list[i] = pattern_dict['pattern'].sub(pattern_dict['replacement'], arg)
            record.args = tuple(args_list)
            
        return True

def get_log_level(level_str: str) -> int:
    """
    Convert string log level to numeric level, with validation.
    
    Args:
        level_str: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
    Returns:
        Numeric log level
    """
    valid_levels = {
        'DEBUG': logging.DEBUG,       # Detailed information, typically for debugging
        'INFO': logging.INFO,         # Confirmation that things are working as expected
        'WARNING': logging.WARNING,   # Indication that something unexpected happened
        'ERROR': logging.ERROR,       # Error that prevented something from working
        'CRITICAL': logging.CRITICAL  # Serious error that may prevent the program from continuing
    }
    
    upper_level = level_str.upper()
    if upper_level not in valid_levels:
        print(f"Warning: Invalid log level '{level_str}'. Using INFO level.")
        return logging.INFO
        
    return valid_levels[upper_level]

# Structlog processor to redact sensitive information
def redact_sensitive_data(_, __, event_dict):
    """Redact sensitive data from structlog event dictionaries."""
    patterns = [
        {
            'pattern': re.compile(r'("x-api-key"|"Authorization"|api_key)(\s*:\s*)("[^"]+"|[^",\s}]+)', re.IGNORECASE),
            'replacement': r'\1\2"[REDACTED]"'
        },
        {
            'pattern': re.compile(r'(password|secret|token|key)(\s*=\s*)("[^"]+"|[^",\s)]+)', re.IGNORECASE),
            'replacement': r'\1\2"[REDACTED]"'
        },
        {
            'pattern': re.compile(r'(ANTHROPIC_API_KEY|OPENAI_API_KEY)([=:])([^&\s,)]+)', re.IGNORECASE),
            'replacement': r'\1\2[REDACTED]'
        }
    ]
    
    # Process event message
    if "event" in event_dict and isinstance(event_dict["event"], str):
        for pattern_dict in patterns:
            event_dict["event"] = pattern_dict['pattern'].sub(
                pattern_dict['replacement'], 
                event_dict["event"]
            )
    
    # Process all string values in the event dict
    for key, value in event_dict.items():
        if isinstance(value, str):
            for pattern_dict in patterns:
                event_dict[key] = pattern_dict['pattern'].sub(
                    pattern_dict['replacement'], 
                    value
                )
                
            # Direct key matching for sensitive keys
            if key.lower() in ['api_key', 'key', 'token', 'password', 'secret'] or 'api_key' in key.lower():
                event_dict[key] = "[REDACTED]"
        elif isinstance(value, dict):
            # Recursively process nested dictionaries
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, str):
                    for pattern_dict in patterns:
                        value[nested_key] = pattern_dict['pattern'].sub(
                            pattern_dict['replacement'], 
                            nested_value
                        )
                    
                    # Direct key matching for sensitive keys
                    if nested_key.lower() in ['api_key', 'key', 'token', 'password', 'secret'] or 'api_key' in nested_key.lower():
                        value[nested_key] = "[REDACTED]"
    
    return event_dict

def configure_logging(level: str = "INFO", log_file: Optional[str] = None, module_levels: Optional[Dict[str, str]] = None) -> logging.Logger:
    """
    Configure logging for the application using structlog.
    
    Args:
        level: Logging level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        module_levels: Dictionary mapping module names to log levels
        
    Returns:
        Configured root logger
    """
    # Convert string level to logging level
    numeric_level = get_log_level(level)
    
    # Configure standard logging
    logging.basicConfig(
        level=numeric_level,
        format="%(message)s",
        stream=sys.stdout,
    )
    
    # Clear existing handlers from root logger
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    
    # Create sensitive data filter
    sensitive_filter = SensitiveDataFilter()
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(simple_formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)
    
    # File handler (only if log_file is provided AND level is ERROR or more verbose)
    if log_file and numeric_level <= logging.ERROR:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)
    
    # Set module-specific log levels if provided
    if module_levels:
        for module_name, module_level in module_levels.items():
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(get_log_level(module_level))
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            redact_sensitive_data,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Log initialization
    logger = structlog.get_logger(__name__)
    if numeric_level <= logging.INFO:
        logger.info("Logging initialized", level=level)
    
    return root_logger

def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger for the specified name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Structured logger
    """
    return structlog.get_logger(name)
