"""Behavioral tests for progressive Markdown traversal."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.resources import MarkdownResourceCatalog
from tts_ci_cd.ctx.traversal import MarkdownTraversal


@pytest.mark.unreviewed_ai
class TestMarkdownTraversal:
    """Verify tree, progressive disclosure, links, and search behavior."""

    def _traversal(self, tmp_path: Path) -> MarkdownTraversal:
        (tmp_path / "guide.md").write_text(
            "# Guide\n\nThis guide introduces setup.\n\n## Install\n\nRun setup.\n\n### Details\n\nMore setup.\n\n"
            "[Local](reference.md#target) [External](https://example.com/docs)\n\n"
            "## TTS Metadata\n\n```yaml\ntts:\n  kind: guide\n```\n"
        )
        (tmp_path / "reference.md").write_text("# Reference\n\n## Target\n\nReference text.\n")
        return MarkdownTraversal(MarkdownResourceCatalog(tmp_path, "test-v1"))

    def test_tree_and_outline_follow_heading_depth(self, tmp_path: Path) -> None:
        """Tree preserves paths and outline depth maps to Markdown levels."""
        traversal = self._traversal(tmp_path)

        documents = traversal.tree()
        outline = traversal.outline("guide.md", depth=2)

        assert [document.path for document in documents] == ["guide.md", "reference.md"]
        assert [(heading.level, heading.title) for heading in outline] == [
            (1, "Guide"),
            (2, "Install"),
            (2, "TTS Metadata"),
        ]
        assert outline[1].anchor == "install"

    def test_section_read_and_links_are_progressive(self, tmp_path: Path) -> None:
        """A section is bounded by its heading and links are resolved locally."""
        traversal = self._traversal(tmp_path)

        section = traversal.section("guide.md", "install")
        local = traversal.follow("guide.md", "reference.md#target")
        external = traversal.follow("guide.md", "https://example.com/docs")

        assert section.heading.title == "Install"
        assert "Run setup." in section.text
        assert "More setup." in section.text
        assert "TTS Metadata" not in section.text
        assert local.external is False
        assert local.document.path == "reference.md"
        assert local.anchor == "target"
        assert external.external is True
        assert external.document is None

    def test_cli_exposes_outline_contract(self, tmp_path: Path) -> None:
        """The CLI exposes the same outline behavior as the Python interface."""
        self._traversal(tmp_path)
        result = CliRunner().invoke(
            app,
            [
                "outline",
                "guide.md",
                "--repository",
                str(tmp_path),
                "--depth",
                "2",
                "--json-output",
            ],
        )

        assert result.exit_code == 0
        assert '"title": "Install"' in result.stdout
        assert '"title": "Details"' not in result.stdout

    def test_search_includes_text_headings_metadata_and_links(self, tmp_path: Path) -> None:
        """Search returns source-located matches across document surfaces."""
        traversal = self._traversal(tmp_path)

        matches = traversal.search("guide")

        assert any(match.kind == "heading" and match.path == "guide.md" for match in matches)
        assert any(match.kind == "text" and match.path == "guide.md" for match in matches)
        assert all(match.line > 0 for match in matches)

    def test_search_classifies_metadata_and_links_precisely(self, tmp_path: Path) -> None:
        """Metadata fields and link-only matches are classified by surface."""
        traversal = self._traversal(tmp_path)

        metadata = traversal.search("kind: guide")
        link_only = traversal.search("example.com")
        prose_with_link = traversal.search("Local")

        assert [match.kind for match in metadata] == ["metadata"]
        assert [match.kind for match in link_only] == ["link"]
        assert [match.kind for match in prose_with_link] == ["link"]
        assert traversal.search("setup")[0].kind == "text"

    def test_fragment_only_links_resolve_against_the_source_document(self, tmp_path: Path) -> None:
        """A `#anchor` link resolves within its own nested source document."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "guide.md").write_text("# Guide\n\n## Install\n")
        traversal = MarkdownTraversal(MarkdownResourceCatalog(tmp_path, "test-v1"))

        link = traversal.follow("docs/guide.md", "#install")

        assert link.document.path == "docs/guide.md"
        assert link.anchor == "install"

    def test_results_carry_revision_and_versioned_cli_envelope(self, tmp_path: Path) -> None:
        """Traversal outputs preserve the shared revision and result version."""
        traversal = self._traversal(tmp_path)

        section = traversal.section("guide.md", "install")
        link = traversal.follow("guide.md", "reference.md#target")
        result = CliRunner().invoke(
            app,
            ["section", "guide.md", "install", "--repository", str(tmp_path), "--json-output"],
        )

        assert section.revision == "test-v1"
        assert link.to_dict()["revision"] == "test-v1"
        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "1.0"
        assert payload["operation"] == "section"
        assert payload["scope"] == str(tmp_path.resolve())
        assert payload["standards_revision"] == "documentation-maintenance-v1"
        assert payload["result"]["heading"]["title"] == "Install"

    def test_read_does_not_append_extra_newline(self, tmp_path: Path) -> None:
        """Reading a newline-terminated document prints it unchanged."""
        self._traversal(tmp_path)

        result = CliRunner().invoke(app, ["read", "reference.md", "--repository", str(tmp_path)])

        assert result.exit_code == 0
        assert result.stdout == "# Reference\n\n## Target\n\nReference text.\n"
