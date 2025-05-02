#!/usr/bin/env python3
"""
File Utilities

Common file operations for the NewsAnalyst application.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def read_file(file_path: str, default_content: str = "") -> str:
    """
    Read content from a file.
    
    Args:
        file_path: Path to the file to read
        default_content: Default content to return if file cannot be read
        
    Returns:
        File content as string or default content if file cannot be read
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        logger.debug(f"Read file: {file_path}")
        return content
    except Exception as e:
        logger.warning(f"Failed to read file {file_path}: {e}")
        return default_content

def write_file(file_path: str, content: str) -> bool:
    """
    Write content to a file.
    
    Args:
        file_path: Path to the file to write
        content: Content to write to the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
            
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.debug(f"Wrote file: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        return False

def ensure_directory_exists(directory_path: str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory
        
    Returns:
        True if the directory exists or was created, False otherwise
    """
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            logger.debug(f"Created directory: {directory_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {directory_path}: {e}")
        return False

def get_file_extension(file_path: str) -> str:
    """
    Get the extension of a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File extension (without the dot) or empty string if no extension
    """
    _, ext = os.path.splitext(file_path)
    return ext[1:] if ext else ""
