#!/usr/bin/env python
"""
Simple test runner for the focused test suite
"""

import sys
import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def check_environment():
    """Check that environment is set up correctly"""
    print("🔍 Checking test environment...")
    
    required_vars = [
        'TEST_SERVER_IP',
        'TEST_SERVER_USERNAME', 
        'TEST_SERVER_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please add these to your .env file:")
        for var in missing_vars:
            print(f"  {var}=your_value_here")
        return False
    
    print(f"✅ Test server: {os.getenv('TEST_SERVER_USERNAME')}@{os.getenv('TEST_SERVER_IP')}")
    return True


def main():
    """Run the simple test suite"""
    print("🧪 Nexus Simple Test Suite")
    print("=" * 50)
    
    # Check environment
    if not check_environment():
        print("\n💡 Tip: Copy the .env configuration artifact and update with your server details")
        sys.exit(1)
    
    # Add project root to path
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Test arguments
    args = [
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--asyncio-mode=auto",  # Auto async mode
        "-s",  # Don't capture output (so we can see prints)
        "tests/simple/",  # Test directory
    ]
    
    # Add any command line arguments
    args.extend(sys.argv[1:])
    
    print(f"Running tests with: {' '.join(args)}")
    print("=" * 50)
    
    # Run tests
    exit_code = pytest.main(args)
    
    print("=" * 50)
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed. Check output above.")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
