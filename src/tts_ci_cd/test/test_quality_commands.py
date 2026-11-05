"""Behavioral tests for the standards-aware quality command surface."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.analysis import RepositoryAnalysisResult, analyze_repository
from tts_ci_cd.ctx.cli import app


@pytest.mark.unreviewed_ai
class TestQualityCommands:
    """Verify standards, combined quality, ranking, and strict checks."""

    def test_quality_combines_documentation_and_test_metrics(self, tmp_path: Path) -> None:
        """Combined quality output includes test-quality evidence."""
        (tmp_path / "sample.py").write_text("def public_function():\n    pass\n")

        result = CliRunner().invoke(app, ["quality", str(tmp_path), "--json-output"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert "test_source_files" in payload["metrics"]
        assert any(item["code"] == "testing.coverage.missing" for item in payload["findings"])

    def test_standards_and_coverage_are_versioned_reports(self, tmp_path: Path) -> None:
        """Standards and coverage commands expose stable JSON envelopes."""
        runner = CliRunner()

        standards = runner.invoke(app, ["standards", "--json-output"])
        coverage = runner.invoke(app, ["coverage", str(tmp_path), "--json-output"])

        assert standards.exit_code == 0
        assert coverage.exit_code == 0
        assert json.loads(standards.stdout)["standards_revision"] == "documentation-maintenance-v1"
        assert "coverage_artifact_present" in json.loads(coverage.stdout)["metrics"]

    def test_next_ranks_findings_and_check_has_explicit_strict_mode(self, tmp_path: Path) -> None:
        """Report mode stays diagnostic while strict mode returns failure."""
        runner = CliRunner()

        next_result = runner.invoke(app, ["next", str(tmp_path), "--json-output"])
        report_check = runner.invoke(app, ["check", str(tmp_path), "--json-output"])
        strict_check = runner.invoke(app, ["check", str(tmp_path), "--strict", "--json-output"])

        assert next_result.exit_code == 0
        assert report_check.exit_code == 0
        assert strict_check.exit_code == 1
        next_payload = json.loads(next_result.stdout)
        findings = next_payload["findings"]
        assert findings == sorted(findings, key=lambda item: (item["severity"], item["code"], item["path"] or "", item["line"] or 0))
        assert [item["rank"] for item in next_payload["ranked_findings"]] == list(range(1, len(findings) + 1))

    def test_result_rejects_unsupported_versions_and_empty_revisions(self, tmp_path: Path) -> None:
        """The public result seam rejects invalid contract configuration."""
        with pytest.raises(ValueError):
            RepositoryAnalysisResult(str(tmp_path), "revision", {}, version="9.9")
        with pytest.raises(ValueError):
            analyze_repository(tmp_path, standards_revision="")
