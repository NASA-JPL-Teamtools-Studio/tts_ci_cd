"""Command implementations for tts-ctx."""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set

from tts_ci_cd.ctx.index_db import IndexDB
from tts_ci_cd.ctx.config import get_db_path, get_knowledge_dir
from tts_ci_cd.ctx.analysis import analyze_repository, render_markdown
from tts_ci_cd.ctx.resources import MarkdownResourceCatalog
from tts_ci_cd.ctx.traversal import MarkdownTraversal, TraversalResult
from tts_ci_cd.ctx.metadata import DOCUMENT_KINDS
from tts_ci_cd.ctx.test_quality import TestQualityAnalyzer
from tts_ci_cd.ctx.metadata_pilot import MetadataPilot
from tts_ci_cd.ctx.context_validation import (
    DEFAULT_QUESTION_SET,
    ContextSnapshot,
    ContextValidator,
    ValidationQuestionSet,
)

def run_kinds(as_json: bool = False) -> None:
    """List the document-kind taxonomy used by Markdown metadata."""
    kinds = [{"name": name, "description": description} for name, description in sorted(DOCUMENT_KINDS.items())]
    payload = {"version": "1.0", "kinds": kinds}
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print("# TTS document kinds\n")
    for kind in kinds:
        print("- `{}` — {}".format(kind["name"], kind["description"]))


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
    summary = repo["summary"] if "summary" in repo.keys() else None
    if summary and summary != "No summary provided.":
        print(f"  {summary}")
    print(f"  Type: {repo['type']}")
    if repo['adapts']:
        print(f"  Adapts: {repo['adapts']}")
    print(f"  Ownership: {repo['ownership']}")
    print(f"  Remote: {repo['git_remote']}")
    print(f"  Path: {repo['path']}\n")

    structure = db.get_repo_structure(repo_name)
    print(f"Structure: {structure['module_count']} modules")
    if structure['subpackages']:
        print("Sub-packages:")
        for sp in structure['subpackages']:
            print(f"  • {sp}")
    print()

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

    mod = db.get_module_by_id(cls['module_id'])
    repo_name = mod['repo_name'] if mod else "?"

    print(f"## {cls['full_path']}")
    print(f"  \"{cls['doc_summary']}\"")
    print(f"  Repo: {repo_name}")
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
            summary = (m['doc_summary'] or "").strip().splitlines()[0] if m['doc_summary'] else ""
            sig = m['signature'] or "()"
            print(f"  • {m['name']}{sig}" + (f" - {summary}" if summary else ""))

    if depth >= 3:
        if mod:
            print(f"\nSource ({mod['file_path']}):")
            file_path = Path(mod['file_path'])
            if file_path.exists():
                lines = file_path.read_text(encoding="utf-8").splitlines()
                start = max(cls['line_start'] - 1, 0)
                end = min(cls['line_end'], len(lines))
                for lineno, line in enumerate(lines[start:end], start=start + 1):
                    print(f"  {lineno:>5} | {line}")
            else:
                print(f"  [File not found: {file_path}]")

def run_search(db: IndexDB, query: str):
    """Global symbol search, ranked by relevance and grouped by repo."""
    results = db.search_symbols(query)
    print(f"Search: '{query}'\n")
    if not results:
        print("No matches found.")
        return

    by_repo: Dict[str, List[Dict]] = {}
    for r in results:
        by_repo.setdefault(r["repo_name"], []).append(r)

    for repo_name, repo_results in by_repo.items():
        print(f"## {repo_name}")
        for r in repo_results:
            summary = (r["doc_summary"] or "").strip().splitlines()[0] if r["doc_summary"] else ""
            print(f"  • {r['full_path']} ({r['kind']}, matched: {r['matched_on']})")
            if summary:
                print(f"      {summary}")
        print()

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



def run_context_validate(
    progressive_path: str,
    exhaustive_path: str,
    as_json: bool = False,
    repository: Optional[str] = None,
    question_set_path: Optional[str] = None,
) -> None:
    """Compare progressive and exhaustive JSON context snapshots.

    Args:
        progressive_path: JSON file containing targeted context evidence.
        exhaustive_path: JSON file containing complete-scope context evidence.
        as_json: Whether to render stable JSON instead of Markdown.
        repository: Optional repository key selecting repository-specific questions.
        question_set_path: Optional JSON file containing a versioned question set.
    """
    with open(progressive_path, "r") as progressive_file:
        progressive = ContextSnapshot.from_dict(json.load(progressive_file))
    with open(exhaustive_path, "r") as exhaustive_file:
        exhaustive = ContextSnapshot.from_dict(json.load(exhaustive_file))
    questions = DEFAULT_QUESTION_SET
    if question_set_path:
        with open(question_set_path, "r") as question_file:
            questions = ValidationQuestionSet.from_dict(json.load(question_file))
    result = ContextValidator().compare(
        progressive, exhaustive, questions, repository=repository
    )
    if as_json:
        print(result.to_json(), end="")
        return
    print("# Context validation", "", sep="\n")
    print("- Classification: `{}`".format(result.classification))
    print("- Scope: `{}`".format(result.scope))
    print("- Question set: `{}`".format(result.question_set_version))
    for finding in result.findings:
        print("- `{}`: {}".format(finding.code, finding.message))
        if finding.remediation:
            print("  - Next step: {}".format(finding.remediation))


def run_quality(repository: str, standards_revision: str, as_json: bool = False) -> None:
    """Run combined documentation-quality and metadata analysis.

    Args:
        repository: Path to the repository to analyze.
        standards_revision: Human-readable revision of the applicable standard.
        as_json: Whether to render the result as JSON instead of Markdown.
    """
    result = analyze_repository(repository, standards_revision=standards_revision)
    print(result.to_json() if as_json else render_markdown(result), end="")


