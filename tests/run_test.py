#!/usr/bin/env python3
"""
Comprehensive test runner with reporting
"""
import argparse
import subprocess
import sys
from pathlib import Path
import datetime
import glob
import os
import ast
import inspect

def extract_tests_from_file(file_path):
    """Extract test classes and functions from a Python test file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse the AST
        tree = ast.parse(content)
        
        test_classes = []
        standalone_functions = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                # Found a test class
                class_methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                        # Get method docstring if available
                        docstring = ast.get_docstring(item)
                        class_methods.append({
                            'name': item.name,
                            'docstring': docstring,
                            'line': item.lineno
                        })
                
                # Get class docstring if available
                class_docstring = ast.get_docstring(node)
                test_classes.append({
                    'name': node.name,
                    'docstring': class_docstring,
                    'line': node.lineno,
                    'methods': class_methods
                })
            
            elif isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                # Check if this function is not inside a class
                # We need to check if it's at module level
                if isinstance(node, ast.FunctionDef):
                    # This is a bit tricky with AST, so we'll use a simpler approach
                    # and filter out class methods later
                    docstring = ast.get_docstring(node)
                    standalone_functions.append({
                        'name': node.name,
                        'docstring': docstring,
                        'line': node.lineno
                    })
        
        # Filter out class methods from standalone functions
        # (This is a simple approach - in practice, we'd need more sophisticated parsing)
        class_method_names = set()
        for test_class in test_classes:
            for method in test_class['methods']:
                class_method_names.add(method['name'])
        
        standalone_functions = [f for f in standalone_functions if f['name'] not in class_method_names]
        
        return test_classes, standalone_functions
        
    except Exception as e:
        print(f"  └── Error parsing file: {e}")
        return [], []

def list_all_tests():
    """List all available test files, classes, and test functions"""
    print("Available Tests:")
    print("=" * 80)
    
    test_files = glob.glob("all_tests/test_*.py")
    if not test_files:
        print("No test files found in all_tests/ directory")
        return
    
    total_files = 0
    total_classes = 0
    total_methods = 0
    total_functions = 0
    
    # Initialize collections to store all test data
    all_test_classes = []
    all_standalone_functions = []
    
    for test_file in sorted(test_files):
        total_files += 1
        print(f"\n📁 {test_file}")
        
        # Extract tests using AST parsing
        test_classes, standalone_functions = extract_tests_from_file(test_file)
        
        # Collect all test data for later use
        all_test_classes.extend(test_classes)
        all_standalone_functions.extend(standalone_functions)
        
        # Also get pytest collection for validation
        pytest_tests = []
        try:
            result = subprocess.run([
                "pytest", "--collect-only", "-q", test_file
            ], capture_output=True, text=True)
            
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                pytest_tests = [line.strip() for line in lines if '::' in line and 'test_' in line]
        except Exception as e:
            print(f"  └── Error running pytest collection: {e}")
        
        # Display test classes and their methods
        if test_classes:
            for test_class in test_classes:
                total_classes += 1
                class_name = test_class['name']
                class_doc = test_class['docstring']
                number_of_tests = len(test_class['methods'])
                
                print(f"  ├── 🏛️  {class_name} ({number_of_tests} tests)")
                # if class_doc:
                #     # Show first line of docstring
                #     first_line = class_doc.split('\n')[0].strip()
                #     if first_line:
                #         print(f"  │    💬 {first_line}")
                
                if test_class['methods']:
                    for i, method in enumerate(test_class['methods']):
                        total_methods += 1
                        is_last_method = i == len(test_class['methods']) - 1
                        connector = "└──" if is_last_method else "├──"
                        
                        method_name = method['name']
                        method_doc = method['docstring']
                        
                        print(f"  │   {connector} 🧪 {method_name}")
                        # print(f"  │   {connector} 🧪 {method_name} (line {method['line']})")
                        # if method_doc:
                        #     # Show first line of docstring
                        #     first_line = method_doc.split('\n')[0].strip()
                        #     if first_line:
                        #         indent = "  │       " if not is_last_method else "      "
                        #         print(f"{indent}💬 {first_line}")
                else:
                    print(f"  │    └── (no test methods found)")
        
        # Display standalone test functions
        if standalone_functions:
            for i, func in enumerate(standalone_functions):
                total_functions += 1
                is_last = i == len(standalone_functions) - 1 and not test_classes
                connector = "└──" if is_last else "├──"
                
                func_name = func['name']
                func_doc = func['docstring']
                
                print(f"  {connector} 🔧 {func_name} (line {func['line']})")
                if func_doc:
                    # Show first line of docstring
                    first_line = func_doc.split('\n')[0].strip()
                    if first_line:
                        indent = "      " if is_last else "  │   "
                        print(f"{indent}💬 {first_line}")
        
        # Show pytest collection count for validation
        pytest_count = len([t for t in pytest_tests if test_file.replace('all_tests/', '') in t])
        if pytest_count > 0:
            print(f"  └── 📊 Pytest found: {pytest_count} test(s)")
        
        if not test_classes and not standalone_functions:
            print(f"  └── ⚠️  No test classes or functions found")
    
    # Summary
    print("\n" + "=" * 80)
    print("📈 SUMMARY")
    print("=" * 80)
    print(f"📁 Test Files: {total_files}")
    print(f"🏛️  Test Classes: {total_classes}")
    print(f"🧪 Test Methods (in classes): {total_methods}")
    print(f"🔧 Standalone Test Functions: {total_functions}")
    print(f"🎯 Total Test Cases: {total_methods + total_functions}")
    
    # Show example usage - now using collected data
    if total_files > 0:
        print(f"\n💡 USAGE EXAMPLES")
        print("=" * 80)
        print("# Run all tests:")
        print("python tests/run_test.py --run")
        print("\n# Run specific test file:")
        print(f"python tests/run_test.py --run --test {Path(test_files[0]).name}")
        
        # Now all_test_classes is guaranteed to be defined
        if all_test_classes:
            example_class = all_test_classes[0]['name']
            example_file = Path(test_files[0]).name
            print(f"\n# Run specific test class:")
            print(f"python tests/run_test.py --run --test {example_class}")
            
            if all_test_classes[0]['methods']:
                example_method = all_test_classes[0]['methods'][0]['name']
                print(f"\n# Run specific test method:")
                print(f"python tests/run_test.py --run --test {example_method}")
                print(f"# OR with full path:")
                print(f"python tests/run_test.py --run --test \"{example_file}::{example_class}::{example_method}\"")
        
        if all_standalone_functions:
            example_function = all_standalone_functions[0]['name']
            print(f"\n# Run standalone test function:")
            print(f"python tests/run_test.py --run --test {example_function}")

def list_tests_detailed():
    """List tests with even more detail including parameters and fixtures"""
    print("Detailed Test Analysis:")
    print("=" * 80)
    
    test_files = glob.glob("all_tests/test_*.py")
    if not test_files:
        print("No test files found in all_tests/ directory")
        return
    
    for test_file in sorted(test_files):
        print(f"\n📁 {test_file}")
        
        try:
            # Use pytest to get detailed collection info
            result = subprocess.run([
                "pytest", "--collect-only", "-v", test_file
            ], capture_output=True, text=True)
            
            if result.stdout:
                lines = result.stdout.split('\n')
                current_class = None
                
                for line in lines:
                    line = line.strip()
                    
                    # Parse pytest collection output
                    if '<Class ' in line and 'Test' in line:
                        # Extract class name
                        class_match = line.split('<Class ')[1].split('>')[0] if '<Class ' in line else None
                        if class_match:
                            current_class = class_match
                            print(f"  ├── 🏛️  {current_class}")
                    
                    elif '<Function ' in line and 'test_' in line:
                        # Extract function name
                        func_match = line.split('<Function ')[1].split('>')[0] if '<Function ' in line else None
                        if func_match:
                            if current_class:
                                print(f"  │   ├── 🧪 {func_match}")
                            else:
                                print(f"  ├── 🔧 {func_match}")
                    
                    elif 'parametrize' in line.lower() or '[' in line and ']' in line:
                        # Parametrized test
                        print(f"  │   │   └── 📊 Parametrized test")
        
        except Exception as e:
            print(f"  └── Error analyzing file: {e}")

def create_report_folder():
    """Create a timestamped report folder and return the path"""
    # Create human-readable timestamp folder
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_folder = Path("reports") / f"test_run_{timestamp}"
    report_folder.mkdir(parents=True, exist_ok=True)
    return report_folder

def generate_reports_only():
    """Generate reports from existing coverage data"""
    print("Generating reports from existing coverage data...")
    
    # Check if coverage data exists
    if not Path(".coverage").exists():
        print("❌ No coverage data found. Run tests first to generate coverage data.")
        return False
    
    # Create report folder
    report_folder = create_report_folder()
    
    try:
        # Generate HTML coverage report
        subprocess.run([
            "coverage", "html", 
            f"--directory={report_folder}/coverage_html"
        ], check=True)
        
        # Generate XML coverage report
        subprocess.run([
            "coverage", "xml", 
            f"--output={report_folder}/coverage.xml"
        ], check=True)
        
        # Generate JSON coverage report
        subprocess.run([
            "coverage", "json", 
            f"--output={report_folder}/coverage.json"
        ], check=True)
        
        print("✅ Reports generated successfully!")
        print(f"📊 Reports location: {report_folder.absolute()}")
        print(f"   📁 Folder: {report_folder.name}")
        print(f"   🌐 HTML Coverage: {report_folder}/coverage_html/index.html")
        print(f"   📄 XML Coverage: {report_folder}/coverage.xml")
        print(f"   📋 JSON Coverage: {report_folder}/coverage.json")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error generating reports: {e}")
        return False

def run_tests(test_target=None, with_reports=False):
    """Run tests with optional report generation"""
    
    # Initialize report_folder to avoid "possibly unbound" warnings
    report_folder = None
    
    # Create report folder if generating reports
    if with_reports:
        report_folder = create_report_folder()
        print(f"📁 Reports will be saved to: {report_folder.name}")
    
    # Build test command - start with just pytest
    # Most options come from pyproject.toml [tool.pytest.ini_options]
    cmd = ["pytest"]
    
    # Override default report locations if generating custom reports
    if with_reports:
        cmd.extend([
            # Override the default locations from pyproject.toml
            f"--cov-report=html:{report_folder}/coverage_html",
            f"--cov-report=xml:{report_folder}/coverage.xml", 
            f"--cov-report=json:{report_folder}/coverage.json",
            f"--junit-xml={report_folder}/junit.xml",
            f"--html={report_folder}/test_report.html",
            "--self-contained-html"
        ])
    else:
        # For no-reports mode, disable file outputs but keep terminal output
        cmd.extend([
            "--cov-report=term-missing",  # Keep terminal output
            "--cov-report=",              # Disable other reports
        ])
    
    # Add test target (specific test or all tests)
    if test_target:
        if test_target.endswith('.py'):
            # Specific test file
            cmd.append(f"all_tests/{test_target}")
        elif '::' in test_target:
            # Specific test function with full path
            cmd.append(f"all_tests/{test_target}")
        else:
            # Test function name pattern
            cmd.extend(["-k", test_target])
    else:
        # Run all tests
        cmd.append("all_tests/")
    
    print("🚀 Running tests...")
    if with_reports:
        print("📊 Reports will be generated after test execution")
    else:
        print("📊 Running tests without file reports (terminal output only)")
    print(f"📝 Command: {' '.join(cmd)}")
    print("=" * 60)
    
    # Run tests
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Print results
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS")
    print("=" * 50)
    print(result.stdout)
    
    if result.stderr:
        print("\n⚠️  ERRORS/WARNINGS:")
        print(result.stderr)
    
    # Print report locations if generated
    if with_reports:
        print(f"\n📁 All reports saved in: {report_folder.absolute()}") # type: ignore
        print(f"  📁 Report folder: {report_folder.name}") # type: ignore
        print("   📊 Generated files:")
        print(f"      🌐 HTML Coverage: coverage_html/index.html")
        print(f"      📄 XML Coverage: coverage.xml")
        print(f"      📋 JSON Coverage: coverage.json")
        print(f"      🧪 JUnit XML: junit.xml")
        print(f"      📋 HTML Test Report: test_report.html")
        
        # Create summary report
        create_summary_file(report_folder, test_target, result.returncode)
    
    # Print summary
    if result.returncode == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code: {result.returncode}")
    
    return result.returncode

def create_summary_file(report_folder, test_target, exit_code):
    """Create a summary file in the report folder"""
    summary_file = report_folder / "README.md"
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_scope = test_target if test_target else "All tests"
    status = "PASSED" if exit_code == 0 else "FAILED"
    
    summary_content = f"""# Test Run Summary

