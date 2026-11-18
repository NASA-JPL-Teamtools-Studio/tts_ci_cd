"""Behavioral tests for packaged Markdown resource access."""

from pathlib import Path

import pytest

from tts_ci_cd.ctx.resources import MarkdownResourceCatalog, ResourceNotFoundError


@pytest.mark.unreviewed_ai
class TestMarkdownResourceCatalog:
    """Verify standards-specific and general Markdown resource access."""

    def test_exposes_packaged_standard_and_revision(self) -> None:
        """The central standard is available without network access."""
        catalog = MarkdownResourceCatalog()

        standard = catalog.read_standard()

        assert standard.path == "standards/documentation_maintenance.md"
        assert standard.revision == "documentation-maintenance-v1"
        assert "## TTS Metadata" in standard.text
        assert "documentation.metadata" in standard.text

    def test_reads_relative_documents_deterministically(self, tmp_path: Path) -> None:
        """A caller can read arbitrary Markdown by repository-relative path."""
        (tmp_path / "guide.md").write_text("# Guide\n")
        (tmp_path / "reference.md").write_text("# Reference\n")
        catalog = MarkdownResourceCatalog(tmp_path, standards_revision="test-v1")

        document = catalog.read_document("guide.md")

        assert document.path == "guide.md"
        assert document.revision == "test-v1"
        assert document.text == "# Guide\n"
        assert catalog.list_documents() == ("guide.md", "reference.md")

    def test_rejects_missing_and_outside_documents(self, tmp_path: Path) -> None:
        """Resource reads cannot escape the configured resource root."""
        catalog = MarkdownResourceCatalog(tmp_path)

        with pytest.raises(ResourceNotFoundError):
            catalog.read_document("missing.md")
        with pytest.raises(ResourceNotFoundError):
            catalog.read_document("../outside.md")
