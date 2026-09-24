import argparse
import sys
from pathlib import Path
from typing import List



def parse_test_results(version):
    return "✅", f"https://your-storage-host.com/{version}/tests-report.html", ""

def parse_cov_results(version):
    return "✅", f"https://your-storage-host.com/{version}/coverage.html", " 85%"

def parse_bandit_results(version):
    return "❌", f"https://your-storage-host.com/{version}/bandit.html", " 3 Critical, 1 High, 0 Medium, 0 low"

def parse_pip_audit_results(version):
    return "✅", f"https://your-storage-host.com/{version}/audit.html", " Oll Korrect"

def generate_markdown_table(artifacts_dir: Path, python_versions: List[str]) -> str:
    """Scans the directory and constructs the GitHub Markdown table."""
    # Markdown Header with your note to users
    markdown_lines = [
        "## 🧪 Python CI/CD Results\n",
        "*💡 Click on the individual report names (Tests, Coverage, etc.) to view detailed logs.*\n",
        "| Version | Tests | Coverage | Security | Audit |",
        "| :---  | :---: | :---: | :---: | :---: |",
    ]

    for version in python_versions:
        # Strip any accidental whitespace from the user input strings
        version = version.strip()

        # -------------------------------------------------------------
        # TODO: PLUG IN YOUR LOGIC HERE
        # Use `artifacts_dir` to find files corresponding to `version`.
        # Determine if overall status passed or failed.
        # Generate the URLs pointing to your hosted reports.
        # -------------------------------------------------------------

        # Placeholder boolean logic (replace with your real checks)

        # Dummy URLs (replace these with the actual links your Action builds)
        test_status, test_url, test_message = parse_test_results(version)
        cov_status, cov_url, cov_message = parse_cov_results(version)
        bandit_status, bandit_url, bandit_message = parse_bandit_results(version)
        pip_audit_status, pip_audit_url, pip_audit_message = parse_pip_audit_results(version)

        # Format rows using standard markdown links
        row = (
            f"| **{version}** | "
            f"[{test_message} {test_status}]({test_url}) | "
            f"[{cov_message} {cov_status}]({cov_url}) | "
            f"[{bandit_message} {bandit_status}]({bandit_url}) | "
            f"[{pip_audit_message} {pip_audit_status}]({pip_audit_url}) |"
        )
        markdown_lines.append(row)

    return "\n".join(markdown_lines)


def main():
    """Handles the CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Generate a GitHub PR comment table from CI/CD artifacts."
    )
    
    # Required positional argument
    parser.add_argument(
        "artifacts_dir",
        type=str,
        help="Path to the directory containing the report files.",
    )

    # Optional comma-delimited versions argument
    default_versions = "3.6,3.7,3.8,3.9,3.10,3.11,3.12,3.13,3.14"
    parser.add_argument(
        "--versions",
        type=str,
        default=default_versions,
        help=f"Comma-separated list of Python versions to include (default: {default_versions})",
    )
    
    # Fixed: changed parser.parse_arguments() to parser.parse_args()
    args = parser.parse_args()
    target_dir = Path(args.artifacts_dir)

    if not target_dir.is_dir():
        print(
            f"Error: The path '{target_dir}' does not exist or is not a directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Split the comma-delimited string into a clean list of strings
    version_list = [v.strip() for v in args.versions.split(",") if v.strip()]

    if not version_list:
        print("Error: No valid Python versions provided.", file=sys.stderr)
        sys.exit(1)

    # Generate the table
    markdown_output = generate_markdown_table(target_dir, version_list)

    # Print to stdout so you can easily pipe it to a file or a GH step variable
    print(markdown_output)


if __name__ == "__main__":
    main()