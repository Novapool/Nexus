#!/usr/bin/env python3
"""
Organize imports in Python files using isort with project-specific configuration
"""

import subprocess
import sys
from pathlib import Path
import argparse

def run_isort(target_path: Path, check_only: bool = False) -> tuple[bool, str, str]:
    """Run isort on the target path"""
    cmd = ["isort"]
    
    if check_only:
        cmd.append("--check-only")
        cmd.append("--diff")
    
    # Add isort configuration
    cmd.extend([
        "--profile", "black",
        "--multi-line", "3",
        "--line-length", "88",
        "--known-first-party", "backend,tests",
        "--sections", "FUTURE,STDLIB,THIRDPARTY,FIRSTPARTY,LOCALFOLDER",
        "--force-grid-wrap", "0",
        "--use-parentheses",
        "--ensure-newline-before-comments",
        str(target_path)
    ])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def find_python_files(directory: Path) -> list[Path]:
    """Find all Python files in directory"""
    python_files = []
    for file_path in directory.rglob("*.py"):
        # Skip __pycache__ and .venv directories
        if "__pycache__" in file_path.parts or ".venv" in file_path.parts:
            continue
        python_files.append(file_path)
    return sorted(python_files)

def main():
    parser = argparse.ArgumentParser(description="Organize Python imports")
    parser.add_argument("--check", action="store_true", help="Check if imports are organized (don't modify files)")
    parser.add_argument("--path", type=str, help="Specific path to organize (default: backend/)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    
    if args.path:
        target_path = Path(args.path)
        if not target_path.is_absolute():
            target_path = project_root / target_path
    else:
        target_path = project_root / "backend"
    
    if not target_path.exists():
        print(f"❌ Target path does not exist: {target_path}")
        sys.exit(1)

    print(f"🔧 {'Checking' if args.check else 'Organizing'} imports in: {target_path}")
    
    if target_path.is_file():
        # Single file
        files_to_process = [target_path]
    else:
        # Directory - find all Python files
        files_to_process = find_python_files(target_path)
    
    if not files_to_process:
        print("📝 No Python files found")
        return
    
    print(f"📁 Found {len(files_to_process)} Python files")
    
    if args.verbose:
        for file_path in files_to_process:
            print(f"   - {file_path.relative_to(project_root)}")
    
    print("\n" + "=" * 60)
    
    # Process all files at once for better performance
    success, stdout, stderr = run_isort(target_path, args.check)
    
    if success:
        if args.check:
            print("✅ All imports are properly organized")
        else:
            print("✅ Import organization completed")
            
        if stdout.strip() and args.verbose:
            print(f"\nOutput:\n{stdout}")
    else:
        if args.check:
            print("❌ Some imports need organization")
            if stdout.strip():
                print(f"\nFiles that need organization:\n{stdout}")
        else:
            print("❌ Import organization failed")
            
        if stderr.strip():
            print(f"\nErrors:\n{stderr}")
        
        sys.exit(1)
    
    # Show import organization standards
    if args.verbose or not success:
        print(f"\n📋 Import Organization Standards:")
        print(f"   - Profile: black")
        print(f"   - Line length: 88")
        print(f"   - Multi-line mode: 3 (vertical hanging indent)")
        print(f"   - Section order: FUTURE, STDLIB, THIRDPARTY, FIRSTPARTY, LOCALFOLDER")
        print(f"   - First-party modules: backend, tests")

if __name__ == "__main__":
    main()
