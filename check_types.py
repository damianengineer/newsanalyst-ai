#!/usr/bin/env python3
"""
Type Checking Script

Run mypy on the codebase to check for type errors.
"""

import os
import sys
import subprocess
from typing import List, Tuple

def run_mypy(paths: List[str]) -> Tuple[int, str]:
    """
    Run mypy on the specified paths.
    
    Args:
        paths: List of paths to check
        
    Returns:
        Tuple of (exit_code, output)
    """
    cmd = ["mypy"] + paths
    process = subprocess.run(cmd, capture_output=True, text=True)
    return process.returncode, process.stdout

def main():
    """Run mypy on the codebase."""
    print("Running type checking with mypy...")
    
    # Paths to check
    paths = [
        "src",
        "newsanalyst.py",
        "tests"
    ]
    
    # Run mypy
    exit_code, output = run_mypy(paths)
    
    # Print output
    print(output)
    
    # Print summary
    if exit_code == 0:
        print("\n✅ Type checking passed!")
    else:
        print(f"\n❌ Type checking failed with exit code {exit_code}")
        print("Fix the type errors above to improve code quality.")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
