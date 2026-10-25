"""Behavioral tests for complete standards-first pilot verification."""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.pilot import verify_pilot


@pytest.mark.unreviewed_ai
class TestPilotVerification:
    """Verify read-only representative pilot evidence."""

    def test_report_preserves_dirty_boundary_and_remaining_gaps(self, tmp_path: Path) -> None:
        """Pilot output keeps pre-existing changes separate from generated changes."""
        repository = tmp_path / "repo"
        repository.mkdir()
        (repository / "README.md").write_text("# Repo\n")
        subprocess.run(["git", "init", "-q"], cwd=str(repository), check=True)
        (repository / "notes.txt").write_text("pre-existing\n")

        report = verify_pilot(tmp_path, {"sample": repository})
        payload = report.to_dict()

        sample = payload["repositories"][0]
        assert sample["dirty"] is True
        assert "notes.txt" in sample["pre_existing_changes"]
        assert sample["generated_changes"] == []
        assert payload["no_github_action"] is True
        assert payload["remaining_gaps"]
        assert sample["traversal_documents"] == 1
        assert sample["grooming_entry_points"] == []
        assert any(finding["code"] == "documentation.metadata.missing" for finding in payload["findings"])

    def test_cli_returns_versioned_pilot_report(self, tmp_path: Path) -> None:
        """The pilot CLI exposes stable JSON without editing the workspace."""
        result = CliRunner().invoke(app, ["pilot", str(tmp_path), "--json-output"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["version"] == "1.0"
        assert payload["mode"] == "verify"
        assert payload["no_github_action"] is True