## Test Execution Details
- **Date & Time**: {timestamp}
- **Test Scope**: {test_scope}
- **Status**: {status}
- **Exit Code**: {exit_code}

## Generated Reports

### Coverage Reports
- **HTML Coverage**: Open `coverage_html/index.html` in your browser for interactive coverage report
- **XML Coverage**: `coverage.xml` - Machine-readable coverage data for CI/CD
- **JSON Coverage**: `coverage.json` - Structured coverage data

### Test Reports  
- **HTML Test Report**: `test_report.html` - Detailed test execution report
- **JUnit XML**: `junit.xml` - Standard test results format for CI/CD

## Quick Access
- **View Coverage**: Open `coverage_html/index.html`
- **View Test Results**: Open `test_report.html`

---
*Generated by HostCart Test Runner*
"""
    
    with open(summary_file, 'w') as f:
        f.write(summary_content)

def list_recent_reports():
    """List recent test report folders"""
    reports_dir = Path("reports")
    if not reports_dir.exists():
        print("No reports directory found.")
        return
    
    # Get all test run folders
    test_folders = [f for f in reports_dir.iterdir() if f.is_dir() and f.name.startswith("test_run_")]
    
    if not test_folders:
        print("No test report folders found.")
        return
    
    # Sort by creation time (newest first)
    test_folders.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    print("Recent Test Reports:")
    print("=" * 50)
    
    for i, folder in enumerate(test_folders[:10]):  # Show last 10 runs
        # Parse timestamp from folder name
        folder_time = folder.name.replace("test_run_", "").replace("_", " ").replace("-", "/", 2).replace("-", ":")
        
        # Check if summary file exists
        summary_file = folder / "README.md"
        status = "📋" if summary_file.exists() else "📁"
        
        print(f"{i+1:2d}. {status} {folder.name}")
        print(f"    📅 {folder_time}")
        print(f"    📂 {folder.absolute()}")
        
        if summary_file.exists():
            try:
                with open(summary_file, 'r') as f:
                    content = f.read()
                    if "✅ PASSED" in content:
                        print("    ✅ Tests passed")
                    elif "❌ FAILED" in content:
                        print("    ❌ Tests failed")
            except:
                pass
        print()

def main():
    """Main function with argument parsing"""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner with reporting for HostCart",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                                    # List all available tests with details
  %(prog)s --list-detailed                           # List tests with even more detail
  %(prog)s --list-reports                            # List recent test report folders
  %(prog)s --run                                     # Run all tests (no reports)
  %(prog)s --run --reports                           # Run all tests with reports
  %(prog)s --run --test test_config.py               # Run specific test file (no reports)
  %(prog)s --run --test TestConfigLoader             # Run specific test class
  %(prog)s --run --test test_singleton_pattern --reports  # Run specific test with reports
  %(prog)s --generate                                # Generate reports from existing coverage data

Report Structure:
  reports/
  └── test_run_2024-01-15_14-30-25/
      ├── README.md              # Summary of test run
      ├── coverage_html/         # Interactive HTML coverage
      ├── coverage.xml           # XML coverage data
      ├── coverage.json          # JSON coverage data
      ├── junit.xml              # JUnit test results
      └── test_report.html       # HTML test report
        """
    )
    
    # Main action group
    action_group = parser.add_mutually_exclusive_group(required=True)
    
    action_group.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available test files, classes, and functions with details"
    )
    
    action_group.add_argument(
        "--list-detailed",
        action="store_true",
        help="List tests with detailed analysis including parameters and fixtures"
    )
    
    action_group.add_argument(
        "--list-reports",
        action="store_true",
        help="List recent test report folders"
    )
    
    action_group.add_argument(
        "--run", "-r",
        action="store_true",
        help="Run tests (use --test to specify which tests, --reports to generate reports)"
    )
    
    action_group.add_argument(
        "--generate", "-g",
        action="store_true",
        help="Generate reports from existing coverage data (no test execution)"
    )
    
    # Test specification (only used with --run)
    parser.add_argument(
        "--test", "-t",
        type=str,
        help="Specify which test to run: test file (test_config.py), test class (TestConfigLoader), test function (test_singleton_pattern), or full path (test_config.py::TestClass::test_method)"
    )
    
    # Report generation flag (only used with --run)
    parser.add_argument(
        "--reports",
        action="store_true",
        help="Generate comprehensive reports in timestamped folder"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.test and not args.run:
        parser.error("--test can only be used with --run")
    
    if args.reports and not args.run:
        parser.error("--reports can only be used with --run")
    
    # Validate all_tests directory exists (except for list-reports)
    if not args.list_reports and not Path("all_tests").exists():
        print("❌ Error: 'all_tests' directory not found!")
        print("   Please ensure you're running this script from the correct directory.")
        sys.exit(1)
    
    # Execute based on arguments
    try:
        if args.list:
            list_all_tests()
            
        elif args.list_detailed:
            list_tests_detailed()
            
        elif args.list_reports:
            list_recent_reports()
            
        elif args.run:
            exit_code = run_tests(
                test_target=args.test,
                with_reports=args.reports
            )
            sys.exit(exit_code)
            
        elif args.generate:
            success = generate_reports_only()
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
