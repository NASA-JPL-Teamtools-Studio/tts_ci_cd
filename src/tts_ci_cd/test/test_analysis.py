"""Behavioral tests for the repository-analysis seam."""

import json
from pathlib import Path

import pytest

from tts_ci_cd.ctx.analysis import analyze_repository, render_markdown


@pytest.mark.unreviewed_ai
class TestRepositoryAnalysis:
    """Verify the public repository-analysis result contract."""

    def test_returns_versioned_result_with_stable_json(self, tmp_path: Path) -> None:
        """A repository analysis exposes stable scope, metrics, and findings."""
        (tmp_path / "README.md").write_text("# Example\n")
        (tmp_path / "src.py").write_text("print('ok')\n")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_src.py").write_text("def test_ok(): pass\n")

        result = analyze_repository(
            tmp_path,
            standards_revision="documentation-maintenance-v1",
            resources={"standards": "teamtools_documentation"},
        )

        assert result.version == "1.0"
        assert result.scope == str(tmp_path.resolve())
        assert result.standards_revision == "documentation-maintenance-v1"
        assert result.metrics == {
            "files": 3,
            "markdown_files": 1,
            "python_files": 2,
            "test_files": 1,
        }
        assert result.findings == ()

        payload = json.loads(result.to_json())
        assert payload == {
            "findings": [],
            "metrics": {
                "files": 3,
                "markdown_files": 1,
                "python_files": 2,
                "test_files": 1,
            },
            "scope": str(tmp_path.resolve()),
            "standards_revision": "documentation-maintenance-v1",
            "version": "1.0",
        }
        assert result.to_json() == result.to_json()

    def test_markdown_report_is_a_cli_facing_integration(self, tmp_path: Path) -> None:
        """The result can be rendered without exposing analyzer internals."""
        result = analyze_repository(tmp_path, standards_revision="standard-v1")

        report = render_markdown(result)

        assert "# Repository analysis" in report
        assert f"- Scope: `{tmp_path.resolve()}`" in report
        assert "- Standards revision: `standard-v1`" in report
        assert "## Metrics" in report
        assert "## Findings" in report
        assert "No findings." in report
