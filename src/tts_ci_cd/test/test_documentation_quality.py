"""Behavioral tests for documentation-quality analysis."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.documentation_quality import DocumentationQualityAnalyzer


_VALID_METADATA = """## TTS Metadata

```yaml
tts:
  kind: repository
  maturity: released
  summary: "Repository guide."
```
"""


@pytest.mark.unreviewed_ai
class TestDocumentationQualityAnalyzer:
    """Verify API, Markdown, maturity, and released-document evidence findings."""

    def test_reports_public_api_and_markdown_quality_findings(self, tmp_path: Path) -> None:
        """Quality findings include source locations and actionable remediation."""
        (tmp_path / "library.py").write_text(
            "class PublicThing:\n    def calculate(self, value):\n        return value\n\n"
            "def public_function(argument):\n    return argument\n"
        )
        (tmp_path / "README.md").write_text(
            "# README\n\nDraft — SME review needed.\n\n[Missing](missing.md)\n\n" + _VALID_METADATA
        )

        findings = DocumentationQualityAnalyzer(tmp_path).analyze()
        codes = {finding.code for finding in findings}

        assert "documentation.api.class_missing" in codes
        assert "documentation.api.method_missing" in codes
        assert "documentation.api.function_missing" in codes
        assert "documentation.maturity.conflict" in codes
        assert "documentation.released.evidence_missing" in codes
        assert "documentation.link.missing" in codes
        assert all(finding.path for finding in findings)
        assert all(finding.remediation for finding in findings)

    def test_quality_cli_uses_shared_result_contract(self, tmp_path: Path) -> None:
        """The quality command returns versioned findings JSON."""
        (tmp_path / "library.py").write_text("def public_function():\n    pass\n")

        result = CliRunner().invoke(app, ["quality", str(tmp_path), "--json-output"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "1.0"
        assert any(item["code"] == "documentation.api.function_missing" for item in payload["findings"])
