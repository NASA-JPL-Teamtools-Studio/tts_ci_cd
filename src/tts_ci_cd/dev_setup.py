import argparse
import subprocess
import sys
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

# Import the base RepoManager class
from tts_ci_cd.repo_manager import RepoManager, RepoInfo


class DevSetup(RepoManager):
    """Base class for developer setup tools.
    
    This class provides the core functionality for cloning and installing repositories
    from YAML manifest files. It can be extended by downstream projects to customize
    behavior or add additional features.
    
    Extends RepoManager to leverage common repository management functionality.
    """
    
    def __init__(self, manifest_path: Optional[Path] = None):
        """Initialize the DevSetup instance.
        
        Args:
            manifest_path: Path to the manifest YAML file. If None, uses the default path.
        """
        # Initialize the base class
        super().__init__(manifest_path)
        
        # For backward compatibility, maintain _all_repos dictionary
        self._all_repos = {}  
        for repo_name, repo_info in self.repos.items():
            repo_data = {
                'repo_path': repo_info.repo_path,
                'branch': repo_info.branch,
                'dependencies': repo_info.dependencies
            }
            self._all_repos[repo_name] = repo_data
    
    def load_additional_manifest(self, manifest_path: Path) -> None:
        """Load an additional manifest file and merge it with the current configuration.
        
        This allows downstream projects to reference repositories defined in the base manifest.
        
        Args:
            manifest_path: Path to the additional manifest file
        """
        # Use the base class method to merge configs
        self.merge_config(manifest_path)
        
        # Update the backward-compatibility _all_repos dictionary
        self._all_repos = {}
        for repo_name, repo_info in self.repos.items():
            repo_data = {
                'repo_path': repo_info.repo_path,
                'branch': repo_info.branch,
                'dependencies': repo_info.dependencies
            }
            self._all_repos[repo_name] = repo_data
    
    def find_repo_group(self, target: str) -> Optional[str]:
        """Find which group a repository belongs to in the manifest.
        
        Args:
            target: Name of the repository to find
            
        Returns:
            Group name or None if not found
        """
        return self._group_cache.get(target)
    
    def get_repo_info(self, target: str) -> Optional[Dict[str, Any]]:
        """Get repository info from any group in the manifest.
        
        This method maintains backward compatibility with old code that expects
        a dictionary return type rather than a RepoInfo object.
        
        Args:
            target: Name of the repository
            
        Returns:
            Repository information dictionary or None if not found
        """
        # Use the new method but convert RepoInfo to dict for backward compatibility
        repo_info = super().get_repo_info(target)
        if repo_info:
            return {
                'repo_path': repo_info.repo_path,
                'branch': repo_info.branch,
                'dependencies': repo_info.dependencies
            }
        return None
    
    def clone_and_install(self, targets: List[str], workspace_dir: str, protocol: str, 
                         extra_index_urls: Optional[List[str]] = None,
                         trusted_hosts: Optional[List[str]] = None) -> None:
        """Clone and install the specified repositories.
        
        Args:
            targets: List of repository names to install
            workspace_dir: Directory to clone repositories into
            protocol: Git protocol to use ('ssh' or 'https')
            extra_index_urls: Additional pip index URLs
            trusted_hosts: Hosts to trust even without valid SSL certificates
        """
        workspace_path = Path(workspace_dir).resolve()
        workspace_path.mkdir(exist_ok=True, parents=True)

        print(f"\n🚀 Starting setup using {protocol.upper()} in: {workspace_path}")
        
        if extra_index_urls:
            print("\n📦 Using extra index URLs:")
            for url in extra_index_urls:
                print(f"   - {url}")
        
        if trusted_hosts:
            print("\n🔒 Using trusted hosts:")
            for host in trusted_hosts:
                print(f"   - {host}")
        print("\n")

        for lib_name in targets:
            # Get the RepoInfo object using the base class method
            repo_info_obj = super().get_repo_info(lib_name)
            if not repo_info_obj:
                print(f"❌ Error: Repository '{lib_name}' not found in any group.")
                continue
                
            # Get the group name from the RepoInfo object
            group_name = repo_info_obj.group
            
            # Use the clone_repo method from the base class which handles cloning/updating
            try:
                target_path = self.clone_repo(repo_info_obj, workspace_path, protocol)
                print(f"[{group_name}/{lib_name}] Repository ready at {target_path}")

                # 2. INSTALL
                print(f"[{group_name}/{lib_name}] Installing editable...")
                try:
                    self._run_install_command(target_path, extra_index_urls, trusted_hosts)
                    print(f"✅ {group_name}/{lib_name} ready.")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to install {group_name}/{lib_name}.")
                    print(e.stderr.decode())
            except Exception as e:
                print(f"❌ Failed to clone/update {group_name}/{lib_name}.")
                print(str(e))
                continue
    
    def _run_clone_command(self, git_url: str, branch: str, target_path: Path) -> None:
        """Run the git clone command.
        
        This method can be overridden by subclasses to customize the clone process.
        Note: This method is kept for backward compatibility but is no longer used directly
        since cloning is now handled by the RepoManager.clone_repo method.
        
        Args:
            git_url: Git URL to clone from
            branch: Branch to clone
            target_path: Path to clone into
            
        Raises:
            subprocess.CalledProcessError: If the command fails
        """
        # For backward compatibility only - this method is no longer called directly
        subprocess.run(
            ["git", "clone", "-b", branch, git_url, str(target_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    def _run_install_command(self, target_path: Path, extra_index_urls: Optional[List[str]] = None, 
                           trusted_hosts: Optional[List[str]] = None) -> None:
        """Run the pip install command.
        
        This method can be overridden by subclasses to customize the installation process.
        
        Args:
            target_path: Path to the repository
            extra_index_urls: Additional pip index URLs
            trusted_hosts: Hosts to trust even without valid SSL certificates
            
        Raises:
            subprocess.CalledProcessError: If the command fails
        """
        pip_cmd = [sys.executable, "-m", "pip", "install", "-e", "."]
        
        # Add any extra index URLs if provided
        if extra_index_urls:
            for url in extra_index_urls:
                pip_cmd.extend(["--extra-index-url", url])
                
        # Add any trusted hosts if provided
        if trusted_hosts:
            for host in trusted_hosts:
                pip_cmd.extend(["--trusted-host", host])
        
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
    
    def build_plan(self, targets: Optional[List[str]] = None, install_all: bool = False) -> List[str]:
        """Build the installation plan based on targets or all repositories.
        
        Args:
            targets: List of specific repositories to install
            install_all: Whether to install all repositories
            
        Returns:
            List of repository names in dependency order
            
        Raises:
            SystemExit: If a target is not found or no repositories are found
        """
        final_plan = []

        if install_all:
            # Use all repositories in the repos dictionary from the base class
            for repo_name in self.repos.keys():
                chain = self.get_recursive_dependencies(repo_name)
                for node in chain:
                    if node not in final_plan:
                        final_plan.append(node)
        elif targets:
            for t in targets:
                # Check if the repository exists using the base class method
                if t not in self.repos:
                    print(f"❌ Error: Repository '{t}' not found in manifest.")
                    sys.exit(1)
                chain = self.get_recursive_dependencies(t)
                for node in chain:
                    if node not in final_plan:
                        final_plan.append(node)

        if not final_plan:
            print("No repositories found.")
            sys.exit(1)
            
        return final_plan


def main():
    """Main entry point for the command-line tool."""
    parser = argparse.ArgumentParser(
        description="Developer Setup Tool - Clones repositories into group subdirectories",
        epilog="""Examples:
  # Install all packages using SSH protocol
  python -m tts_ci_cd.dev_setup --all
  
  # Install specific packages using HTTPS and a custom private PyPI mirror
  python -m tts_ci_cd.dev_setup --targets tts_utilities tts_dictionary_interface --protocol https --extra-index-url https://pypi.internal.company.com/simple
  
  # Use multiple index URLs (they will be tried in order)
  python -m tts_ci_cd.dev_setup --targets tts_utilities --extra-index-url https://pypi.internal.company.com/simple --extra-index-url https://pypi.org/simple
  
  # Use trusted hosts for pip (for hosts without valid SSL certificates)
  python -m tts_ci_cd.dev_setup --targets tts_utilities --trusted-host pypi.internal.company.com
  
  # Repositories will be cloned into subdirectories based on their group in the YAML file
  # For example, tts_utilities will be cloned into <workspace>/tts_core/tts_utilities
  
  # Reference additional manifest files
  python -m tts_ci_cd.dev_setup --targets tts_utilities --additional-manifest /path/to/other/manifest.yaml
  
  # Run tests for installed packages
  python -m tts_ci_cd.dev_setup --targets tts_utilities --run-tests
  
  # Run tests without HTML reports (plain text only)
  python -m tts_ci_cd.dev_setup --targets tts_utilities --run-tests --no-html-reports
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
                       
    # Additional manifest files
    parser.add_argument('--additional-manifest', action='append', dest='additional_manifests',
                      help="Additional manifest YAML files to load (can be used multiple times)")
    
    # Test options
    parser.add_argument('--run-tests', action='store_true', default=False,
                      help="Run tests for each repository after installation")
    parser.add_argument('--no-html-reports', action='store_false', dest='html_reports', default=True,
                      help="Disable HTML test reports (requires pytest-html)")

    args = parser.parse_args()
    
    # Initialize the DevSetup instance
    setup = DevSetup()
    
    # Load any additional manifest files
    if args.additional_manifests:
        for manifest_path in args.additional_manifests:
            setup.load_additional_manifest(Path(manifest_path))
    
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
    
    # Run post-install hook if tests are requested
    if hasattr(setup, 'post_install_hook'):
        setup.post_install_hook(
            Path(args.workspace).resolve(),
            run_tests=args.run_tests if hasattr(args, 'run_tests') else False,
            installed_repos=final_plan
        )
    
    print("\n✨ All Done!")


if __name__ == "__main__":
    main()