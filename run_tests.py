#!/usr/bin/env python
"""
Test runner for Nexus
"""

import sys
import pytest
import asyncio
from pathlib import Path

def main():
    """Run tests with appropriate configuration"""
    
    # Add project root to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Test arguments
    args = [
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--asyncio-mode=auto",  # Auto async mode
        "tests/",  # Test directory
    ]
    
    # Add any command line arguments
    args.extend(sys.argv[1:])
    
    # Run tests
    exit_code = pytest.main(args)
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())