def run_test_quality(
    repository: str,
    coverage_path: Optional[str] = None,
    run_tests: bool = False,
    test_command: Optional[List[str]] = None,
    as_json: bool = False,
) -> None:
    """Run deterministic test-quality analysis through the shared result seam."""
    result = TestQualityAnalyzer(repository, coverage_path=coverage_path).analyze(
        run_tests=run_tests, test_command=test_command
    )
    print(result.to_json() if as_json else render_markdown(result), end="")


def run_metadata(repository: str, standards_revision: str, as_json: bool = False) -> None:
    """Validate Markdown metadata through the shared analysis seam.

    Args:
        repository: Path to the repository to validate.
        standards_revision: Human-readable revision of the applicable standard.
        as_json: Whether to render the result as JSON instead of Markdown.
    """
    result = analyze_repository(repository, standards_revision=standards_revision)
    print(result.to_json() if as_json else render_markdown(result), end="")


def run_analysis(repository: str, standards_revision: str, as_json: bool = False) -> None:
    """Analyze one repository and render its stable result contract.

    Args:
        repository: Path to the repository to analyze.
        standards_revision: Human-readable revision of the applicable standard.
        as_json: Whether to render the result as JSON instead of Markdown.
    """
    result = analyze_repository(repository, standards_revision=standards_revision)
    print(result.to_json() if as_json else render_markdown(result), end="")


def _get_traversal(repository: str) -> MarkdownTraversal:
    """Create Markdown traversal for a repository path."""
    return MarkdownTraversal(MarkdownResourceCatalog(Path(repository)))


def _print_json(operation: str, repository: str, result: object) -> None:
    """Print a traversal payload inside the shared versioned envelope."""
    scope = str(Path(repository).expanduser().resolve())
    revision = _get_traversal(repository).catalog.standards_revision
    print(TraversalResult(operation, scope, revision, result).to_json())


def run_tree(repository: str, as_json: bool = False) -> None:
    """Render the Markdown document tree for a repository.

    Args:
        repository: Repository or documentation root to inspect.
        as_json: Whether to render stable JSON instead of Markdown.
    """
    documents = _get_traversal(repository).tree()
    if as_json:
        _print_json("tree", repository, [document.to_dict() for document in documents])
        return
    for document in documents:
        print(document.path)


def run_outline(repository: str, path: str, depth: int = 1, as_json: bool = False) -> None:
    """Render a Markdown page outline at a requested heading depth.

    Args:
        repository: Repository or documentation root to inspect.
        path: Markdown path relative to the repository root.
        depth: Maximum Markdown heading level to include.
        as_json: Whether to render stable JSON instead of Markdown.
    """
    headings = _get_traversal(repository).outline(path, depth)
    if as_json:
        _print_json("outline", repository, [heading.to_dict() for heading in headings])
        return
    for heading in headings:
        print("{} {} #{}".format("  " * (heading.level - 1), heading.title, heading.anchor))


def run_section(repository: str, path: str, selector: str, as_json: bool = False) -> None:
    """Render one Markdown section.

    Args:
        repository: Repository or documentation root to inspect.
        path: Markdown path relative to the repository root.
        selector: Heading title or anchor to select.
        as_json: Whether to render stable JSON instead of Markdown.
    """
    section = _get_traversal(repository).section(path, selector)
    if as_json:
        _print_json("section", repository, section.to_dict())
        return
    print(section.text)


def run_follow(repository: str, source_path: str, target: str, as_json: bool = False) -> None:
    """Follow a local link or report an external link without fetching it.

    Args:
        repository: Repository or documentation root to inspect.
        source_path: Markdown path containing the link.
        target: Link target to resolve.
        as_json: Whether to render stable JSON instead of Markdown.
    """
    link = _get_traversal(repository).follow(source_path, target)
    if as_json:
        _print_json("follow", repository, link.to_dict())
        return
    if link.external:
        print("External link (not fetched): {}".format(link.target))
    else:
        print(link.document.path)
        if link.anchor:
            print("#{}".format(link.anchor))


def run_doc_search(repository: str, query: str, as_json: bool = False) -> None:
    """Search Markdown text, headings, metadata, and links.

    Args:
        repository: Repository or documentation root to inspect.
        query: Case-insensitive text to locate.
        as_json: Whether to render stable JSON instead of Markdown.
    """
    matches = _get_traversal(repository).search(query)
    if as_json:
        _print_json("doc-search", repository, [match.to_dict() for match in matches])
        return
    for match in matches:
        print("{}:{} [{}] {}".format(match.path, match.line, match.kind, match.text))


def run_read(repository: str, path: str, as_json: bool = False) -> None:
    """Read a complete Markdown document.

    Args:
        repository: Repository or documentation root to inspect.
        path: Markdown path relative to the repository root.
        as_json: Whether to render stable JSON instead of Markdown.
    """
    document = _get_traversal(repository).read(path)
    if as_json:
        _print_json("read", repository, {"path": document.path, "revision": document.revision, "text": document.text})
        return
    print(document.text, end="" if document.text.endswith("\n") else "\n")


def run_metadata_pilot(workspace: str, as_json: bool = False) -> None:
    """Report representative metadata migration readiness without editing files.

    Args:
        workspace: Workspace root containing representative repositories.
        as_json: Whether to render stable JSON instead of Markdown.
    """
    report = MetadataPilot(workspace).report()
    print(report.to_json() if as_json else report.to_markdown(), end="")


def run_index():
    """Build the index."""
    from tts_ci_cd.ctx.index_db import IndexDB
    db = IndexDB()
    from tts_ci_cd.ctx.indexer import run_full_index
    run_full_index(db)
    print("Index complete.")
