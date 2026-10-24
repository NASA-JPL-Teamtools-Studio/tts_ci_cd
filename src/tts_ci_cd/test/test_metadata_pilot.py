"""Behavioral tests for the representative metadata pilot."""

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.cli import app
from tts_ci_cd.ctx.metadata_pilot import MetadataPilot


@pytest.mark.unreviewed_ai
class TestMetadataPilot:
    """Verify representative-scope reporting and dirty-checkout safeguards."""

    def test_report_covers_named_scopes_and_preserves_existing_changes(self, tmp_path: Path) -> None:
        """The pilot reports target identity, findings, and pre-existing changes."""
        central = tmp_path / "central"
        central.mkdir()
        (central / "guide.md").write_text("# Guide\n")
        subprocess.run(["git", "init", "-q"], cwd=str(central), check=True)
        (central / "notes.txt").write_text("pre-existing\n")
        core = tmp_path / "core"
        core.mkdir()
        (core / "README.md").write_text("# Core\n")

        report = MetadataPilot(
            tmp_path,
            {"central": central, "core": core, "missing": tmp_path / "missing"},
        ).report()

        assert [item.name for item in report.repositories] == ["central", "core", "missing"]
        central_report = report.repositories[0]
        assert central_report.dirty is True
        assert "notes.txt" in central_report.pre_existing_changes
        assert central_report.migration_status == "blocked_dirty"
        assert report.repositories[2].migration_status == "missing"

    def test_cli_pilot_returns_stable_json(self, tmp_path: Path) -> None:
        """The pilot CLI reports the configured representative scope."""
        result = CliRunner().invoke(
            app,
            ["metadata-pilot", str(tmp_path), "--json-output"],
        )

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["scope"] == str(tmp_path.resolve())
        assert [item["name"] for item in payload["repositories"]] == [
            "central",
            "core",
            "oco2",
            "tts_ci_cd",
        ]
        assert payload["mode"] == "report"
