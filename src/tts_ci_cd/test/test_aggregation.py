"""Behavioral tests for repository and workspace quality scopes."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tts_ci_cd.ctx.aggregation import ScopeResolver, analyze_scope
from tts_ci_cd.ctx.cli import app


@pytest.mark.unreviewed_ai
class TestQualityAggregation:
    """Verify deterministic repository, workspace, and related scopes."""

    def _workspace(self, tmp_path: Path) -> Path:
        core = tmp_path / "tts_core" / "core_lib"
        mission = tmp_path / "mission" / "mission_lib"
        for repository in (core, mission):
            (repository / ".git").mkdir(parents=True)
            (repository / "README.md").write_text("# Repo\n")
        return tmp_path

    def test_workspace_and_related_scopes_preserve_repository_identity(self, tmp_path: Path) -> None:
        """Workspace and adaptation scopes return consistent per-repository results."""
        workspace = self._workspace(tmp_path)
        resolver = ScopeResolver(workspace, {"mission/mission_lib": "core_lib"})

        workspace_result = analyze_scope("workspace", resolver=resolver)
        related_result = analyze_scope("related", str(workspace / "tts_core" / "core_lib"), resolver=resolver)

        assert len(workspace_result.repositories) == 2
        assert len(related_result.repositories) == 2
        assert {result.scope for result in related_result.repositories} == {
            str(workspace / "tts_core" / "core_lib"),
            str(workspace / "mission" / "mission_lib"),
        }
        payload = json.loads(related_result.to_json())
        assert payload["repositories"][0]["standards_revision"] == "documentation-maintenance-v1"

    def test_missing_scope_is_source_located_and_deterministic(self, tmp_path: Path) -> None:
        """A missing named repository yields a stable actionable finding."""
        result = analyze_scope("repository", "missing", resolver=ScopeResolver(tmp_path, {}))

        assert result.repositories == ()
        assert result.findings[0].code == "scope.repository_missing"

    def test_cli_accepts_explicit_workspace_scope(self, tmp_path: Path) -> None:
        """The quality CLI exposes aggregate scope selection."""
        workspace = self._workspace(tmp_path)

        result = CliRunner().invoke(app, ["quality", str(workspace), "--scope", "workspace", "--json-output"])

        assert result.exit_code == 0
        assert len(json.loads(result.stdout)["repositories"]) == 2
