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
            config = toml.load(pyproject_path)
            
            # Ensure [tool.tts-ctx] exists
            if "tool" not in config:
                config["tool"] = {}
            if "tts-ctx" not in config["tool"]:
                config["tool"]["tts-ctx"] = {}
                
            config["tool"]["tts-ctx"]["type"] = suggested
            
            with open(pyproject_path, "w", encoding="utf-8") as f:
                toml.dump(config, f)
            print(f"  ✓ Updated {repo_path.name}")
        except Exception as e:
            print(f"  ⚠ Failed to update {repo_path.name}: {e}")

    print("\nMetadata migration complete. Run 'tts-ctx index' to refresh.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Apply changes without confirmation")
    args = parser.parse_args()
    run_migration(force=args.force)
