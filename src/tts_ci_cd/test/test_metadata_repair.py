"""Behavioral tests for deterministic metadata repairs."""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.metadata_repair import MetadataRepairEngine


@pytest.mark.unreviewed_ai
class TestMetadataRepairEngine:
    """Verify dry-run, diff, and explicit confirmation seams."""

    def _repository(self, tmp_path: Path) -> Path:
        repository = tmp_path / "repo"
        repository.mkdir()
        (repository / "guide.md").write_text(
            "# Guide\n\n## TTS Metadata\n\n```yaml\ntts:\n"
            "  kind: guide\n  maturity: draft\n  summary: \"Guide.\"\n```\n"
        )
        return repository

    def test_plan_is_dry_run_and_repairs_only_known_kind_aliases(self, tmp_path: Path) -> None:
        """Planning returns a reviewable diff without changing maturity or files."""
        repository = self._repository(tmp_path)
        original = (repository / "guide.md").read_text()

        plan = MetadataRepairEngine(repository).plan()

        assert len(plan.operations) == 1
        assert "-  kind: guide" in plan.diff
        assert "+  kind: procedure" in plan.diff
        assert "maturity: draft" in plan.diff
        assert (repository / "guide.md").read_text() == original

    def test_apply_requires_confirmation_and_preserves_dirty_boundary(self, tmp_path: Path) -> None:
        """Writing requires explicit confirmation and records pre-existing changes."""
        repository = self._repository(tmp_path)
        subprocess.run(["git", "init", "-q"], cwd=str(repository), check=True)
        (repository / "notes.txt").write_text("pre-existing\n")
        engine = MetadataRepairEngine(repository)
        plan = engine.plan()

        with pytest.raises(ValueError):
            engine.apply(plan)
        result = engine.apply(plan, confirm=True)

        assert "notes.txt" in result.pre_existing_changes
        assert result.generated_changes == ("guide.md",)
        assert "kind: procedure" in (repository / "guide.md").read_text()
        assert "maturity: draft" in (repository / "guide.md").read_text()

    def test_cli_returns_versioned_repair_plan(self, tmp_path: Path) -> None:
        """The CLI defaults to dry-run and exposes stable JSON."""
        repository = self._repository(tmp_path)

        result = CliRunner().invoke(
            app, ["metadata-repair", str(repository), "--json-output"]
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["mode"] == "dry-run"
        assert payload["operations"][0]["rule_id"] == "documentation.metadata.invalid_kind"
        assert "kind: guide" in (repository / "guide.md").read_text()
