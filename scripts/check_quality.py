#!/usr/bin/env python3
"""
Run all code quality checks for the Nexus project
"""

import subprocess
import sys
from pathlib import Path
import argparse

def run_command(cmd: list, description: str) -> tuple[bool, str, str]:
    """Run a command and return success status with output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    parser = argparse.ArgumentParser(description="Run code quality checks")
    parser.add_argument("--fix", action="store_true", help="Automatically fix issues where possible")
    parser.add_argument("--check", choices=["all", "format", "imports", "lint", "types"], 
                       default="all", help="Which checks to run")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    backend_path = project_root / "backend"
    
    if not backend_path.exists():
        print("❌ Backend directory not found")
        sys.exit(1)

    checks = []
    
    # Define all available checks
    all_checks = [
        (["black", "--check" if not args.fix else "", str(backend_path)], "Code formatting (Black)", "format"),
        (["isort", "--check-only" if not args.fix else "", str(backend_path)], "Import organization (isort)", "imports"),
        (["flake8", str(backend_path)], "Linting (flake8)", "lint"),
        (["mypy", str(backend_path)], "Type checking (mypy)", "types"),
    ]
    
    # Filter commands based on --fix flag
    for cmd, desc, check_type in all_checks:
        if args.check == "all" or args.check == check_type:
            # Remove empty strings from command (like when --fix removes --check flags)
            filtered_cmd = [arg for arg in cmd if arg]
            checks.append((filtered_cmd, desc, check_type))
    
    print(f"🔍 Running code quality checks on {backend_path}")
    print("=" * 60)
    
    failed_checks = []
    
    for cmd, description, check_type in checks:
        print(f"\n📋 {description}...")
        success, stdout, stderr = run_command(cmd, description)
        
        if success:
            print(f"✅ {description} passed")
            if stdout.strip():
                print(f"   Output: {stdout.strip()}")
        else:
            print(f"❌ {description} failed")
            failed_checks.append(description)
            
            if stdout.strip():
                print(f"   stdout: {stdout.strip()}")
            if stderr.strip():
                print(f"   stderr: {stderr.strip()}")
    
    print("\n" + "=" * 60)
    
    if failed_checks:
        print(f"💥 {len(failed_checks)} check(s) failed:")
        for check in failed_checks:
            print(f"   - {check}")
        
        if not args.fix:
            print("\n💡 Try running with --fix to automatically fix some issues")
        
        sys.exit(1)
    else:
        print("🎉 All code quality checks passed!")
        
        # Show summary
        print(f"\n📊 Summary:")
        print(f"   - Checked: {len(checks)} quality aspects")
        print(f"   - Backend files: {backend_path}")
        print(f"   - Mode: {'Fix' if args.fix else 'Check'}")

if __name__ == "__main__":
    main()
