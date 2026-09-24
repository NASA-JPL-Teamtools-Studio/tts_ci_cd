"""Command implementations for tts-ctx."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set

from tts_ci_cd.ctx.index_db import IndexDB
from tts_ci_cd.ctx.config import get_db_path, get_knowledge_dir

def run_start_here(db: IndexDB):
    """Render the start_here knowledge card and workspace overview."""
    print("# tts-ctx — Where to start\n")
    
    # Load static card
    card_path = get_knowledge_dir() / "start_here.md"
    if card_path.exists():
        print(card_path.read_text())
    
    print("\n## Workspace at a glance")
    repos = db.get_all_repos()
    
    # Taxonomy counts
    counts = {"core": 0, "adaptation": 0, "application": 0, "incidental": 0}
    for r in repos:
        rt = r["type"] or "incidental"
        counts[rt] = counts.get(rt, 0) + 1
        
    print(f"Total Repos: {len(repos)}")
    for rt, count in counts.items():
        print(f"  {rt}: {count}")

    print("\n┈┈┈ Suggested next calls ┈┈┈")
    print("tts-ctx core\ntts-ctx adaptations\ntts-ctx concepts\ntts-ctx class <dotted.path>\ntts-ctx repo <repo>\ntts-ctx deps <repo>\ntts-ctx search <query>")

def run_core(db: IndexDB):
    """Render core library overview."""
    print("# TTS Core Libraries\n")
    card_path = get_knowledge_dir() / "core.md"
    if card_path.exists():
        print(card_path.read_text())
    
    print("\n## Indexed Core Libs")
    repos = db.get_all_repos()
    core_repos = [r["name"] for r in repos if r["type"] == "core"]
    for repo in sorted(core_repos):
        classes = db.get_key_classes_for_repo(repo)
        print(f"• {repo} ({len(classes)} key classes)")

def run_adaptations(db: IndexDB):
    """Render mission adaptation overview."""
    print("# Mission Adaptations\n")
    print(f"{'Repo':<30} ← {'Adapts'}")
    print("-" * 60)
    repos = db.get_all_repos()
    adaptations = [r for r in repos if r["type"] == "adaptation" and r["adapts"]]
    for r in sorted(adaptations, key=lambda x: x["name"]):
        print(f"{r['name']:<30} {r['adapts']}")

def run_concepts(db: IndexDB):
    """Render the concepts knowledge card."""
    card_path = get_knowledge_dir() / "concepts.md"
    if card_path.exists():
        print(card_path.read_text())

def run_repo(db: IndexDB, repo_name: str):
    """Get a summary of one repository."""
    repo = db.get_repo_by_name(repo_name)
    if not repo:
        print(f"Repo not found: {repo_name}")
        return

    print(f"## {repo['name']}")
    print(f"  Type: {repo['type']}")
    print(f"  Ownership: {repo['ownership']}")
    print(f"  Remote: {repo['git_remote']}")
    print(f"  Path: {repo['path']}\n")

    classes = db.get_key_classes_for_repo(repo_name)
    print("Key Classes:")
    for c in classes:
        print(f"  • {c['name']} ({c['full_path']})")

def run_class(db: IndexDB, class_path: str, depth: int = 1):
    """Inspect a class and its MRO."""
    cls = db.get_class_by_path(class_path)
    if not cls:
        print(f"Class not found: {class_path}")
        return

    print(f"## {cls['full_path']}")
    print(f"  \"{cls['doc_summary']}\"")
    print(f"  Repo: {cls['module_id']}") # simplified
    print(f"  Public: {cls['is_public']}\n")

    print("  MRO:")
    mro = db.get_class_mro(cls['id'])
    for i, (cid, path, ext) in enumerate(mro):
        indent = "  " * i
        name = path if path else f"(external: {ext})"
        print(f"{indent}├── {name}")

    if depth >= 2:
        methods = db.get_class_methods(cls['id'])
        print("\nMethods:")
        for m in methods:
            print(f"  • {m['name']} - {m['doc_summary']}")

    if depth >= 3:
        mod = db.get_module_by_id(cls['module_id'])
        if mod:
            print(f"\nSource ({mod['file_path']}):")
            # In a real tool, we'd read the file and slice by line_start/end
            print("  [Source code snippet would appear here]")

def run_search(db: IndexDB, query: str):
    """Global symbol search."""
    results = db.search_symbols(query)
    print(f"Search: '{query}'\n")
    print(f"{'Symbol':<60} | {'Kind':<10} | {'Summary'}")
    print("-" * 100)
    for r in results:
        print(f"{r['full_path']:<60} | {r['kind']:<10} | {r['doc_summary']}")

def run_deps(db: IndexDB, start_repo: str):
    """Truthful dependency mapping for a library, with mission-aware filtering."""
    from tts_ci_cd.ctx.config import get_current_mission
    current_mission = get_current_mission()
    
    repo = db.get_repo_by_name(start_repo)
    if not repo:
        print(f"Repo not found: {start_repo}")
        return

    print(f"Dependency Graph for {start_repo}")
    if current_mission:
        print(f"Filtering for mission: {current_mission}")
    print("-" * 40)
    
    visited = set()
    # (repo_name, depth, prefix)
    stack = [(start_repo, 0, "")]
    
    STD_LIB = {"sys", "os", "re", "json", "datetime", "collections", "pathlib", "logging", "typing", "abc", "copy", "enum", "functools", "itertools", "math", "random", "time", "traceback", "uuid", "tempfile", "inspect", "importlib", "argparse", "shutil", "subprocess", "xml.etree.ElementTree"}

    while stack:
        current_repo, depth, prefix = stack.pop()
        
        # Resolve tagging for the current node
        repo_info = db.get_repo_by_name(current_repo)
        tag = ""
        if repo_info:
            if repo_info['type'] == "adaptation":
                tag = " [ADAPTATION]"
            elif repo_info['type'] == "core":
                tag = " [CORE]"

        if current_repo == start_repo:
            print(f"{start_repo}{tag}")
        else:
            print(f"{prefix}└── {current_repo}{tag}")
        
        if current_repo in visited:
            continue
        visited.add(current_repo)
        
        modules = db.conn.execute(
            "SELECT id FROM modules WHERE repo_name = ?", (current_repo,)
        ).fetchall()
        
        deps_for_this_repo = set()
        
        for mod in modules:
            imports = db.get_imports_for_module(mod['id'])
            for imp in imports:
                res_mod = imp['resolved_module']
                if not res_mod:
                    continue
                
                repo_row = db.conn.execute(
                    "SELECT repo_name FROM modules WHERE dotted_path = ? OR dotted_path LIKE ? LIMIT 1",
                    (res_mod, f"{res_mod}.%")
                ).fetchone()
                
                if repo_row:
                    dep_repo_name = repo_row['repo_name']
                    if dep_repo_name != current_repo:
                        # Mission Filtering
                        dep_repo_info = db.get_repo_by_name(dep_repo_name)
                        if dep_repo_info:
                            mission = dep_repo_info['mission']
                            # Keep if it's core, matches current mission, or is the root
                            if not mission or mission == current_mission or dep_repo_name == start_repo:
                                deps_for_this_repo.add(dep_repo_name)
                        else:
                            deps_for_this_repo.add(dep_repo_name)
                else:
                    base_mod = res_mod.split('.')[0]
                    if base_mod not in STD_LIB:
                        deps_for_this_repo.add(f"(external: {res_mod})")

        for dep in sorted(list(deps_for_this_repo)):
            if dep.startswith("(external:"):
                print(f"{prefix}  └── {dep}")
            elif dep != start_repo:
                stack.append((dep, depth + 1, prefix + "  "))



def run_index():
    """Build the index."""
    from tts_ci_cd.ctx.index_db import IndexDB
    db = IndexDB()
    from tts_ci_cd.ctx.indexer import run_full_index
    run_full_index(db)
    print("Index complete.")
