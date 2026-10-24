"""Behavioral tests for packaged documentation-grooming skills."""

from pathlib import Path

import pytest


_SKILL_ROOT = Path(__file__).parents[1] / "ai_skills"
_ROUTER = _SKILL_ROOT / "documentation_grooming.md"
_FOCUSED = {
    "metadata": _SKILL_ROOT / "metadata_grooming.md",
    "links": _SKILL_ROOT / "link_grooming.md",
    "policy": _SKILL_ROOT / "policy_sync.md",
    "validation": _SKILL_ROOT / "documentation_validation.md",
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

    def test_focused_workflows_are_independently_invocable(self) -> None:
        """Each focused skill declares human invocation and a completion check."""
        for skill_path in _FOCUSED.values():
            text = skill_path.read_text(encoding="utf-8")
            assert "disable-model-invocation: true" in text
            assert "## Done when" in text
