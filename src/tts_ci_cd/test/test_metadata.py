"""Behavioral tests for Markdown metadata validation."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.metadata import MarkdownMetadataValidator


_VALID_METADATA = """## TTS Metadata

```yaml
tts:
  kind: guide
  maturity: baseline
  summary: "A guide."
  related:
    - reference.md
  policy_ids:
    - documentation.metadata
```
"""


@pytest.mark.unreviewed_ai
class TestMarkdownMetadataValidator:
    """Verify public metadata findings and shared CLI analysis output."""

    def test_valid_metadata_has_no_findings_and_related_is_local(self, tmp_path: Path) -> None:
        """A complete document with an existing relative relation passes.

        Args:
            tmp_path: Temporary repository directory used by the test.
        """
        (tmp_path / "reference.md").write_text("# Reference\n\n" + _VALID_METADATA)
        (tmp_path / "guide.md").write_text("# Guide\n\nBody.\n\n" + _VALID_METADATA)

        findings = MarkdownMetadataValidator(tmp_path).validate()

        assert findings == ()

    def test_missing_metadata_is_actionable_and_source_located(self, tmp_path: Path) -> None:
        """Missing metadata produces a stable rule, path, line, and next step.

        Args:
            tmp_path: Temporary repository directory used by the test.
        """
        (tmp_path / "guide.md").write_text("# Guide\n")

        findings = MarkdownMetadataValidator(tmp_path).validate()

        assert len(findings) == 1
        assert findings[0].code == "documentation.metadata.missing"
        assert findings[0].path == "guide.md"
        assert findings[0].line == 1
        assert findings[0].remediation
        assert findings[0].evidence == "No bottom-of-file TTS Metadata section found."

    def test_duplicate_malformed_and_semantically_invalid_metadata_are_distinct(
        self, tmp_path: Path
    ) -> None:
        """Structural and semantic metadata failures use distinct rule IDs.

        Args:
            tmp_path: Temporary repository directory used by the test.
        """
        (tmp_path / "broken.md").write_text(
            "# Broken\n\n## TTS Metadata\n```yaml\ntts: [\n```\n\n"
            "## TTS Metadata\n```yaml\n"
            "tts:\n  kind: unknown\n  maturity: unknown\n  summary: \"\"\n"
            "```\n\nTrailing text.\n"
        )

        findings = MarkdownMetadataValidator(tmp_path).validate()
        codes = {finding.code for finding in findings}

        assert "documentation.metadata.duplicate" in codes
        assert "documentation.metadata.malformed" in codes
        assert "documentation.metadata.misplaced" in codes

    def test_invalid_values_and_related_paths_are_reported_without_mutation(
        self, tmp_path: Path
    ) -> None:
        """Semantic validation reports invalid values and preserves declared maturity.

        Args:
            tmp_path: Temporary repository directory used by the test.
        """
        original = (
            "# Guide\n\n## TTS Metadata\n\n```yaml\n"
            "tts:\n  kind: unknown\n  maturity: released\n  summary: 42\n"
            "  related:\n    - missing.md\n    - ../outside.md\n    - https://example.com/guide.md\n"
            "```\n"
        )
        (tmp_path / "guide.md").write_text(original)

        findings = MarkdownMetadataValidator(tmp_path).validate()
        codes = {finding.code for finding in findings}

        assert "documentation.metadata.invalid_kind" in codes
        assert "documentation.metadata.invalid_field" in codes
        assert "documentation.metadata.related_missing" in codes
        assert "documentation.metadata.related_invalid" in codes
        assert (tmp_path / "guide.md").read_text() == original

    def test_structural_failure_does_not_emit_semantic_findings(self, tmp_path: Path) -> None:
        """Malformed structure is reported without parsing a partial YAML block.

        Args:
            tmp_path: Temporary repository directory used by the test.
        """
        (tmp_path / "mixed.md").write_text(
            "## TTS Metadata\n\n```yaml\ntts:\n  kind: invalid\n  maturity: invalid\n  summary: \"Valid block.\"\n```\n"
            "Unexpected trailing content.\n"
        )

        findings = MarkdownMetadataValidator(tmp_path).validate()

        assert [finding.code for finding in findings] == ["documentation.metadata.malformed", "documentation.metadata.misplaced"]

    def test_unclosed_or_extra_metadata_content_is_malformed(self, tmp_path: Path) -> None:
        """An unclosed fence or prose outside the fence cannot pass validation.

        Args:
            tmp_path: Temporary repository directory used by the test.
        """
        (tmp_path / "unclosed.md").write_text(
            "## TTS Metadata\n\n```yaml\ntts:\n  kind: guide\n  maturity: baseline\n  summary: \"Guide.\"\n"
        )
        (tmp_path / "prose.md").write_text(
            "## TTS Metadata\n\nUnexpected prose.\n\n```yaml\ntts:\n  kind: guide\n  maturity: baseline\n  summary: \"Guide.\"\n```\n"
        )
        (tmp_path / "mismatch.md").write_text(
            "## TTS Metadata\n\n```yaml\ntts:\n  kind: guide\n  maturity: baseline\n  summary: \"Guide.\"\n~~~\n"
        )

        findings = MarkdownMetadataValidator(tmp_path).validate()

        assert {finding.path for finding in findings} == {"mismatch.md", "prose.md", "unclosed.md"}
        assert all(
            any(
                finding.path == path and finding.code == "documentation.metadata.malformed"
                for finding in findings
            )
            for path in ("prose.md", "unclosed.md")
        )

    def test_cli_exposes_metadata_findings_through_analysis_result(self, tmp_path: Path) -> None:
        """The metadata report uses the shared versioned result envelope.

        Args:
            tmp_path: Temporary repository directory used by the test.
        """
        (tmp_path / "guide.md").write_text("# Guide\n")

        result = CliRunner().invoke(
            app,
            ["metadata", str(tmp_path), "--json-output"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "1.0"
        assert payload["findings"][0]["code"] == "documentation.metadata.missing"
