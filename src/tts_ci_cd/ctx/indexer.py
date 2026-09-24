"""AST-based indexer for tts-ctx.

Parses Python files to build a symbol index including classes, methods,
functions, and inheritance relationships.
"""
from __future__ import annotations

import ast
import os
import re
import toml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

from tts_ci_cd.ctx.config import (
    get_workspace_root,
    get_src_dirs,
    get_all_python_files,
    get_overrides,
)
from tts_ci_cd.ctx.index_db import IndexDB


def _get_base_repr(node, current_dotted: str) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        val = _get_base_repr(node.value, current_dotted)
        return f"{val}.{node.attr}" if val else node.attr
    return None


def get_summary_from_agents_md(repo_path: Path) -> Optional[str]:
    """Fallback: attempt to scrape the first paragraph of AGENTS.md."""
    agents_md = repo_path / "AGENTS.md"
    if not agents_md.exists():
        return None
    try:
        text = agents_md.read_text().strip()
        if not text:
            return None
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.startswith("#")]
        return lines[0] if lines else None
    except Exception:
        return None


def run_full_index(db: IndexDB) -> None:
    """Perform a complete indexing run of the workspace."""
    root = get_workspace_root()
    print(f"Indexing workspace at {root}...")

    overrides = get_overrides()
    description_registry: Dict[str, List[str]] = {}
    
    from tts_ci_cd.ctx.config import list_git_repos
    repos = list_git_repos(root)
    
    from tts_ci_cd.ctx.config import parse_workspace_map
    adapts_map = parse_workspace_map()

    # Define non-mission directories
    EXCLUDE_DIRS = {"tts_core", "work_tracking", "sandboxes", "tts_candidates", "venv"}

    for repo_path in repos:
        try:
            rel = repo_path.relative_to(root)
        except ValueError:
            rel = repo_path
        rel_str = str(rel).replace("\\", "/")

        if rel_str.startswith("tts_core/tts_genai_utils"):
            print(f"  ↷ Skipping {rel_str} (genai workspace)")
            continue

        repo_name = repo_path.name
        repo_type = "incidental"
        summary = None
        
        # Derive mission
        mission = None
        if rel.parts:
            top_dir = rel.parts[0]
            if top_dir not in EXCLUDE_DIRS:
                mission = top_dir

        pyproject_path = repo_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                pyproject = toml.load(pyproject_path)
                repo_type = pyproject.get("tool", {}).get("tts-ctx", {}).get("type", "incidental")
                summary = pyproject.get("project", {}).get("description")
            except Exception as e:
                print(f"  ⚠ Error parsing pyproject.toml in {repo_name}: {e}")

        if not summary:
            summary = overrides.get(repo_name)

        if not summary:
            summary = get_summary_from_agents_md(repo_path)

        if summary != "No summary provided." and summary:
            description_registry.setdefault(summary, []).append(repo_name)
        elif not summary:
            print(f"  ⚠ {repo_name}: Missing description in pyproject.toml (or overrides/AGENTS.md)")
            summary = "No summary provided."

        from tts_ci_cd.ctx.config import get_remote_info, ownership_category
        host, repo_ref = get_remote_info(repo_path)
        ownership = ownership_category(host, repo_ref.split("/")[0] if repo_ref else None)
        adapts = adapts_map.get(rel_str)

        db.add_repo(repo_name, str(repo_path), "tts_core" if "tts_core/" in rel_str else "mission", 
                    git_remote=host, ownership=ownership, adapts=adapts, repo_type=repo_type, mission=mission)


        src_dirs = get_src_dirs(repo_path)
        if not src_dirs:
            print(f"  ⚬ {repo_name}: no src/ dir")
            continue

        for src_dir in src_dirs:
            package_root = src_dir.name
            py_files = get_all_python_files([src_dir])
            
            for py_file in py_files:
                if any(x in py_file.parts for x in ("build", "egg-info", "tests", "test")):
                    continue
                
                rel_to_src = py_file.relative_to(src_dir)
                if py_file.name == "__init__.py":
                    dotted = ".".join([package_root] + list(rel_to_src.parts[:-1]))
                else:
                    dotted = ".".join([package_root] + list(rel_to_src.parts[:-1]) + [py_file.stem])

                module_id = db.add_module(repo_name, dotted, str(py_file), package_root)
                
                try:
                    with open(py_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    tree = ast.parse(content)
                    
                    # 1. Imports
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for n in node.names:
                                db.add_import(module_id, n.name, n.name, None)
                        elif isinstance(node, ast.ImportFrom):
                            module_name = node.module or ""
                            for n in node.names:
                                db.add_import(module_id, n.name, module_name, n.name)

                    # 2. Classes
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            class_full_path = f"{dotted}.{node.name}"
                            doc = ast.get_docstring(node) or ""
                            class_id = db.add_class(
                                module_id=module_id,
                                name=node.name,
                                full_path=class_full_path,
                                doc_summary=doc,
                                is_public=not node.name.startswith("_"),
                                line_start=node.lineno,
                                line_end=getattr(node, 'end_lineno', node.lineno)
                            )
                            for base in node.bases:
                                base_repr = _get_base_repr(base, dotted)
                                if base_repr:
                                    db.conn.execute(
                                        "INSERT INTO class_bases (class_id, base_repr) VALUES (?, ?)",
                                        (class_id, base_repr)
                                    )

                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            # Top level functions
                            func_full_path = f"{dotted}.{node.name}"
                            doc = ast.get_docstring(node) or ""
                            db.add_symbol(
                                class_id=None,
                                module_id=module_id,
                                name=node.name,
                                full_path=func_full_path,
                                signature=node.args.args[0].arg if node.args.args else "",
                                doc_summary=doc,
                                is_public=not node.name.startswith("_"),
                                line_start=node.lineno,
                                line_end=getattr(node, 'end_lineno', node.lineno),
                                kind='function'
                            )
                except Exception as e:
                    print(f"  ⚠ Error parsing {py_file}: {e}")

        print(f"  ✓ {repo_name} indexed")

    print("\n--- Indexing Quality Report ---")
    duplicates = {s: rs for s, rs in description_registry.items() if len(rs) > 1}
    if duplicates:
        for summary, repos in duplicates.items():
            print(f"  ⚠ Duplicate description: \"{summary[:50]}...\" used by {', '.join(repos)}")
    else:
        print("  ✓ No duplicate descriptions found.")
