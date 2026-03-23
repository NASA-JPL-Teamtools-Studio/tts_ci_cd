#!/usr/bin/env python3
"""
Example of extending the DevSetup class for a downstream project.

This example shows how to:
1. Create a custom setup class that extends DevSetup
2. Override methods to customize behavior
3. Add custom functionality
4. Load and reference repositories from the base manifest
"""

import argparse
import subprocess
import os
import shutil
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
import sys

# Import the base DevSetup class
from tts_ci_cd.dev_setup import DevSetup


class DemoSatDev(DevSetup):
    """Custom developer setup for a downstream project."""
    
    def __init__(self, manifest_path: Optional[Path] = None):
        """Initialize with custom manifest and load the base manifest."""
        # First load the base manifest
        base_manifest_path = Path(__file__).parent.joinpath("support_files/dev_setup.yaml")
        
        # Initialize with the base manifest first
        super().__init__(base_manifest_path)
        
        # Then load the DemoSat-specific manifest
        if manifest_path is None:
            manifest_path = Path(__file__).parent.joinpath("support_files/demosat_setup.yaml")
            
        self.load_additional_manifest(manifest_path)
        
        # Keep track of loaded manifests
        if 'manifest_files' not in self.config:
            self.config['manifest_files'] = []
        self.config['manifest_files'].append(str(base_manifest_path))
        self.config['manifest_files'].append(str(manifest_path))
        
        # Add any custom initialization here
        self.custom_config = self.config.get('custom_config', {})
        
        # Debug info
        print(f"\n📚 Loaded manifests: {self.config['manifest_files']}")
        print(f"📦 Available repositories: {list(self._all_repos.keys())}")
        
        # Print the repository groups
        groups = {}
        for repo_name, group_name in self._group_cache.items():
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(repo_name)
            
        print("\n📂 Repository groups:")
        for group_name, repos in groups.items():
            print(f"  - {group_name}: {', '.join(repos)}")
    
    def get_repo_info(self, target: str) -> Optional[Dict[str, Any]]:
        """Get repository info from any group in the manifest.
        
        This override handles cross-manifest repository references by looking up
        repositories with different names but the same repo_path.
        
        Args:
            target: Name of the repository
            
        Returns:
            Repository information or None if not found
        """
        # First try the standard lookup
        repo_info = super().get_repo_info(target)
        if repo_info:
            return repo_info
        
        # If not found, check if this is a cross-manifest reference
        # For example, 'tts_dictionary_interface' in the base manifest might be
        # referenced as a dependency in the demosat manifest
        for repo_name, repo_data in self._all_repos.items():
            # Skip the target itself to avoid infinite recursion
            if repo_name == target:
                continue
                
            # Check if this repo has the same path as what we're looking for
            if repo_name.endswith(target) or target.endswith(repo_name):
                print(f"Cross-manifest match: '{target}' -> '{repo_name}'")
                return repo_data
        
        return None
    
    def _run_install_command(self, target_path: Path, extra_index_urls: Optional[List[str]] = None,
                           trusted_hosts: Optional[List[str]] = None) -> None:
        """Override the install command to add custom behavior.
        
        This example adds a pre-install step and modifies the pip command.
        
        Args:
            target_path: Path to the repository
            extra_index_urls: Additional pip index URLs
            trusted_hosts: Hosts to trust even without valid SSL certificates
        """
        # Example: Run a pre-install step
        print(f"Running custom pre-install steps for {target_path}")
        
        # Example: Check if there's a setup.py or pyproject.toml
        has_setup_py = (target_path / "setup.py").exists()
        has_pyproject = (target_path / "pyproject.toml").exists()
        
        if not (has_setup_py or has_pyproject):
            print(f"⚠️ Warning: No setup.py or pyproject.toml found in {target_path}")
            return
        
        # Call the base class implementation with our modifications
        pip_cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
        
        # Add any extra index URLs if provided
        if extra_index_urls:
            for url in extra_index_urls:
                pip_cmd.extend(["--extra-index-url", url])
        
        # Add any trusted hosts if provided
        if trusted_hosts:
            for host in trusted_hosts:
                pip_cmd.extend(["--trusted-host", host])
                
        # Skip dependencies if specified in the custom config
        if self.custom_config.get('skip_dependencies', False):
            pip_cmd.append("--no-deps")
        
        # Add any custom pip options from our config
        if 'pip_options' in self.custom_config:
            for option in self.custom_config['pip_options']:
                pip_cmd.append(option)
        
        subprocess.run(
            pip_cmd,
            cwd=target_path,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
    
    def run_tests(self, target_path: Path, html_report: bool = True) -> Dict[str, Any]:
        """Run unit tests for a repository and generate a report.
        
        Args:
            target_path: Path to the repository
            html_report: Whether to generate an HTML report
            
        Returns:
            Dictionary with test results information
        """
        # Try to find the test directory
        # First check the standard path: repo/src/repo_name/test
        test_dir = target_path / "src" / target_path.name / "test"
        
        # If that doesn't exist, try some alternatives
        if not test_dir.exists():
            # Try repo/tests
            alt_test_dir = target_path / "tests"
            if alt_test_dir.exists():
                test_dir = alt_test_dir
            else:
                # Try repo/test
                alt_test_dir = target_path / "test"
                if alt_test_dir.exists():
                    test_dir = alt_test_dir
        
        if not test_dir.exists():
            print(f"⚠️ No test directory found for {target_path.name}")
            return {"success": False, "reason": "no_test_dir"}
            
        print(f"🧪 Running tests for {target_path.name}...")
        
        # Create a directory for test reports if it doesn't exist
        reports_dir = Path(target_path.parent.parent) / "test_reports"
        reports_dir.mkdir(exist_ok=True)
        
        # Generate a timestamp for the report filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_name = f"{target_path.name}_{timestamp}"
        
        # Build the pytest command
        pytest_cmd = [sys.executable, "-m", "pytest", str(test_dir)]
        
        # Add HTML report option if requested
        html_report_path = None
        if html_report:
            html_report_path = reports_dir / f"{report_name}.html"
            pytest_cmd.extend(["--html", str(html_report_path), "--self-contained-html"])
        
        # Add JUnit XML report for programmatic access
        xml_report_path = reports_dir / f"{report_name}.xml"
        pytest_cmd.extend(["--junitxml", str(xml_report_path)])
        
        try:
            # Run pytest
            result = subprocess.run(
                pytest_cmd,
                cwd=target_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True  # equivalent to text=True in Python 3.7+
            )
            
            success = result.returncode == 0
            status = "✅ Tests passed" if success else "❌ Tests failed"
            print(f"{status} for {target_path.name}")
            
            # Create a summary file with basic info
            summary_path = reports_dir / f"{report_name}_summary.txt"
            with open(summary_path, 'w') as f:
                f.write(f"Test results for {target_path.name}\n")
                f.write(f"Status: {'PASSED' if success else 'FAILED'}\n")
                f.write(f"Return code: {result.returncode}\n")
                f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n\n")
                f.write("=== STDOUT ===\n")
                f.write(result.stdout)
                f.write("\n=== STDERR ===\n")
                f.write(result.stderr)
            
            return {
                "success": success,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "html_report": str(html_report_path) if html_report else None,
                "xml_report": str(xml_report_path),
                "summary": str(summary_path)
            }
            
        except Exception as e:
            print(f"❌ Error running tests for {target_path.name}: {str(e)}")
            return {"success": False, "reason": "exception", "error": str(e)}
    
    def post_install_hook(self, workspace_path: Path, run_tests: bool = True, installed_repos: Optional[List[str]] = None) -> None:
        """Custom post-installation hook.
        
        Args:
            workspace_path: Path to the workspace directory
            run_tests: Whether to run tests
            installed_repos: List of repositories that were installed
        """
        print("\n🔧 Running post-install configuration...")
        
        # Example: Create a .env file with configuration
        env_file = workspace_path / ".env"
        if not env_file.exists():
            with open(env_file, 'w') as f:
                f.write("# Generated by DemoSatDevSetup\n")
                f.write("PYTHONPATH=.\n")
                
                # Add any custom environment variables from config
                if 'env_vars' in self.custom_config:
                    for key, value in self.custom_config['env_vars'].items():
                        f.write(f"{key}={value}\n")
            
            print(f"✅ Created environment file at {env_file}")
        
        # Run tests if requested
        if run_tests:
            self.run_all_tests(workspace_path, installed_repos)
    
    def run_all_tests(self, workspace_path: Path, installed_repos: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run tests for all installed repositories.
        
        Args:
            workspace_path: Path to the workspace directory
            installed_repos: Optional list of repositories that were installed
            
        Returns:
            Dictionary with test results for each repository
        """
        print("\n🧪 Running tests for installed repositories...")
        
        results = {}
        
        # Create a directory for the combined report
        reports_dir = workspace_path / "test_reports"
        reports_dir.mkdir(exist_ok=True)
        
        # If we have a list of installed repositories, only test those
        if installed_repos:
            for repo_name in installed_repos:
                # Find the repository in the workspace
                group_name = self.find_repo_group(repo_name)
                if not group_name:
                    print(f"\n⚠️ Warning: Could not find group for repository '{repo_name}'")
                    continue
                
                repo_path = workspace_path / group_name / repo_name
                if not repo_path.exists() or not repo_path.is_dir():
                    print(f"\n⚠️ Warning: Repository directory not found: {repo_path}")
                    continue
                
                # Run tests for this repository
                print(f"\n🧪 Testing {group_name}/{repo_name}...")
                results[repo_name] = self.run_tests(repo_path)
        else:
            # No specific repositories provided, use manifest data
            print("\n⚠️ No specific repositories provided for testing.")
            print("Using repositories defined in the manifest...")
            
            # Get all repositories from the manifest
            for repo_name, repo_info in self._all_repos.items():
                group_name = self.find_repo_group(repo_name)
                if not group_name:
                    continue
                    
                repo_path = workspace_path / group_name / repo_name
                if not repo_path.exists() or not repo_path.is_dir():
                    continue
                
                # Run tests for this repository
                print(f"\n🧪 Testing {group_name}/{repo_name}...")
                results[repo_name] = self.run_tests(repo_path)
        
        # Create a combined report
        self._create_combined_report(results, reports_dir)
        
        return results
    
    def _create_combined_report(self, results: Dict[str, Any], reports_dir: Path) -> None:
        """Create a combined report of all test results.
        
        Args:
            results: Dictionary with test results for each repository
            reports_dir: Directory to save the report
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = reports_dir / f"combined_report_{timestamp}.html"
        
        # Count successes and failures
        total = len(results)
        passed = sum(1 for r in results.values() if r.get("success", False))
        failed = total - passed
        
        with open(report_path, 'w') as f:
            f.write("<!DOCTYPE html>\n")
            f.write("<html>\n")
            f.write("<head>\n")
            f.write("  <title>Combined Test Report</title>\n")
            f.write("  <style>\n")
            f.write("    body { font-family: Arial, sans-serif; margin: 20px; }\n")
            f.write("    h1 { color: #333; }\n")
            f.write("    .summary { margin: 20px 0; padding: 10px; background-color: #f5f5f5; border-radius: 5px; }\n")
            f.write("    .passed { color: green; }\n")
            f.write("    .failed { color: red; }\n")
            f.write("    table { border-collapse: collapse; width: 100%; }\n")
            f.write("    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n")
            f.write("    th { background-color: #f2f2f2; }\n")
            f.write("    tr:nth-child(even) { background-color: #f9f9f9; }\n")
            f.write("  </style>\n")
            f.write("</head>\n")
            f.write("<body>\n")
            f.write("  <h1>Combined Test Report</h1>\n")
            f.write("  <div class='summary'>\n")
            f.write(f"    <p>Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>\n")
            f.write(f"    <p>Total repositories: {total}</p>\n")
            f.write(f"    <p class='passed'>Passed: {passed}</p>\n")
            f.write(f"    <p class='failed'>Failed: {failed}</p>\n")
            f.write("  </div>\n")
            f.write("  <table>\n")
            f.write("    <tr>\n")
            f.write("      <th>Repository</th>\n")
            f.write("      <th>Status</th>\n")
            f.write("      <th>Report</th>\n")
            f.write("    </tr>\n")
            
            # Add a row for each repository
            for repo_name, result in results.items():
                status = "PASSED" if result.get("success", False) else "FAILED"
                status_class = "passed" if result.get("success", False) else "failed"
                html_report = result.get("html_report", "")
                html_link = f"<a href='{html_report}'>View Report</a>" if html_report else "No report"
                
                f.write("    <tr>\n")
                f.write(f"      <td>{repo_name}</td>\n")
                f.write(f"      <td class='{status_class}'>{status}</td>\n")
                f.write(f"      <td>{html_link}</td>\n")
                f.write("    </tr>\n")
            
            f.write("  </table>\n")
            f.write("</body>\n")
            f.write("</html>\n")
        
        print(f"\n📊 Combined test report created at: {report_path}")


def main():
    """Main entry point for the custom setup tool."""
    parser = argparse.ArgumentParser(
        description="DemoSat Developer Setup Tool",
        epilog="""Examples:
  # Install all packages
  tts-demosat-dev-setup --all
  
  # Install specific packages from the base manifest
  tts-demosat-dev-setup --targets tts_utilities tts_dictionary_interface
  
  # Use trusted hosts for pip (for hosts without valid SSL certificates)
  tts-demosat-dev-setup --targets tts_utilities --trusted-host pypi.internal.company.com
  
  # Run tests for installed packages
  tts-demosat-dev-setup --targets tts_utilities --run-tests
  """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Target selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help="Install ALL repositories")
    group.add_argument('--targets', dest='targets', nargs='+', help="Specific repository(s) to install")
    
    # Workspace selection
    parser.add_argument('-w', '--workspace', default=".", help="Target directory (default: current)")
    
    # Protocol selection
    parser.add_argument('--protocol', choices=['ssh', 'https'], default='ssh', 
                        help="Git clone protocol (default: ssh)")
    
    # Extra index URLs for pip
    parser.add_argument('--extra-index-url', action='append', dest='extra_index_urls',
                       help="Additional package index URL(s) for pip (can be used multiple times)")
    
    # Trusted hosts for pip
    parser.add_argument('--trusted-host', action='append', dest='trusted_hosts',
                       help="Mark this host as trusted, even without valid SSL certificate (can be used multiple times)")
    
    # Test options
    parser.add_argument('--run-tests', action='store_true', default=False,
                      help="Run tests for each repository after installation")
    parser.add_argument('--no-html-reports', action='store_false', dest='html_reports', default=True,
                      help="Disable HTML test reports (requires pytest-html)")

    args = parser.parse_args()
    
    # Initialize the custom setup
    setup = DemoSatDev()
    
    # Build the installation plan
    final_plan = setup.build_plan(
        targets=args.targets if not args.all else None,
        install_all=args.all
    )

    print(f"Build Plan: {final_plan}")
    
    # Combine command-line and manifest extra index URLs (command-line takes precedence)
    extra_index_urls = args.extra_index_urls or []
    if not extra_index_urls and setup.extra_index_urls:
        print("Using extra index URLs from manifest file")
        extra_index_urls = setup.extra_index_urls
    
    # Execute the installation
    setup.clone_and_install(final_plan, args.workspace, args.protocol, extra_index_urls, args.trusted_hosts)
    
    # Run our custom post-install hook with test option and pass the installed repositories
    setup.post_install_hook(
        Path(args.workspace).resolve(), 
        run_tests=args.run_tests,
        installed_repos=final_plan
    )
    
    print("\n✨ All Done!")


if __name__ == "__main__":    
    main()
