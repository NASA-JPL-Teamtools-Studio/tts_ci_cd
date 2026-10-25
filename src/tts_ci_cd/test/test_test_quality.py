"""Behavioral tests for deterministic test-quality analysis."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.test_quality import TestQualityAnalyzer


@pytest.mark.unreviewed_ai
class TestTestQualityAnalyzer:
    """Verify public test-quality evidence and the CLI result contract."""

    def test_reports_inventory_markers_and_inspection_certification(self, tmp_path: Path) -> None:
        """Test inventory separates source matches, markers, and inspection evidence."""
        source = tmp_path / "src" / "sample.py"
        source.parent.mkdir()
        source.write_text("def calculate(value):\n    return value\n")
        tests = tmp_path / "tests" / "test_sample.py"
        tests.parent.mkdir()
        tests.write_text(
            "import pytest\n"
            "@pytest.mark.unreviewed_ai\n"
            "class TestVisual:\n"
            "    @pytest.mark.inspection\n"
            "    @pytest.mark.xfail\n"
            "    def test_calculate(self):\n        pytest.skip('pending')\n"
        )
        artifact = tmp_path / "test_files" / "sample.html"
        artifact.parent.mkdir()
        artifact.write_text("<html>inspection</html>\n")
        (artifact.with_suffix(".html.sha256")).write_text("approved\n")

        result = TestQualityAnalyzer(tmp_path).analyze()

        assert result.metrics["source_files"] == 1
        assert result.metrics["matched_test_files"] == 1
        assert result.metrics["unreviewed_ai_tests"] == 1
        assert result.metrics["inspection_tests"] == 1
        assert result.metrics["certified_inspection_artifacts"] == 1
        assert result.metrics["skipped_tests"] == 1
        assert result.metrics["xfailed_tests"] == 1
        assert not any(finding.code == "testing.inventory.source_test_missing" for finding in result.findings)

    def test_reports_coverage_artifact_states(self, tmp_path: Path) -> None:
        """Missing, malformed, and readable coverage artifacts are distinct."""
        missing = TestQualityAnalyzer(tmp_path).analyze()
        assert any(finding.code == "testing.coverage.missing" for finding in missing.findings)

        artifact = tmp_path / "coverage.xml"
        artifact.write_text("not xml")
        malformed = TestQualityAnalyzer(tmp_path).analyze()
        assert any(finding.code == "testing.coverage.malformed" for finding in malformed.findings)

        artifact.write_text('<coverage line-rate="0.75" branch-rate="0.50"></coverage>')
        present = TestQualityAnalyzer(tmp_path).analyze()
        assert present.metrics["coverage_line_rate"] == 75.0
        assert present.metrics["coverage_branch_rate"] == 50.0
        assert not any(finding.code == "testing.coverage.missing" for finding in present.findings)

    def test_opt_in_test_command_runs_only_when_requested(self, tmp_path: Path) -> None:
        """An explicit command can run before artifact analysis."""
        result = TestQualityAnalyzer(tmp_path).analyze(
            run_tests=True,
            test_command=[sys.executable, "-c", "print('ok')"],
        )

        assert not any(finding.code == "testing.execution.failed" for finding in result.findings)

    def test_consumes_sqlite_coverage_artifact_without_running_tests(self, tmp_path: Path) -> None:
        """The standard .coverage runtime artifact is consumed as evidence."""
        artifact = tmp_path / ".coverage"
        connection = sqlite3.connect(str(artifact))
        connection.execute("create table file (id integer, path text)")
        connection.execute("create table line_bits (file_id integer, numbits integer, bits blob)")
        connection.commit()
        connection.close()

        result = TestQualityAnalyzer(tmp_path).analyze()

        assert result.metrics["coverage_artifact_present"] == 1
        assert not any(finding.code == "testing.coverage.malformed" for finding in result.findings)

    def test_requires_a_sidecar_for_the_specific_inspection_artifact(self, tmp_path: Path) -> None:
        """An unrelated hash file cannot certify an inspection artifact."""
        tests = tmp_path / "tests" / "test_visual.py"
        tests.parent.mkdir()
        tests.write_text(
            "import pytest\n"
            "@pytest.mark.inspection\n"
            "def test_visual():\n    pass\n"
        )
        artifact = tmp_path / "test_files" / "visual.html"
        artifact.parent.mkdir()
        artifact.write_text("<html></html>\n")
        (tmp_path / "unrelated.sha256").write_text("hash\n")

        result = TestQualityAnalyzer(tmp_path).analyze()

        assert any(finding.code == "testing.inspection.certification_missing" for finding in result.findings)
        assert result.metrics["certified_inspection_artifacts"] == 0

    def test_counts_each_skipped_and_xfailed_test_case(self, tmp_path: Path) -> None:
        """Skip and xfail inventory counts test cases rather than files."""
        tests = tmp_path / "tests" / "test_cases.py"
        tests.parent.mkdir()
        tests.write_text(
            "import pytest\n"
            "@pytest.mark.xfail\n"
            "def test_one():\n    pytest.skip('one')\n"
            "@pytest.mark.xfail\n"
            "def test_two():\n    pytest.skip('two')\n"
        )

        result = TestQualityAnalyzer(tmp_path).analyze()

        assert result.metrics["skipped_tests"] == 2
        assert result.metrics["xfailed_tests"] == 2

    def test_symbol_evidence_ignores_comments_and_strings(self, tmp_path: Path) -> None:
        """Symbol evidence comes from AST references rather than raw text."""
        source = tmp_path / "sample.py"
        source.write_text("def calculate(value):\n    return value\n")
        tests = tmp_path / "tests" / "test_sample.py"
        tests.parent.mkdir()
        tests.write_text("def test_note():\n    # calculate appears only in a comment\n    return 'calculate'\n")

        result = TestQualityAnalyzer(tmp_path).analyze()

        assert result.metrics["referenced_symbols"] == 0
        assert any(finding.code == "testing.inventory.symbol_reference_missing" for finding in result.findings)

    def test_cli_exposes_test_quality_as_shared_versioned_result(self, tmp_path: Path) -> None:
        """The CLI exposes stable JSON for test-quality analysis."""
        result = CliRunner().invoke(app, ["test-quality", str(tmp_path), "--json-output"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "1.0"
        assert payload["metrics"]["source_files"] == 0
        assert any(item["code"] == "testing.coverage.missing" for item in payload["findings"])
