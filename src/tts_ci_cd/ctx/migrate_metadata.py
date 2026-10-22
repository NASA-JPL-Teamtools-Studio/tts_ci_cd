"""Migration utility for tts-ctx metadata.

This script analyzes the workspace and suggests types for repositories
based on their location and purpose, then updates pyproject.toml files.
"""
from __future__ import annotations

import argparse
import os
import toml
from pathlib import Path
from typing import Set

from tts_ci_cd.ctx.config import get_workspace_root, list_git_repos, parse_workspace_map

def _set_tts_ctx_type(pyproject_path: Path, type_value: str) -> None:
    """Set [tool.tts-ctx] type = "..." by editing text in place.

    Deliberately avoids toml.load()/toml.dump() round-tripping, which
    reformats the whole file (drops comments, reflows arrays, reorders
    tables) and would corrupt every pyproject.toml it touches.
    """
    import re

    text = pyproject_path.read_text(encoding="utf-8")
    section_re = re.compile(r"^\[tool\.tts-ctx\]\s*$", re.MULTILINE)
    match = section_re.search(text)

    if match is None:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f'\n[tool.tts-ctx]\ntype = "{type_value}"\n'
        pyproject_path.write_text(text, encoding="utf-8")
        return

    section_start = match.end()
    next_section = re.search(r"^\[", text[section_start:], re.MULTILINE)
    section_end = section_start + next_section.start() if next_section else len(text)
    section_body = text[section_start:section_end]

    type_re = re.compile(r'^type\s*=\s*".*"\s*$', re.MULTILINE)
    if type_re.search(section_body):
        new_body = type_re.sub(f'type = "{type_value}"', section_body, count=1)
    else:
        new_body = section_body.rstrip("\n") + f'\ntype = "{type_value}"\n'

    text = text[:section_start] + new_body + text[section_end:]
    pyproject_path.write_text(text, encoding="utf-8")


def suggest_type(repo_path: Path, root: Path, adapts_map: dict) -> str:
    """Suggest a type based on path and WORKSPACE_MAP."""
    rel = repo_path.relative_to(root)
    rel_str = str(rel).replace("\\", "/")
    
    # 1. Core libs
    if rel_str.startswith("tts_core/tts_"):
        return "core"
    
    # 2. Adaptations (found in WORKSPACE_MAP as adaptations)
    if rel_str in adapts_map:
        return "adaptation"
    
    # 3. Other TTS-like libraries
    if "tts_" in repo_path.name:
        return "application"
    
    # 4. Fallback
    return "incidental"

def run_migration(force: bool = False):
    """Analyze the workspace and suggest types for repositories."""
    root = get_workspace_root()
    adapts_map = parse_workspace_map()
    repos = list_git_repos(root)
    
    print(f"Analyzing {len(repos)} repositories for tts-ctx metadata...")
    
    pending = []
    for repo_path in repos:
        pyproject_path = repo_path / "pyproject.toml"
        if not pyproject_path.exists():
            continue
            
        try:
            config = toml.load(pyproject_path)
            current_type = config.get("tool", {}).get("tts-ctx", {}).get("type")
            suggested = suggest_type(repo_path, root, adapts_map)
            
            if current_type != suggested:
                pending.append((repo_path, current_type, suggested))
        except Exception as e:
            print(f"  ⚠ Error reading {repo_path}: {e}")

    if not pending:
        print("All repositories already have optimal metadata tags.")
        return

    print(f"Found {len(pending)} repositories that could use metadata updates:")
    for path, curr, sugg in pending:
        print(f"  {path.name}: {curr} -> {sugg}")
        
    if not force:
        try:
            confirm = input("\nApply these changes to pyproject.toml? (y/N): ")
            if confirm.lower() != 'y':
                print("Aborted.")
                return
        except EOFError:
            print("\nEOF encountered. Use --force to apply changes without interaction.")
            return

    for repo_path, _, suggested in pending:
        pyproject_path = repo_path / "pyproject.toml"
        try:
            _set_tts_ctx_type(pyproject_path, suggested)
            print(f"  ✓ Updated {repo_path.name}")
        except Exception as e:
            print(f"  ⚠ Failed to update {repo_path.name}: {e}")

    print("\nMetadata migration complete. Run 'tts-ctx index' to refresh.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Apply changes without confirmation")
    args = parser.parse_args()
    run_migration(force=args.force)
