"""Behavioral tests for packaged documentation-grooming skills."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


_SKILL_ROOT = Path(__file__).parents[1] / "ai_skills"
_ROUTER = _SKILL_ROOT / "documentation_grooming.md"
_FOCUSED = {
    "metadata": _SKILL_ROOT / "metadata_grooming.md",
    "links": _SKILL_ROOT / "link_grooming.md",
    "policy": _SKILL_ROOT / "policy_sync.md",
    "validation": _SKILL_ROOT / "documentation_validation.md",
    "tts_ctx_quality": _SKILL_ROOT / "tts_ctx_quality.md",
}


@pytest.mark.unreviewed_ai
class TestDocumentationGroomingSkills:
    """Verify the skill package exposes the documented grooming entry points."""

    def test_router_and_focused_skills_are_packaged(self) -> None:
        """The router and every focused workflow are present and structured."""
        assert _ROUTER.exists()
        router = _ROUTER.read_text(encoding="utf-8")
        assert "description:" in router
        for skill_path in _FOCUSED.values():
            assert skill_path.exists()
            text = skill_path.read_text(encoding="utf-8")
            assert text.startswith("---\n")
            assert "description:" in text.split("---\n", 2)[1]

    def test_router_names_each_workflow_and_guardrails(self) -> None:
        """The router points each branch at its focused workflow and safeguards."""
        router = _ROUTER.read_text(encoding="utf-8")
        for skill_path in _FOCUSED.values():
            assert skill_path.name in router
        assert "maturity" in router.lower()
        assert "dirty" in router.lower()
        assert "safety" in router.lower()

    def test_built_package_exposes_skills_outside_source_checkout(self, tmp_path: Path) -> None:
        """A built wheel exposes the router and focused skills after installation."""
        wheel_dir = tmp_path / "wheel"
        install_dir = tmp_path / "installed"
        wheel_dir.mkdir()
        install_dir.mkdir()
        repository = Path(__file__).parents[3]
        build_environment = dict(os.environ)
        utilities_source = Path(__file__).parents[4] / "tts_utilities" / "src"
        build_environment["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(utilities_source), build_environment.get("PYTHONPATH")) if part
        )
        subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheel_dir), "--no-isolation"],
            cwd=str(repository),
            env=build_environment,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        wheel = next(wheel_dir.glob("*.whl"))
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(install_dir), str(wheel)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(install_dir)
        script = (
            "from pathlib import Path\n"
            "import tts_ci_cd\n"
            "root = Path(tts_ci_cd.__file__).parent / 'ai_skills'\n"
            "assert (root / 'documentation_grooming.md').is_file()\n"
            "assert (root / 'tts_ctx_quality.md').is_file()\n"
            "assert 'tts-ctx test-quality' in (root / 'tts_ctx_quality.md').read_text()\n"
        )
        subprocess.run([sys.executable, "-c", script], cwd=str(tmp_path), env=environment, check=True)

    def test_focused_workflows_are_independently_invocable(self) -> None:
        """Each focused skill declares human invocation and a completion check."""
        for skill_path in _FOCUSED.values():
            text = skill_path.read_text(encoding="utf-8")
            assert "disable-model-invocation: true" in text
            assert "## Done when" in text
